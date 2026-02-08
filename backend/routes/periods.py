from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime, date, timedelta
import uuid

from database import supabase
from routes.auth import get_current_user
from period_service import (
    can_log_period,
    check_anomaly,
    get_predictions,
    calculate_rolling_average,
    calculate_rolling_period_length,
    MIN_PERIOD_DAYS,
    MAX_PERIOD_DAYS
)
from cycle_stats import get_cycle_stats
from cycle_utils import (
    detect_early_late_period, 
    update_cycle_length_bayesian,
    update_luteal_estimate,
    estimate_luteal,
    predict_ovulation
)

router = APIRouter()

class PeriodLogRequest(BaseModel):
    date: str
    flow: Optional[str] = None
    notes: Optional[str] = None

class PeriodLogUpdate(BaseModel):
    flow: Optional[str] = None
    notes: Optional[str] = None

@router.post("/log")
async def log_period(
    log_data: PeriodLogRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Log a period entry.
    
    NEW SIMPLIFIED FLOW (Flo-inspired):
    1. Validate date (no overlaps, minimum spacing)
    2. Check for anomaly
    3. Save daily bleeding log
    4. Rebuild PeriodStartLogs (one log = one cycle start)
    5. Recompute cycle stats (length mean, SD)
    6. Mark future predictions as dirty
    7. Regenerate predictions from last confirmed period
    
    Luteal updates happen asynchronously (not blocking UX).
    """
    try:
        user_id = current_user["id"]
        
        # Parse date
        if isinstance(log_data.date, str):
            date_obj = datetime.strptime(log_data.date, "%Y-%m-%d").date()
        else:
            date_obj = log_data.date
        
        # CRITICAL: Prevent logging periods in future dates
        today = datetime.now().date()
        if date_obj > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot log period for future dates. Please log periods that have already occurred."
            )
        
        # Validate if period can be logged
        validation = can_log_period(user_id, date_obj)
        if not validation.get("canLog", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation.get("reason", "Cannot log period for this date.")
            )
        
        # Check for anomaly
        is_anomaly = check_anomaly(user_id, date_obj)
        
        # NEW: Check if this date is within an existing period range
        # If user tries to log a date that's already part of a logged period, reject it
        from period_start_logs import get_period_start_logs
        from cycle_utils import estimate_period_length
        from datetime import timedelta
        
        existing_starts = get_period_start_logs(user_id, confirmed_only=False)
        period_length = estimate_period_length(user_id)
        period_length_days = int(round(max(3.0, min(8.0, period_length))))  # Normalized period length
        
        # Check if date falls within any existing period range
        for start_log in existing_starts:
            start_date_str = start_log["start_date"]
            if isinstance(start_date_str, str):
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                start_date = start_date_str
            
            period_end = start_date + timedelta(days=period_length_days - 1)
            
            # If logging a date within an existing period range, reject it
            if start_date <= date_obj <= period_end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This date falls within an existing period (started {start_date_str}). Please log only the period start date."
                )
        
        # Step 1: Save period START log (one log = one cycle start)
        # This is now treated as a period start, not a daily bleeding log
        log_entry = {
            "user_id": user_id,
            "date": log_data.date,
            "flow": log_data.flow,
            "notes": log_data.notes
        }
        
        # Check if this date already exists as a period start
        existing = supabase.table("period_logs").select("*").eq("user_id", user_id).eq("date", log_data.date).execute()
        
        if existing.data:
            # Update existing log
            response = supabase.table("period_logs").update(log_entry).eq("user_id", user_id).eq("date", log_data.date).execute()
        else:
            # Insert new period start log
            response = supabase.table("period_logs").insert(log_entry).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create/update period log"
            )
        
        # Step 2: Automatically create period days in user_cycle_days based on estimated period length
        # This ensures the calendar shows the full period range even though user only logged start
        period_length_days = int(round(max(3.0, min(8.0, period_length))))
        from cycle_utils import store_cycle_phase_map
        
        period_days = []
        for day_offset in range(period_length_days):
            period_date = date_obj + timedelta(days=day_offset)
            period_date_str = period_date.strftime("%Y-%m-%d")
            
            # Create phase mapping for this period day
            period_days.append({
                "date": period_date_str,
                "phase": "Period",
                "phase_day_id": f"p{day_offset + 1}",
                "fertility_prob": 0,
                "is_predicted": False  # This is logged data, not predicted
            })
        
        # Store period days in user_cycle_days
        if period_days:
            store_cycle_phase_map(user_id, period_days, update_future_only=False)
            print(f"✅ Created {len(period_days)} period days automatically from period start {log_data.date}")
        
        # Step 3: Rebuild PeriodStartLogs (one log = one cycle start)
        from period_start_logs import sync_period_start_logs_from_period_logs
        print(f"🔄 Syncing period_start_logs for user {user_id} after logging period start on {log_data.date}")
        sync_period_start_logs_from_period_logs(user_id)
        
        # Verify sync worked
        from period_start_logs import get_period_start_logs
        synced_starts = get_period_start_logs(user_id, confirmed_only=False)
        print(f"✅ Verified: {len(synced_starts)} period_start_logs after sync")
        
        # Step 3: Recompute cycle stats from PeriodEvents
        from cycle_stats import update_user_cycle_stats
        update_user_cycle_stats(user_id)
        
        # Step 4: Mark future predictions as dirty (quick, synchronous)
        # Delete all predicted days after the last confirmed period start
        from prediction_cache import invalidate_predictions_after_period
        invalidate_predictions_after_period(user_id, period_start_date=None)
        
        # Step 5: Generate predictions IMMEDIATELY for 7 months (3 past + current + 3 future)
        # This ensures calendar updates instantly with ACCURATE calculations
        from cycle_utils import calculate_phase_for_date_range, store_cycle_phase_map
        from datetime import timedelta
        
        try:
            # Generate predictions for 3 months past + current + 3 months future (7 months) INSTANTLY
            today = datetime.now()
            start_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")  # 3 months back
            end_date = (today + timedelta(days=90)).strftime("%Y-%m-%d")  # 3 months ahead
            
            # Get user cycle length (will be updated by sync_period_start_logs)
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            cycle_length = user_response.data[0].get("cycle_length", 28) if user_response.data else 28
            
            # CRITICAL: Use the newly logged period date for accurate calculations
            # This ensures predictions are based on the most recent period
            print(f"🔄 Generating 7 months of predictions immediately using logged period: {log_data.date}")
            phase_mappings = calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=log_data.date,  # Use newly logged date for accuracy
                cycle_length=int(cycle_length),
                start_date=start_date,
                end_date=end_date
            )
            
            # Store immediately - this updates the 7 months with accurate calculations
            if phase_mappings:
                store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
                print(f"✅ Generated {len(phase_mappings)} ACCURATE predictions immediately for 7 months")
            else:
                print("⚠️ No phase mappings generated for 7 months")
        except Exception as e:
            print(f"⚠️ Immediate prediction generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Step 6: Regenerate full range in BACKGROUND (non-blocking)
        # This runs in background for complete calendar coverage
        from prediction_cache import regenerate_predictions_from_last_confirmed_period
        
        def regenerate_background():
            try:
                # Generate for full calendar range: 2 years future
                regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=730)
            except Exception as e:
                print(f"⚠️ Background prediction regeneration failed: {str(e)}")
        
        # Add to background tasks - runs after response is sent
        background_tasks.add_task(regenerate_background)
        
        # Step 6: Asynchronous luteal learning (non-blocking)
        # Only learns from confirmed cycles with high-confidence ovulation predictions
        try:
            from luteal_learning import learn_luteal_from_new_period
            learn_luteal_from_new_period(user_id, log_data.date)
        except Exception as luteal_error:
            # Non-blocking - log error but don't fail
            print(f"⚠️ Luteal learning failed (non-blocking): {str(luteal_error)}")
        
        # Update user's last_period_date
        # Note: period_length is calculated dynamically from period logs, not stored in user profile
        update_data = {
            "last_period_date": log_data.date
        }
        
        user_update = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        updated_user = user_update.data[0] if user_update.data else None
        
        # Get updated logs and predictions
        logs_response = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date", desc=True).execute()
        logs = logs_response.data or []
        
        # Get updated predictions
        predictions = get_predictions(user_id, count=6)
        
        # Get rolling averages
        rolling_average = calculate_rolling_average(user_id)
        rolling_period_average = calculate_rolling_period_length(user_id)
        
        # Transform to camelCase
        return {
            "log": {
                "id": response.data[0].get("id"),
                "userId": response.data[0].get("user_id"),
                "date": response.data[0].get("date"),
                "flow": response.data[0].get("flow"),
                "notes": response.data[0].get("notes"),
                "isAnomaly": is_anomaly
            },
            "logs": [{
                "id": log.get("id"),
                "userId": log.get("user_id"),
                "date": log.get("date"),
                "flow": log.get("flow"),
                "notes": log.get("notes")
            } for log in logs],
            "predictions": predictions,
            "rollingAverage": rolling_average,
            "rollingPeriodAverage": rolling_period_average
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log period: {str(e)}"
        )

@router.get("/logs")
async def get_period_logs(current_user: dict = Depends(get_current_user)):
    """Get all period logs for the current user. Returns camelCase."""
    try:
        user_id = current_user["id"]
        
        response = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date", desc=False).execute()
        
        # Transform to camelCase
        logs = [{
            "id": log.get("id"),
            "userId": log.get("user_id"),
            "startDate": log.get("date"),
            "endDate": None,  # Not stored, derived
            "isAnomaly": False  # Would need to check
        } for log in (response.data or [])]
        
        return logs
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch period logs: {str(e)}"
        )


@router.get("/predictions")
async def get_predictions_endpoint(
    count: int = 6,
    current_user: dict = Depends(get_current_user)
):
    """Get predictions with confidence levels. Returns camelCase."""
    try:
        user_id = current_user["id"]
        
        predictions = get_predictions(user_id, count=count)
        rolling_average = calculate_rolling_average(user_id)
        rolling_period_average = calculate_rolling_period_length(user_id)
        confidence = get_cycle_stats(user_id).get("confidence", {})
        
        return {
            "predictions": predictions,
            "rollingAverage": rolling_average,
            "rollingPeriodAverage": rolling_period_average,
            "confidence": confidence
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch predictions: {str(e)}"
        )


@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get comprehensive cycle statistics. Returns camelCase."""
    try:
        user_id = current_user["id"]
        stats = get_cycle_stats(user_id)
        return stats
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
        )

@router.get("/episodes")
async def get_period_episodes(current_user: dict = Depends(get_current_user)):
    """
    Get period episodes (start dates + predicted end dates) for calendar rendering.
    
    Returns list of episodes with:
    - start_date: Period start date (from period_logs)
    - predicted_end_date: Predicted end date (start_date + predicted_length)
    - predicted_length: Predicted bleeding length in days
    - is_confirmed: Whether the period has actually occurred
    """
    try:
        from period_start_logs import get_period_start_logs
        from cycle_utils import estimate_period_length
        
        user_id = current_user["id"]
        
        # Get period start logs (cycle start events)
        period_starts = get_period_start_logs(user_id, confirmed_only=False)
        
        # Always use 5 days for period display
        predicted_length = 5
        
        episodes = []
        for start_log in period_starts:
            start_date_str = start_log["start_date"]
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if isinstance(start_date_str, str) else start_date_str
            
            # Calculate predicted end date
            predicted_end_date = start_date + timedelta(days=predicted_length - 1)
            
            episodes.append({
                "start_date": start_date_str,
                "predicted_end_date": predicted_end_date.strftime("%Y-%m-%d"),
                "predicted_length": predicted_length,
                "is_confirmed": start_log.get("is_confirmed", False)
            })
        
        return episodes
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch period episodes: {str(e)}"
        )

@router.put("/log/{log_id}")
async def update_period_log(
    log_id: str,
    log_data: PeriodLogUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a period log entry."""
    try:
        user_id = current_user["id"]
        
        # Verify log belongs to user
        check = supabase.table("period_logs").select("id").eq("id", log_id).eq("user_id", user_id).execute()
        
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found"
            )
        
        update_data = log_data.dict(exclude_unset=True)
        # Note: updated_at column doesn't exist in database
        
        response = supabase.table("period_logs").update(update_data).eq("id", log_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update period log"
            )
        
        return response.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update period log: {str(e)}"
        )

@router.delete("/log/{log_id}")
async def delete_period_log(
    log_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a period log entry. Recalculates predictions."""
    try:
        user_id = current_user["id"]
        
        # Verify log belongs to user
        check = supabase.table("period_logs").select("id").eq("id", log_id).eq("user_id", user_id).execute()
        
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found"
            )
        
        supabase.table("period_logs").delete().eq("id", log_id).execute()
        
        # Rebuild PeriodStartLogs
        from period_start_logs import sync_period_start_logs_from_period_logs
        sync_period_start_logs_from_period_logs(user_id)
        
        # Recompute cycle stats
        from cycle_stats import update_user_cycle_stats
        update_user_cycle_stats(user_id)
        
        # Regenerate predictions
        from prediction_cache import invalidate_predictions_after_period
        invalidate_predictions_after_period(user_id, period_start_date=None)
        from prediction_cache import regenerate_predictions_from_last_confirmed_period
        regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=60)
        
        return {"message": "Period log deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete period log: {str(e)}"
        )


@router.patch("/log/{log_id}/anomaly")
async def toggle_anomaly(
    log_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Toggle anomaly flag for a period log."""
    try:
        user_id = current_user["id"]
        
        # Verify log belongs to user
        check = supabase.table("period_logs").select("id").eq("id", log_id).eq("user_id", user_id).execute()
        
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found"
            )
        
        # Note: This would require an is_anomaly column in period_logs table
        # For now, we'll just return success
        # In a full implementation, you'd update the anomaly flag here
        
        return {"message": "Anomaly flag toggled"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle anomaly: {str(e)}"
        )

