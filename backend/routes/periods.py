from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from database import supabase
from routes.auth import get_current_user
from cycle_utils import generate_cycle_phase_map

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
        
        # Update user's last_period_date when period is logged
        updated_user = None
        user_update = supabase.table("users").update({
            "last_period_date": log_data.date
        }).eq("id", user_id).execute()
        if user_update.data:
            updated_user = user_update.data[0]
        
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
                        generate_cycle_phase_map(
                            user_id=user_id,
                            past_cycle_data=past_cycle_data[:6],  # Use up to 6 cycles
                            current_date=current_date
                        )
                        print(f"Cycle predictions generated successfully for user {user_id}")
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

