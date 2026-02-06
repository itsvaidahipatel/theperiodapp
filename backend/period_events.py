"""
PeriodEvent utilities (DEPRECATED - use period_start_logs.py instead).

This module is kept for backward compatibility but is being replaced by period_start_logs.py
which implements the simpler "one log = one cycle start" model.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from database import supabase


def build_period_events(user_id: str) -> List[Dict]:
    """
    Build PeriodEvents from period_logs.
    
    Groups consecutive bleeding days into period events.
    A period event is confirmed if there's a gap >= 1 non-bleeding day after it.
    
    Args:
        user_id: User ID
    
    Returns:
        List of PeriodEvent dicts with: start_date, end_date, length, is_confirmed
    """
    try:
        # Get all period logs, ordered by date
        logs_response = supabase.table("period_logs").select("date, flow").eq("user_id", user_id).order("date").execute()
        
        if not logs_response.data:
            return []
        
        # Filter to only bleeding days (flow != 'none' and flow is not null/empty)
        bleeding_days = []
        for log in logs_response.data:
            flow = log.get("flow", "").lower() if log.get("flow") else ""
            if flow and flow != "none" and flow != "":
                date_str = log.get("date")
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date() if isinstance(date_str, str) else date_str
                        bleeding_days.append(date_obj)
                    except:
                        continue
        
        if not bleeding_days:
            return []
        
        # Sort by date
        bleeding_days = sorted(set(bleeding_days))
        
        # Group consecutive days into periods
        period_events = []
        if not bleeding_days:
            return []
        
        current_period_start = bleeding_days[0]
        current_period_end = bleeding_days[0]
        
        for i in range(1, len(bleeding_days)):
            days_gap = (bleeding_days[i] - current_period_end).days
            
            if days_gap == 1:
                # Consecutive day - extend current period
                current_period_end = bleeding_days[i]
            else:
                # Gap > 1 day - end current period and start new one
                period_length = (current_period_end - current_period_start).days + 1
                
                # Check if period is confirmed (gap >= 1 day after)
                # We'll mark it as confirmed if there's a gap after it
                is_confirmed = days_gap > 1
                
                period_events.append({
                    "start_date": current_period_start,
                    "end_date": current_period_end,
                    "length": period_length,
                    "is_confirmed": is_confirmed
                })
                
                # Start new period
                current_period_start = bleeding_days[i]
                current_period_end = bleeding_days[i]
        
        # Add the last period
        if current_period_start:
            period_length = (current_period_end - current_period_start).days + 1
            # Last period is confirmed if it's not the most recent (we'll check this after)
            # For now, mark as unconfirmed if it's within the last 7 days
            today = datetime.now().date()
            days_since_end = (today - current_period_end).days
            is_confirmed = days_since_end >= 1  # Confirmed if at least 1 day has passed since period ended
            
            period_events.append({
                "start_date": current_period_start,
                "end_date": current_period_end,
                "length": period_length,
                "is_confirmed": is_confirmed
            })
        
        return period_events
    
    except Exception as e:
        print(f"Error building period events: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def sync_period_events_to_db(user_id: str) -> None:
    """
    Sync PeriodEvents to database.
    
    Rebuilds PeriodEvents from period_logs and stores them in period_events table.
    This should be called whenever period_logs change.
    
    Args:
        user_id: User ID
    """
    try:
        # Build PeriodEvents from logs
        period_events = build_period_events(user_id)
        
        # Delete existing PeriodEvents for this user
        supabase.table("period_events").delete().eq("user_id", user_id).execute()
        
        # Insert new PeriodEvents
        if period_events:
            insert_data = []
            for event in period_events:
                insert_data.append({
                    "user_id": user_id,
                    "start_date": event["start_date"].strftime("%Y-%m-%d") if hasattr(event["start_date"], 'strftime') else str(event["start_date"]),
                    "end_date": event["end_date"].strftime("%Y-%m-%d") if hasattr(event["end_date"], 'strftime') else str(event["end_date"]),
                    "length": event["length"],
                    "is_confirmed": event["is_confirmed"]
                })
            
            supabase.table("period_events").insert(insert_data).execute()
            print(f"✅ Synced {len(period_events)} PeriodEvents to database for user {user_id}")
    
    except Exception as e:
        print(f"Error syncing period events to database: {str(e)}")
        import traceback
        traceback.print_exc()


def get_period_events(user_id: str, confirmed_only: bool = False) -> List[Dict]:
    """
    Get PeriodEvents from database.
    
    Args:
        user_id: User ID
        confirmed_only: If True, only return confirmed PeriodEvents
    
    Returns:
        List of PeriodEvent dicts, ordered by start_date
    """
    try:
        query = supabase.table("period_events").select("*").eq("user_id", user_id).order("start_date")
        
        if confirmed_only:
            query = query.eq("is_confirmed", True)
        
        response = query.execute()
        return response.data or []
    
    except Exception as e:
        print(f"Error getting period events: {str(e)}")
        return []


def get_cycles_from_period_events(user_id: str) -> List[Dict]:
    """
    Derive cycles from PeriodEvents.
    
    Cycles are NOT stored permanently - they are computed from PeriodEvents.
    
    Cycle definition:
    - Cycle.start = PeriodEvent[n].start_date
    - Cycle.length = PeriodEvent[n+1].start_date - PeriodEvent[n].start_date
    
    Args:
        user_id: User ID
    
    Returns:
        List of cycle dicts with: cycle_number, start_date, length
    """
    try:
        # Get confirmed PeriodEvents only (for cycle calculation)
        period_events = get_period_events(user_id, confirmed_only=True)
        
        if len(period_events) < 2:
            return []
        
        cycles = []
        for i in range(len(period_events) - 1):
            cycle_start = period_events[i]["start_date"]
            next_cycle_start = period_events[i + 1]["start_date"]
            
            # Parse dates if needed
            if isinstance(cycle_start, str):
                cycle_start_date = datetime.strptime(cycle_start, "%Y-%m-%d").date()
            else:
                cycle_start_date = cycle_start
            
            if isinstance(next_cycle_start, str):
                next_cycle_start_date = datetime.strptime(next_cycle_start, "%Y-%m-%d").date()
            else:
                next_cycle_start_date = next_cycle_start
            
            cycle_length = (next_cycle_start_date - cycle_start_date).days
            
            # Only include valid cycle lengths (15-60 days)
            if 15 <= cycle_length <= 60:
                cycles.append({
                    "cycle_number": len(period_events) - i - 1,  # Most recent = 1
                    "start_date": cycle_start,
                    "length": cycle_length
                })
        
        return cycles
    
    except Exception as e:
        print(f"Error deriving cycles from period events: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_last_confirmed_period_start(user_id: str) -> Optional[str]:
    """
    Get the start date of the last confirmed period.
    
    This is the anchor point for predictions - everything after this is soft.
    
    Args:
        user_id: User ID
    
    Returns:
        Last confirmed period start date (YYYY-MM-DD) or None
    """
    try:
        period_events = get_period_events(user_id, confirmed_only=True)
        
        if not period_events:
            return None
        
        # Get the most recent confirmed period
        last_event = period_events[-1]
        start_date = last_event["start_date"]
        
        # Return as string
        if isinstance(start_date, str):
            return start_date
        elif hasattr(start_date, 'strftime'):
            return start_date.strftime("%Y-%m-%d")
        else:
            return str(start_date)
    
    except Exception as e:
        print(f"Error getting last confirmed period start: {str(e)}")
        return None
