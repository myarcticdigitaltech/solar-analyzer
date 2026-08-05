from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.database.supabase_client import get_supabase_client


router = APIRouter(prefix="/api/sites", tags=["Sites"])

ANALYSIS_HISTORY_FIELDS = (
    "analysis_date,"
    "average_solar_kwh,"
    "average_usage_kwh,"
    "daytime_coverage_percent,"
    "recommendation,"
    "result_payload"
)


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    site_code: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    address: str
    tel: str
    panel_current: int = Field(ge=0)
    panel_max: int = Field(ge=0)
    battery: bool
    install_date: date | None
    tou: bool
    installed_size_kwp: float = Field(ge=0)
    battery_size_kwh: float | None = Field(ge=0)
    inverter_brand: str
    inverter_model: str
    status: str = Field(min_length=1)


class SiteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    site_code: str | None = Field(default=None, min_length=1)
    customer_name: str | None = Field(default=None, min_length=1)
    address: str | None = None
    tel: str | None = None
    panel_current: int | None = Field(default=None, ge=0)
    panel_max: int | None = Field(default=None, ge=0)
    battery: bool | None = None
    install_date: date | None = None
    tou: bool | None = None
    installed_size_kwp: float | None = Field(default=None, ge=0)
    battery_size_kwh: float | None = Field(default=None, ge=0)
    inverter_brand: str | None = None
    inverter_model: str | None = None
    status: str | None = Field(default=None, min_length=1)


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
        error_code = str(getattr(exc, "code", ""))
        error_text = str(exc).lower()
        if unique_site_code and (
            error_code == "23505"
            or "duplicate key" in error_text
            or "unique constraint" in error_text
        ):
            raise HTTPException(
                status_code=409,
                detail="A site with this site_code already exists.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Unable to access site data in Supabase.",
        ) from exc

    return response.data or []


def _find_site(site_code: str) -> dict[str, Any] | None:
    client = get_supabase_client()
    sites = _execute(
        client.table("sites")
        .select("*")
        .eq("site_code", site_code)
        .limit(1)
    )
    return sites[0] if sites else None


def _get_site(site_code: str) -> dict[str, Any]:
    site = _find_site(site_code)

    if not site:
        raise HTTPException(
            status_code=404,
            detail=f"Site '{site_code}' was not found.",
        )

    return site


def _get_history(site: dict[str, Any]) -> list[dict[str, Any]]:
    site_id = site.get("id")
    if not site_id:
        raise HTTPException(
            status_code=500,
            detail="The site record does not contain its database ID.",
        )

    client = get_supabase_client()
    history = _execute(
        client.table("analysis_history")
        .select(ANALYSIS_HISTORY_FIELDS)
        .eq("site_id", site_id)
        .order("analysis_date", desc=True)
    )
    return history


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


@router.post("", status_code=201)
def create_site(payload: SiteCreate) -> dict[str, Any]:
    if _find_site(payload.site_code):
        raise HTTPException(
            status_code=409,
            detail="A site with this site_code already exists.",
        )

    client = get_supabase_client()
    sites = _execute(
        client.table("sites")
        .insert(payload.model_dump(mode="json")),
        unique_site_code=True,
    )

    if not sites:
        raise HTTPException(
            status_code=502,
            detail="Supabase did not return the created site.",
        )

    return {"site": sites[0]}


@router.get("/{site_code}/history")
def get_site_history(site_code: str) -> dict[str, Any]:
    site = _get_site(site_code)
    history = _get_history(site)

    return {
        "site_code": site["site_code"],
        "count": len(history),
        "history": history,
    }


@router.get("/{site_code}/latest")
def get_latest_site_analysis(site_code: str) -> dict[str, Any]:
    site = _get_site(site_code)
    history = _get_history(site)

    return {
        "site_code": site["site_code"],
        "latest": history[0] if history else None,
    }


@router.get("/{site_code}")
def get_site(site_code: str) -> dict[str, Any]:
    return {"site": _get_site(site_code)}


@router.put("/{site_code}")
def update_site(
    site_code: str,
    payload: SiteUpdate,
) -> dict[str, Any]:
    existing_site = _get_site(site_code)
    changes = payload.model_dump(mode="json", exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="At least one site field must be provided.",
        )

    new_site_code = changes.get("site_code")
    if new_site_code and new_site_code != site_code:
        if _find_site(new_site_code):
            raise HTTPException(
                status_code=409,
                detail="A site with this site_code already exists.",
            )

    client = get_supabase_client()
    sites = _execute(
        client.table("sites")
        .update(changes)
        .eq("id", existing_site["id"]),
        unique_site_code=True,
    )

    if not sites:
        raise HTTPException(
            status_code=502,
            detail="Supabase did not return the updated site.",
        )

    return {"site": sites[0]}


@router.delete("/{site_code}")
def delete_site(site_code: str) -> dict[str, Any]:
    existing_site = _get_site(site_code)
    client = get_supabase_client()
    _execute(
        client.table("sites")
        .delete()
        .eq("id", existing_site["id"])
    )

    return {
        "status": "deleted",
        "site_code": existing_site["site_code"],
    }
