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


def regenerate_predictions_from_last_confirmed_period(user_id: str, days_ahead: int = 730) -> None:
    """
    Regenerate predictions from the last confirmed period (BACKGROUND TASK).
    
    This runs AFTER the immediate 7-month update to fill in remaining months.
    It uses the same accurate calculation method but for the full calendar range.
    
    Flow:
    1. Immediate: 7 months updated synchronously (3 past + current + 3 future)
    2. Background: Full range updated asynchronously (1 year past to 2 years future)
    
    Args:
        user_id: User ID
        days_ahead: Number of days ahead to generate predictions (default 730 = 2 years)
    """
    try:
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
        
        # Calculate date range: 1 year past to N days ahead (full calendar range)
        # NOTE: The immediate 7-month update already covered 3 months past to 3 months future
        # This background task fills in the remaining months
        last_period_date = datetime.strptime(last_confirmed_start, "%Y-%m-%d")
        today = datetime.now()
        # Start from 1 year before today to cover past dates
        start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        # End at N days ahead (default 730 = 2 years)
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
