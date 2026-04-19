"""
Auto-Close Logic for Periods

If a user forgets to click "Period Ended", the system automatically closes
periods that have been open for more than 10 days to prevent "runaway periods"
from breaking cycle statistics.

Threshold: If current_date > start_date + 10 days and end_date is still NULL:
Action: Auto-fill end_date with start_date + estimated_period_length (capped at resolved "today": client_today or IST fallback).

TODO: Move this job to a nightly Supabase Edge Function (or pg_cron) so period logging
requests avoid even this bounded round-trip; keep this module callable from the API for
immediate consistency when users log periods.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from cycle_utils import estimate_period_length
from database import supabase

logger = logging.getLogger(__name__)

THRESHOLD_DAYS = 10


def _apply_auto_close_batch(user_id: str, payloads: List[Dict[str, Any]]) -> None:
    """Single upsert round-trip when PostgREST merge is available; else per-row updates."""
    if not payloads:
        return
    try:
        supabase.table("period_logs").upsert(payloads, on_conflict="id").execute()
        return
    except Exception:
        logger.warning("Batch period_logs upsert failed; using per-row updates", exc_info=True)

    for row in payloads:
        try:
            supabase.table("period_logs").update(
                {"end_date": row["end_date"], "is_manual_end": row["is_manual_end"]}
            ).eq("id", row["id"]).eq("user_id", user_id).execute()
        except Exception:
            logger.exception("Per-row auto-close failed for period id=%s", row.get("id"))


def auto_close_open_periods(user_id: str, client_today_str: Optional[str] = None) -> List[Dict]:
    """
    Auto-close periods that have been open for more than THRESHOLD_DAYS days.

    Uses one batched upsert when possible to reduce DB round-trips (important when
    this runs on the request path). Safe to schedule via FastAPI BackgroundTasks only
    if callers do not depend on these rows being closed before subsequent queries in
    the same request (today /periods/log runs this before validation — keep that order).

    Returns:
        List of metadata dicts for periods that were auto-closed.
    """
    try:
        # Device-first, IST-fallback: this runs without client context, so rely on resolver.
        from cycle_utils import get_user_today

        today = get_user_today(client_today_str)
        open_periods = (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .is_("end_date", "null")
            .execute()
        )

        if not open_periods.data:
            return []

        estimated_len = estimate_period_length(user_id, normalized=True)
        estimated_days = int(round(max(3.0, min(8.0, estimated_len))))

        payloads: List[Dict[str, Any]] = []
        auto_closed_meta: List[Dict] = []

        for period in open_periods.data:
            start_date_str = period["date"]
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            days_open = (today - start_date_obj).days

            if days_open <= THRESHOLD_DAYS:
                continue

            auto_end_date = start_date_obj + timedelta(days=estimated_days - 1)
            if auto_end_date > today:
                auto_end_date = today
            if auto_end_date < start_date_obj:
                auto_end_date = start_date_obj

            end_str = auto_end_date.strftime("%Y-%m-%d")
            payloads.append(
                {
                    "id": period["id"],
                    "user_id": user_id,
                    "date": period["date"],
                    "end_date": end_str,
                    "is_manual_end": False,
                }
            )
            auto_closed_meta.append(
                {
                    "period_id": period["id"],
                    "start_date": start_date_str,
                    "auto_end_date": end_str,
                    "days_open": days_open,
                }
            )

        if not payloads:
            return []

        _apply_auto_close_batch(user_id, payloads)

        n = len(auto_closed_meta)
        logger.info("Auto-closed %d periods for user %s", n, user_id)
        return auto_closed_meta

    except Exception:
        logger.exception("Error auto-closing periods for user %s", user_id)
        return []
