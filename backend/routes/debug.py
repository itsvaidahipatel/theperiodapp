"""
Temporary debug routes for phase-map and sync diagnostics.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from database import supabase
from routes.auth import get_current_user
from cycle_utils import calculate_phase_for_date_range

router = APIRouter()


@router.get("/6-month-diagnostic")
async def six_month_phase_diagnostic(current_user: dict = Depends(get_current_user)):
    """
    Run calculate_phase_for_date_range for the last 180 days and log each date with
    its assigned anchor and days from anchor. Helps diagnose why dates before the
    first log show F1.
    """
    user_id = current_user["id"]
    # Last 180 days
    end = datetime.now()
    start = end - timedelta(days=180)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
    if not user_response.data or not user_response.data[0]:
        return {"error": "User data not found", "diagnostic": []}
    user = user_response.data[0]
    last_period_date = user.get("last_period_date") or end.strftime("%Y-%m-%d")
    if hasattr(last_period_date, "strftime"):
        last_period_date = last_period_date.strftime("%Y-%m-%d")
    cycle_length = int(user.get("cycle_length", 28))

    logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
    period_logs = logs_response.data or []

    diagnostic_log = []
    phase_mappings = calculate_phase_for_date_range(
        user_id=user_id,
        last_period_date=last_period_date,
        cycle_length=cycle_length,
        period_logs=period_logs,
        start_date=start_str,
        end_date=end_str,
        diagnostic_log=diagnostic_log,
    )

    for entry in diagnostic_log:
        print(f"Date: {entry['date']} | Anchor used: {entry['anchor']} | Days from Anchor: {entry['days_from_anchor']} | Phase: {entry.get('phase', '?')}")

    return {
        "message": "6-month diagnostic complete; check server console for Date | Anchor | Days from Anchor",
        "total_days": len(phase_mappings),
        "diagnostic_sample": diagnostic_log[:31],
        "period_logs_count": len(period_logs),
    }


@router.get("/analyze-phases")
async def analyze_phases(current_user: dict = Depends(get_current_user)):
    """
    Phase map for today-90 to today+90; prints [DEBUG] lines to backend terminal
    so you can verify exact math for every date (anchor, diff, phase, source).
    """
    user_id = current_user["id"]
    today = datetime.now().date()
    start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=90)).strftime("%Y-%m-%d")

    user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
    if not user_response.data or not user_response.data[0]:
        return {"error": "User data not found", "diagnostic_count": 0}
    user = user_response.data[0]
    last_period_date = user.get("last_period_date") or today.strftime("%Y-%m-%d")
    if hasattr(last_period_date, "strftime"):
        last_period_date = last_period_date.strftime("%Y-%m-%d")
    cycle_length = int(user.get("cycle_length", 28))

    logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
    period_logs = logs_response.data or []

    diagnostic_log = []
    phase_mappings = calculate_phase_for_date_range(
        user_id=user_id,
        last_period_date=last_period_date,
        cycle_length=cycle_length,
        period_logs=period_logs,
        start_date=start,
        end_date=end,
        diagnostic_log=diagnostic_log,
    )

    for entry in diagnostic_log:
        diff = entry.get("days_from_anchor", 0)
        phase = entry.get("phase", "?")
        phase_day_id = entry.get("phase_day_id", "")
        source = entry.get("source", "Predicted")
        anchor = entry.get("anchor", "?")
        date_str = entry.get("date", "?")
        print(f"[DEBUG] Date: {date_str} | Nearest Anchor: {anchor} | Diff: {diff} days | Phase: {phase} ({phase_day_id}) | Source: {source}")

    return {
        "message": "6-month analyze-phases complete; check backend terminal for [DEBUG] lines.",
        "total_days": len(phase_mappings),
        "diagnostic_count": len(diagnostic_log),
        "period_logs_count": len(period_logs),
    }
