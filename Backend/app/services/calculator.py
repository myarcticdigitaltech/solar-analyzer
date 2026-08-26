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

    # AC-side solar energy available to serve load/export after charge.
    data["solar_available_ac_kwh"] = (
        solar_available_ac_kw * data["interval_hour"]
    )

    # 7) Aggregate raw values; rounding happens only at API output.
    grouped = (
        data.groupby(["analysis_date", "period"])
        .agg(
            solar_kwh=("solar_kwh", "sum"),
            usage_kwh=("usage_kwh", "sum"),
            solar_used_kwh=("solar_used_kwh", "sum"),
            solar_available_ac_kwh=("solar_available_ac_kwh", "sum"),
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
        solar_available_ac = period_values("solar_available_ac_kwh")
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
            "solar_available_ac": solar_available_ac,
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
    average_solar_available_ac = [
        average_period("solar_available_ac", i) for i in range(3)
    ]
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

    # 10) Derived energy gaps. Keep comparisons on the AC/load side.
    daytime_surplus_ac = max(
        0.0,
        average_solar_available_ac[0] - average_solar_used[0],
    )
    daytime_uncovered = max(
        0.0,
        average_usage[0] - average_solar_used[0],
    )
    evening_uncovered = max(
        0.0,
        average_usage[1] - average_solar_used[1] - average_discharge[1],
    )
    night_uncovered = max(
        0.0,
        average_usage[2] - average_solar_used[2] - average_discharge[2],
    )
    load_after_16 = average_usage[1] + average_usage[2]

    # 11) Panel recommendation
    uncovered_daytime = daytime_uncovered

    recommended_panels = (
        math.ceil(uncovered_daytime / PANEL_DAILY_YIELD_KWH)
        if uncovered_daytime > 1
        else 0
    )

    # 12) Dynamic, evidence-based insights and recommendations.
    day_direct_ratio = (
        average_solar_used[0] / average_usage[0] * 100
        if average_usage[0] > 0 else 0.0
    )
    evening_direct_ratio = (
        average_solar_used[1] / average_usage[1] * 100
        if average_usage[1] > 0 else 0.0
    )
    night_direct_ratio = (
        average_solar_used[2] / average_usage[2] * 100
        if average_usage[2] > 0 else 0.0
    )

    # Section 3: factual interpretation. Avoid repeating Section 4 actions.
    if average_usage[0] <= 0:
        day_insight = "ไม่พบโหลดช่วง 09:00–16:00 เพียงพอสำหรับประเมิน Coverage"
    elif coverage >= 99.5:
        day_insight = (
            f"Solar จ่ายโหลดกลางวันได้ครบตามข้อมูลที่วัดได้ "
            f"({round_number(average_solar_used[0])}/{round_number(average_usage[0])} kWh/วัน)"
        )
        if daytime_surplus_ac >= 0.5:
            day_insight += (
                f" และยังมีพลังงาน Solar ฝั่ง AC ที่ไม่ได้ใช้กับโหลดโดยตรง "
                f"ประมาณ {round_number(daytime_surplus_ac)} kWh/วัน"
            )
    elif coverage >= 90:
        day_insight = (
            f"Solar รองรับโหลดกลางวันได้ {round_number(coverage, 1)}% "
            f"เหลือโหลดที่ Solar ไม่ได้จ่ายตรงประมาณ "
            f"{round_number(daytime_uncovered)} kWh/วัน"
        )
    elif coverage >= 60:
        day_insight = (
            f"Solar ช่วยโหลดกลางวันได้ {round_number(coverage, 1)}% "
            f"แต่ยังมีโหลดประมาณ {round_number(daytime_uncovered)} kWh/วัน "
            f"ที่ต้องพึ่งแหล่งพลังงานอื่น"
        )
    else:
        day_insight = (
            f"Solar ครอบคลุมโหลดกลางวันเพียง {round_number(coverage, 1)}% "
            f"โดยมีโหลดที่ไม่ได้รับจาก Solar โดยตรงประมาณ "
            f"{round_number(daytime_uncovered)} kWh/วัน"
        )

    if average_usage[1] <= 0:
        evening_insight = "แทบไม่มีโหลดช่วง 16:00–22:00 ในชุดข้อมูลนี้"
    elif average_discharge[1] > 0.1:
        evening_insight = (
            f"ช่วงเย็นมีโหลด {round_number(average_usage[1])} kWh/วัน; "
            f"Solar จ่ายตรง {round_number(average_solar_used[1])} และ Battery จ่าย "
            f"{round_number(average_discharge[1])} kWh/วัน"
        )
        if evening_uncovered > 0.1:
            evening_insight += (
                f" เหลือประมาณ {round_number(evening_uncovered)} kWh/วัน "
                f"ที่ต้องมาจากแหล่งอื่น"
            )
    elif average_solar_used[1] > 0.1:
        evening_insight = (
            f"ช่วงเย็น Solar ยังจ่ายโหลดโดยตรงประมาณ "
            f"{round_number(average_solar_used[1])} จาก "
            f"{round_number(average_usage[1])} kWh/วัน; "
            f"ไม่พบ Battery discharge ที่มีนัยสำคัญ"
        )
    else:
        evening_insight = (
            f"ช่วง 16:00–22:00 มีโหลดเฉลี่ย {round_number(average_usage[1])} kWh/วัน "
            f"แต่แทบไม่พบ Solar จ่ายตรงหรือ Battery discharge"
        )

    if average_usage[2] <= 0:
        night_insight = "แทบไม่มีโหลดช่วงกลางคืนในชุดข้อมูลนี้"
    elif abnormal_dates:
        night_insight = (
            f"พบคืนที่ใช้พลังงานสูงกว่าฐานปกติ {len(abnormal_dates)} วัน: "
            + ", ".join(abnormal_dates)
        )
    elif average_discharge[2] > 0.1:
        night_insight = (
            f"โหลดกลางคืนเฉลี่ย {round_number(average_usage[2])} kWh/วัน "
            f"และ Battery จ่ายเฉลี่ย {round_number(average_discharge[2])} kWh/วัน"
        )
    else:
        night_insight = (
            f"โหลดกลางคืนเฉลี่ย {round_number(average_usage[2])} kWh/วัน "
            f"ไม่พบ Battery discharge ที่มีนัยสำคัญและไม่พบคืนผิดปกติชัดเจน"
        )

    # Section 4: actions change by actual case.
    if coverage < 70 and daytime_uncovered >= 1:
        load_title = "ปรับโหลดบางส่วนเข้าสู่ช่วง Solar"
        load_recommendation = (
            f"ช่วงกลางวันยังขาด Solar ประมาณ {round_number(daytime_uncovered)} kWh/วัน "
            f"จึงควรพิจารณาย้ายโหลดที่เลื่อนได้มา 09:00–16:00 "
            f"เฉพาะเมื่อช่วงนั้นยังมี Solar เหลือ"
        )
    elif coverage < 95 and daytime_uncovered >= 0.5:
        load_title = "ลดช่องว่างโหลดกลางวัน"
        load_recommendation = (
            f"Coverage อยู่ที่ {round_number(coverage, 1)}% "
            f"ยังมีโหลดที่ Solar ไม่ได้จ่ายตรงประมาณ "
            f"{round_number(daytime_uncovered)} kWh/วัน ควรตรวจช่วงเวลาที่เกิดช่องว่างก่อนปรับตารางโหลด"
        )
    elif daytime_surplus_ac >= 1:
        load_title = "ใช้ประโยชน์จาก Solar ส่วนเกิน"
        load_recommendation = (
            f"กลางวัน Solar ครอบคลุมโหลดได้ดีและมีส่วนเกินฝั่ง AC "
            f"ประมาณ {round_number(daytime_surplus_ac)} kWh/วัน "
            f"หากมีโหลดที่เลื่อนได้ สามารถย้ายมาใช้ช่วง Solar สูงเพื่อเพิ่ม Self-consumption"
        )
    else:
        load_title = "คงรูปแบบโหลดกลางวัน"
        load_recommendation = (
            f"โหลดกลางวันสอดคล้องกับ Solar ค่อนข้างดี "
            f"ยังไม่เห็นเหตุผลชัดเจนให้ย้ายโหลดเพิ่มจากข้อมูลชุดนี้"
        )

    battery_activity = (
        average_charge[0] + average_charge[1] + average_charge[2]
        + average_discharge[0] + average_discharge[1] + average_discharge[2]
    )

    if battery_activity > 0.1:
        if daytime_surplus_ac >= 1.5 and load_after_16 >= 5 and evening_uncovered + night_uncovered >= 1:
            battery_title = "ตรวจความจุ Battery เทียบกับโหลดหลังเย็น"
            battery_recommendation = (
                f"มี Solar เหลือกลางวันประมาณ {round_number(daytime_surplus_ac)} kWh/วัน "
                f"และยังมีโหลดหลัง 16:00 ที่ไม่ได้ถูก Solar/Battery ครอบคลุมประมาณ "
                f"{round_number(evening_uncovered + night_uncovered)} kWh/วัน "
                f"ควรดู SOC และความจุใช้งานจริงก่อนตัดสินใจเพิ่ม Battery"
            )
        else:
            battery_title = "ติดตามการทำงานของ Battery"
            battery_recommendation = (
                f"พบ Battery charge/discharge ในข้อมูลแล้ว แต่ยังไม่มีหลักฐานเพียงพอว่า "
                f"ต้องเพิ่มความจุ ควรตรวจ SOC ต่ำสุดช่วงกลางคืนและพลังงานเหลือก่อนชาร์จเต็ม"
            )
    elif daytime_surplus_ac >= 2 and load_after_16 >= 5:
        battery_title = "ประเมิน Battery เพิ่มเติม"
        battery_recommendation = (
            f"มี Solar ส่วนเกินกลางวันประมาณ {round_number(daytime_surplus_ac)} kWh/วัน "
            f"และมีโหลดหลัง 16:00 ประมาณ {round_number(load_after_16)} kWh/วัน "
            f"แต่ไฟล์นี้ไม่พบกิจกรรม Battery จึงควรยืนยันว่าหน้างานมี Battery หรือไม่ก่อนแนะนำขนาด"
        )
    else:
        battery_title = "ยังไม่มีเหตุผลชัดเจนให้เพิ่ม Battery"
        battery_recommendation = (
            f"จากรูปแบบ Solar และโหลดชุดนี้ ยังไม่พบทั้ง Solar ส่วนเกินและโหลดหลังเย็นในระดับที่ "
            f"สนับสนุนการเพิ่ม Battery อย่างชัดเจน"
        )

    if abnormal_dates:
        night_title = "ตรวจโหลดกลางคืนในวันที่ผิดปกติ"
        night_recommendation = (
            f"พบ {len(abnormal_dates)} วันที่โหลดกลางคืนสูงผิดจากฐานปกติ "
            f"ควรตรวจอุปกรณ์ที่ทำงานในวันดังกล่าวก่อนสรุปว่าเป็นพฤติกรรมประจำ"
        )
    elif average_usage[2] >= average_usage[0] * 0.5 and average_usage[2] >= 3:
        night_title = "ทบทวน Base Load กลางคืน"
        night_recommendation = (
            f"โหลดกลางคืนเฉลี่ย {round_number(average_usage[2])} kWh/วัน "
            f"คิดเป็นสัดส่วนค่อนข้างสูงเมื่อเทียบกับกลางวัน ควรแยกโหลดจำเป็นและโหลดที่ปิดได้"
        )
    elif average_usage[2] < 1:
        night_title = "โหลดกลางคืนอยู่ในระดับต่ำ"
        night_recommendation = (
            f"โหลดกลางคืนเฉลี่ย {round_number(average_usage[2])} kWh/วัน "
            f"และไม่พบวันที่พุ่งผิดปกติ จึงยังไม่มีประเด็นเร่งด่วนจากข้อมูลชุดนี้"
        )
    else:
        night_title = "ติดตามโหลดกลางคืนต่อเนื่อง"
        night_recommendation = (
            f"โหลดกลางคืนเฉลี่ย {round_number(average_usage[2])} kWh/วัน "
            f"ยังไม่พบ outlier ชัดเจน ควรใช้ข้อมูลหลายสัปดาห์เพื่อยืนยันรูปแบบ"
        )

    # Section 5: panel sizing conclusion.
    if average_usage[0] <= 0:
        panel_status = "insufficient_data"
        panel_title = "ข้อมูลโหลดกลางวันไม่เพียงพอสำหรับประเมินจำนวนแผง"
        recommended_panels = 0
    elif coverage >= 99.5 or uncovered_daytime <= 0.25:
        panel_status = "not_needed"
        panel_title = "ยังไม่เห็นความจำเป็นต้องเพิ่มแผงจากโหลดกลางวัน"
        recommended_panels = 0
    elif uncovered_daytime <= 1:
        panel_status = "monitor"
        panel_title = "ช่องว่างโหลดกลางวันยังเล็ก ควรเก็บข้อมูลเพิ่มก่อนเพิ่มแผง"
        recommended_panels = 0
    else:
        panel_status = "consider"
        panel_title = f"พิจารณาเพิ่มประมาณ {recommended_panels} แผง"
    daily = []
    for item in daily_raw:
        daily.append({
            "date_iso": item["date_iso"],
            "solar": [round_number(v) for v in item["solar"]],
            "usage": [round_number(v) for v in item["usage"]],
            "solar_used": [round_number(v) for v in item["solar_used"]],
            "solar_available_ac": [
                round_number(v) for v in item["solar_available_ac"]
            ],
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
                "solar_available_ac_kwh": round_number(average_solar_available_ac[0]),
                "uncovered_load_kwh": round_number(daytime_uncovered),
                "battery_charge_kwh": round_number(average_charge[0]),
                "battery_discharge_kwh": round_number(average_discharge[0]),
            },
            "16_22": {
                "solar_kwh": round_number(average_solar[1]),
                "usage_kwh": round_number(average_usage[1]),
                "solar_used_kwh": round_number(average_solar_used[1]),
                "solar_available_ac_kwh": round_number(average_solar_available_ac[1]),
                "uncovered_load_kwh": round_number(evening_uncovered),
                "battery_charge_kwh": round_number(average_charge[1]),
                "battery_discharge_kwh": round_number(average_discharge[1]),
            },
            "22_09": {
                "solar_kwh": round_number(average_solar[2]),
                "usage_kwh": round_number(average_usage[2]),
                "solar_used_kwh": round_number(average_solar_used[2]),
                "solar_available_ac_kwh": round_number(average_solar_available_ac[2]),
                "uncovered_load_kwh": round_number(night_uncovered),
                "battery_charge_kwh": round_number(average_charge[2]),
                "battery_discharge_kwh": round_number(average_discharge[2]),
            },
        },
        "daily": daily,
        "insights": {
            "day": day_insight,
            "evening": evening_insight,
            "night": night_insight,
        },
        "recommendations": {
            "load_title": load_title,
            "load": load_recommendation,
            "battery_title": battery_title,
            "battery": battery_recommendation,
            "night_title": night_title,
            "night": night_recommendation,
            "abnormal_night_dates": abnormal_dates,
        },
        "panel": {
            "status": panel_status,
            "title": panel_title,
            "recommended_count": recommended_panels,
            "uncovered_daytime_kwh": round_number(uncovered_daytime),
            "assumed_panel_daily_yield_kwh": PANEL_DAILY_YIELD_KWH,
        },
        "formula": {
            "version": "v1.3",
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
