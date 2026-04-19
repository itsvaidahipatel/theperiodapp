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

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import supabase, supabase_admin

logger = logging.getLogger("periodcycle_ai.start_logs")

# ACOG Guidelines - Standard cycle length range
MIN_CYCLE_DAYS = 21
MAX_CYCLE_DAYS = 45


def _log_user_id_safe(msg: str, user_id: str, *args: Any) -> None:
    """Log with user_id only when LOG_LEVEL=DEBUG (privacy)."""
    if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
        logger.debug(msg, user_id, *args)
    else:
        logger.info(msg.replace("%s", "").strip() or msg, *args)


def _build_cycle_data_json_payload(
    user_id: str, cycle_start_str: str, cycle_end_str: str, period_logs: List[Dict]
) -> Optional[List[Dict]]:
    """
    Build phase rows for a completed cycle (no database writes).
    cycle_end_str is the next period start (exclusive end of this cycle).
    """
    try:
        from cycle_utils import calculate_phase_for_date_range

        start_dt = datetime.strptime(cycle_start_str, "%Y-%m-%d").date()
        end_dt = datetime.strptime(cycle_end_str, "%Y-%m-%d").date()
        cycle_length_days = (end_dt - start_dt).days
        last_day_of_cycle = (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        phase_mappings = calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=cycle_start_str,
            cycle_length=cycle_length_days,
            period_logs=period_logs,
            start_date=cycle_start_str,
            end_date=last_day_of_cycle,
            late_anchor_shift_days=0,
        )
        if not phase_mappings:
            return None

        cycle_data: List[Dict] = []
        for m in phase_mappings:
            entry = dict(m)
            entry["is_predicted"] = False
            cycle_data.append(entry)
        return cycle_data
    except Exception:
        logger.exception("Failed to build cycle_data_json payload for cycle starting %s", cycle_start_str)
        return None


def sync_period_start_logs_from_period_logs(user_id: str) -> List[Dict]:
    """
    Sync PeriodStartLogs from period_logs.

    IMMUTABLE PAST: Preserves existing cycle_data_json in the insert payload (no per-row updates).
    For newly completed cycles (no stored cycle_data_json), phase JSON is generated in memory
    and included in a single batch insert.

    Rules:
    - One log = one cycle start
    - cycle_data_json is NEVER overwritten once set (re-applied from preserved snapshot on sync)
    - New period = generate cycle_data_json for the completed cycle only
    """
    try:
        logs_response = (
            supabase.table("period_logs")
            .select("date, end_date")
            .eq("user_id", user_id)
            .order("date")
            .execute()
        )
        period_logs_full: List[Dict] = logs_response.data or []

        start_dates: List[Any] = []
        seen_dates = set()
        for log in period_logs_full:
            date_str = log.get("date")
            if date_str and date_str not in seen_dates:
                try:
                    date_obj = (
                        datetime.strptime(date_str, "%Y-%m-%d").date()
                        if isinstance(date_str, str)
                        else date_str
                    )
                    start_dates.append(date_obj)
                    seen_dates.add(date_str)
                except Exception:
                    continue

        start_dates = sorted(set(start_dates))
        # Naive-date model: treat stored YYYY-MM-DD strings as absolute truth.
        # When deciding confirmed/past vs future, use IST as the default calendar day
        # (or client-provided today via higher-level routes).
        ist = timezone(timedelta(hours=5, minutes=30))
        today = datetime.now(ist).date()
        client = supabase_admin if supabase_admin else supabase

        preserved: Dict[str, Any] = {}
        preserved_outlier: Dict[str, bool] = {}
        try:
            existing = (
                client.table("period_start_logs")
                .select("start_date, cycle_data_json, is_outlier")
                .eq("user_id", user_id)
                .execute()
            )
            for row in existing.data or []:
                sd = row.get("start_date")
                if not sd:
                    continue
                sd = str(sd)
                if row.get("cycle_data_json") is not None:
                    preserved[sd] = row["cycle_data_json"]
                if row.get("is_outlier"):
                    preserved_outlier[sd] = True
        except Exception:
            logger.exception("Could not read existing period_start_logs for preserve pass")

        if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
            logger.debug("Syncing period_start_logs for user_id=%s", user_id)
        else:
            logger.info("Syncing period_start_logs from period_logs")

        try:
            client.table("period_start_logs").delete().eq("user_id", user_id).execute()
        except Exception:
            logger.warning("period_start_logs delete failed (non-fatal)", exc_info=True)

        result: List[Dict] = []
        if not start_dates:
            logger.info("period_start_logs synced: 0 records")
            return result

        insert_data: List[Dict[str, Any]] = []
        for idx, start_date in enumerate(start_dates):
            sd_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
            row: Dict[str, Any] = {
                "user_id": user_id,
                "start_date": sd_str,
                "is_confirmed": start_date <= today,
                "is_outlier": bool(preserved_outlier.get(sd_str, False)),
            }
            if sd_str in preserved:
                row["cycle_data_json"] = preserved[sd_str]
            elif idx < len(start_dates) - 1:
                next_str = start_dates[idx + 1].strftime("%Y-%m-%d")
                if sd_str not in preserved:
                    payload = _build_cycle_data_json_payload(user_id, sd_str, next_str, period_logs_full)
                    if payload is not None:
                        row["cycle_data_json"] = payload
            insert_data.append(row)

        insert_response = client.table("period_start_logs").insert(insert_data).execute()
        inserted = insert_response.data if insert_response.data else insert_data
        result = [
            {
                "start_date": r.get("start_date"),
                "is_confirmed": r.get("is_confirmed", True),
                "is_outlier": bool(r.get("is_outlier", False)),
            }
            for r in inserted
        ]
        logger.info("period_start_logs synced: %s records", len(inserted))

        return result

    except Exception as e:
        error_msg = str(e)
        if "42501" in error_msg or "row-level security" in error_msg.lower():
            logger.error(
                "RLS error syncing period_start_logs; service role may be required: %s",
                error_msg,
            )
            if not supabase_admin:
                logger.error("SUPABASE_SERVICE_ROLE_KEY is not configured")
        else:
            logger.exception("Error syncing period start logs: %s", error_msg)
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

    except Exception:
        logger.exception("Error getting period start logs")
        return []


def get_cycles_from_period_starts(user_id: str, period_starts: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Derive cycles from PeriodStartLogs.

    Cycle definition:
    - Cycle.start = PeriodStartLog[n].start_date
    - Cycle.length = PeriodStartLog[n+1].start_date - PeriodStartLog[n].start_date

    Only uses confirmed PeriodStartLogs (past dates).
    Database ``is_outlier`` on the cycle start row is always honored for stats (Bayesian / means).

    Args:
        user_id: User ID
        period_starts: Optional pre-fetched list (e.g. from sync return). If provided, used instead of DB. Filtered by is_confirmed=True.

    Returns:
        List of cycle dicts with: cycle_number, start_date, length, is_outlier, optional is_irregular, reason
    """
    try:
        if period_starts is not None:
            period_starts = [p for p in period_starts if p.get("is_confirmed", True)]
        else:
            period_starts = get_period_start_logs(user_id, confirmed_only=True)

        if len(period_starts) < 2:
            return []

        cycles: List[Dict] = []
        for i in range(len(period_starts) - 1):
            cycle_start = period_starts[i]["start_date"]
            next_cycle_start = period_starts[i + 1]["start_date"]

            if isinstance(cycle_start, str):
                cycle_start_date = datetime.strptime(cycle_start, "%Y-%m-%d").date()
            else:
                cycle_start_date = cycle_start

            if isinstance(next_cycle_start, str):
                next_cycle_start_date = datetime.strptime(next_cycle_start, "%Y-%m-%d").date()
            else:
                next_cycle_start_date = next_cycle_start

            cycle_length = (next_cycle_start_date - cycle_start_date).days

            start_meta = period_starts[i] if isinstance(period_starts[i], dict) else {}
            db_outlier = bool(start_meta.get("is_outlier", False))

            if MIN_CYCLE_DAYS <= cycle_length <= MAX_CYCLE_DAYS:
                reason: Optional[str] = None
                if db_outlier:
                    reason = (
                        "Flagged outlier in cycle history; length is within ACOG typical range (21–45 days) "
                        "but excluded from typical-cycle averaging."
                    )
                cycles.append(
                    {
                        "cycle_number": len(period_starts) - i - 1,
                        "start_date": cycle_start,
                        "length": cycle_length,
                        "is_outlier": db_outlier,
                        "is_irregular": False,
                        "reason": reason,
                    }
                )
            elif cycle_length < MIN_CYCLE_DAYS:
                cycles.append(
                    {
                        "cycle_number": len(period_starts) - i - 1,
                        "start_date": cycle_start,
                        "length": cycle_length,
                        "is_outlier": db_outlier or True,
                        "is_irregular": False,
                        "reason": f"Cycle < {MIN_CYCLE_DAYS} days (below ACOG typical minimum for a single cycle interval).",
                    }
                )
            else:
                cycles.append(
                    {
                        "cycle_number": len(period_starts) - i - 1,
                        "start_date": cycle_start,
                        "length": cycle_length,
                        "is_outlier": db_outlier,
                        "is_irregular": True,
                        "reason": f"Cycle > {MAX_CYCLE_DAYS} days (above ACOG typical upper bound; may reflect delayed ovulation, gap in logging, or amenorrhea workup threshold).",
                    }
                )

        return cycles

    except Exception:
        logger.exception("Error deriving cycles from period starts")
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

        last_start = period_starts[-1]
        start_date = last_start["start_date"]

        if isinstance(start_date, str):
            return start_date
        if hasattr(start_date, "strftime"):
            return start_date.strftime("%Y-%m-%d")
        return str(start_date)

    except Exception:
        logger.exception("Error getting last confirmed period start")
        return None


def validate_cycle_length(cycle_length: int) -> Dict[str, Any]:
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
            "reason": f"Very short cycle (< {MIN_CYCLE_DAYS} days) - likely mistake or fake log",
        }
    if cycle_length > MAX_CYCLE_DAYS:
        return {
            "is_valid": False,
            "is_outlier": False,
            "is_irregular": True,
            "should_exclude_from_average": True,
            "reason": f"Very long cycle (> {MAX_CYCLE_DAYS} days) - irregular, gap, or skipped month",
        }
    return {
        "is_valid": True,
        "is_outlier": False,
        "is_irregular": False,
        "should_exclude_from_average": False,
        "reason": "Normal cycle length (ACOG guidelines)",
    }
