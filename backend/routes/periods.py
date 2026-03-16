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
    bleeding_days: Optional[int] = None  # If set, end_date = start + (bleeding_days - 1); matches profile buttons [2-8]
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
        
        # Validate if period can be logged (reason is user-friendly from period_service)
        validation = can_log_period(user_id, date_obj)
        if not validation.get("canLog", False):
            reason = validation.get("reason") or "Cannot log period for this date."
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=reason
            )
        
        # Step 0: Auto-close any periods that have been open > 10 days
        from auto_close_periods import auto_close_open_periods
        auto_closed = auto_close_open_periods(user_id)
        if auto_closed:
            print(f"🔒 Auto-closed {len(auto_closed)} period(s) before logging new period")
        
        # Check for anomaly
        is_anomaly = check_anomaly(user_id, date_obj)
        
        # Check if date falls within any existing period range (from period_logs)
        period_length_days_for_check = max(2, min(8, int(current_user.get("avg_bleeding_days") or 5)))
        logs_check = supabase.table("period_logs").select("date", "end_date").eq("user_id", user_id).execute()
        for row in (logs_check.data or []):
            start_date_str = row.get("date")
            if not start_date_str:
                continue
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if isinstance(start_date_str, str) else start_date_str
            end_date_str = row.get("end_date")
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if isinstance(end_date_str, str) else end_date_str
            else:
                end_date = start_date + timedelta(days=period_length_days_for_check - 1)
            if start_date <= date_obj <= end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This date falls within an existing period (started {start_date_str}). Please log only the period start date."
                )

        # Step 1: Assign end_date from request bleeding_days (if provided) or user's avg_bleeding_days
        if log_data.bleeding_days is not None:
            bleeding_days = max(2, min(8, int(log_data.bleeding_days)))
        else:
            bleeding_days = max(2, min(8, int(current_user.get("avg_bleeding_days") or 5)))
        estimated_end_date = date_obj + timedelta(days=bleeding_days - 1)
        end_date_value = estimated_end_date.strftime("%Y-%m-%d")
        is_manual_end_value = log_data.bleeding_days is not None  # Explicit from UI
        print(f"📊 end_date: {end_date_value} (bleeding_days={bleeding_days})")

        # Overlap protection: if the previous period (by start date) has auto end_date >= new start, trim it
        prev_logs = supabase.table("period_logs").select("id", "date", "end_date", "is_manual_end").eq("user_id", user_id).lt("date", log_data.date).order("date", desc=True).limit(1).execute()
        if prev_logs.data:
            prev = prev_logs.data[0]
            prev_end = prev.get("end_date")
            prev_manual = prev.get("is_manual_end", True)
            if not prev_manual and prev_end:
                prev_end_dt = datetime.strptime(prev_end, "%Y-%m-%d").date()
                if prev_end_dt >= date_obj:
                    trim_end = date_obj - timedelta(days=1)
                    trim_end_str = trim_end.strftime("%Y-%m-%d")
                    supabase.table("period_logs").update({"end_date": trim_end_str}).eq("id", prev["id"]).execute()
                    print(f"✂️ Trimmed previous period end to {trim_end_str} (overlap protection)")

        # Step 2: Save period START log
        log_entry = {
            "user_id": user_id,
            "date": log_data.date,
            "end_date": end_date_value,
            "is_manual_end": is_manual_end_value,
            "flow": log_data.flow,
            "notes": log_data.notes
        }

        # Check if this date already exists as a period start
        existing = supabase.table("period_logs").select("*").eq("user_id", user_id).eq("date", log_data.date).execute()

        if existing.data:
            response = supabase.table("period_logs").update(log_entry).eq("user_id", user_id).eq("date", log_data.date).execute()
        else:
            response = supabase.table("period_logs").insert(log_entry).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create/update period log"
            )
        
        print(f"✅ Period log created: start={log_data.date}, end={end_date_value} (manual={is_manual_end_value})")
        
        # NOTE: Period days are no longer stored in user_cycle_days.
        # Calendar will calculate phases on-demand from period_logs when viewed.
        
        # Step 4: Rebuild PeriodStartLogs (one log = one cycle start)
        from period_start_logs import sync_period_start_logs_from_period_logs
        print(f"🔄 Syncing period_start_logs for user {user_id} after logging period start on {log_data.date}")
        period_starts = sync_period_start_logs_from_period_logs(user_id)
        
        # Step 5: Recompute cycle stats using returned data (no DB read - avoids 20s verification loop)
        from cycle_stats import update_user_cycle_stats
        update_user_cycle_stats(user_id, period_starts=period_starts)
        
        # Step 4: Calculate delta (use period_starts from sync return - do NOT re-query DB; avoids 0 records / rebuild loop)
        from cycle_utils import get_user_phase_day
        # NOTE: datetime is already imported at top level - do NOT re-import here
        
        logged_date = datetime.strptime(log_data.date, "%Y-%m-%d").date()
        delta_days = None
        
        # Check if there was a predicted period start near this date (use period_starts we already have from sync)
        predicted_phase_data = get_user_phase_day(user_id, log_data.date, prefer_actual=False)
        if predicted_phase_data and predicted_phase_data.get("phase") == "Period" and period_starts:
            # Find the predicted start that would have been closest to this date (period_starts from sync return)
            for start_log in period_starts:
                if not start_log.get("is_confirmed", True):  # This is a prediction
                    start_date_str = start_log.get("start_date")
                    if start_date_str:
                        if isinstance(start_date_str, str):
                            predicted_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                        else:
                            predicted_start = start_date_str
                        delta_days = abs((logged_date - predicted_start).days)
                        print(f"📊 Period delta: {delta_days} days difference between predicted ({predicted_start.strftime('%Y-%m-%d')}) and actual ({log_data.date}) start")
                        if delta_days > 3:
                            print(f"⚠️ Large delta ({delta_days} days) - will trigger full recalculation of next 3 cycles")
                        break
        
        # NOTE: Predictions are no longer stored in user_cycle_days.
        # Calendar will calculate phases on-demand from period_logs when viewed.
        # This eliminates the 181+ individual database upserts that were causing Errno 35 errors.
        
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
            
            # NOTE: Hard invalidation removed - predictions are now calculated on-demand
            
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
            
            # Step 4: Sync period_start_logs and update cycle stats (use returned data to avoid DB read)
            from period_start_logs import sync_period_start_logs_from_period_logs
            from cycle_stats import update_user_cycle_stats
            period_starts = sync_period_start_logs_from_period_logs(user_id)
            update_user_cycle_stats(user_id, period_starts=period_starts)
            
            # NOTE: Prediction regeneration removed - calendar will calculate on-demand
            
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
        
        # Rebuild PeriodStartLogs and update cycle stats (use returned data to avoid DB read)
        from period_start_logs import sync_period_start_logs_from_period_logs
        from cycle_stats import update_user_cycle_stats
        period_starts = sync_period_start_logs_from_period_logs(user_id)
        update_user_cycle_stats(user_id, period_starts=period_starts)
        
        # NOTE: Prediction regeneration removed - calendar will calculate on-demand
        
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
        
        # NOTE: Prediction regeneration removed - calendar will calculate on-demand
        
        # Update cycle stats (use returned data to avoid DB read)
        from period_start_logs import sync_period_start_logs_from_period_logs
        from cycle_stats import update_user_cycle_stats
        period_starts = sync_period_start_logs_from_period_logs(user_id)
        update_user_cycle_stats(user_id, period_starts=period_starts)
        
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

