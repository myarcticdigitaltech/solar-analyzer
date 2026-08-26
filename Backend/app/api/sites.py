from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.database.supabase_client import get_supabase_client


router = APIRouter(prefix="/api/sites", tags=["Sites"])


# =========================================================
# Analysis History fields
# เพิ่ม id เพื่อใช้ View Analysis ย้อนหลัง
# =========================================================

ANALYSIS_HISTORY_FIELDS = (
    "id,"
    "analysis_date,"
    "average_solar_kwh,"
    "average_usage_kwh,"
    "daytime_coverage_percent,"
    "recommendation,"
    "result_payload"
)


# =========================================================
# Site Create Model
# =========================================================

class SiteCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # -----------------------------------------------------
    # Basic / Customer Database
    # -----------------------------------------------------

    site_code: str = Field(min_length=1)

    site_name: str | None = None

    customer_name: str | None = None

    tel: str | None = None

    email: str | None = None

    address: str | None = None

    date_of_birth: date | None = None

    # -----------------------------------------------------
    # Site Database
    # -----------------------------------------------------

    install_date: date | None = None

    tou: bool = False

    status: str = "Active"

    # PV
    pv_brand: str | None = None

    pv_size_module_w: float | None = Field(
        default=None,
        ge=0,
    )

    installed_size_kwp: float = Field(
        default=0,
        ge=0,
    )

    panel_current: int = Field(
        default=0,
        ge=0,
    )

    panel_max: int | None = Field(
        default=None,
        ge=0,
    )

    # Inverter
    inverter_brand: str | None = None

    inverter_model: str | None = None

    inverter_phase: str | None = None

    inverter_size_kw: float | None = Field(
        default=None,
        ge=0,
    )

    # Battery
    battery: bool = False

    battery_brand: str | None = None

    battery_model: str | None = None

    battery_phase: str | None = None

    battery_size_kwh: float | None = Field(
        default=None,
        ge=0,
    )

    # Backup
    backup_brand: str | None = None

    backup_model: str | None = None

    backup_phase: str | None = None

    backup_size_amp: float | None = Field(
        default=None,
        ge=0,
    )

    # -----------------------------------------------------
    # Site Intelligent
    # Future / Maximum capacity
    # -----------------------------------------------------

    # PV
    intelligent_pv_brand: str | None = None

    intelligent_pv_size_module_w: float | None = Field(
        default=None,
        ge=0,
    )

    intelligent_pv_capacity_kwp: float | None = Field(
        default=None,
        ge=0,
    )

    intelligent_pv_qty_module: int | None = Field(
        default=None,
        ge=0,
    )

    # Inverter
    intelligent_inverter_brand: str | None = None

    intelligent_inverter_model: str | None = None

    intelligent_inverter_phase: str | None = None

    intelligent_inverter_size_kw: float | None = Field(
        default=None,
        ge=0,
    )

    # Battery
    intelligent_battery_brand: str | None = None

    intelligent_battery_model: str | None = None

    intelligent_battery_phase: str | None = None

    intelligent_battery_size_kwh: float | None = Field(
        default=None,
        ge=0,
    )

    # Backup
    intelligent_backup_brand: str | None = None

    intelligent_backup_model: str | None = None

    intelligent_backup_phase: str | None = None

    intelligent_backup_size_amp: float | None = Field(
        default=None,
        ge=0,
    )


# =========================================================
# Site Update Model
# =========================================================

class SiteUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # -----------------------------------------------------
    # Customer Database
    # -----------------------------------------------------

    site_code: str | None = Field(
        default=None,
        min_length=1,
    )

    site_name: str | None = None

    customer_name: str | None = None

    tel: str | None = None

    email: str | None = None

    address: str | None = None

    date_of_birth: date | None = None

    # -----------------------------------------------------
    # Site Database
    # -----------------------------------------------------

    install_date: date | None = None

    tou: bool | None = None

    status: str | None = None

    # PV
    pv_brand: str | None = None

    pv_size_module_w: float | None = Field(
        default=None,
        ge=0,
    )

    installed_size_kwp: float | None = Field(
        default=None,
        ge=0,
    )

    panel_current: int | None = Field(
        default=None,
        ge=0,
    )

    panel_max: int | None = Field(
        default=None,
        ge=0,
    )

    # Inverter
    inverter_brand: str | None = None

    inverter_model: str | None = None

    inverter_phase: str | None = None

    inverter_size_kw: float | None = Field(
        default=None,
        ge=0,
    )

    # Battery
    battery: bool | None = None

    battery_brand: str | None = None

    battery_model: str | None = None

    battery_phase: str | None = None

    battery_size_kwh: float | None = Field(
        default=None,
        ge=0,
    )

    # Backup
    backup_brand: str | None = None

    backup_model: str | None = None

    backup_phase: str | None = None

    backup_size_amp: float | None = Field(
        default=None,
        ge=0,
    )

    # -----------------------------------------------------
    # Site Intelligent
    # -----------------------------------------------------

    intelligent_pv_brand: str | None = None

    intelligent_pv_size_module_w: float | None = Field(
        default=None,
        ge=0,
    )

    intelligent_pv_capacity_kwp: float | None = Field(
        default=None,
        ge=0,
    )

    intelligent_pv_qty_module: int | None = Field(
        default=None,
        ge=0,
    )

    intelligent_inverter_brand: str | None = None

    intelligent_inverter_model: str | None = None

    intelligent_inverter_phase: str | None = None

    intelligent_inverter_size_kw: float | None = Field(
        default=None,
        ge=0,
    )

    intelligent_battery_brand: str | None = None

    intelligent_battery_model: str | None = None

    intelligent_battery_phase: str | None = None

    intelligent_battery_size_kwh: float | None = Field(
        default=None,
        ge=0,
    )

    intelligent_backup_brand: str | None = None

    intelligent_backup_model: str | None = None

    intelligent_backup_phase: str | None = None

    intelligent_backup_size_amp: float | None = Field(
        default=None,
        ge=0,
    )


# =========================================================
# Supabase helper
# =========================================================

def _execute(
    query: Any,
    *,
    unique_site_code: bool = False,
) -> list[dict[str, Any]]:

    try:
        response = query.execute()

    except HTTPException:
        raise

    except Exception as exc:

        # Log the real Supabase error in Render Logs so insert/update
        # failures can be diagnosed without guessing.
        print("SUPABASE ERROR:", repr(exc), flush=True)

        error_code = str(
            getattr(exc, "code", "")
        )

        error_text = str(exc).lower()

        if unique_site_code and (
            error_code == "23505"
            or "duplicate key" in error_text
            or "unique constraint" in error_text
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "A site with this site_code "
                    "already exists."
                ),
            ) from exc

        # Temporarily return the Supabase error message while debugging.
        # Once the schema issue is fixed, change this back to a generic
        # production-safe message.
        raise HTTPException(
            status_code=502,
            detail=f"Supabase error: {str(exc)}",
        ) from exc

    return response.data or []


# =========================================================
# Find Site
# =========================================================

def _find_site(
    site_code: str,
) -> dict[str, Any] | None:

    client = get_supabase_client()

    sites = _execute(
        client.table("sites")
        .select("*")
        .eq("site_code", site_code)
        .limit(1)
    )

    return sites[0] if sites else None


# =========================================================
# Get Site
# =========================================================

def _get_site(
    site_code: str,
) -> dict[str, Any]:

    site = _find_site(site_code)

    if not site:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Site '{site_code}' "
                "was not found."
            ),
        )

    return site


# =========================================================
# Get History
# =========================================================

def _get_history(
    site: dict[str, Any],
) -> list[dict[str, Any]]:

    site_id = site.get("id")

    if not site_id:
        raise HTTPException(
            status_code=500,
            detail=(
                "The site record does not contain "
                "its database ID."
            ),
        )

    client = get_supabase_client()

    history = _execute(
        client.table("analysis_history")
        .select(ANALYSIS_HISTORY_FIELDS)
        .eq("site_id", site_id)
        .order(
            "analysis_date",
            desc=True,
        )
    )

    return history


# =========================================================
# LIST SITES
# =========================================================

@router.get("")
def list_sites() -> dict[str, Any]:

    client = get_supabase_client()

    sites = _execute(
        client.table("sites")
        .select("*")
        .order("site_code")
    )

    return {
        "count": len(sites),
        "sites": sites,
    }


# =========================================================
# CREATE SITE
# =========================================================

@router.post("", status_code=201)
def create_site(
    payload: SiteCreate,
) -> dict[str, Any]:

    if _find_site(payload.site_code):

        raise HTTPException(
            status_code=409,
            detail=(
                "A site with this site_code "
                "already exists."
            ),
        )

    client = get_supabase_client()

    payload_data = payload.model_dump(
        mode="json",
        exclude_none=True,
    )

    sites = _execute(
        client.table("sites")
        .insert(payload_data),
        unique_site_code=True,
    )

    if not sites:

        raise HTTPException(
            status_code=502,
            detail=(
                "Supabase did not return "
                "the created site."
            ),
        )

    return {
        "site": sites[0],
    }


# =========================================================
# SITE HISTORY
# =========================================================

@router.get("/{site_code}/history")
def get_site_history(
    site_code: str,
) -> dict[str, Any]:

    site = _get_site(site_code)

    history = _get_history(site)

    return {
        "site_code": site["site_code"],
        "count": len(history),
        "history": history,
    }


# =========================================================
# LATEST ANALYSIS
# =========================================================

@router.get("/{site_code}/latest")
def get_latest_site_analysis(
    site_code: str,
) -> dict[str, Any]:

    site = _get_site(site_code)

    history = _get_history(site)

    return {
        "site_code": site["site_code"],
        "latest": (
            history[0]
            if history
            else None
        ),
    }


# =========================================================
# GET SITE
# =========================================================

@router.get("/{site_code}")
def get_site(
    site_code: str,
) -> dict[str, Any]:

    return {
        "site": _get_site(site_code),
    }


# =========================================================
# UPDATE SITE
# =========================================================

@router.put("/{site_code}")
def update_site(
    site_code: str,
    payload: SiteUpdate,
) -> dict[str, Any]:

    existing_site = _get_site(
        site_code
    )

    changes = payload.model_dump(
        mode="json",
        exclude_unset=True,
    )

    if not changes:

        raise HTTPException(
            status_code=400,
            detail=(
                "At least one site field "
                "must be provided."
            ),
        )

    new_site_code = changes.get(
        "site_code"
    )

    if (
        new_site_code
        and new_site_code != site_code
    ):

        if _find_site(new_site_code):

            raise HTTPException(
                status_code=409,
                detail=(
                    "A site with this site_code "
                    "already exists."
                ),
            )

    client = get_supabase_client()

    sites = _execute(
        client.table("sites")
        .update(changes)
        .eq(
            "id",
            existing_site["id"],
        ),
        unique_site_code=True,
    )

    if not sites:

        raise HTTPException(
            status_code=502,
            detail=(
                "Supabase did not return "
                "the updated site."
            ),
        )

    return {
        "site": sites[0],
    }


# =========================================================
# DELETE SITE
# =========================================================

@router.delete("/{site_code}")
def delete_site(
    site_code: str,
) -> dict[str, Any]:

    existing_site = _get_site(
        site_code
    )

    client = get_supabase_client()

    _execute(
        client.table("sites")
        .delete()
        .eq(
            "id",
            existing_site["id"],
        )
    )

    return {
        "status": "deleted",
        "site_code": (
            existing_site["site_code"]
        ),
    }