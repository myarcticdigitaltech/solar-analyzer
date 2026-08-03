from fastapi import APIRouter, File, Form, UploadFile
from app.services.calculator import calculate_analysis
from app.services.detector import detect_columns
from app.services.file_parser import parse_uploaded_file
from app.services.normalizer import normalize_dataframe

router=APIRouter(prefix="/api",tags=["Analysis"])

@router.post("/analyze")
async def analyze(
    file: UploadFile=File(...),
    site_name: str=Form(...),
    installed_size_kwp: float=Form(...),
    panel_count: int=Form(...),
):
    dataframe=await parse_uploaded_file(file)
    detected_columns=detect_columns(dataframe)
    normalized=normalize_dataframe(dataframe=dataframe,detected=detected_columns)
    result=calculate_analysis(normalized)

    charge_detected = (
        "battery_charge_kw" in normalized.columns
        and float(normalized["battery_charge_kw"].max()) > 0.01
    )
    discharge_detected = (
        "battery_discharge_kw" in normalized.columns
        and float(normalized["battery_discharge_kw"].max()) > 0.01
    )

    if charge_detected or discharge_detected:
        battery_status = "with_battery"
    elif detected_columns.get("battery_charge") or detected_columns.get("battery_discharge"):
        battery_status = "without_battery"
    else:
        battery_status = "unknown"

    return {
        "status":"completed",
        "file":{"name":file.filename,"content_type":file.content_type},
        "site_info":{
            "site_name":site_name,
            "installed_size_kwp":installed_size_kwp,
            "battery_status":battery_status,
            "battery_detection": {
                "charge_detected": charge_detected,
                "discharge_detected": discharge_detected,
            },
            "panel_count":panel_count,
        },
        "data_quality":{
            "source_rows":len(dataframe),
            "valid_rows":len(normalized),
            "removed_rows":len(dataframe)-len(normalized),
        },
        "detected_columns":detected_columns,
        **result,
    }