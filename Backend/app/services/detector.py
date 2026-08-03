from typing import Any

import pandas as pd
from fastapi import HTTPException


COLUMN_KEYWORDS = {
    "time": [
        "time",
        "datetime",
        "date time",
        "timestamp",
        "วันที่",
        "เวลา",
    ],
    "solar_dc": [
        "total dc power",
        "pv dc power",
        "solar dc power",
        "dc power",
    ],
    "active_power": [
        "total active power",
        "active power",
        "inverter output",
        "ac output",
    ],
    "battery_charge": [
        "battery charging power",
        "charging power",
        "battery charge",
    ],
    "battery_discharge": [
        "battery discharging power",
        "discharging power",
        "battery discharge",
    ],
}


def normalize_column_name(value: Any) -> str:
    return " ".join(str(value).lower().strip().split())


def find_column(
    columns: list[str],
    keywords: list[str],
) -> str | None:
    for keyword in keywords:
        for column in columns:
            normalized = normalize_column_name(column)

            if keyword in normalized:
                return column

    return None


def detect_columns(
    dataframe: pd.DataFrame,
) -> dict[str, str | None]:
    columns = list(dataframe.columns)

    detected = {
        name: find_column(columns, keywords)
        for name, keywords in COLUMN_KEYWORDS.items()
    }

    required = {
        "time": "Time",
        "solar_dc": "Total DC Power",
        "active_power": "Total Active Power",
    }

    missing = [
        label
        for key, label in required.items()
        if not detected[key]
    ]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "ไม่พบคอลัมน์ที่จำเป็น: "
                + ", ".join(missing)
            ),
        )

    return detected