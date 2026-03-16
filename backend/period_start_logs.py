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


def _generate_and_save_cycle_data_json(user_id: str, cycle_start_str: str, cycle_end_str: str, period_logs: List[Dict]) -> bool:
    """
    Generate phase mappings for a completed cycle and save to period_start_logs.cycle_data_json.
    IMMUTABLE: Only writes when cycle_data_json is null; never overwrites existing.
    """
    try:
        from cycle_utils import calculate_phase_for_date_range

        # Get period_logs for the cycle date range
        start_dt = datetime.strptime(cycle_start_str, "%Y-%m-%d").date()
        end_dt = datetime.strptime(cycle_end_str, "%Y-%m-%d").date()
        cycle_length_days = (end_dt - start_dt).days
        last_day_of_cycle = (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")  # Cycle ends day before next period

        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=cycle_start_str,
            cycle_length=cycle_length_days,
            period_logs=period_logs,
            start_date=cycle_start_str,
            end_date=last_day_of_cycle,
        )
        if not phase_mappings:
            return False

        # Store as JSON array; add is_predicted=False for actual/stored phases
        cycle_data = []
        for m in phase_mappings:
            entry = dict(m)
            entry["is_predicted"] = False
            cycle_data.append(entry)

        client = supabase_admin if supabase_admin else supabase
        # Only update if cycle_data_json is currently null (immutable - never overwrite)
        r = client.table("period_start_logs").update({
            "cycle_data_json": cycle_data,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("user_id", user_id).eq("start_date", cycle_start_str).is_("cycle_data_json", "null").execute()

        updated = r.data and len(r.data) > 0
        if updated:
            print(f"✅ Saved cycle_data_json for cycle {cycle_start_str}→{cycle_end_str} ({len(cycle_data)} days)")
        return bool(updated)
    except Exception as e:
        print(f"⚠️ Failed to generate cycle_data_json: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_period_start_logs_from_period_logs(user_id: str) -> List[Dict]:
    """
    Sync PeriodStartLogs from period_logs.
    
    IMMUTABLE PAST: Preserves existing cycle_data_json. Uses delete+insert but restores
    cycle_data_json after insert. For newly completed cycles (no stored cycle_data_json),
    generates and saves phase mappings.
    
    Rules:
    - One log = one cycle start
    - cycle_data_json is NEVER overwritten once set
    - New period = generate cycle_data_json for the completed cycle only
    """
    try:
        logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date").execute()
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
                    except Exception:
                        continue

        start_dates = sorted(set(start_dates))
        today = datetime.now().date()
        client = supabase_admin if supabase_admin else supabase

        # 1) Before delete: preserve cycle_data_json for existing records
        preserved = {}
        try:
            existing = client.table("period_start_logs").select("start_date, cycle_data_json").eq("user_id", user_id).execute()
            for row in (existing.data or []):
                sd = row.get("start_date")
                if sd and row.get("cycle_data_json") is not None:
                    preserved[str(sd)] = row["cycle_data_json"]
        except Exception:
            pass

        # 2) Delete and rebuild
        print(f"🔄 Syncing period_start_logs for user {user_id}")
        try:
            client.table("period_start_logs").delete().eq("user_id", user_id).execute()
        except Exception as delete_error:
            print(f"⚠️ Warning: Error deleting (non-fatal): {str(delete_error)}")

        result = []
        if start_dates:
            insert_data = []
            for start_date in start_dates:
                sd_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)
                insert_data.append({
                    "user_id": user_id,
                    "start_date": sd_str,
                    "is_confirmed": start_date <= today,
                })
            insert_response = client.table("period_start_logs").insert(insert_data).execute()
            inserted = insert_response.data if insert_response.data else insert_data
            result = [{"start_date": r.get("start_date"), "is_confirmed": r.get("is_confirmed", True)} for r in inserted]
            print(f"✅ period_start_logs synced: {len(inserted)} records")

            # 3) Restore cycle_data_json for records that had it (immutable past)
            for row in inserted:
                sd = row.get("start_date")
                if sd and sd in preserved:
                    try:
                        client.table("period_start_logs").update({
                            "cycle_data_json": preserved[sd],
                            "updated_at": datetime.utcnow().isoformat()
                        }).eq("user_id", user_id).eq("start_date", sd).execute()
                    except Exception:
                        pass

            # 4) Generate cycle_data_json for newly completed cycles (no stored data)
            logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date").execute()
            period_logs_full = logs_response.data or []
            for i in range(len(start_dates) - 1):
                prev_str = start_dates[i].strftime("%Y-%m-%d")
                curr_str = start_dates[i + 1].strftime("%Y-%m-%d")
                if prev_str not in preserved:
                    _generate_and_save_cycle_data_json(user_id, prev_str, curr_str, period_logs_full)
        else:
            print(f"✅ period_start_logs synced: 0 records")

        return result
    
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
        return []


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


def get_cycles_from_period_starts(user_id: str, period_starts: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Derive cycles from PeriodStartLogs.
    
    Cycle definition:
    - Cycle.start = PeriodStartLog[n].start_date
    - Cycle.length = PeriodStartLog[n+1].start_date - PeriodStartLog[n].start_date
    
    Only uses confirmed PeriodStartLogs (past dates).
    
    Args:
        user_id: User ID
        period_starts: Optional pre-fetched list (e.g. from sync return). If provided, used instead of DB. Filtered by is_confirmed=True.
    
    Returns:
        List of cycle dicts with: cycle_number, start_date, length
    """
    try:
        if period_starts is not None:
            period_starts = [p for p in period_starts if p.get("is_confirmed", True)]
        else:
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
