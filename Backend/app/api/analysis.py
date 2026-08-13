from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.database.supabase_client import get_supabase_client
from app.services.calculator import calculate_analysis
from app.services.detector import detect_columns
from app.services.file_parser import parse_uploaded_file
from app.services.normalizer import normalize_dataframe


router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),

    # NEW: ใช้เชื่อมกับ Supabase Site
    site_code: str = Form(...),

    # เก็บของเดิมไว้ก่อน เพื่อไม่ให้ Analyzer เดิมพัง
    site_name: str = Form(...),
    installed_size_kwp: float = Form(...),
    panel_count: int = Form(...),
):
    # --------------------------------------------------
    # 1. Find Site from Supabase
    # --------------------------------------------------
    client = get_supabase_client()

    site_response = (
        client.table("sites")
        .select("id, site_code")
        .eq("site_code", site_code)
        .limit(1)
        .execute()
    )

    if not site_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"Site '{site_code}' not found.",
        )

    site = site_response.data[0]
    site_id = site["id"]

    # --------------------------------------------------
    # 2. Existing Analyzer Flow
    # --------------------------------------------------
    dataframe = await parse_uploaded_file(file)

    detected_columns = detect_columns(dataframe)

    normalized = normalize_dataframe(
        dataframe=dataframe,
        detected=detected_columns,
    )

    result = calculate_analysis(normalized)

    # --------------------------------------------------
    # 3. Battery Detection
    # --------------------------------------------------
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

    elif (
        detected_columns.get("battery_charge")
        or detected_columns.get("battery_discharge")
    ):
        battery_status = "without_battery"

    else:
        battery_status = "unknown"

    # --------------------------------------------------
    # 4. Build final API result
    # --------------------------------------------------
    final_result = {
        "status": "completed",

        "file": {
            "name": file.filename,
            "content_type": file.content_type,
        },

        "site_info": {
            "site_code": site_code,
            "site_name": site_name,
            "installed_size_kwp": installed_size_kwp,
            "battery_status": battery_status,
            "battery_detection": {
                "charge_detected": charge_detected,
                "discharge_detected": discharge_detected,
            },
            "panel_count": panel_count,
        },

        "data_quality": {
            "source_rows": len(dataframe),
            "valid_rows": len(normalized),
            "removed_rows": len(dataframe) - len(normalized),
        },

        "detected_columns": detected_columns,

        **result,
    }

    # --------------------------------------------------
    # 5. Get approved summary fields
    # --------------------------------------------------
    summary = result.get("summary", {})

    average_solar_kwh = summary.get(
        "average_solar_kwh",
        result.get("average_solar_kwh"),
    )

    average_usage_kwh = summary.get(
        "average_usage_kwh",
        result.get("average_usage_kwh"),
    )

    daytime_coverage_percent = summary.get(
        "daytime_coverage_percent",
        result.get("daytime_coverage_percent"),
    )

    recommendation = result.get(
        "recommendation",
        summary.get("recommendation"),
    )

    # --------------------------------------------------
    # 6. Save to analysis_history
    # --------------------------------------------------
    history_payload = {
        "site_id": site_id,
        "analysis_date": datetime.now(timezone.utc).isoformat(),
        "average_solar_kwh": average_solar_kwh,
        "average_usage_kwh": average_usage_kwh,
        "daytime_coverage_percent": daytime_coverage_percent,
        "recommendation": recommendation,
        "result_payload": final_result,
    }

    history_response = (
        client.table("analysis_history")
        .insert(history_payload)
        .execute()
    )

    if not history_response.data:
        raise HTTPException(
            status_code=502,
            detail="Analysis completed but could not be saved to analysis history.",
        )

    # --------------------------------------------------
    # 7. Return result
    # --------------------------------------------------
    final_result["analysis_history_id"] = history_response.data[0]["id"]

    return final_result