"""
PeriodStartLog utilities.

DESIGN: One log = one cycle start (period start only, no end/duration)
This is simpler and medically valid (doctors track LMP - Last Menstrual Period)

Core truth: PeriodStartLog = cycle start date
Everything else (cycle length, ovulation, predictions) is derived.

Invariant: A cycle is always anchored to a confirmed period start date.
Everything else is a prediction.

Key principles:
- One log = one cycle start
- No period end, no flow, no duration
- Cycle length = gap between consecutive period starts
- Late logs are allowed (retroactive insertion)
- Future logs are marked as is_confirmed=false
- Duplicate dates are prevented (UNIQUE constraint)
- Deletions trigger full recalculation
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from database import supabase, supabase_admin

# ACOG Guidelines - Standard cycle length range
MIN_CYCLE_DAYS = 21
MAX_CYCLE_DAYS = 45


def sync_period_start_logs_from_period_logs(user_id: str) -> None:
    """
    Sync PeriodStartLogs from period_logs using incremental upserts.
    
    Since period_logs now represents cycle starts (one per cycle),
    we extract unique dates and create/update PeriodStartLogs.
    
    Rules:
    - One log = one cycle start
    - Duplicate dates are prevented (keep latest)
    - Future dates are marked as is_confirmed=false
    - Past dates are marked as is_confirmed=true
    - Preserves created_at timestamps for existing records
    - Only updates changed records (is_confirmed status)
    - Only deletes records that no longer exist in period_logs
    
    Args:
        user_id: User ID
    """
    try:
        # Get all period logs (these are cycle start dates)
        logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date").execute()
        
        # Extract unique dates (one per cycle start)
        start_dates = []
        seen_dates = set()
        
        if logs_response.data:
            for log in logs_response.data:
                date_str = log.get("date")
                if date_str and date_str not in seen_dates:
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date() if isinstance(date_str, str) else date_str
                        start_dates.append(date_obj)
                        seen_dates.add(date_str)
                    except:
                        continue
        
        # Sort by date
        start_dates = sorted(set(start_dates))
        
        # Determine which are confirmed (past dates) vs predicted (future dates)
        today = datetime.now().date()
        
        # Use service role client if available (bypasses RLS), otherwise use regular client
        client = supabase_admin if supabase_admin else supabase
        
        # Get existing PeriodStartLogs to compare
        existing_response = client.table("period_start_logs").select("start_date, is_confirmed").eq("user_id", user_id).execute()
        existing_logs = existing_response.data or []
        
        # Create sets for comparison
        expected_dates = {date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date) for date in start_dates}
        existing_dates = {log["start_date"] for log in existing_logs}
        
        # Track what needs to be done
        dates_to_insert = []
        dates_to_update = []
        dates_to_delete = []
        
        # Find dates that need to be inserted (new)
        for start_date in start_dates:
            date_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)
            if date_str not in existing_dates:
                dates_to_insert.append(start_date)
        
        # Find dates that need to be updated (is_confirmed status changed)
        existing_by_date = {log["start_date"]: log for log in existing_logs}
        for start_date in start_dates:
            date_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)
            if date_str in existing_dates:
                existing_log = existing_by_date[date_str]
                new_is_confirmed = start_date <= today
                if existing_log["is_confirmed"] != new_is_confirmed:
                    dates_to_update.append((date_str, new_is_confirmed))
        
        # Find dates that need to be deleted (no longer in period_logs)
        for existing_log in existing_logs:
            if existing_log["start_date"] not in expected_dates:
                dates_to_delete.append(existing_log["start_date"])
        
        # Perform incremental updates
        stats = {"inserted": 0, "updated": 0, "deleted": 0}
        
        # Insert new records
        if dates_to_insert:
            insert_data = []
            for start_date in dates_to_insert:
                is_confirmed = start_date <= today
                insert_data.append({
                    "user_id": user_id,
                    "start_date": start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date),
                    "is_confirmed": is_confirmed
                })
            
            client.table("period_start_logs").insert(insert_data).execute()
            stats["inserted"] = len(insert_data)
        
        # Update changed records (is_confirmed status)
        for date_str, new_is_confirmed in dates_to_update:
            client.table("period_start_logs").update({
                "is_confirmed": new_is_confirmed
            }).eq("user_id", user_id).eq("start_date", date_str).execute()
            stats["updated"] += 1
        
        # Delete records that no longer exist
        if dates_to_delete:
            for date_str in dates_to_delete:
                client.table("period_start_logs").delete().eq("user_id", user_id).eq("start_date", date_str).execute()
            stats["deleted"] = len(dates_to_delete)
        
        # Log summary
        if any(stats.values()):
            changes = [f"{k}={v}" for k, v in stats.items() if v > 0]
            print(f"✅ Incrementally synced PeriodStartLogs for user {user_id}: {', '.join(changes)}")
        else:
            print(f"✅ PeriodStartLogs already in sync for user {user_id}")
    
    except Exception as e:
        error_msg = str(e)
        if '42501' in error_msg or 'row-level security' in error_msg.lower():
            print(f"⚠️ RLS policy error syncing period start logs. This may require SUPABASE_SERVICE_ROLE_KEY to be set.")
            print(f"   Error: {error_msg}")
            if not supabase_admin:
                print(f"   ⚠️ Service role key not configured. Please set SUPABASE_SERVICE_ROLE_KEY in your environment.")
        else:
            print(f"Error syncing period start logs: {error_msg}")
        import traceback
        traceback.print_exc()


def get_period_start_logs(user_id: str, confirmed_only: bool = False) -> List[Dict]:
    """
    Get PeriodStartLogs from database.
    
    Args:
        user_id: User ID
        confirmed_only: If True, only return confirmed PeriodStartLogs (past dates)
    
    Returns:
        List of PeriodStartLog dicts, ordered by start_date
    """
    try:
        query = supabase.table("period_start_logs").select("*").eq("user_id", user_id).order("start_date")
        
        if confirmed_only:
            query = query.eq("is_confirmed", True)
        
        response = query.execute()
        return response.data or []
    
    except Exception as e:
        print(f"Error getting period start logs: {str(e)}")
        return []


def get_cycles_from_period_starts(user_id: str) -> List[Dict]:
    """
    Derive cycles from PeriodStartLogs.
    
    Cycle definition:
    - Cycle.start = PeriodStartLog[n].start_date
    - Cycle.length = PeriodStartLog[n+1].start_date - PeriodStartLog[n].start_date
    
    Only uses confirmed PeriodStartLogs (past dates).
    
    Args:
        user_id: User ID
    
    Returns:
        List of cycle dicts with: cycle_number, start_date, length
    """
    try:
        # Get confirmed PeriodStartLogs only (for cycle calculation)
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        if len(period_starts) < 2:
            return []
        
        cycles = []
        for i in range(len(period_starts) - 1):
            cycle_start = period_starts[i]["start_date"]
            next_cycle_start = period_starts[i + 1]["start_date"]
            
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
            
            # Only include valid cycle lengths (21-45 days per ACOG guidelines)
            # Very short cycles (< 21) are outliers (mistakes/fake logs)
            # Very long cycles (> 45) are irregular (gaps/skipped months)
            if MIN_CYCLE_DAYS <= cycle_length <= MAX_CYCLE_DAYS:
                cycles.append({
                    "cycle_number": len(period_starts) - i - 1,  # Most recent = 1
                    "start_date": cycle_start,
                    "length": cycle_length
                })
            else:
                # Store but mark as outlier/irregular
                cycles.append({
                    "cycle_number": len(period_starts) - i - 1,
                    "start_date": cycle_start,
                    "length": cycle_length,
                    "is_outlier": cycle_length < 15,
                    "is_irregular": cycle_length > 60
                })
        
        return cycles
    
    except Exception as e:
        print(f"Error deriving cycles from period starts: {str(e)}")
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
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        if not period_starts:
            return None
        
        # Get the most recent confirmed period start
        last_start = period_starts[-1]
        start_date = last_start["start_date"]
        
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


def validate_cycle_length(cycle_length: int) -> Dict[str, any]:
    """
    Validate and classify a cycle length per ACOG guidelines.
    
    Rules:
    - 21-45 days: Valid (included in averages) - ACOG normal range
    - < 21 days: Outlier (excluded from averages, likely mistake)
    - > 45 days: Irregular (excluded from averages, gap/skipped month)
    
    Args:
        cycle_length: Cycle length in days
    
    Returns:
        Dict with: is_valid, is_outlier, is_irregular, should_exclude_from_average
    """
    if cycle_length < MIN_CYCLE_DAYS:
        return {
            "is_valid": False,
            "is_outlier": True,
            "is_irregular": False,
            "should_exclude_from_average": True,
            "reason": f"Very short cycle (< {MIN_CYCLE_DAYS} days) - likely mistake or fake log"
        }
    elif cycle_length > MAX_CYCLE_DAYS:
        return {
            "is_valid": False,
            "is_outlier": False,
            "is_irregular": True,
            "should_exclude_from_average": True,
            "reason": f"Very long cycle (> {MAX_CYCLE_DAYS} days) - irregular, gap, or skipped month"
        }
    else:
        return {
            "is_valid": True,
            "is_outlier": False,
            "is_irregular": False,
            "should_exclude_from_average": False,
            "reason": "Normal cycle length (ACOG guidelines)"
        }
