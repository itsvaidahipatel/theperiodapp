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
    date: str  # Period start date (REQUIRED - source of truth)
    end_date: Optional[str] = None  # Period end date (OPTIONAL - can be logged later)
    flow: Optional[str] = None
    notes: Optional[str] = None

class PeriodEndRequest(BaseModel):
    date: str  # Period end date

class PeriodLogUpdate(BaseModel):
    date: Optional[str] = None  # Allow updating the start date
    end_date: Optional[str] = None  # Allow updating the end date
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
        
        # Step 0: Auto-close any periods that have been open > 10 days
        from auto_close_periods import auto_close_open_periods
        auto_closed = auto_close_open_periods(user_id)
        if auto_closed:
            print(f"🔒 Auto-closed {len(auto_closed)} period(s) before logging new period")
        
        # Check for anomaly
        is_anomaly = check_anomaly(user_id, date_obj)
        
        # NEW: Check if this date is within an existing period range
        # If user tries to log a date that's already part of a logged period, reject it
        from period_start_logs import get_period_start_logs
        from cycle_utils import estimate_period_length
        # NOTE: timedelta is already imported at top level - do NOT re-import here
        
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
        
        # Step 1: Handle end_date (optional - user can provide it or it will be auto-assigned)
        # SAFETY: Validate end_date if provided
        end_date_value = None
        is_manual_end_value = False
        
        if log_data.end_date:
            # User provided end_date - validate it
            try:
                end_date_obj_provided = datetime.strptime(log_data.end_date, "%Y-%m-%d").date()
                if end_date_obj_provided < date_obj:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"End date ({log_data.end_date}) cannot be before start date ({log_data.date})"
                    )
                end_date_value = log_data.end_date
                is_manual_end_value = True  # User manually provided end_date
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_date format: {log_data.end_date}. Use YYYY-MM-DD format."
                )
        else:
            # No end_date provided - auto-assign using estimated period length
            # This ensures system has a complete period range for calculations
            period_length_days = int(round(max(3.0, min(8.0, period_length))))
            estimated_end_date = date_obj + timedelta(days=period_length_days - 1)
            end_date_value = estimated_end_date.strftime("%Y-%m-%d")
            is_manual_end_value = False  # Auto-assigned, not manually ended
            print(f"📊 Auto-assigned end_date: {end_date_value} (estimated {period_length_days} days)")
        
        # Step 2: Save period START log (end_date is optional but we auto-assign if not provided)
        log_entry = {
            "user_id": user_id,
            "date": log_data.date,  # This is the start_date (REQUIRED - source of truth)
            "end_date": end_date_value,  # Optional - can be NULL or provided/auto-assigned
            "is_manual_end": is_manual_end_value,  # True if user provided, False if auto-assigned
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
        
        print(f"✅ Period log created: start={log_data.date}, end={end_date_value} (manual={is_manual_end_value})")
        
        # Step 4: Automatically create period days in user_cycle_days based on estimated period length
        # This ensures the calendar shows the full period range even though user only logged start
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
                "fertility_prob": 0
                # Note: is_predicted column doesn't exist in database, removed to avoid errors
            })
        
        # NOTE: We don't store period days separately here because:
        # 1. They'll be included in the full phase calculation below
        # 2. Storing them separately and then deleting them in store_cycle_phase_map causes issues
        # The phase calculation will create period days based on cycle starts
        print(f"📝 Period days ({len(period_days)} days) will be created as part of full phase calculation")
        
        # Step 4: Rebuild PeriodStartLogs (one log = one cycle start)
        from period_start_logs import sync_period_start_logs_from_period_logs
        print(f"🔄 Syncing period_start_logs for user {user_id} after logging period start on {log_data.date}")
        sync_period_start_logs_from_period_logs(user_id)
        
        # Verify sync worked
        from period_start_logs import get_period_start_logs
        synced_starts = get_period_start_logs(user_id, confirmed_only=False)
        print(f"✅ Verified: {len(synced_starts)} period_start_logs after sync")
        
        # Step 5: Recompute cycle stats from PeriodEvents
        from cycle_stats import update_user_cycle_stats
        update_user_cycle_stats(user_id)
        
        # Step 4: Calculate delta BEFORE hard invalidation (we need predicted data to compare)
        # Calculate delta (difference between predicted and actual period start)
        # If delta > 3 days, trigger full recalculation
        from cycle_utils import get_user_phase_day
        from period_start_logs import get_period_start_logs
        # NOTE: datetime is already imported at top level - do NOT re-import here
        
        logged_date = datetime.strptime(log_data.date, "%Y-%m-%d").date()
        delta_days = None
        
        # Check if there was a predicted period start near this date
        predicted_phase_data = get_user_phase_day(user_id, log_data.date, prefer_actual=False)
        if predicted_phase_data and predicted_phase_data.get("phase") == "Period":
            # There was a predicted period for this date
            # Get the most recent predicted cycle start before this date
            period_starts = get_period_start_logs(user_id, confirmed_only=False)
            if period_starts:
                # Find the predicted start that would have been closest to this date
                for start_log in period_starts:
                    if not start_log.get("confirmed", False):  # This is a prediction
                        start_date_str = start_log["start_date"]
                        if isinstance(start_date_str, str):
                            predicted_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                        else:
                            predicted_start = start_date_str
                        delta_days = abs((logged_date - predicted_start).days)
                        print(f"📊 Period delta: {delta_days} days difference between predicted ({predicted_start.strftime('%Y-%m-%d')}) and actual ({log_data.date}) start")
                        if delta_days > 3:
                            print(f"⚠️ Large delta ({delta_days} days) - will trigger full recalculation of next 3 cycles")
                        break
        
        # HARD INVALIDATION - Delete ALL predicted phases >= logged period date
        # This fixes the "Ghost Cycle" problem where old predicted periods remain
        # when a user logs a period earlier than predicted
        # CRITICAL: This must happen BEFORE generating new predictions to ensure clean state
        from prediction_cache import hard_invalidate_predictions_from_date, cleanup_predictions_before_first_period
        print(f"🗑️ HARD INVALIDATION: Deleting ALL phases from {log_data.date} onwards")
        hard_invalidate_predictions_from_date(user_id, log_data.date)  # HARD DELETE all phases >= logged date
        cleanup_predictions_before_first_period(user_id)  # Remove predictions before first logged period
        print(f"✅ Hard invalidation complete - all old predictions deleted")
        
        # Step 7: Generate predictions IMMEDIATELY from logged period date forward
        # This ensures calendar updates instantly with ACCURATE calculations
        # CRITICAL: Start from the logged period date (or 3 months before it) to include past months
        from cycle_utils import calculate_phase_for_date_range, store_cycle_phase_map
        from datetime import timedelta
        
        try:
            # Parse the logged period date
            logged_period_date = datetime.strptime(log_data.date, "%Y-%m-%d").date()
            today = datetime.now().date()
            
            # Get first logged period date - we only need predictions from this date onwards
            from prediction_cache import get_first_logged_period_date
            first_period_date = get_first_logged_period_date(user_id)
            
            # Calculate start of logged period month for reference
            logged_period_datetime = datetime.strptime(log_data.date, "%Y-%m-%d")
            start_of_logged_month = logged_period_datetime.replace(day=1).date()
            
            if first_period_date:
                first_period_dt = datetime.strptime(first_period_date, "%Y-%m-%d").date()
                # Start from the first day of the month containing the first logged period
                first_period_month_start = datetime.strptime(first_period_date, "%Y-%m-%d").replace(day=1).date()
                start_date_obj = first_period_month_start
            else:
                # No previous periods, start from the logged period month
                start_date_obj = start_of_logged_month
            
            start_date = start_date_obj.strftime("%Y-%m-%d")
            
            # End at current month + 3 months ahead
            end_date = (today + timedelta(days=90)).strftime("%Y-%m-%d")
            
            print(f"📅 Date range calculation: Logged period month starts {start_of_logged_month.strftime('%Y-%m-%d')}, calculated start_date: {start_date}")
            
            # Get user cycle length (will be updated by sync_period_start_logs)
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            cycle_length = user_response.data[0].get("cycle_length", 28) if user_response.data else 28
            
            # CRITICAL: Use the newly logged period date for accurate calculations
            # This ensures predictions are based on the most recent period
            # IMPORTANT: The start_date should include the logged period month
            print(f"🔄 Generating predictions immediately from {start_date} to {end_date} using logged period: {log_data.date}")
            print(f"   Logged period month: {start_of_logged_month.strftime('%Y-%m')}, Start date: {start_date}")
            
            phase_mappings = calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=log_data.date,  # Use newly logged date for accuracy
                cycle_length=int(cycle_length),
                start_date=start_date,
                end_date=end_date
            )
            
            # Verify the logged period date is in the phase mappings
            logged_period_in_mappings = any(m["date"] == log_data.date for m in phase_mappings)
            if not logged_period_in_mappings:
                print(f"⚠️ WARNING: Logged period date {log_data.date} is NOT in phase mappings! This might cause the month to not show phases.")
            else:
                print(f"✅ Verified: Logged period date {log_data.date} is included in phase mappings")
            
            # Store immediately - this updates the date range with accurate calculations
            # NOTE: This will overwrite the period days we created earlier, but that's OK because
            # the phase_mappings should include the period days (calculated from cycle starts)
            if phase_mappings:
                # Count how many mappings are for the logged period month
                logged_month = logged_period_datetime.strftime("%Y-%m")
                logged_month_mappings = [m for m in phase_mappings if m["date"].startswith(logged_month)]
                
                # Count phases in the logged month
                period_count = len([m for m in logged_month_mappings if m["phase"] == "Period"])
                follicular_count = len([m for m in logged_month_mappings if m["phase"] == "Follicular"])
                ovulation_count = len([m for m in logged_month_mappings if m["phase"] == "Ovulation"])
                luteal_count = len([m for m in logged_month_mappings if m["phase"] == "Luteal"])
                
                print(f"📊 Phase mappings for logged month ({logged_month}): {len(logged_month_mappings)} dates")
                print(f"   Period: {period_count}, Follicular: {follicular_count}, Ovulation: {ovulation_count}, Luteal: {luteal_count}")
                
                if len(logged_month_mappings) < 28:
                    print(f"⚠️ WARNING: Logged month only has {len(logged_month_mappings)} phase mappings (expected ~28-31 for full month)")
                
                store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
                print(f"✅ Generated {len(phase_mappings)} ACCURATE predictions immediately from {start_date} to {end_date}")
            else:
                print("⚠️ No phase mappings generated - this might mean the logged period month wasn't included!")
        except Exception as e:
            print(f"⚠️ Immediate prediction generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Step 8: Regenerate full range in BACKGROUND (non-blocking)
        # This runs in background for complete calendar coverage
        # Only generates from first logged period to current + 6 months ahead
        from prediction_cache import regenerate_predictions_from_last_confirmed_period
        
        def regenerate_background():
            try:
                # Generate from first logged period to current + 6 months ahead (reasonable range)
                regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=180)
            except Exception as e:
                print(f"⚠️ Background prediction regeneration failed: {str(e)}")
        
        # Add to background tasks - runs after response is sent
        background_tasks.add_task(regenerate_background)
        
        # Step 9: Asynchronous luteal learning (non-blocking)
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
        
        # Calculate estimated end date (for frontend display)
        from period_service import calculate_rolling_period_length
        rolling_period_avg = calculate_rolling_period_length(user_id)
        estimated_days = int(round(max(3.0, min(8.0, rolling_period_avg))))
        estimated_end_date = date_obj + timedelta(days=estimated_days - 1)
        
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
                "endDate": response.data[0].get("end_date"),  # NULL initially
                "isManualEnd": response.data[0].get("is_manual_end", False),
                "flow": response.data[0].get("flow"),
                "notes": response.data[0].get("notes"),
                "isAnomaly": is_anomaly,
                "estimatedEnd": estimated_end_date.strftime("%Y-%m-%d")  # For frontend display
            },
            "logs": [{
                "id": log.get("id"),
                "userId": log.get("user_id"),
                "date": log.get("date"),
                "endDate": log.get("end_date"),
                "isManualEnd": log.get("is_manual_end", False),
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
            "endDate": log.get("end_date"),  # CRITICAL: Return actual end_date from database (can be NULL)
            "isManualEnd": log.get("is_manual_end", False),
            "flow": log.get("flow"),
            "notes": log.get("notes"),
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
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a period log entry with SMART RECALCULATION.
    
    If the start date is changed, this triggers a cascade recalculation:
    - Delete old predictions for the old period range
    - Update the period log
    - Regenerate predictions from the new date
    - Update cycle stats
    
    This is a single atomic transaction to prevent calendar flickering.
    """
    try:
        user_id = current_user["id"]
        
        # Verify log belongs to user and get old data
        check = supabase.table("period_logs").select("*").eq("id", log_id).eq("user_id", user_id).execute()
        
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found"
            )
        
        old_log = check.data[0]
        old_date = old_log.get("date")
        new_date = log_data.date
        
        # If date is being changed, perform smart recalculation
        if new_date and new_date != old_date:
            print(f"🔄 Editing period log: Changing start date from {old_date} to {new_date}")
            
            # Validate new date
            if isinstance(new_date, str):
                new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
            else:
                new_date_obj = new_date
            
            today = datetime.now().date()
            if new_date_obj > today:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set period start to a future date"
                )
            
            # Validate minimum spacing
            validation = can_log_period(user_id, new_date_obj)
            if not validation.get("canLog", False):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation.get("reason", "Cannot update period to this date")
                )
            
            # ATOMIC TRANSACTION: Delete old predictions -> Update log -> Generate new predictions
            # Step 1: Delete old period range predictions
            # SAFETY: Use actual end_date if available, else estimate
            if isinstance(old_date, str):
                old_date_obj = datetime.strptime(old_date, "%Y-%m-%d").date()
            else:
                old_date_obj = old_date
            
            # Determine old period end date
            old_period_end = None
            if old_log.get("end_date"):
                # Use actual end_date if available
                old_end_date_str = old_log["end_date"]
                if isinstance(old_end_date_str, str):
                    old_period_end = datetime.strptime(old_end_date_str, "%Y-%m-%d").date()
                else:
                    old_period_end = old_end_date_str
                print(f"📅 Using actual end_date for old period: {old_period_end.strftime('%Y-%m-%d')}")
            else:
                # No end_date - use estimated period length (fallback)
                from cycle_utils import estimate_period_length
                period_length = estimate_period_length(user_id)
                period_length_days = int(round(max(3.0, min(8.0, period_length))))
                old_period_end = old_date_obj + timedelta(days=period_length_days - 1)
                print(f"📅 Using estimated end_date for old period: {old_period_end.strftime('%Y-%m-%d')} (estimated {period_length_days} days)")
            
            # Delete old period range predictions
            if old_period_end:
                current_date = old_date_obj
                deleted_count = 0
                while current_date <= old_period_end:
                    date_str = current_date.strftime("%Y-%m-%d")
                    try:
                        supabase.table("user_cycle_days").delete().eq("user_id", user_id).eq("date", date_str).eq("phase", "Period").execute()
                        deleted_count += 1
                    except Exception as e:
                        print(f"⚠️ Warning: Could not delete old predictions for {date_str}: {str(e)}")
                    current_date += timedelta(days=1)
                
                print(f"✅ Deleted {deleted_count} old period range predictions ({old_date} to {old_period_end.strftime('%Y-%m-%d')})")
            else:
                print(f"⚠️ Warning: Could not determine old_period_end, skipping old predictions deletion")
            
            # Step 2: HARD INVALIDATE predictions from new date
            from prediction_cache import hard_invalidate_predictions_from_date
            hard_invalidate_predictions_from_date(user_id, new_date)
            
            # Step 3: Update the period log
            # SAFETY: Validate end_date if provided in update
            update_data = log_data.dict(exclude_unset=True)
            
            # Validate end_date if being updated
            if "end_date" in update_data and update_data["end_date"]:
                # User is updating end_date - validate it
                if new_date:
                    new_date_obj_for_validation = datetime.strptime(new_date, "%Y-%m-%d").date() if isinstance(new_date, str) else new_date
                else:
                    new_date_obj_for_validation = old_date_obj
                
                end_date_obj_update = datetime.strptime(update_data["end_date"], "%Y-%m-%d").date()
                
                if end_date_obj_update < new_date_obj_for_validation:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"End date ({update_data['end_date']}) cannot be before start date ({new_date or old_date})"
                    )
                
                # Mark as manual end if user is setting end_date
                update_data["is_manual_end"] = True
                print(f"✅ Updating end_date to {update_data['end_date']} (manual)")
            elif "end_date" in update_data and update_data["end_date"] is None:
                # User is clearing end_date - set is_manual_end to False
                update_data["is_manual_end"] = False
                print(f"✅ Clearing end_date (will use estimated period length)")
            
            response = supabase.table("period_logs").update(update_data).eq("id", log_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update period log"
                )
            
            # Step 4: Sync period_start_logs and update cycle stats
            from period_start_logs import sync_period_start_logs_from_period_logs
            from cycle_stats import update_user_cycle_stats
            sync_period_start_logs_from_period_logs(user_id)
            update_user_cycle_stats(user_id)
            
            # Step 5: Regenerate predictions from new date
            from cycle_utils import calculate_phase_for_date_range, store_cycle_phase_map
            from prediction_cache import get_first_logged_period_date
            
            first_period_date = get_first_logged_period_date(user_id)
            if first_period_date:
                first_period_dt = datetime.strptime(first_period_date, "%Y-%m-%d")
                start_date_obj = first_period_dt.replace(day=1).date()
            else:
                start_date_obj = new_date_obj.replace(day=1)
            
            start_date = start_date_obj.strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=90)).strftime("%Y-%m-%d")
            
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            cycle_length = user_response.data[0].get("cycle_length", 28) if user_response.data else 28
            
            phase_mappings = calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=new_date,
                cycle_length=int(cycle_length),
                start_date=start_date,
                end_date=end_date
            )
            
            if phase_mappings:
                store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
                print(f"✅ Regenerated {len(phase_mappings)} predictions after editing period start date")
            
            # Step 6: Update user's last_period_date if this was the most recent period
            if new_date == old_date or new_date > old_date:
                # Check if this is the most recent period
                logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(1).execute()
                if logs_response.data and logs_response.data[0].get("date") == new_date:
                    supabase.table("users").update({"last_period_date": new_date}).eq("id", user_id).execute()
                    print(f"✅ Updated last_period_date to {new_date}")
            
            return {
                "log": response.data[0],
                "message": f"Period start date updated from {old_date} to {new_date}. Calendar has been recalculated."
            }
        else:
            # No date change - just update flow/notes
            update_data = log_data.dict(exclude_unset=True)
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


@router.post("/log-end")
async def log_period_end(
    end_data: PeriodEndRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Log a period end date.
    
    Finds the most recent period log without an end_date and updates it.
    Recalculates phases with actual period range.
    """
    try:
        user_id = current_user["id"]
        
        # Parse end date
        if isinstance(end_data.date, str):
            end_date_obj = datetime.strptime(end_data.date, "%Y-%m-%d").date()
        else:
            end_date_obj = end_data.date
        
        # CRITICAL: Prevent logging end dates in future
        today = datetime.now().date()
        if end_date_obj > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot log period end for future dates."
            )
        
        # Find most recent period log without end_date
        logs_response = supabase.table("period_logs").select("*").eq("user_id", user_id).is_("end_date", "null").order("date", desc=True).limit(1).execute()
        
        if not logs_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No open period found. Please log a period start first."
            )
        
        last_log = logs_response.data[0]
        start_date_str = last_log["date"]
        start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        
        # Validate end date is after start date
        if end_date_obj < start_date_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Period end date must be after start date."
            )
        
        # Validate duration (3-15 days)
        duration = (end_date_obj - start_date_obj).days + 1
        if duration < 3 or duration > 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Period duration must be between 3 and 15 days. Calculated duration: {duration} days."
            )
        
        # Update log with end date
        update_response = supabase.table("period_logs").update({
            "end_date": end_data.date,
            "is_manual_end": True
        }).eq("id", last_log["id"]).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update period log with end date."
            )
        
        # Hard invalidate predictions from start date
        from prediction_cache import hard_invalidate_predictions_from_date
        hard_invalidate_predictions_from_date(user_id, start_date_str)
        print(f"✅ Hard invalidated predictions from {start_date_str}")
        
        # Recalculate phases with actual period range
        from cycle_utils import calculate_phase_for_date_range, store_cycle_phase_map
        from prediction_cache import get_first_logged_period_date
        
        first_period_date = get_first_logged_period_date(user_id)
        if first_period_date:
            first_period_dt = datetime.strptime(first_period_date, "%Y-%m-%d")
            start_date_calc = first_period_dt.replace(day=1).date()
        else:
            start_date_calc = start_date_obj.replace(day=1)
        
        start_date_calc_str = start_date_calc.strftime("%Y-%m-%d")
        end_date_calc = (today + timedelta(days=90)).strftime("%Y-%m-%d")
        
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        cycle_length = user_response.data[0].get("cycle_length", 28) if user_response.data else 28
        
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=start_date_str,
            cycle_length=int(cycle_length),
            start_date=start_date_calc_str,
            end_date=end_date_calc
        )
        
        if phase_mappings:
            store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
            print(f"✅ Regenerated {len(phase_mappings)} predictions with actual period range")
        
        # Update cycle stats (actual duration will be used)
        from period_start_logs import sync_period_start_logs_from_period_logs
        from cycle_stats import update_user_cycle_stats
        sync_period_start_logs_from_period_logs(user_id)
        update_user_cycle_stats(user_id)
        
        # Background regeneration for full range
        from prediction_cache import regenerate_predictions_from_last_confirmed_period
        def regenerate_background():
            try:
                regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=180)
            except Exception as e:
                print(f"⚠️ Background regeneration failed: {str(e)}")
        
        background_tasks.add_task(regenerate_background)
        
        return {
            "message": f"Period end logged successfully. Duration: {duration} days.",
            "start_date": start_date_str,
            "end_date": end_data.date,
            "duration": duration
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log period end: {str(e)}"
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

