import pandas as pd
from fastapi import HTTPException


def numeric_series(
    series: pd.Series | None,
    index: pd.Index,
) -> pd.Series:
    if series is None:
        return pd.Series(
            0.0,
            index=index,
            dtype="float64",
        )

    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    return pd.to_numeric(
        cleaned,
        errors="coerce",
    ).fillna(0.0)


def normalize_dataframe(
    dataframe: pd.DataFrame,
    detected: dict[str, str | None],
) -> pd.DataFrame:
    normalized = pd.DataFrame(
        index=dataframe.index,
    )

    normalized["datetime"] = pd.to_datetime(
        dataframe[detected["time"]],
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )

    normalized["solar_dc_kw"] = numeric_series(
        dataframe[detected["solar_dc"]],
        dataframe.index,
    ).clip(lower=0)

    normalized["active_power_kw"] = numeric_series(
        dataframe[detected["active_power"]],
        dataframe.index,
    ).abs()

    charge_column = detected.get("battery_charge")
    discharge_column = detected.get("battery_discharge")

    normalized["battery_charge_kw"] = numeric_series(
        dataframe[charge_column]
        if charge_column else None,
        dataframe.index,
    ).clip(lower=0)

    normalized["battery_discharge_kw"] = numeric_series(
        dataframe[discharge_column]
        if discharge_column else None,
        dataframe.index,
    ).clip(lower=0)

    normalized = (
        normalized
        .dropna(subset=["datetime"])
        .drop_duplicates(
            subset=["datetime"],
            keep="last",
        )
        .sort_values("datetime")
        .reset_index(drop=True)
    )

    if normalized.empty:
        raise HTTPException(
            status_code=400,
            detail="ไม่สามารถอ่านวันและเวลาในไฟล์ได้",
        )

    return normalized