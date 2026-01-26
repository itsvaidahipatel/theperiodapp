from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from database import supabase
from routes.auth import get_current_user
from cycle_utils import (
    generate_cycle_phase_map, 
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
    current_user: dict = Depends(get_current_user)
):
    """Log a period entry."""
    try:
        user_id = current_user["id"]
        
        # Note: period_logs table only has: id, created_at, user_id, date, flow, notes
        log_entry = {
            "user_id": user_id,
            "date": log_data.date,
            "flow": log_data.flow,
            "notes": log_data.notes
        }
        
        # Check if user already has a log for this date
        # Note: If schema has UNIQUE on (user_id, date), this will work
        # If schema only has UNIQUE on user_id, we need to delete old and insert new
        existing = supabase.table("period_logs").select("*").eq("user_id", user_id).eq("date", log_data.date).execute()
        
        if existing.data:
            # Update existing log
            response = supabase.table("period_logs").update(log_entry).eq("user_id", user_id).eq("date", log_data.date).execute()
        else:
            # Insert new log
            # If user_id is UNIQUE (only one log per user), delete old first
            try:
                # Try to delete any existing log for this user (if UNIQUE constraint exists)
                supabase.table("period_logs").delete().eq("user_id", user_id).execute()
            except:
                pass  # If deletion fails, continue with insert
            response = supabase.table("period_logs").insert(log_entry).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create/update period log"
            )
        
        # Detect early/late period and calculate new cycle length
        logged_date = log_data.date
        previous_period_date = None
        
        # Get previous period date for cycle length calculation
        user_data_before = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        if user_data_before.data:
            previous_period_date = user_data_before.data[0].get("last_period_date")
            old_cycle_length = user_data_before.data[0].get("cycle_length", 28)
        
        # Update user's last_period_date when period is logged
        updated_user = None
        user_update = supabase.table("users").update({
            "last_period_date": log_data.date
        }).eq("id", user_id).execute()
        if user_update.data:
            updated_user = user_update.data[0]
        
        # Calculate new cycle length if we have previous period date
        if previous_period_date and previous_period_date != logged_date:
            try:
                prev_date = datetime.strptime(previous_period_date, "%Y-%m-%d")
                curr_date = datetime.strptime(logged_date, "%Y-%m-%d")
                new_cycle_length = (curr_date - prev_date).days
                
                if new_cycle_length > 0:
                    # Update using Bayesian smoothing
                    update_cycle_length_bayesian(user_id, new_cycle_length)
                    print(f"Updated cycle_length based on logged period: {old_cycle_length} -> {new_cycle_length} (Bayesian)")
                    
                    # Calculate and update luteal length
                    try:
                        # Get predicted ovulation for the previous cycle
                        luteal_mean, luteal_sd = estimate_luteal(user_id)
                        # cycle_start_sd will be estimated adaptively based on cycle variance and logging consistency
                        predicted_ov_date_str, ovulation_sd, _ = predict_ovulation(
                            previous_period_date,
                            float(old_cycle_length),
                            luteal_mean,
                            luteal_sd,
                            cycle_start_sd=None,  # Will be estimated adaptively
                            user_id=user_id
                        )
                        predicted_ov_date = datetime.strptime(predicted_ov_date_str, "%Y-%m-%d")
                        
                        # Observed luteal length = period_start - predicted_ovulation
                        observed_luteal = (curr_date - predicted_ov_date).days
                        
                        # Confidence gating: Only update if ovulation prediction was high confidence
                        # This prevents training on incorrect ovulation predictions from:
                        # - Stress cycles
                        # - PCOS-like patterns
                        # - Anovulatory cycles
                        # - Early app usage (limited data)
                        # - Missed ovulation
                        confidence_threshold = 1.5  # High confidence threshold (days)
                        
                        if 10 <= observed_luteal <= 18:  # Valid range
                            if ovulation_sd <= confidence_threshold:
                                # High confidence ovulation prediction - safe to learn from
                                # Check if user has LH/BBT markers (for now, assume False)
                                has_markers = False  # TODO: Get from user data if available
                                update_luteal_estimate(user_id, float(observed_luteal), has_markers)
                                print(f"✅ Updated luteal estimate: observed={observed_luteal} days (ovulation_sd={ovulation_sd:.2f} <= {confidence_threshold})")
                            else:
                                # Low confidence ovulation prediction - skip update to avoid bad training
                                print(f"⚠️ Skipped luteal update: low confidence ovulation prediction (ovulation_sd={ovulation_sd:.2f} > {confidence_threshold})")
                                print(f"   Observed luteal={observed_luteal} days, but ovulation prediction uncertainty too high")
                                print(f"   This prevents training on incorrect predictions from stress cycles, PCOS patterns, or anovulatory cycles")
                        else:
                            # Observed luteal outside valid range (10-18 days)
                            print(f"⚠️ Skipped luteal update: observed_luteal={observed_luteal} days outside valid range (10-18 days)")
                    except Exception as luteal_error:
                        print(f"Warning: Failed to update luteal estimate: {str(luteal_error)}")
            except Exception as e:
                print(f"Warning: Failed to update cycle_length from period log: {str(e)}")
        
        # Detect early/late period
        early_late_info = detect_early_late_period(user_id, logged_date)
        if early_late_info and early_late_info.get("should_adjust"):
            print(f"⚠️ Early/Late period detected: {early_late_info['difference_days']} days difference")
            print(f"   Predicted: {early_late_info['predicted_date']}, Actual: {logged_date}")
        
        # Try to auto-generate cycle predictions if we have enough period data
        # Since period_logs might have UNIQUE user_id, we'll use user's last_period_date
        # and calculate from cycle_length to build past cycle data
        try:
            # Get user data to check cycle history (after update)
            user_data = supabase.table("users").select("*").eq("id", user_id).execute()
            if user_data.data:
                user_info = user_data.data[0]
                last_period = user_info.get("last_period_date") or log_data.date  # Use logged date if last_period not set
                cycle_length = user_info.get("cycle_length", 28)
                
                # Get all period logs (might be limited by UNIQUE constraint)
                all_logs = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date").execute()
                
                # Build past cycle data from logs and user's cycle_length
                past_cycle_data = []
                
                if all_logs.data and len(all_logs.data) >= 1:
                    # If we have multiple logs, use them
                    period_dates = [log["date"] for log in all_logs.data]
                    period_dates.sort()
                    
                    if len(period_dates) >= 3:
                        # Use actual period dates
                        for i in range(len(period_dates)):
                            cycle_start = period_dates[i]
                            period_length = 5  # Default period length
                            
                            past_cycle_data.append({
                                "cycle_start_date": cycle_start,
                                "period_length": period_length
                            })
                    elif len(period_dates) >= 1 and last_period:
                        # If we have at least one period date, generate synthetic data
                        # based on cycle_length to get to 3 cycles
                        from datetime import datetime, timedelta
                        try:
                            last_period_dt = datetime.strptime(last_period, "%Y-%m-%d")
                        except:
                            # If last_period is not a valid date string, use the logged date
                            last_period_dt = datetime.strptime(log_data.date, "%Y-%m-%d")
                        
                        # Generate 5 cycles going backwards to ensure we have enough data
                        for i in range(5):
                            cycle_date = last_period_dt - timedelta(days=cycle_length * i)
                            past_cycle_data.append({
                                "cycle_start_date": cycle_date.strftime("%Y-%m-%d"),
                                "period_length": 5
                            })
                
                # Generate predictions if we have enough data (need at least 3 cycles)
                if len(past_cycle_data) >= 3:
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    try:
                        print(f"Generating cycle predictions for user {user_id} with {len(past_cycle_data)} cycles")
                        
                        # Use partial update if early/late period detected (preserve past data)
                        update_future_only = early_late_info and early_late_info.get("should_adjust", False)
                        
                        generate_cycle_phase_map(
                            user_id=user_id,
                            past_cycle_data=past_cycle_data[:6],  # Use up to 6 cycles
                            current_date=current_date,
                            update_future_only=update_future_only
                        )
                        print(f"Cycle predictions generated successfully for user {user_id} (update_future_only={update_future_only})")
                    except Exception as pred_error:
                        # Don't fail the log if prediction fails, but log the error
                        import traceback
                        print(f"Auto-prediction failed for user {user_id}: {str(pred_error)}")
                        print(traceback.format_exc())
                else:
                    print(f"Not enough cycle data for user {user_id}: {len(past_cycle_data)} cycles (need 3+)")
        except Exception as auto_pred_error:
            # Don't fail the log if auto-prediction fails, but log the error
            import traceback
            print(f"Auto-prediction error for user {user_id}: {str(auto_pred_error)}")
            print(traceback.format_exc())
        
        return {
            "message": "Period logged successfully",
            "log": response.data[0],
            "user": updated_user
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
    """Get all period logs for the current user."""
    try:
        user_id = current_user["id"]
        
        response = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date", desc=True).execute()
        
        return response.data or []
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch period logs: {str(e)}"
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
    """Delete a period log entry."""
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
        
        return {"message": "Period log deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete period log: {str(e)}"
        )

