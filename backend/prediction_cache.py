"""
Prediction cache management.

user_cycle_days is treated as a cache that can be fully regenerated.
This module handles cache invalidation and regeneration.
"""

from datetime import datetime, timedelta
from typing import Optional
from database import supabase
from period_start_logs import get_last_confirmed_period_start
from cycle_utils import calculate_phase_for_date_range


def get_first_logged_period_date(user_id: str) -> Optional[str]:
    """
    Get the first (earliest) logged period date for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        First logged period date (YYYY-MM-DD) or None if no periods logged
    """
    try:
        # Get the earliest period log (ordered ascending by date)
        period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=False).limit(1).execute()
        
        if period_logs_response.data and len(period_logs_response.data) > 0:
            first_date = period_logs_response.data[0]["date"]
            return first_date if isinstance(first_date, str) else first_date.strftime("%Y-%m-%d")
        
        return None
    except Exception as e:
        print(f"Error getting first logged period date: {str(e)}")
        return None


def cleanup_predictions_before_first_period(user_id: str) -> None:
    """
    Delete all predictions that are earlier than the first logged period date.
    We don't need predictions for dates before the user started logging periods.
    
    Args:
        user_id: User ID
    """
    try:
        first_period_date = get_first_logged_period_date(user_id)
        
        if not first_period_date:
            print(f"⚠️ No logged periods found for user {user_id}, skipping cleanup")
            return
        
        # Delete all predictions before the first logged period date
        deleted = supabase.table("user_cycle_days").delete().eq("user_id", user_id).lt("date", first_period_date).execute()
        print(f"🧹 Cleaned up predictions before first logged period ({first_period_date}) for user {user_id}")
    
    except Exception as e:
        print(f"Error cleaning up predictions before first period: {str(e)}")
        import traceback
        traceback.print_exc()


def invalidate_predictions_after_period(user_id: str, period_start_date: Optional[str] = None) -> None:
    """
    Invalidate (delete) all predicted days after a period start.
    
    When a period is logged, everything after the previous confirmed period is soft.
    This function deletes all predicted days after the specified period start.
    
    Args:
        user_id: User ID
        period_start_date: Period start date (YYYY-MM-DD). If None, uses last confirmed period start.
    """
    try:
        if not period_start_date:
            period_start_date = get_last_confirmed_period_start(user_id)
        
        if not period_start_date:
            # No confirmed period - delete all predictions
            print(f"⚠️ No confirmed period found, deleting all predictions for user {user_id}")
            supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()
            return
        
        # Delete all predictions after (and including) the period start date
        # This ensures we regenerate everything from the last confirmed period
        deleted = supabase.table("user_cycle_days").delete().eq("user_id", user_id).gte("date", period_start_date).execute()
        print(f"✅ Invalidated predictions after {period_start_date} for user {user_id}")
    
    except Exception as e:
        print(f"Error invalidating predictions: {str(e)}")
        import traceback
        traceback.print_exc()


def hard_invalidate_predictions_from_date(user_id: str, invalidation_date: str) -> None:
    """
    HARD INVALIDATION BOUNDARY: Delete ALL predicted phases >= invalidation_date.
    
    This fixes the "Ghost Cycle" problem where old predicted periods remain
    when a user logs a period earlier than predicted.
    
    Flo's Approach: Any predicted state is "soft" and must be vaporized
    the moment "hard" data (a log) arrives.
    
    CRITICAL: This deletes ALL user_cycle_days entries >= invalidation_date,
    regardless of whether they are actual or predicted. The system will regenerate
    them with correct calculations based on the new logged period.
    
    Args:
        user_id: User ID
        invalidation_date: Date from which to delete all predictions (YYYY-MM-DD)
                          Typically the logged period start date
    """
    try:
        # CRITICAL FIX: Delete ALL user_cycle_days entries >= invalidation_date
        # This includes both predicted AND actual entries, because when a new period
        # is logged, we need to recalculate everything from that point forward
        # The actual period days will be regenerated correctly in the next step
        deleted = supabase.table("user_cycle_days").delete().eq("user_id", user_id).gte("date", invalidation_date).execute()
        deleted_count = len(deleted.data) if deleted.data else 0
        print(f"🗑️ HARD INVALIDATION: Deleted {deleted_count} phase entries (ALL types) from {invalidation_date} onwards for user {user_id}")
        print(f"   This ensures no 'ghost cycles' remain when period is logged earlier than predicted")
        print(f"   All phases will be regenerated with correct calculations based on the new logged period")
    
    except Exception as e:
        print(f"Error in hard invalidation: {str(e)}")
        import traceback
        traceback.print_exc()


def regenerate_predictions_from_last_confirmed_period(user_id: str, days_ahead: int = 730) -> None:
    """
    Regenerate predictions from the first logged period to current month + a few months ahead.
    
    This runs AFTER the immediate update to fill in remaining months.
    It only generates predictions from the first logged period date onwards (not before).
    
    Flow:
    1. Immediate: Update from logged period month to current + 3 months
    2. Background: Fill in from first logged period to current + N months ahead
    
    Args:
        user_id: User ID
        days_ahead: Number of days ahead to generate predictions (default 730 = 2 years)
    """
    try:
        # Get first logged period date - we don't need predictions before this
        first_period_date = get_first_logged_period_date(user_id)
        
        if not first_period_date:
            print(f"⚠️ No logged periods found for user {user_id}, cannot regenerate predictions")
            return
        
        # Clean up any predictions before the first logged period
        cleanup_predictions_before_first_period(user_id)
        
        # Get last confirmed period start (should be the newly logged period)
        last_confirmed_start = get_last_confirmed_period_start(user_id)
        
        if not last_confirmed_start:
            print(f"⚠️ No confirmed period found for user {user_id}, cannot regenerate predictions")
            return
        
        # Get user data
        user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        if not user_response.data:
            print(f"⚠️ No user data found for user {user_id}")
            return
        
        user_data = user_response.data[0]
        cycle_length = user_data.get("cycle_length", 28)
        
        # Calculate date range: Start from FIRST logged period (not before it)
        # End at current month + a few months ahead
        first_period_dt = datetime.strptime(first_period_date, "%Y-%m-%d")
        today = datetime.now()
        
        # Start from the first day of the month containing the first logged period
        start_date_obj = first_period_dt.replace(day=1)
        start_date = start_date_obj.strftime("%Y-%m-%d")
        
        # End at N days ahead (default 730 = 2 years, but typically 3-6 months is enough)
        end_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # Generate predictions using ACCURATE method (same as immediate update)
        print(f"🔄 BACKGROUND: Regenerating full range predictions from {start_date} to {end_date} for user {user_id}")
        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=last_confirmed_start,  # Use confirmed period for accuracy
            cycle_length=int(cycle_length),
            start_date=start_date,
            end_date=end_date
        )
        
        # Store in cache (user_cycle_days) - this will merge with immediate 7-month update
        if phase_mappings:
            from cycle_utils import store_cycle_phase_map
            # Use upsert to merge with existing data (won't overwrite immediate update)
            store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
            print(f"✅ BACKGROUND: Regenerated {len(phase_mappings)} predictions for full calendar range")
        else:
            print(f"⚠️ BACKGROUND: No predictions generated for user {user_id}")
    
    except Exception as e:
        print(f"Error in background prediction regeneration: {str(e)}")
        import traceback
        traceback.print_exc()
