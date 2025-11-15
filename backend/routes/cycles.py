from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

from database import supabase
from routes.auth import get_current_user
from cycle_utils import (
    generate_cycle_phase_map,
    get_user_phase_day,
    process_cycle_data,
    get_predicted_cycle_starts,
    get_average_period_length,
    get_average_cycle_length
)

router = APIRouter()

class CyclePredictionRequest(BaseModel):
    past_cycle_data: List[Dict]
    current_date: Optional[str] = None

@router.post("/predict")
async def predict_cycles(
    request: CyclePredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate cycle predictions and phase mappings for user."""
    try:
        user_id = current_user["id"]
        current_date = request.current_date or datetime.now().strftime("%Y-%m-%d")
        
        # Generate cycle phase map
        phase_mappings = generate_cycle_phase_map(
            user_id=user_id,
            past_cycle_data=request.past_cycle_data,
            current_date=current_date
        )
        
        # Get current phase-day
        current_phase = get_user_phase_day(user_id, current_date)
        
        return {
            "message": "Cycle predictions generated successfully",
            "phase_mappings": phase_mappings,
            "current_phase": current_phase
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cycle prediction failed: {str(e)}"
        )

@router.get("/current-phase")
async def get_current_phase(
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current phase-day information for user."""
    try:
        user_id = current_user["id"]
        check_date = date or datetime.now().strftime("%Y-%m-%d")
        
        # Try to get from stored cycle predictions first
        phase_info = get_user_phase_day(user_id, check_date)
        
        if phase_info and phase_info.get("phase_day_id"):
            # Check if today is p1 (first day of period) - auto-update last_period_date
            phase_day_id = phase_info.get("phase_day_id", "").lower()
            if phase_day_id == "p1":
                # Auto-update last_period_date to today
                from database import supabase
                supabase.table("users").update({
                    "last_period_date": check_date
                }).eq("id", user_id).execute()
                print(f"Auto-updated last_period_date to {check_date} for user {user_id} (p1 detected)")
            
            return phase_info
        
        # Fallback: Calculate from last_period_date if predictions don't exist
        from cycle_utils import calculate_today_phase_day_id
        today_phase_day_id = calculate_today_phase_day_id(user_id)
        
        if today_phase_day_id:
            # Check if today is p1 - auto-update last_period_date
            if today_phase_day_id.lower() == "p1":
                from database import supabase
                supabase.table("users").update({
                    "last_period_date": check_date
                }).eq("id", user_id).execute()
                print(f"Auto-updated last_period_date to {check_date} for user {user_id} (p1 calculated)")
            
            # Determine phase from phase_day_id
            phase_map = {
                "p": "Period",
                "f": "Follicular", 
                "o": "Ovulation",
                "l": "Luteal"
            }
            phase_prefix = today_phase_day_id[0].lower()
            phase = phase_map.get(phase_prefix, "Period")
            
            return {
                "phase": phase,
                "phase_day_id": today_phase_day_id,
                "date": check_date,
                "calculated": True  # Indicates this was calculated, not from stored predictions
            }
        
        # No data available
        return {
            "phase": None,
            "phase_day_id": None,
            "id": None,
            "message": "No phase data available. Please set your last period date."
        }
    
    except Exception as e:
        # Return a response instead of raising an error
        return {
            "phase": None,
            "phase_day_id": None,
            "id": None,
            "message": f"No phase data available: {str(e)}"
        }

@router.get("/phase-map")
async def get_phase_map(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get phase mappings for a date range."""
    try:
        user_id = current_user["id"]
        
        query = supabase.table("user_cycle_days").select("*").eq("user_id", user_id)
        
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
        
        response = query.order("date").execute()
        
        print(f"Retrieved {len(response.data or [])} phase mappings for user {user_id}")
        return {"phase_map": response.data or []}
    
    except Exception as e:
        print(f"Error getting phase map: {str(e)}")
        # Return empty map instead of raising error
        return {"phase_map": []}

@router.get("/debug/cycle-data")
async def debug_cycle_data(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check cycle data for current user."""
    try:
        user_id = current_user["id"]
        
        # Check period logs
        period_logs = supabase.table("period_logs").select("*").eq("user_id", user_id).execute()
        
        # Check cycle days
        cycle_days = supabase.table("user_cycle_days").select("*").eq("user_id", user_id).execute()
        
        # Check user data
        user_data = supabase.table("users").select("*").eq("id", user_id).execute()
        
        return {
            "user_id": user_id,
            "period_logs_count": len(period_logs.data or []),
            "period_logs": period_logs.data or [],
            "cycle_days_count": len(cycle_days.data or []),
            "cycle_days_sample": (cycle_days.data or [])[:5],  # First 5 entries
            "user_last_period_date": user_data.data[0].get("last_period_date") if user_data.data else None,
            "user_cycle_length": user_data.data[0].get("cycle_length") if user_data.data else None
        }
    except Exception as e:
        return {"error": str(e)}

