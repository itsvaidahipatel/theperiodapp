from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import logging
import os

from database import supabase, async_supabase_call, retry_supabase_call
from routes.auth import get_current_user
from cycle_utils import (
    calculate_phase_for_date_range,
    get_user_phase_day,
    group_logs_into_episodes,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _late_anchor_shift_days_from_user(user: dict) -> int:
    try:
        return int(max(0, user.get("late_period_anchor_shift_days") or 0))
    except (TypeError, ValueError):
        return 0


# NOTE: _prediction_in_progress removed - predictions are now calculated synchronously on-demand

class CyclePredictionRequest(BaseModel):
    past_cycle_data: List[Dict]
    current_date: Optional[str] = None

@router.post("/predict")
async def predict_cycles(
    request: CyclePredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate cycle predictions and phase mappings for user using adaptive local algorithms."""
    try:
        user_id = current_user["id"]
        from missing_period_handler import handle_missing_period

        handle_missing_period(user_id)
        current_date = request.current_date or datetime.now().strftime("%Y-%m-%d")
        
        # Get user data
        user_response = supabase.table("users").select(
            "last_period_date, cycle_length, late_period_anchor_shift_days"
        ).eq("id", user_id).execute()
        if not user_response.data or not user_response.data[0]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User data not found. Please set last_period_date."
            )
        
        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        # Type safety: cast cycle_length explicitly
        try:
            cycle_length = int(user.get("cycle_length", 28) or 28)
        except (TypeError, ValueError):
            cycle_length = 28
        
        if not last_period_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="last_period_date is required. Please log a period or set it in your profile."
            )
        
        # Convert to string if needed
        if hasattr(last_period_date, 'strftime'):
            last_period_date_str = last_period_date.strftime("%Y-%m-%d")
        else:
            last_period_date_str = str(last_period_date)
        
        # Calculate date range (3 months around current date)
        current_date_obj = datetime.strptime(str(current_date), "%Y-%m-%d")
        start_date = (current_date_obj - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = (current_date_obj + timedelta(days=60)).strftime("%Y-%m-%d")

        logs_response = (
            supabase.table("period_logs")
            .select("date, end_date")
            .eq("user_id", user_id)
            .order("date")
            .execute()
        )
        period_logs = logs_response.data or []
        
        # Generate cycle phase map using adaptive local algorithms
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=last_period_date_str,
            cycle_length=cycle_length,
            period_logs=period_logs,
            start_date=start_date,
            end_date=end_date,
            late_anchor_shift_days=_late_anchor_shift_days_from_user(user),
        )
        
        # Get current phase-day
        current_phase = get_user_phase_day(user_id, current_date)
        
        return {
            "message": "Cycle predictions generated successfully using adaptive local algorithms",
            "phase_mappings": phase_mappings,
            "current_phase": current_phase
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cycle prediction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cycle prediction failed: {str(e)}"
        )

@router.get("/current-phase")
async def get_current_phase(
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current phase using the same logic as the calendar (calculate_phase_for_date_range).
    If the date is inside a period_log, phase is always Period (p1, p2, ...)."""
    try:
        from cycle_utils import get_period_phase_day_from_logs, calculate_phase_for_date_range

        user_id = current_user["id"]
        check_date = str(date or datetime.now().strftime("%Y-%m-%d"))
        today = datetime.now().date()

        from missing_period_handler import handle_missing_period_async

        await handle_missing_period_async(user_id, check_date)

        # Type safety: validate incoming date
        try:
            check_date_obj = datetime.strptime(check_date, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

        # 1) Fetch user and period_logs in parallel (reduces latency)
        @retry_supabase_call(max_retries=3)
        def _fetch_user():
            return supabase.table("users").select(
                "last_period_date, cycle_length, late_period_anchor_shift_days"
            ).eq("id", user_id).execute()

        @retry_supabase_call(max_retries=3)
        def _fetch_logs():
            return supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()

        user_response, logs_response = await asyncio.gather(
            async_supabase_call(_fetch_user),
            async_supabase_call(_fetch_logs),
        )

        if not getattr(user_response, "data", None) or not user_response.data[0]:
            return {"phase": None, "phase_day_id": None, "id": None, "message": "User data not found."}

        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        if hasattr(last_period_date, "strftime"):
            last_period_date = last_period_date.strftime("%Y-%m-%d") if last_period_date else None
        elif last_period_date is not None and not isinstance(last_period_date, str):
            last_period_date = str(last_period_date)

        # Type safety: cast cycle_length explicitly
        try:
            cycle_length = int(user.get("cycle_length", 28) or 28)
        except (TypeError, ValueError):
            cycle_length = 28

        period_logs = (getattr(logs_response, "data", None) or [])

        # 2) If date is inside a period_log, always return Period + pN (matches calendar)
        period_day_id = get_period_phase_day_from_logs(user_id, period_logs, check_date)
        if period_day_id is not None:
            # Graceful auto-update: only update last_period_date for today or past, never future dates
            if period_day_id.lower() == "p1" and check_date_obj <= today:
                supabase.table("users").update({"last_period_date": check_date}).eq("id", user_id).execute()
                logger.info("Auto-updated last_period_date due to p1 (log)")
            return {
                "phase": "Period",
                "phase_day_id": period_day_id,
                "date": check_date,
                "is_actual": True,
            }

        # Log to See Data: no last_period_date -> no phase (do not default to today)
        if not last_period_date:
            return {
                "phase": None,
                "phase_day_id": None,
                "id": None,
                "message": "No phase data. Please set your last period date or log a period."
            }

        # 3) Use same math as calendar: single-day calculate_phase_for_date_range
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=last_period_date,
            cycle_length=cycle_length,
            period_logs=period_logs,
            start_date=check_date,
            end_date=check_date,
            late_anchor_shift_days=_late_anchor_shift_days_from_user(user),
        )
        if phase_mappings and len(phase_mappings) >= 1:
            m = phase_mappings[0]
            phase = m.get("phase") or "Follicular"
            phase_day_id = m.get("phase_day_id") or "f1"
            # Graceful auto-update: only update last_period_date for today or past, never future dates
            if phase_day_id.lower() == "p1" and check_date_obj <= today:
                supabase.table("users").update({"last_period_date": check_date}).eq("id", user_id).execute()
                logger.info("Auto-updated last_period_date due to p1 (calc)")
            return {
                "phase": phase,
                "phase_day_id": phase_day_id,
                "date": check_date,
                "is_actual": False,
                **{k: m[k] for k in ("fertility_prob", "predicted_ovulation_date", "luteal_estimate") if k in m},
            }

        # Fallback: no phase data
        return {
            "phase": None,
            "phase_day_id": None,
            "id": None,
            "message": "No phase data available. Please set your last period date."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in get_current_phase")
        return {"phase": None, "phase_day_id": None, "id": None, "message": f"No phase data available: {str(e)}"}

# NOTE: _generate_phase_map_background removed - predictions are now calculated synchronously on-demand

@router.get("/phase-map")
async def get_phase_map(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force_recalculate: bool = False,  # Kept for API compatibility but ignored
    debug: bool = Query(False, description="If true, include a compact debug slice for the requested range"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get phase mappings for a date range. Calculates on-demand in RAM.
    
    NEW STATELESS ARCHITECTURE:
    - Fetches period_logs once (source of truth)
    - Calculates phases in RAM using calculate_phase_for_date_range()
    - Returns JSON immediately (no background tasks, no DB writes)
    
    Args:
        start_date: Start date for phase map (YYYY-MM-DD)
        end_date: End date for phase map (YYYY-MM-DD)
        force_recalculate: Ignored (always calculates fresh)
    """
    try:
        user_id = current_user["id"]

        from missing_period_handler import handle_missing_period_async

        await handle_missing_period_async(user_id)
        
        # 1) Get user cycle config
        user_response = supabase.table("users").select(
            "last_period_date, cycle_length, late_period_anchor_shift_days"
        ).eq("id", user_id).execute()
        
        if not user_response.data or not user_response.data[0]:
            return {"phase_map": []}
        
        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        # Type safety: cast cycle_length explicitly
        try:
            cycle_length = int(user.get("cycle_length", 28) or 28)
        except (TypeError, ValueError):
            cycle_length = 28
        
        # Log to See Data: no last_period_date -> empty phase map (onboarding collects it)
        if not last_period_date:
            return {"phase_map": []}
        
        # Normalize last_period_date to string
        if hasattr(last_period_date, "strftime"):
            last_period_date_str = last_period_date.strftime("%Y-%m-%d")
        elif isinstance(last_period_date, str):
            last_period_date_str = last_period_date
        else:
            last_period_date_str = str(last_period_date)
        
        cycle_length_int = cycle_length
        
        # 2) Fetch period_logs once (source of truth)
        logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
        period_logs = logs_response.data or []

        # 2b) Fetch stored cycle_data_json from period_start_logs (immutable past)
        from period_start_logs import get_period_start_logs
        period_starts_with_cycle = get_period_start_logs(user_id, confirmed_only=False)
        stored_phases_by_date = {}  # date_str -> {phase, phase_day_id, is_predicted: False, ...}
        for ps in period_starts_with_cycle or []:
            cycle_json = ps.get("cycle_data_json")
            if cycle_json and isinstance(cycle_json, list):
                for entry in cycle_json:
                    d = entry.get("date")
                    if d:
                        stored_phases_by_date[str(d)] = dict(entry)
                        stored_phases_by_date[str(d)]["is_predicted"] = False
        
        # 3) Validate dates
        logger.info("Phase map requested")
        try:
            datetime.strptime(last_period_date_str, "%Y-%m-%d")
            if start_date:
                datetime.strptime(str(start_date), "%Y-%m-%d")
            if end_date:
                datetime.strptime(str(end_date), "%Y-%m-%d")
        except Exception as date_error:
            logger.error("Invalid date format in phase-map request")
            return {"phase_map": []}
        
        # 4) Calculate phases (dynamic predictions)
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=last_period_date_str,
            cycle_length=cycle_length_int,
            period_logs=period_logs,
            start_date=start_date,
            end_date=end_date,
            late_anchor_shift_days=_late_anchor_shift_days_from_user(user),
        )

        # 5) Override with stored phases where available (immutable past)
        result = []
        for m in phase_mappings or []:
            d = m.get("date")
            if d and str(d) in stored_phases_by_date:
                stored = stored_phases_by_date[str(d)]
                out = dict(stored)
                out.setdefault("is_predicted", False)
                out.setdefault("is_virtual", False)
                result.append(out)
            else:
                out = dict(m)
                # Preserve is_predicted and is_virtual from calculate_phase_for_date_range
                out.setdefault("is_predicted", True)
                out.setdefault("is_virtual", out.get("is_virtual", False))
                result.append(out)

        if debug:
            debug_rows = []
            for row in result or []:
                debug_rows.append(
                    {
                        "date": row.get("date"),
                        "phase": row.get("phase"),
                        "phase_day_id": row.get("phase_day_id"),
                        "fertility_prob": row.get("fertility_prob"),
                        "is_predicted": row.get("is_predicted"),
                        "is_virtual": row.get("is_virtual"),
                        "is_fertile_window": row.get("is_fertile_window"),
                        "is_ovulation_event": row.get("is_ovulation_event"),
                    }
                )
            return {"phase_map": result, "debug_rows": debug_rows}

        return {"phase_map": result}
    
    except Exception:
        logger.exception("Error getting phase map")
        return {"phase_map": []}


@router.get("/period-start-logs")
async def get_period_start_logs_endpoint(
    confirmed_only: bool = Query(False, description="If true, only confirmed (on or before today) starts"),
    current_user: dict = Depends(get_current_user),
):
    """
    Return synced period start anchors for the authenticated user (same source as phase-map past window).

    Scoped strictly by ``get_current_user`` → ``users.id`` from the verified JWT ``sub``.
    """
    from period_start_logs import get_period_start_logs

    user_id = current_user["id"]
    logs = get_period_start_logs(user_id, confirmed_only=confirmed_only)
    return {"period_start_logs": logs}


@router.get("/health-check")
async def cycle_health_check(
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze last 7 cycles for abnormalities and medical concerns.
    
    Checks for:
    - Irregular cycle lengths (PCOS pattern, hormonal imbalances)
    - Very short cycles (< 21 days)
    - Very long cycles (> 45 days)
    - Missing periods (amenorrhea)
    - Cycle length variance (irregularity indicators)
    
    Returns:
    - Cycle statistics for last 7 cycles
    - Abnormalities detected
    - Risk level (low, medium, high)
    - Recommendations
    """
    try:
        user_id = current_user["id"]
        
        # Get user data for current cycle stats
        user_response = supabase.table("users").select(
            "last_period_date, cycle_length, late_period_anchor_shift_days"
        ).eq("id", user_id).execute()
        user_data = user_response.data[0] if user_response.data else {}
        last_period_date = user_data.get("last_period_date")
        # Type safety: cast cycle_length explicitly
        try:
            cycle_length = int(user_data.get("cycle_length", 28) or 28)
        except (TypeError, ValueError):
            cycle_length = 28
        
        # Calculate current cycle stats
        current_cycle_stats = None
        if last_period_date:
            try:
                # Parse last_period_date
                if isinstance(last_period_date, str):
                    last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
                elif hasattr(last_period_date, 'date'):
                    last_period = datetime.combine(last_period_date.date(), datetime.min.time())
                else:
                    last_period = last_period_date
                
                # Normalize to date for comparison
                if isinstance(last_period, datetime):
                    last_period_date_only = last_period.date()
                else:
                    last_period_date_only = last_period
                
                today = datetime.now().date()
                days_since_period = (today - last_period_date_only).days
                
                # Get period logs to calculate period length
                period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(10).execute()
                period_days = []
                if period_logs_response.data:
                    for log in period_logs_response.data:
                        if log.get("date"):
                            try:
                                if isinstance(log["date"], str):
                                    log_date = datetime.strptime(log["date"], "%Y-%m-%d").date()
                                else:
                                    log_date = log["date"] if hasattr(log["date"], 'date') else log["date"].date()
                                
                                # Check if within 7 days of last period
                                if abs((log_date - last_period_date_only).days) <= 7:
                                    period_days.append(log_date)
                            except Exception:
                                logger.error("Error parsing period log date in health-check")
                                continue
                
                period_length = len(period_days) if period_days else 5  # Default to 5 if no logs
                
                # Calculate estimated next period
                estimated_next = last_period_date_only + timedelta(days=cycle_length)
                days_until_next = (estimated_next - today).days
                
                current_cycle_stats = {
                    "last_period_date": last_period_date if isinstance(last_period_date, str) else last_period_date.strftime("%Y-%m-%d") if hasattr(last_period_date, 'strftime') else str(last_period_date),
                    "days_since_period": max(0, days_since_period),
                    "cycle_length": int(cycle_length) if cycle_length else 28,
                    "period_length": period_length,
                    "estimated_next_period": estimated_next.strftime("%Y-%m-%d"),
                    "days_until_next_period": days_until_next
                }
            except Exception:
                logger.exception("Error calculating current cycle stats")
                current_cycle_stats = None
        
        # Use PeriodStartLogs for cycle analysis (one log = one cycle start)
        from period_start_logs import get_period_start_logs, get_cycles_from_period_starts
        
        # Get PeriodStartLogs (confirmed only for cycle analysis)
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        # Always show data if we have at least 1 period start
        # We'll display whatever cycles we can derive, even if it's just 1
        if len(period_starts) < 1:
            return {
                "has_sufficient_data": False,
                "cycles_analyzed": 0,
                "message": "No period data available. Please log at least one period to see your cycle information.",
                "current_cycle_stats": current_cycle_stats,
                "abnormalities": [],
                "risk_level": "unknown",
                "recommendations": [],
                "cycle_timeline": [],
                "cycle_statistics": {
                    "average_cycle_length": cycle_length if cycle_length else 28.0,
                    "min_cycle_length": cycle_length if cycle_length else 28,
                    "max_cycle_length": cycle_length if cycle_length else 28,
                    "standard_deviation": 0.0,
                    "variance": 0.0
                },
                "cycle_data": []
            }
        
        # Derive cycles from PeriodStartLogs
        cycles = get_cycles_from_period_starts(user_id)
        
        # Get cycle lengths from derived cycles (even if just 1 cycle)
        cycle_lengths = [c["length"] for c in cycles] if cycles else []
        
        # Get last 7 cycles (or all if less than 7)
        last_7_cycles = cycle_lengths[-7:] if len(cycle_lengths) >= 7 else cycle_lengths
        
        # Determine if we have sufficient data for full analysis (need 2+ cycles)
        has_sufficient_data = len(last_7_cycles) >= 2
        
        # Calculate statistics (use user's cycle_length if no cycles calculated yet)
        if len(last_7_cycles) > 0:
            avg_cycle_length = sum(last_7_cycles) / len(last_7_cycles)
            min_cycle = min(last_7_cycles)
            max_cycle = max(last_7_cycles)
        else:
            # No cycles calculated yet (only 1 period start), use user's estimated cycle length
            avg_cycle_length = cycle_length if cycle_length else 28.0
            min_cycle = cycle_length if cycle_length else 28
            max_cycle = cycle_length if cycle_length else 28
        
        # Calculate variance and standard deviation
        if len(last_7_cycles) > 1:
            variance = sum((x - avg_cycle_length) ** 2 for x in last_7_cycles) / (len(last_7_cycles) - 1)
            std_dev = variance ** 0.5
        else:
            variance = 0
            std_dev = 0
        
        # Medical checks for abnormalities (only if we have 2+ cycles)
        abnormalities = []
        risk_level = "low"
        recommendations = []
        
        # Only perform medical checks if we have sufficient data (2+ cycles)
        if not has_sufficient_data:
            # Still return timeline and stats, but no abnormalities analysis.
            # PERFORMANCE: build full timeline in one pass using calculate_phase_for_date_range.
            cycle_timeline = []

            # Fetch period logs once (needed for correct "Period" override)
            logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
            period_logs = logs_response.data or []

            # Build overall range (from first period start to today + avg_cycle_length)
            first_start = period_starts[0]["start_date"]
            last_start = period_starts[-1]["start_date"]
            first_start_dt = datetime.strptime(first_start, "%Y-%m-%d").date() if isinstance(first_start, str) else first_start
            last_start_dt = datetime.strptime(last_start, "%Y-%m-%d").date() if isinstance(last_start, str) else last_start
            today = datetime.now().date()
            horizon_days = int(avg_cycle_length) if avg_cycle_length else 28
            overall_start = first_start_dt.strftime("%Y-%m-%d")
            overall_end = (max(today, last_start_dt) + timedelta(days=horizon_days)).strftime("%Y-%m-%d")

            # Normalize anchor last_period_date to string
            anchor = last_period_date if isinstance(last_period_date, str) else last_period_date.strftime("%Y-%m-%d") if hasattr(last_period_date, "strftime") else None
            if not anchor:
                anchor = last_start_dt.strftime("%Y-%m-%d")

            phase_rows = calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=anchor,
                cycle_length=cycle_length,
                period_logs=period_logs,
                start_date=overall_start,
                end_date=overall_end,
                late_anchor_shift_days=_late_anchor_shift_days_from_user(user_data),
            ) or []
            phases_by_date = {str(r.get("date")): (r.get("phase") or "Follicular") for r in phase_rows if r.get("date")}

            # Create cycle boundaries
            start_dates = [datetime.strptime(ps["start_date"], "%Y-%m-%d").date() if isinstance(ps["start_date"], str) else ps["start_date"] for ps in period_starts]
            for idx, start_dt in enumerate(start_dates):
                is_last = idx == len(start_dates) - 1
                end_dt = (start_dates[idx + 1]) if not is_last else (start_dt + timedelta(days=horizon_days))
                cycle_len_days = (end_dt - start_dt).days
                daily_phases = []
                cur = start_dt
                for d in range(max(0, cycle_len_days)):
                    date_str = cur.strftime("%Y-%m-%d")
                    daily_phases.append({"date": date_str, "phase": phases_by_date.get(date_str, "Follicular"), "day": d + 1})
                    cur += timedelta(days=1)

                cycle_timeline.append({
                    "cycle_number": len(start_dates) - idx,
                    "start_date": start_dt.strftime("%Y-%m-%d"),
                    "end_date": end_dt.strftime("%Y-%m-%d"),
                    "cycle_length": cycle_len_days,
                    "status": "current" if is_last else "normal",
                    "is_current": is_last,
                    "daily_phases": daily_phases,
                })
            
            # Get current phase and additional stats
            current_phase_info = None
            predicted_ovulation_date = None
            cycles_tracked = len(period_starts)
            cycle_regularity = "Unknown"
            
            try:
                from cycle_utils import get_user_phase_day
                today_str = datetime.now().strftime("%Y-%m-%d")
                phase_data = get_user_phase_day(user_id, today_str)
                
                if phase_data:
                    current_phase_info = {
                        "phase": phase_data.get("phase"),
                        "phase_day_id": phase_data.get("phase_day_id")
                    }
                
                if last_period_date:
                    from cycle_utils import predict_ovulation, estimate_luteal
                    luteal_mean, luteal_sd = estimate_luteal(user_id)
                    
                    predicted_ov_date_str, _, _ = predict_ovulation(
                        last_period_date if isinstance(last_period_date, str) else last_period_date.strftime("%Y-%m-%d"),
                        float(cycle_length),
                        luteal_mean,
                        luteal_sd,
                        cycle_start_sd=None,
                        user_id=user_id
                    )
                    predicted_ovulation_date = predicted_ov_date_str
            except Exception:
                logger.exception("Error getting additional stats")
            
            return {
                "has_sufficient_data": False,
                "cycles_analyzed": len(period_starts),
                "current_cycle_stats": current_cycle_stats,
                "cycle_statistics": {
                    "average_cycle_length": round(avg_cycle_length, 1) if avg_cycle_length else 28.0,
                    "min_cycle_length": cycle_length if cycle_length else 28,
                    "max_cycle_length": cycle_length if cycle_length else 28,
                    "standard_deviation": 0.0,
                    "variance": 0.0
                },
                "cycle_data": [],
                "cycle_timeline": cycle_timeline,
                "abnormalities": [],
                "risk_level": "unknown",
                "recommendations": ["Log more periods to get cycle length analysis and abnormality detection."],
                "current_phase": current_phase_info,
                "predicted_ovulation_date": predicted_ovulation_date,
                "cycles_tracked": cycles_tracked,
                "cycle_regularity": cycle_regularity,
                "last_updated": datetime.now().isoformat()
            }
        
        # Medical checks for abnormalities
        # Check 1: Very short cycles (< 21 days)
        short_cycles = [c for c in last_7_cycles if c < 21]
        if short_cycles:
            abnormalities.append({
                "type": "short_cycles",
                "severity": "high",
                "title": "Very Short Cycles Detected",
                "description": f"{len(short_cycles)} cycle(s) shorter than 21 days. Normal cycles are typically 21-35 days.",
                "cycles_affected": short_cycles,
                "medical_concern": "May indicate hormonal imbalances, thyroid issues, or other medical conditions."
            })
            risk_level = "high"
            recommendations.append("Consult with a healthcare provider. Short cycles may require medical evaluation.")
        
        # Check 2: Very long cycles (> 45 days)
        long_cycles = [c for c in last_7_cycles if c > 45]
        if long_cycles:
            abnormalities.append({
                "type": "long_cycles",
                "severity": "high",
                "title": "Very Long Cycles Detected",
                "description": f"{len(long_cycles)} cycle(s) longer than 45 days. Normal cycles are typically 21-35 days.",
                "cycles_affected": long_cycles,
                "medical_concern": "May indicate PCOS, hormonal imbalances, thyroid issues, or other medical conditions."
            })
            if risk_level != "high":
                risk_level = "high"
            recommendations.append("Consult with a healthcare provider. Long cycles may indicate underlying health issues.")
        
        # Check 3: High variance (irregular cycles) - PCOS pattern
        if std_dev >= 7:
            abnormalities.append({
                "type": "high_variance",
                "severity": "medium",
                "title": "Highly Irregular Cycles",
                "description": f"Cycle length varies significantly (standard deviation: {std_dev:.1f} days). Your cycles range from {min_cycle} to {max_cycle} days.",
                "cycles_affected": last_7_cycles,
                "medical_concern": "High variance may indicate PCOS, hormonal imbalances, or other conditions. Regular cycles typically vary by less than 7 days."
            })
            if risk_level == "low":
                risk_level = "medium"
            recommendations.append("Consider consulting with a healthcare provider if irregularity persists. This pattern may indicate PCOS or other hormonal conditions.")
        
        # Check 4: Moderate variance (somewhat irregular)
        elif std_dev >= 4:
            abnormalities.append({
                "type": "moderate_variance",
                "severity": "low",
                "title": "Somewhat Irregular Cycles",
                "description": f"Cycle length varies moderately (standard deviation: {std_dev:.1f} days). Your cycles range from {min_cycle} to {max_cycle} days.",
                "cycles_affected": last_7_cycles,
                "medical_concern": "Some variation is normal, but consistent irregularity may warrant monitoring."
            })
            if risk_level == "low":
                risk_level = "low"
            recommendations.append("Continue tracking your cycles. If irregularity persists or worsens, consider consulting a healthcare provider.")
        
        # Check 5: Missing periods (amenorrhea) - if gap between periods > 90 days
        if len(period_starts) >= 2:
            max_gap = 0
            for i in range(1, len(period_starts)):
                start1_str = period_starts[i-1]["start_date"]
                start2_str = period_starts[i]["start_date"]
                
                # Parse dates if needed
                if isinstance(start1_str, str):
                    start1 = datetime.strptime(start1_str, "%Y-%m-%d")
                else:
                    start1 = start1_str
                
                if isinstance(start2_str, str):
                    start2 = datetime.strptime(start2_str, "%Y-%m-%d")
                else:
                    start2 = start2_str
                
                # Parse dates if needed
                if isinstance(start1, str):
                    date1 = datetime.strptime(start1, "%Y-%m-%d")
                else:
                    date1 = start1
                
                if isinstance(start2, str):
                    date2 = datetime.strptime(start2, "%Y-%m-%d")
                else:
                    date2 = start2
                
                gap = (start2 - start1).days
                if gap > max_gap:
                    max_gap = gap
            
            if max_gap > 90:
                abnormalities.append({
                    "type": "amenorrhea",
                    "severity": "high",
                    "title": "Missing Periods (Amenorrhea)",
                    "description": f"Gap of {max_gap} days between periods detected. Missing periods for more than 90 days requires medical attention.",
                    "cycles_affected": [max_gap],
                    "medical_concern": "Amenorrhea (absence of periods) can indicate pregnancy, hormonal imbalances, PCOS, thyroid issues, or other medical conditions."
                })
                if risk_level != "high":
                    risk_level = "high"
                recommendations.append("⚠️ URGENT: Consult with a healthcare provider immediately. Missing periods for more than 90 days requires medical evaluation.")
        
        # Check 6: Cycle length outside normal range (21-35 days)
        cycles_outside_normal = [c for c in last_7_cycles if c < 21 or c > 35]
        if cycles_outside_normal and len(cycles_outside_normal) >= len(last_7_cycles) * 0.5:  # More than 50% of cycles
            if not any(a["type"] in ["short_cycles", "long_cycles"] for a in abnormalities):
                abnormalities.append({
                    "type": "abnormal_range",
                    "severity": "medium",
                    "title": "Cycles Outside Normal Range",
                    "description": f"{len(cycles_outside_normal)} out of {len(last_7_cycles)} cycles are outside the normal range (21-35 days).",
                    "cycles_affected": cycles_outside_normal,
                    "medical_concern": "Consistent cycles outside the normal range may indicate underlying health issues."
                })
                if risk_level == "low":
                    risk_level = "medium"
                recommendations.append("Consider consulting with a healthcare provider if this pattern continues.")
        
        # Overall assessment
        if not abnormalities:
            recommendations.append("Your cycles appear to be within normal ranges. Continue tracking for ongoing monitoring.")
        
        # Format cycle data for display
        cycle_data = []
        for i, cycle_length in enumerate(last_7_cycles):
            cycle_data.append({
                "cycle_number": len(last_7_cycles) - i,
                "cycle_length": cycle_length,
                "status": "normal" if 21 <= cycle_length <= 35 else ("short" if cycle_length < 21 else "long")
            })
        
        # Build complete cycle timeline with dates and daily phase data
        # PERFORMANCE: compute all phases in one pass, then slice per cycle.
        logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
        period_logs = logs_response.data or []

        start_dates = [datetime.strptime(ps["start_date"], "%Y-%m-%d").date() if isinstance(ps["start_date"], str) else ps["start_date"] for ps in period_starts]
        today = datetime.now().date()
        horizon_days = int(round(avg_cycle_length)) if avg_cycle_length else 28
        overall_start = start_dates[0].strftime("%Y-%m-%d")
        overall_end = (max(today, start_dates[-1]) + timedelta(days=horizon_days)).strftime("%Y-%m-%d")

        anchor = last_period_date if isinstance(last_period_date, str) else last_period_date.strftime("%Y-%m-%d") if hasattr(last_period_date, "strftime") else start_dates[-1].strftime("%Y-%m-%d")

        phase_rows = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=anchor,
            cycle_length=cycle_length,
            period_logs=period_logs,
            start_date=overall_start,
            end_date=overall_end,
            late_anchor_shift_days=_late_anchor_shift_days_from_user(user_data),
        ) or []
        phases_by_date = {str(r.get("date")): (r.get("phase") or "Follicular") for r in phase_rows if r.get("date")}

        cycle_timeline = []
        for idx, start_dt in enumerate(start_dates):
            is_last = idx == len(start_dates) - 1
            end_dt = (start_dates[idx + 1]) if not is_last else (start_dt + timedelta(days=horizon_days))
            cycle_len_days = (end_dt - start_dt).days
            status = "current" if is_last else ("short" if cycle_len_days < 21 else "long" if cycle_len_days > 35 else "normal")

            daily_phases = []
            cur = start_dt
            for d in range(max(0, cycle_len_days)):
                date_str = cur.strftime("%Y-%m-%d")
                daily_phases.append({"date": date_str, "phase": phases_by_date.get(date_str, "Follicular"), "day": d + 1})
                cur += timedelta(days=1)

            cycle_timeline.append({
                "cycle_number": len(start_dates) - idx,
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": end_dt.strftime("%Y-%m-%d"),
                "cycle_length": cycle_len_days,
                "status": status,
                "is_current": is_last,
                "daily_phases": daily_phases,
            })
        
        # Get current phase and additional stats for dashboard
        current_phase_info = None
        predicted_ovulation_date = None
        cycles_tracked = len(period_starts)
        cycle_regularity = "Unknown"
        
        try:
            # Get current phase
            from cycle_utils import get_user_phase_day
            today_str = datetime.now().strftime("%Y-%m-%d")
            phase_data = get_user_phase_day(user_id, today_str)
            
            if phase_data:
                current_phase_info = {
                    "phase": phase_data.get("phase"),
                    "phase_day_id": phase_data.get("phase_day_id")
                }
            
            # Calculate predicted ovulation (if we have last period date)
            if last_period_date:
                from cycle_utils import predict_ovulation, estimate_luteal
                luteal_mean, luteal_sd = estimate_luteal(user_id)
                
                predicted_ov_date_str, _, _ = predict_ovulation(
                    last_period_date if isinstance(last_period_date, str) else last_period_date.strftime("%Y-%m-%d"),
                    float(cycle_length),
                    luteal_mean,
                    luteal_sd,
                    cycle_start_sd=None,
                    user_id=user_id
                )
                predicted_ovulation_date = predicted_ov_date_str
            
            # Calculate regularity based on standard deviation
            if std_dev < 2:
                cycle_regularity = "Very Regular"
            elif std_dev < 4:
                cycle_regularity = "Regular"
            elif std_dev < 7:
                cycle_regularity = "Somewhat Irregular"
            else:
                cycle_regularity = "Irregular"
        
        except Exception:
            logger.exception("Error getting additional stats")
        
        return {
            "has_sufficient_data": True,
            "cycles_analyzed": len(last_7_cycles),
            "current_cycle_stats": current_cycle_stats,
            "cycle_statistics": {
                "average_cycle_length": round(avg_cycle_length, 1),
                "min_cycle_length": min_cycle,
                "max_cycle_length": max_cycle,
                "standard_deviation": round(std_dev, 1),
                "variance": round(variance, 1) if len(last_7_cycles) > 1 else 0
            },
            "cycle_data": cycle_data,
            "cycle_timeline": cycle_timeline,  # Complete timeline with dates
            "abnormalities": abnormalities,
            "risk_level": risk_level,
            "recommendations": recommendations,
            # Additional stats for comprehensive view
            "current_phase": current_phase_info,
            "predicted_ovulation_date": predicted_ovulation_date,
            "cycles_tracked": cycles_tracked,
            "cycle_regularity": cycle_regularity,
            "last_updated": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.exception("Error in cycle health check")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze cycles: {str(e)}"
        )

@router.get("/debug/cycle-data")
async def debug_cycle_data(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check cycle data for current user."""
    try:
        debug_mode = str(os.getenv("DEBUG_MODE", "")).strip().lower() in ("1", "true", "yes", "on")
        if not debug_mode:
            # Hide endpoint existence when not in debug mode
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        user_id = current_user["id"]
        
        # Check period logs
        period_logs = supabase.table("period_logs").select("*").eq("user_id", user_id).execute()
        
        # Check cycle days
        cycle_days = supabase.table("user_cycle_days").select("*").eq("user_id", user_id).execute()
        
        # Check user data
        user_data = supabase.table("users").select("*").eq("id", user_id).execute()
        
        pl = period_logs.data or []
        return {
            "period_logs_count": len(pl),
            "period_logs": pl,
            "bleeding_episodes": group_logs_into_episodes(pl),
            "cycle_days_count": len(cycle_days.data or []),
            "cycle_days_sample": (cycle_days.data or [])[:5],  # First 5 entries
            "user_last_period_date": user_data.data[0].get("last_period_date") if user_data.data else None,
            "user_cycle_length": user_data.data[0].get("cycle_length") if user_data.data else None
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error in debug_cycle_data")
        return {"error": "debug_failed"}
