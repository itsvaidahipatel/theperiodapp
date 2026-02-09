"""
Auto-Close Logic for Periods

If a user forgets to click "Period Ended", the system automatically closes
periods that have been open for more than 10 days to prevent "runaway periods"
from breaking cycle statistics.

Threshold: If current_date > start_date + 10 days and end_date is still NULL:
Action: Auto-fill end_date with start_date + estimated_period_length
"""

from datetime import datetime, timedelta
from typing import List, Dict
from database import supabase
from cycle_utils import estimate_period_length


def auto_close_open_periods(user_id: str) -> List[Dict]:
    """
    Auto-close periods that have been open for more than 10 days.
    
    This prevents "runaway periods" from breaking cycle statistics.
    
    Args:
        user_id: User ID
    
    Returns:
        List of periods that were auto-closed
    """
    try:
        today = datetime.now().date()
        threshold_days = 10
        
        # Get all period logs without end_date
        open_periods = supabase.table("period_logs").select("*").eq("user_id", user_id).is_("end_date", "null").execute()
        
        if not open_periods.data:
            return []
        
        auto_closed = []
        
        for period in open_periods.data:
            start_date_str = period["date"]
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            
            # Check if period has been open for more than threshold days
            days_open = (today - start_date_obj).days
            
            if days_open > threshold_days:
                # Auto-close with estimated period length
                estimated_len = estimate_period_length(user_id, normalized=True)
                estimated_days = int(round(max(3.0, min(8.0, estimated_len))))
                auto_end_date = start_date_obj + timedelta(days=estimated_days - 1)
                
                # Update period log
                update_response = supabase.table("period_logs").update({
                    "end_date": auto_end_date.strftime("%Y-%m-%d"),
                    "is_manual_end": False  # Auto-closed, not manually ended
                }).eq("id", period["id"]).execute()
                
                if update_response.data:
                    auto_closed.append({
                        "period_id": period["id"],
                        "start_date": start_date_str,
                        "auto_end_date": auto_end_date.strftime("%Y-%m-%d"),
                        "days_open": days_open
                    })
                    print(f"🔒 Auto-closed period {start_date_str} (was open for {days_open} days, set end to {auto_end_date.strftime('%Y-%m-%d')})")
        
        return auto_closed
    
    except Exception as e:
        print(f"Error auto-closing periods: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
