from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta

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
    """Get phase mappings for a date range. Calculates on the fly if not in database."""
    try:
        user_id = current_user["id"]
        
        # Try to get from database first (RapidAPI predictions)
        query = supabase.table("user_cycle_days").select("*").eq("user_id", user_id)
        
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
        
        try:
            response = query.order("date").execute()
            stored_data = response.data or []
        except Exception as db_error:
            print(f"Database query error (non-fatal, will calculate): {str(db_error)}")
            stored_data = []
        
        print(f"Retrieved {len(stored_data)} stored phase mappings for user {user_id}")
        
        # If we have stored data (from RapidAPI), return it
        if stored_data:
            print("✅ Returning stored RapidAPI phase predictions from database")
            # Convert stored data to the expected format
            formatted_data = []
            for item in stored_data:
                formatted_data.append({
                    "date": item.get("date"),
                    "phase": item.get("phase"),
                    "phase_day_id": item.get("phase_day_id") or item.get("id")  # id is phase_day_id in this table
                })
            return {"phase_map": formatted_data}
        
        # If no stored data, try to generate RapidAPI predictions first
        print("=" * 60)
        print("CALENDAR PHASE MAP REQUEST")
        print(f"User ID: {user_id}")
        print(f"Date range: {start_date} to {end_date}")
        print("No stored RapidAPI predictions found. Attempting to generate...")
        print("=" * 60)
        
        # Quick check: if date range is too large, limit it for performance
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
            days_diff = (end_dt - start_dt).days
            if days_diff > 90:  # More than 3 months - limit to 3 months for performance
                print(f"⚠️ Date range is large ({days_diff} days), limiting to 3 months for performance")
                end_dt = start_dt + timedelta(days=90)
                end_date = end_dt.strftime("%Y-%m-%d")
        except:
            pass  # Continue with original dates if parsing fails
        
        from cycle_utils import generate_cycle_phase_map, calculate_phase_for_date_range
        
        # Get user data
        user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        
        if not user_response.data or not user_response.data[0]:
            print("❌ ERROR: No user data found")
            return {"phase_map": []}
        
        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        cycle_length = user.get("cycle_length", 28)
        
        print(f"✅ User data retrieved:")
        print(f"   - last_period_date: {last_period_date}")
        print(f"   - cycle_length: {cycle_length}")
        
        if not last_period_date:
            print("❌ ERROR: No last_period_date found for user")
            print("💡 User needs to log a period or set last_period_date in profile")
            return {"phase_map": []}
        
        # Convert last_period_date to string if it's a date object
        if hasattr(last_period_date, 'strftime'):
            last_period_date_str = last_period_date.strftime("%Y-%m-%d")
        elif isinstance(last_period_date, str):
            last_period_date_str = last_period_date
        else:
            last_period_date_str = str(last_period_date)
        
        # Quick validation: ensure dates are valid
        try:
            datetime.strptime(last_period_date_str, "%Y-%m-%d")
            if start_date:
                datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                datetime.strptime(end_date, "%Y-%m-%d")
        except Exception as date_error:
            print(f"❌ Invalid date format: {str(date_error)}")
            return {"phase_map": []}
        
        # Try to generate RapidAPI predictions first
        try:
            from datetime import datetime, timedelta
            
            # Build past cycle data for RapidAPI
            # Try to use actual period logs first, then fall back to synthetic cycles
            past_cycle_data = []
            try:
                # First, try to get actual period logs from database
                period_logs_response = supabase.table("period_logs").select("start_date, end_date").eq("user_id", user_id).order("start_date", desc=True).limit(12).execute()
                period_logs = period_logs_response.data or []
                
                if period_logs and len(period_logs) >= 3:
                    # Use actual period logs (RapidAPI prefers real data)
                    print(f"📊 Using {len(period_logs)} actual period logs for RapidAPI")
                    for log in reversed(period_logs):  # Reverse to get chronological order
                        start_date = log.get("start_date")
                        end_date = log.get("end_date")
                        if start_date:
                            # Calculate period length
                            if end_date:
                                try:
                                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                                    period_length = max(1, (end_dt - start_dt).days + 1)
                                except:
                                    period_length = 5
                            else:
                                period_length = 5  # Default if no end_date
                            
                            past_cycle_data.append({
                                "cycle_start_date": start_date,
                                "period_length": period_length
                            })
                else:
                    # Fall back to synthetic cycles (generate more cycles for better accuracy)
                    print(f"📊 Using synthetic cycles (only {len(period_logs)} period logs available)")
                    last_period_dt = datetime.strptime(last_period_date_str, "%Y-%m-%d")
                    cycle_length_int = int(cycle_length) if cycle_length else 28
                    # Generate 12 cycles going backwards (RapidAPI typically needs 6-12 cycles)
                    for i in range(12):
                        cycle_date = last_period_dt - timedelta(days=cycle_length_int * i)
                        past_cycle_data.append({
                            "cycle_start_date": cycle_date.strftime("%Y-%m-%d"),
                            "period_length": 5
                        })
                
                # Ensure we have at least 6 cycles (RapidAPI minimum requirement)
                if len(past_cycle_data) < 6:
                    print(f"⚠️ Only {len(past_cycle_data)} cycles available, generating more synthetic cycles...")
                    last_period_dt = datetime.strptime(last_period_date_str, "%Y-%m-%d")
                    cycle_length_int = int(cycle_length) if cycle_length else 28
                    # Add more cycles to reach minimum
                    while len(past_cycle_data) < 6:
                        cycle_date = last_period_dt - timedelta(days=cycle_length_int * len(past_cycle_data))
                        past_cycle_data.append({
                            "cycle_start_date": cycle_date.strftime("%Y-%m-%d"),
                            "period_length": 5
                        })
                
                print(f"🔄 Attempting to generate RapidAPI predictions with {len(past_cycle_data)} cycles...")
                current_date = datetime.now().strftime("%Y-%m-%d")
                
                # Generate predictions using RapidAPI
                generate_cycle_phase_map(
                    user_id=user_id,
                    past_cycle_data=past_cycle_data,
                    current_date=current_date
                )
                
                print("✅ RapidAPI predictions generated successfully!")
                
                # Now fetch the stored predictions
                query = supabase.table("user_cycle_days").select("*").eq("user_id", user_id)
                if start_date:
                    query = query.gte("date", start_date)
                if end_date:
                    query = query.lte("date", end_date)
                
                response = query.order("date").execute()
                stored_data = response.data or []
                
                if stored_data:
                    print(f"✅ Retrieved {len(stored_data)} RapidAPI predictions from database")
                    formatted_data = []
                    for item in stored_data:
                        formatted_entry = {
                            "date": item.get("date"),
                            "phase": item.get("phase"),
                            "phase_day_id": item.get("phase_day_id") or item.get("id")
                        }
                        # Add new adaptive fields if present in stored data
                        # Note: These may need to be recalculated if not stored
                        if "fertility_prob" in item:
                            formatted_entry["fertility_prob"] = item["fertility_prob"]
                        if "predicted_ovulation_date" in item:
                            formatted_entry["predicted_ovulation_date"] = item["predicted_ovulation_date"]
                        if "luteal_estimate" in item:
                            formatted_entry["luteal_estimate"] = item["luteal_estimate"]
                        if "luteal_sd" in item:
                            formatted_entry["luteal_sd"] = item["luteal_sd"]
                        if "ovulation_sd" in item:
                            formatted_entry["ovulation_sd"] = item["ovulation_sd"]
                        if "source" in item:
                            formatted_entry["source"] = item["source"]
                        if "confidence" in item:
                            formatted_entry["confidence"] = item["confidence"]
                        formatted_data.append(formatted_entry)
                    print("=" * 60)
                    return {"phase_map": formatted_data}
                else:
                    print("⚠️ RapidAPI predictions generated but not found in database")
            except Exception as rapidapi_error:
                error_msg = str(rapidapi_error)
                print(f"⚠️ RapidAPI prediction failed: {error_msg}")
                # Check if it's a "not enough cycles" error
                if "not enough" in error_msg.lower() or "insufficient" in error_msg.lower():
                    print(f"   ⚠️ RapidAPI requires more cycle data. Provided {len(past_cycle_data)} cycles.")
                    print("   💡 Tip: Log more period dates to improve predictions.")
                print("   Falling back to simple calculation...")
        except Exception as gen_error:
            print(f"⚠️ Failed to generate RapidAPI predictions: {str(gen_error)}")
            print("   Falling back to simple calculation...")
        
        # Fallback: Use improved calculation if RapidAPI fails
        print(f"🔄 Using improved fallback calculation from {start_date} to {end_date}")
        try:
            from cycle_utils import calculate_phase_for_date_range
            cycle_length_int = int(cycle_length) if cycle_length else 28
            
            # Limit date range to prevent slow calculations
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
                days_diff = (end_dt - start_dt).days
                if days_diff > 90:  # Limit to 3 months for performance
                    print(f"⚠️ Limiting calculation to 90 days (was {days_diff} days)")
                    end_dt = start_dt + timedelta(days=90)
                    end_date = end_dt.strftime("%Y-%m-%d")
            except:
                pass
            
            calculated_map = calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=last_period_date_str,
                cycle_length=cycle_length_int,
                start_date=start_date,
                end_date=end_date
            )
            
            # Format for response (include new fields for Flutter frontend)
            formatted_map = []
            for item in calculated_map:
                formatted_entry = {
                    "date": item["date"],
                    "phase": item["phase"],
                    "phase_day_id": item["phase_day_id"]
                }
                # Add new adaptive fields if present
                if "fertility_prob" in item:
                    formatted_entry["fertility_prob"] = item["fertility_prob"]
                if "predicted_ovulation_date" in item:
                    formatted_entry["predicted_ovulation_date"] = item["predicted_ovulation_date"]
                if "luteal_estimate" in item:
                    formatted_entry["luteal_estimate"] = item["luteal_estimate"]
                if "luteal_sd" in item:
                    formatted_entry["luteal_sd"] = item["luteal_sd"]
                if "ovulation_sd" in item:
                    formatted_entry["ovulation_sd"] = item["ovulation_sd"]
                if "source" in item:
                    formatted_entry["source"] = item["source"]
                if "confidence" in item:
                    formatted_entry["confidence"] = item["confidence"]
                formatted_map.append(formatted_entry)
            
            print(f"✅ Calculated {len(formatted_map)} phase mappings (improved fallback)")
            if len(formatted_map) > 0:
                print(f"   First 3 dates: {formatted_map[:3]}")
            print("=" * 60)
            return {"phase_map": formatted_map}
        except Exception as calc_error:
            print(f"❌ ERROR in fallback calculation: {str(calc_error)}")
            import traceback
            traceback.print_exc()
            print("=" * 60)
            return {"phase_map": []}
    
    except Exception as e:
        print(f"Error getting phase map: {str(e)}")
        import traceback
        traceback.print_exc()
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

