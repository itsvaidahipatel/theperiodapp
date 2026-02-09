"""
Missing Period Algorithm: Handle late periods gracefully.

If today is Predicted_Start + 4 days and no log exists:
- Don't just let the calendar stay pink
- Move the "Predicted Period" block forward by 1 day, every day
- After 14 days, switch state to "Late"
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from database import supabase
from cycle_utils import get_user_phase_day, estimate_period_length
from period_start_logs import get_period_start_logs


def handle_missing_period(user_id: str, today: Optional[str] = None) -> Optional[Dict]:
    """
    Check if a predicted period is late and adjust predictions accordingly.
    
    Algorithm:
    1. Find the most recent predicted period start (p1)
    2. If today >= predicted_start + 4 days and no log exists:
       - Move predicted period forward by 1 day
       - After 14 days, mark as "Late"
    
    Args:
        user_id: User ID
        today: Today's date (YYYY-MM-DD), defaults to current date
    
    Returns:
        Dict with adjustment info, or None if no adjustment needed
    """
    try:
        if not today:
            today = datetime.now().strftime("%Y-%m-%d")
        
        today_obj = datetime.strptime(today, "%Y-%m-%d").date()
        
        # Get the most recent predicted period start
        period_starts = get_period_start_logs(user_id, confirmed_only=False)
        
        if not period_starts:
            return None
        
        # Find the most recent predicted (unconfirmed) period start
        most_recent_predicted = None
        for start_log in sorted(period_starts, key=lambda x: x["start_date"], reverse=True):
            if not start_log.get("confirmed", False):  # This is a prediction
                start_date_str = start_log["start_date"]
                if isinstance(start_date_str, str):
                    predicted_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                else:
                    predicted_start = start_date_str
                
                # Check if this predicted period has passed without a log
                days_since_predicted = (today_obj - predicted_start).days
                
                if days_since_predicted >= 4:  # 4 days after predicted start
                    # Check if user has logged a period for this date range
                    period_length = estimate_period_length(user_id)
                    period_length_days = int(round(max(3.0, min(8.0, period_length))))
                    period_end = predicted_start + timedelta(days=period_length_days - 1)
                    
                    # Check if any period was logged in this range
                    logged_periods = supabase.table("period_logs").select("date").eq("user_id", user_id).gte("date", predicted_start.strftime("%Y-%m-%d")).lte("date", period_end.strftime("%Y-%m-%d")).execute()
                    
                    if not logged_periods.data:  # No log found
                        most_recent_predicted = predicted_start
                        days_late = days_since_predicted
                        break
        
        if not most_recent_predicted:
            return None
        
        # Calculate adjustment
        days_late = (today_obj - most_recent_predicted).days
        
        if days_late >= 14:
            # Period is very late - mark as "Late" state
            return {
                "is_late": True,
                "days_late": days_late,
                "predicted_start": most_recent_predicted.strftime("%Y-%m-%d"),
                "action": "mark_late",
                "message": f"Period is {days_late} days late. Consider logging it or checking with a healthcare provider."
            }
        elif days_late >= 4:
            # Period is late - move predicted period forward by 1 day
            new_predicted_start = most_recent_predicted + timedelta(days=1)
            return {
                "is_late": False,
                "days_late": days_late,
                "predicted_start": most_recent_predicted.strftime("%Y-%m-%d"),
                "new_predicted_start": new_predicted_start.strftime("%Y-%m-%d"),
                "action": "shift_forward",
                "message": f"Period is {days_late} days late. Adjusting prediction forward."
            }
        
        return None
    
    except Exception as e:
        print(f"Error handling missing period: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def adjust_late_period_predictions(user_id: str, days_to_shift: int = 1) -> bool:
    """
    Shift predicted period predictions forward by specified days.
    
    This is called when a period is detected as late.
    
    Args:
        user_id: User ID
        days_to_shift: Number of days to shift predictions forward (default 1)
    
    Returns:
        True if adjustment was made, False otherwise
    """
    try:
        # Get predicted period starts
        period_starts = get_period_start_logs(user_id, confirmed_only=False)
        
        if not period_starts:
            return False
        
        # Find unconfirmed (predicted) period starts
        predicted_starts = [s for s in period_starts if not s.get("confirmed", False)]
        
        if not predicted_starts:
            return False
        
        # Shift the most recent predicted start forward
        most_recent = max(predicted_starts, key=lambda x: x["start_date"])
        old_start = most_recent["start_date"]
        
        if isinstance(old_start, str):
            old_start_obj = datetime.strptime(old_start, "%Y-%m-%d").date()
        else:
            old_start_obj = old_start
        
        new_start_obj = old_start_obj + timedelta(days=days_to_shift)
        new_start = new_start_obj.strftime("%Y-%m-%d")
        
        # Update the period_start_logs entry
        # Note: This would require updating the period_start_logs table
        # For now, we'll invalidate and regenerate predictions
        from prediction_cache import hard_invalidate_predictions_from_date
        hard_invalidate_predictions_from_date(user_id, old_start)
        
        # Regenerate predictions with shifted start
        from cycle_utils import calculate_phase_for_date_range, store_cycle_phase_map
        from datetime import timedelta
        
        today = datetime.now().date()
        start_date = old_start_obj.strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=90)).strftime("%Y-%m-%d")
        
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        cycle_length = user_response.data[0].get("cycle_length", 28) if user_response.data else 28
        
        # Use the shifted start date for regeneration
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=new_start,
            cycle_length=int(cycle_length),
            start_date=start_date,
            end_date=end_date
        )
        
        if phase_mappings:
            store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
            print(f"✅ Adjusted late period predictions: shifted from {old_start} to {new_start}")
            return True
        
        return False
    
    except Exception as e:
        print(f"Error adjusting late period predictions: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
