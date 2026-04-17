"""
Temporary debug routes for phase-map and sync diagnostics.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import datetime, timedelta
import logging
import os
from typing import Any, Dict, List, Tuple

from database import supabase
from routes.auth import get_current_user
from cycle_utils import calculate_phase_for_date_range

router = APIRouter()
logger = logging.getLogger("periodcycle_ai.debug")


def _guard_not_production() -> None:
    """Block diagnostic endpoints in production."""
    if os.getenv("ENV") == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diagnostics are disabled in production.",
        )


def _safe_int(value: Any, default: int = 28) -> int:
    try:
        return int(value)
    except Exception:
        return default


async def _execute_phase_diagnostic(
    *,
    user_id: str,
    start_date: str,
    end_date: str,
    fallback_anchor: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """
    Shared diagnostic executor: fetch user + logs, run calculate_phase_for_date_range once.

    Returns:
      (phase_mappings, diagnostic_log, period_logs_count)
    """
    user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
    if not user_response.data or not user_response.data[0]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User data not found")
    user = user_response.data[0]

    last_period_date = user.get("last_period_date") or fallback_anchor
    if hasattr(last_period_date, "strftime"):
        last_period_date = last_period_date.strftime("%Y-%m-%d")
    elif last_period_date is not None and not isinstance(last_period_date, str):
        last_period_date = str(last_period_date)

    cycle_length = _safe_int(user.get("cycle_length"), 28)

    logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
    period_logs = logs_response.data or []

    diagnostic_log: List[Dict[str, Any]] = []
    phase_mappings = calculate_phase_for_date_range(
        user_id=user_id,
        last_period_date=last_period_date,
        cycle_length=cycle_length,
        period_logs=period_logs,
        start_date=start_date,
        end_date=end_date,
        diagnostic_log=diagnostic_log,
    ) or []

    return phase_mappings, diagnostic_log, len(period_logs)


@router.get("/6-month-diagnostic")
async def six_month_phase_diagnostic(current_user: dict = Depends(get_current_user)):
    """
    Run calculate_phase_for_date_range for the last 180 days and log each date with
    its assigned anchor and days from anchor. Helps diagnose why dates before the
    first log show F1.
    """
    _guard_not_production()
    user_id = current_user["id"]
    # Last 180 days
    end = datetime.now()
    start = end - timedelta(days=180)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    phase_mappings, diagnostic_log, period_logs_count = await _execute_phase_diagnostic(
        user_id=user_id,
        start_date=start_str,
        end_date=end_str,
        fallback_anchor=end_str,
    )

    for entry in diagnostic_log:
        logger.debug(
            "phase_diagnostic date=%s anchor=%s diff_days=%s phase=%s phase_day_id=%s source=%s",
            entry.get("date"),
            entry.get("anchor"),
            entry.get("days_from_anchor"),
            entry.get("phase"),
            entry.get("phase_day_id"),
            entry.get("source"),
        )

    return {
        "message": "6-month diagnostic complete.",
        "total_days": len(phase_mappings),
        "diagnostic_sample": diagnostic_log[:31],
        "period_logs_count": period_logs_count,
    }


@router.get("/analyze-phases")
async def analyze_phases(
    days: int = Query(90, ge=7, le=365, description="Diagnostic window: today±days (default 90)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Phase map for today-90 to today+90; prints [DEBUG] lines to backend terminal
    so you can verify exact math for every date (anchor, diff, phase, source).
    """
    _guard_not_production()
    user_id = current_user["id"]
    today = datetime.now().date()
    days_int = _safe_int(days, 90)
    start = (today - timedelta(days=days_int)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=days_int)).strftime("%Y-%m-%d")

    phase_mappings, diagnostic_log, period_logs_count = await _execute_phase_diagnostic(
        user_id=user_id,
        start_date=start,
        end_date=end,
        fallback_anchor=today.strftime("%Y-%m-%d"),
    )

    for entry in diagnostic_log:
        logger.debug(
            "phase_analyze date=%s anchor=%s diff_days=%s phase=%s phase_day_id=%s source=%s",
            entry.get("date"),
            entry.get("anchor"),
            entry.get("days_from_anchor"),
            entry.get("phase"),
            entry.get("phase_day_id"),
            entry.get("source"),
        )

    return {
        "message": "analyze-phases complete.",
        "window_days": days_int,
        "total_days": len(phase_mappings),
        "diagnostic_count": len(diagnostic_log),
        "period_logs_count": period_logs_count,
    }
