import math

import pandas as pd


INVERTER_EFFICIENCY = 0.96
PANEL_DAILY_YIELD_KWH = 2.5


def get_period(hour: int) -> int:
    if 9 <= hour < 16:
        return 0
    if 16 <= hour < 22:
        return 1
    return 2


def round_number(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def calculate_analysis(dataframe: pd.DataFrame) -> dict:
    data = dataframe.copy()

    # 1) Sampling interval
    differences = data["datetime"].diff().dt.total_seconds().div(3600)
    valid_differences = differences[(differences > 0) & (differences <= 6)]

    fallback_interval = (
        float(valid_differences.median())
        if not valid_differences.empty
        else 1.0
    )

    next_differences = (
        data["datetime"].shift(-1).sub(data["datetime"])
        .dt.total_seconds().div(3600)
    )

    data["interval_hour"] = next_differences.where(
        (next_differences > 0)
        & (next_differences <= fallback_interval * 3),
        fallback_interval,
    )

    # 2) Dashboard periods
    data["period"] = data["datetime"].dt.hour.map(get_period)

    # 3) IMPORTANT: use real calendar date from CSV.
    # Do not move 00:00-08:59 to the previous day.
    data["analysis_date"] = data["datetime"].dt.normalize()

    # 4) kW -> kWh
    data["solar_kwh"] = data["solar_dc_kw"] * data["interval_hour"]
    data["usage_kwh"] = data["active_power_kw"] * data["interval_hour"]
    data["charge_kwh"] = data["battery_charge_kw"] * data["interval_hour"]
    data["discharge_kwh"] = data["battery_discharge_kw"] * data["interval_hour"]

    # 5) Solar available on AC side after battery charging
    solar_available_ac_kw = (
        (data["solar_dc_kw"] - data["battery_charge_kw"])
        .clip(lower=0)
        * INVERTER_EFFICIENCY
    )

    # 6) Direct solar contribution to load PER TIMESTAMP.
    data["solar_used_kwh"] = (
        pd.concat(
            [data["active_power_kw"], solar_available_ac_kw],
            axis=1,
        )
        .min(axis=1)
        * data["interval_hour"]
    )

    # 7) Aggregate raw values; rounding happens only at API output.
    grouped = (
        data.groupby(["analysis_date", "period"])
        .agg(
            solar_kwh=("solar_kwh", "sum"),
            usage_kwh=("usage_kwh", "sum"),
            solar_used_kwh=("solar_used_kwh", "sum"),
            charge_kwh=("charge_kwh", "sum"),
            discharge_kwh=("discharge_kwh", "sum"),
        )
        .reset_index()
    )

    daily_raw = []

    for date_value in sorted(grouped["analysis_date"].unique()):
        day = grouped[grouped["analysis_date"] == date_value]

        def period_values(column: str) -> list[float]:
            values = [0.0, 0.0, 0.0]
            for _, row in day.iterrows():
                values[int(row["period"])] = float(row[column])
            return values

        solar = period_values("solar_kwh")
        usage = period_values("usage_kwh")
        solar_used = period_values("solar_used_kwh")
        charge = period_values("charge_kwh")
        discharge = period_values("discharge_kwh")

        daytime_coverage = (
            min(100.0, solar_used[0] / usage[0] * 100)
            if usage[0] > 0
            else 0.0
        )

        daily_raw.append({
            "date_iso": pd.Timestamp(date_value).date().isoformat(),
            "solar": solar,
            "usage": usage,
            "solar_used": solar_used,
            "charge": charge,
            "discharge": discharge,
            "daytime_coverage_percent": daytime_coverage,
        })

    day_count = len(daily_raw)
    if day_count == 0:
        raise ValueError("No valid daily data available for analysis.")

    def average_period(key: str, period_index: int) -> float:
        return sum(item[key][period_index] for item in daily_raw) / day_count

    average_solar = [average_period("solar", i) for i in range(3)]
    average_usage = [average_period("usage", i) for i in range(3)]
    average_solar_used = [average_period("solar_used", i) for i in range(3)]
    average_charge = [average_period("charge", i) for i in range(3)]
    average_discharge = [average_period("discharge", i) for i in range(3)]

    average_solar_total = sum(average_solar)
    average_usage_total = sum(average_usage)

    # 8) Coverage from unrounded interval-level totals.
    daytime_usage_total = float(
        data.loc[data["period"] == 0, "usage_kwh"].sum()
    )
    daytime_solar_used_total = float(
        data.loc[data["period"] == 0, "solar_used_kwh"].sum()
    )

    coverage = (
        min(100.0, daytime_solar_used_total / daytime_usage_total * 100)
        if daytime_usage_total > 0
        else 0.0
    )

    # 9) Night anomaly
    abnormal_threshold = max(
        average_usage[2] * 1.5,
        average_usage[2] + 5,
    )

    abnormal_dates = [
        item["date_iso"]
        for item in daily_raw
        if item["usage"][2] > abnormal_threshold
    ]

    # 10) Battery recommendation
    solar_surplus = max(
        0.0,
        average_solar[0] - average_solar_used[0] - average_charge[0],
    )
    load_after_16 = average_usage[1] + average_usage[2]

    # 11) Panel recommendation
    uncovered_daytime = max(
        0.0,
        average_usage[0] - average_solar_used[0],
    )

    recommended_panels = (
        math.ceil(uncovered_daytime / PANEL_DAILY_YIELD_KWH)
        if uncovered_daytime > 1
        else 0
    )

    # 12) Recommendations
    if coverage < 90:
        load_recommendation = (
            "ควรย้ายเครื่องซักผ้า ปั๊มน้ำ เครื่องทำน้ำร้อน "
            "และ EV charger มาใช้ช่วง 09:00–16:00 น."
        )
    else:
        load_recommendation = (
            "Solar ครอบคลุมโหลดกลางวันได้ดี "
            "ควรรักษาโหลดหลักไว้ในช่วงนี้"
        )

    if solar_surplus >= 2 and load_after_16 >= 8:
        battery_recommendation = (
            "มี Solar ส่วนเกินกลางวันและมีโหลดหลัง 16:00 สูง "
            "ควรพิจารณาเพิ่มความจุ Battery"
        )
    elif (
        average_charge[0] > 0
        and (average_discharge[1] + average_discharge[2]) > 0
    ):
        battery_recommendation = (
            "Battery มีการชาร์จและจ่ายไฟ "
            "ควรติดตามว่า SOC เพียงพอถึงช่วงกลางคืนหรือไม่"
        )
    else:
        battery_recommendation = (
            "ข้อมูลยังไม่ชี้ว่าจำเป็นต้องเพิ่ม Battery ทันที"
        )

    if abnormal_dates:
        night_recommendation = (
            "ควรตรวจสอบ EV charger ปั๊มน้ำ Heater แอร์ "
            "หรืออุปกรณ์เปิดค้างในวันที่ "
            + ", ".join(abnormal_dates)
        )
    else:
        night_recommendation = (
            "ยังไม่พบค่ากลางคืนผิดปกติชัดเจน "
            "แต่ควรติดตามต่อเนื่อง"
        )

    daily = []
    for item in daily_raw:
        daily.append({
            "date_iso": item["date_iso"],
            "solar": [round_number(v) for v in item["solar"]],
            "usage": [round_number(v) for v in item["usage"]],
            "solar_used": [round_number(v) for v in item["solar_used"]],
            "charge": [round_number(v) for v in item["charge"]],
            "discharge": [round_number(v) for v in item["discharge"]],
            "daytime_coverage_percent": round_number(
                item["daytime_coverage_percent"]
            ),
        })

    return {
        "site": {
            "date_from": daily[0]["date_iso"],
            "date_to": daily[-1]["date_iso"],
            "day_count": day_count,
        },
        "summary": {
            "average_usage_kwh": round_number(average_usage_total),
            "average_solar_kwh": round_number(average_solar_total),
            "daytime_coverage_percent": round_number(coverage),
        },
        "periods": {
            "09_16": {
                "solar_kwh": round_number(average_solar[0]),
                "usage_kwh": round_number(average_usage[0]),
                "solar_used_kwh": round_number(average_solar_used[0]),
                "battery_charge_kwh": round_number(average_charge[0]),
                "battery_discharge_kwh": round_number(average_discharge[0]),
            },
            "16_22": {
                "solar_kwh": round_number(average_solar[1]),
                "usage_kwh": round_number(average_usage[1]),
                "solar_used_kwh": round_number(average_solar_used[1]),
                "battery_charge_kwh": round_number(average_charge[1]),
                "battery_discharge_kwh": round_number(average_discharge[1]),
            },
            "22_09": {
                "solar_kwh": round_number(average_solar[2]),
                "usage_kwh": round_number(average_usage[2]),
                "solar_used_kwh": round_number(average_solar_used[2]),
                "battery_charge_kwh": round_number(average_charge[2]),
                "battery_discharge_kwh": round_number(average_discharge[2]),
            },
        },
        "daily": daily,
        "recommendations": {
            "load": load_recommendation,
            "battery": battery_recommendation,
            "night": night_recommendation,
            "abnormal_night_dates": abnormal_dates,
        },
        "panel": {
            "recommended_count": recommended_panels,
            "uncovered_daytime_kwh": round_number(uncovered_daytime),
            "assumed_panel_daily_yield_kwh": PANEL_DAILY_YIELD_KWH,
        },
        "formula": {
            "version": "v1.2",
            "inverter_efficiency": INVERTER_EFFICIENCY,
            "daytime": "09:00–16:00",
            "evening": "16:00–22:00",
            "night": "00:00–09:00 + 22:00–24:00 (calendar date)",
            "coverage_method": (
                "sum(interval solar_used_kwh) / "
                "sum(interval daytime usage_kwh)"
            ),
            "date_method": (
                "calendar date from uploaded timestamp; no day shifting"
            ),
        },
    }
