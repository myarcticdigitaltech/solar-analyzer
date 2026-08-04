from typing import Any

from fastapi import APIRouter, HTTPException

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


def _execute(query: Any) -> list[dict[str, Any]]:
    try:
        response = query.execute()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to read site data from Supabase.",
        ) from exc

    return response.data or []


def _get_site(site_code: str) -> dict[str, Any]:
    client = get_supabase_client()
    sites = _execute(
        client.table("sites")
        .select("*")
        .eq("site_code", site_code)
        .limit(1)
    )

    if not sites:
        raise HTTPException(
            status_code=404,
            detail=f"Site '{site_code}' was not found.",
        )

    return sites[0]


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
