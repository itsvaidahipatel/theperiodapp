from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from database import supabase
from routes.auth import get_current_user
from cycle_utils import (
    get_user_phase_day,
    calculate_phase_for_date_range
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
    """Generate cycle predictions and phase mappings for user using adaptive local algorithms."""
    try:
        user_id = current_user["id"]
        current_date = request.current_date or datetime.now().strftime("%Y-%m-%d")
        
        # Get user data
        user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        if not user_response.data or not user_response.data[0]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User data not found. Please set last_period_date."
            )
        
        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        cycle_length = user.get("cycle_length", 28)
        
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
        current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        start_date = (current_date_obj - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = (current_date_obj + timedelta(days=60)).strftime("%Y-%m-%d")
        
        # Generate cycle phase map using adaptive local algorithms
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=last_period_date_str,
            cycle_length=int(cycle_length),
            start_date=start_date,
            end_date=end_date
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cycle prediction failed: {str(e)}"
        )

@router.get("/current-phase")
async def get_current_phase(
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current phase-day information for user. Fast lookup with minimal calculation."""
    try:
        user_id = current_user["id"]
        check_date = date or datetime.now().strftime("%Y-%m-%d")
        
        # FAST PATH: Try to get from stored cycle predictions first
        phase_info = get_user_phase_day(user_id, check_date)
        
        if phase_info and phase_info.get("phase") and phase_info.get("phase_day_id"):
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
        
        # FAST FALLBACK: Use calculate_today_phase_day_id (fast, single-date calculation)
        # This is much faster than calculating a full date range
        from cycle_utils import calculate_today_phase_day_id
        today_phase_day_id = calculate_today_phase_day_id(user_id)
        
        if today_phase_day_id:
            # Determine phase from phase_day_id
            phase_map = {
                "p": "Period",
                "f": "Follicular", 
                "o": "Ovulation",
                "l": "Luteal"
            }
            phase_prefix = today_phase_day_id[0].lower()
            phase = phase_map.get(phase_prefix, "Period")
            
            # Check if today is p1 - auto-update last_period_date
            if today_phase_day_id.lower() == "p1":
                from database import supabase
                supabase.table("users").update({
                    "last_period_date": check_date
                }).eq("id", user_id).execute()
                print(f"Auto-updated last_period_date to {check_date} for user {user_id} (p1 calculated)")
            
            return {
                "phase": phase,
                "phase_day_id": today_phase_day_id,
                "date": check_date,
                "calculated": True
            }
        
        # No data available
        return {
            "phase": None,
            "phase_day_id": None,
            "id": None,
            "message": "No phase data available. Please set your last period date."
        }
    
    except Exception as e:
        import traceback
        print(f"❌ Error in get_current_phase: {str(e)}")
        traceback.print_exc()
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
    force_recalculate: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get phase mappings for a date range. Calculates on the fly if not in database.
    
    Args:
        start_date: Start date for phase map (YYYY-MM-DD)
        end_date: End date for phase map (YYYY-MM-DD)
        force_recalculate: If True, force regeneration even if data exists in database
    """
    try:
        user_id = current_user["id"]
        
        # Try to get from database first (stored predictions)
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
        
        # If force_recalculate is True, delete old data first
        if force_recalculate and stored_data:
            print("🔄 Force recalculation requested - clearing old phase map data...")
            try:
                delete_query = supabase.table("user_cycle_days").delete().eq("user_id", user_id)
                if start_date:
                    delete_query = delete_query.gte("date", start_date)
                if end_date:
                    delete_query = delete_query.lte("date", end_date)
                delete_query.execute()
                print("✅ Old phase map data cleared")
                stored_data = []  # Clear stored_data so we regenerate
            except Exception as delete_error:
                print(f"⚠️ Error clearing old data (non-fatal): {str(delete_error)}")
        
        # If we have stored data, return it IMMEDIATELY (unless force_recalculate is True)
        # This is FAST - no calculation needed
        if stored_data and not force_recalculate:
            print(f"⚡ FAST PATH: Returning {len(stored_data)} stored predictions from database")
            # Convert stored data to the expected format - optimized for speed
            formatted_data = []
            for item in stored_data:
                formatted_data.append({
                    "date": item.get("date"),
                    "phase": item.get("phase"),
                    "phase_day_id": item.get("phase_day_id") or item.get("id"),
                    "fertility_prob": item.get("fertility_prob") or 0,
                    "is_predicted": item.get("is_predicted", True)
                })
            return {"phase_map": formatted_data}
        
        # If no stored data, generate predictions using local adaptive algorithms
        print("=" * 60)
        print("CALENDAR PHASE MAP REQUEST")
        print(f"User ID: {user_id}")
        print(f"Date range: {start_date} to {end_date}")
        print("No stored predictions found. Generating using adaptive local algorithms...")
        print("=" * 60)
        
        # Check date range and optimize for future months
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
            days_diff = (end_dt - start_dt).days
            today = datetime.now()
            
            # If requesting far future dates (> 1 year ahead), limit to reasonable range
            if end_dt > today + timedelta(days=365):
                print(f"⚠️ Requested date range extends > 1 year in future. Limiting to 1 year ahead for performance.")
                end_dt = today + timedelta(days=365)
                end_date = end_dt.strftime("%Y-%m-%d")
                days_diff = (end_dt - start_dt).days
                print(f"📅 Adjusted date range: {days_diff} days ({start_date} to {end_date})")
            else:
                print(f"📅 Requested date range: {days_diff} days ({start_date} to {end_date})")
        except:
            pass  # Continue with original dates if parsing fails
        
        from cycle_utils import calculate_phase_for_date_range
        
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
            print("⚠️ No last_period_date found for user - generating predictions from today")
            # Generate predictions from today using default cycle length
            from datetime import datetime
            last_period_date = datetime.now().strftime("%Y-%m-%d")
            print(f"💡 Using today ({last_period_date}) as last_period_date for predictions")
        
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
        
        # Generate predictions using adaptive local algorithms (medically credible)
        print(f"🔄 Generating predictions using adaptive local algorithms...")
        try:
            from cycle_utils import calculate_phase_for_date_range
            cycle_length_int = int(cycle_length) if cycle_length else 28
            
            # Process full date range - predictions are optimized now
            # No artificial limits - we want complete calendar coverage
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
                days_diff = (end_dt - start_dt).days
                print(f"📊 Calculating phases for {days_diff} days")
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
            # ⚠️ MEDICAL SAFETY: Minimum confidence threshold for fertility data
            MIN_CONFIDENCE_FOR_FERTILITY = 0.5  # Only show fertility_prob if prediction_confidence >= 0.5
            
            for item in calculated_map:
                formatted_entry = {
                    "date": item["date"],
                    "phase": item["phase"],
                    "phase_day_id": item["phase_day_id"]
                }
                # Add new adaptive fields if present
                
                # ⚠️ MEDICAL SAFETY: Suppress fertility_prob if prediction_confidence is too low
                prediction_confidence = item.get("prediction_confidence") or item.get("confidence", 0.0)  # Backward compatibility
                if "fertility_prob" in item and prediction_confidence >= MIN_CONFIDENCE_FOR_FERTILITY:
                    formatted_entry["fertility_prob"] = item["fertility_prob"]
                # If prediction_confidence is low, do NOT include fertility_prob (suppressed for safety)
                
                # Always include predicted_ovulation_date but mark as "estimated"
                if "predicted_ovulation_date" in item:
                    formatted_entry["predicted_ovulation_date"] = item["predicted_ovulation_date"]
                    formatted_entry["predicted_ovulation_date_label"] = "Estimated ovulation date"  # Medical safety wording
                
                if "ovulation_offset" in item:
                    formatted_entry["ovulation_offset"] = item["ovulation_offset"]
                if "luteal_estimate" in item:
                    formatted_entry["luteal_estimate"] = item["luteal_estimate"]
                if "luteal_sd" in item:
                    formatted_entry["luteal_sd"] = item["luteal_sd"]
                if "ovulation_sd" in item:
                    formatted_entry["ovulation_sd"] = item["ovulation_sd"]
                if "source" in item:
                    formatted_entry["source"] = item["source"]
                if "prediction_confidence" in item:
                    formatted_entry["prediction_confidence"] = item["prediction_confidence"]
                elif "confidence" in item:  # Backward compatibility
                    formatted_entry["prediction_confidence"] = item["confidence"]
                if "is_predicted" in item:
                    formatted_entry["is_predicted"] = item["is_predicted"]
                # Ensure fertility_prob is always included
                if "fertility_prob" not in formatted_entry:
                    formatted_entry["fertility_prob"] = item.get("fertility_prob", 0)
                formatted_map.append(formatted_entry)
            
            print(f"✅ Calculated {len(formatted_map)} phase mappings using adaptive local algorithms")
            if len(formatted_map) > 0:
                sample_dates = [f"{item.get('date', 'N/A')} ({item.get('phase', 'N/A')})" for item in formatted_map[:3]]
                print(f"   First 3 dates: {sample_dates}")
                phases_found = set(item.get('phase') for item in formatted_map if item.get('phase'))
                print(f"   Phases included: {phases_found}")
            else:
                print("⚠️ WARNING: No phase mappings generated!")
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
        user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        user_data = user_response.data[0] if user_response.data else {}
        last_period_date = user_data.get("last_period_date")
        cycle_length = user_data.get("cycle_length", 28)
        
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
                            except Exception as log_error:
                                print(f"Error parsing log date: {str(log_error)}")
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
            except Exception as e:
                print(f"Error calculating current cycle stats: {str(e)}")
                import traceback
                traceback.print_exc()
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
            # Still return timeline and stats, but no abnormalities analysis
            cycle_timeline = []
            from cycle_utils import get_user_phase_day, estimate_period_length, predict_ovulation, estimate_luteal, select_ovulation_days
            
            # Build timeline even with just 1 period start
            for i, period_start in enumerate(period_starts):
                start_date = period_start["start_date"]
                
                if isinstance(start_date, str):
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                else:
                    start_date_obj = start_date
                
                cycle_number = len(period_starts) - i
                cycle_length = int(avg_cycle_length) if avg_cycle_length else 28
                end_date_obj = start_date_obj + timedelta(days=cycle_length)
                end_date = end_date_obj.strftime("%Y-%m-%d")
                
                # Get daily phase data
                daily_phases = []
                period_days = int(estimate_period_length(user_id, normalized=True))  # Use normalized for phase calculations
                luteal_mean, luteal_sd = estimate_luteal(user_id)
                ov_date_str, calculated_ovulation_sd, _ = predict_ovulation(
                    start_date_obj.strftime("%Y-%m-%d"),
                    float(cycle_length),
                    luteal_mean,
                    luteal_sd,
                    cycle_start_sd=None,
                    user_id=user_id
                )
                ovulation_date = datetime.strptime(ov_date_str, "%Y-%m-%d")
                ovulation_days = select_ovulation_days(calculated_ovulation_sd, max_days=3)
                
                current_date = start_date_obj
                for day in range(cycle_length):
                    date_str = current_date.strftime("%Y-%m-%d")
                    phase_data = get_user_phase_day(user_id, date_str)
                    
                    if phase_data and phase_data.get("phase"):
                        phase = phase_data.get("phase")
                    else:
                        day_in_cycle = day + 1
                        offset_from_ov = (current_date - ovulation_date).days
                        
                        if day_in_cycle <= period_days:
                            phase = "Period"
                        elif offset_from_ov in ovulation_days:
                            phase = "Ovulation"
                        elif current_date < ovulation_date:
                            phase = "Follicular"
                        else:
                            phase = "Luteal"
                    
                    daily_phases.append({
                        "date": date_str,
                        "phase": phase,
                        "day": day + 1
                    })
                    current_date += timedelta(days=1)
                
                cycle_timeline.append({
                    "cycle_number": cycle_number,
                    "start_date": start_date_obj.strftime("%Y-%m-%d"),
                    "end_date": end_date,
                    "cycle_length": cycle_length,
                    "status": "current" if i == len(period_starts) - 1 else "normal",
                    "is_current": i == len(period_starts) - 1,
                    "daily_phases": daily_phases
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
            except Exception as e:
                print(f"Error getting additional stats: {str(e)}")
            
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
        cycle_timeline = []
        from cycle_utils import get_user_phase_day, estimate_period_length, predict_ovulation, estimate_luteal, select_ovulation_days
        
        for i, period_start in enumerate(period_starts):
            start_date = period_start["start_date"]
            
            # Parse start date
            if isinstance(start_date, str):
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start_date_obj = start_date
            
            cycle_number = len(period_starts) - i
            cycle_length = None
            end_date = None
            status = "normal"
            
            # Calculate cycle length and end date
            if i < len(period_starts) - 1:
                next_start = period_starts[i + 1]["start_date"]
                if isinstance(next_start, str):
                    next_start_obj = datetime.strptime(next_start, "%Y-%m-%d")
                else:
                    next_start_obj = next_start
                
                cycle_length = (next_start_obj - start_date_obj).days
                end_date = next_start_obj.strftime("%Y-%m-%d")
                
                if cycle_length < 21:
                    status = "short"
                elif cycle_length > 35:
                    status = "long"
            else:
                # Last cycle - estimate end date
                cycle_length = int(avg_cycle_length)
                end_date_obj = start_date_obj + timedelta(days=cycle_length)
                end_date = end_date_obj.strftime("%Y-%m-%d")
                status = "current"
            
            # Get daily phase data for this cycle
            daily_phases = []
            period_days = int(estimate_period_length(user_id))
            
            # Calculate ovulation date for this cycle
            luteal_mean, luteal_sd = estimate_luteal(user_id)
            ov_date_str, calculated_ovulation_sd, _ = predict_ovulation(
                start_date_obj.strftime("%Y-%m-%d"),
                float(cycle_length),
                luteal_mean,
                luteal_sd,
                cycle_start_sd=None,
                user_id=user_id
            )
            ovulation_date = datetime.strptime(ov_date_str, "%Y-%m-%d")
            
            # Get ovulation window (fertile days) using calculated SD
            ovulation_days = select_ovulation_days(calculated_ovulation_sd, max_days=3)
            
            # Generate phase for each day in the cycle
            current_date = start_date_obj
            for day in range(cycle_length):
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Try to get from database first
                phase_data = get_user_phase_day(user_id, date_str)
                
                if phase_data and phase_data.get("phase"):
                    phase = phase_data.get("phase")
                else:
                    # Calculate phase based on cycle day
                    day_in_cycle = day + 1
                    offset_from_ov = (current_date - ovulation_date).days
                    
                    if day_in_cycle <= period_days:
                        phase = "Period"
                    elif offset_from_ov in ovulation_days:
                        phase = "Ovulation"
                    elif current_date < ovulation_date:
                        phase = "Follicular"
                    else:
                        phase = "Luteal"
                
                daily_phases.append({
                    "date": date_str,
                    "phase": phase,
                    "day": day + 1
                })
                
                current_date += timedelta(days=1)
            
            cycle_timeline.append({
                "cycle_number": cycle_number,
                "start_date": start_date_obj.strftime("%Y-%m-%d"),
                "end_date": end_date,
                "cycle_length": cycle_length,
                "status": status,
                "is_current": i == len(period_starts) - 1,
                "daily_phases": daily_phases  # Daily phase data for visual timeline
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
        
        except Exception as e:
            print(f"Error getting additional stats: {str(e)}")
        
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
        print(f"Error in cycle health check: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze cycles: {str(e)}"
        )

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
