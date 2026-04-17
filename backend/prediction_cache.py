"""
Prediction cache management.

user_cycle_days is treated as a cache that can be fully regenerated.
This module handles cache invalidation and regeneration using async I/O so
API handlers stay responsive.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database import async_supabase_call, supabase
from period_start_logs import get_last_confirmed_period_start
from cycle_utils import calculate_phase_for_date_range

logger = logging.getLogger("periodcycle_ai.cache")


async def get_first_logged_period_date(user_id: str) -> Optional[str]:
    """
    Get the first (earliest) logged period date for a user.
    """

    def _fetch() -> Optional[str]:
        period_logs_response = (
            supabase.table("period_logs")
            .select("date")
            .eq("user_id", user_id)
            .order("date", desc=False)
            .limit(1)
            .execute()
        )
        if period_logs_response.data and len(period_logs_response.data) > 0:
            first_date = period_logs_response.data[0]["date"]
            return first_date if isinstance(first_date, str) else first_date.strftime("%Y-%m-%d")
        return None

    try:
        return await async_supabase_call(_fetch)
    except Exception:
        logger.exception("Error getting first logged period date")
        return None


async def cleanup_predictions_before_first_period(user_id: str) -> None:
    """
    Delete all predictions that are earlier than the first logged period date.
    """

    first_period_date = await get_first_logged_period_date(user_id)
    if not first_period_date:
        logger.info("No logged periods found; skipping cleanup before first period")
        return

    def _delete():
        return supabase.table("user_cycle_days").delete().eq("user_id", user_id).lt("date", first_period_date).execute()

    try:
        await async_supabase_call(_delete)
        logger.info("Cleaned up predictions before first logged period (%s)", first_period_date)
    except Exception:
        logger.exception("Error cleaning up predictions before first period")


async def invalidate_predictions_after_period(user_id: str, period_start_date: Optional[str] = None) -> None:
    """
    Invalidate (delete) cached user_cycle_days on/after a period start (or all if no anchor).
    """

    if not period_start_date:
        period_start_date = await asyncio.to_thread(get_last_confirmed_period_start, user_id)

    try:
        if not period_start_date:

            def _delete_all():
                return supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()

            await async_supabase_call(_delete_all)
            logger.warning("No confirmed period anchor; deleted all user_cycle_days cache rows")
            return

        def _delete_from():
            return (
                supabase.table("user_cycle_days")
                .delete()
                .eq("user_id", user_id)
                .gte("date", period_start_date)
                .execute()
            )

        await async_supabase_call(_delete_from)
        logger.info("Invalidated user_cycle_days cache from %s onward", period_start_date)
    except Exception:
        logger.exception("Error invalidating predictions after period")


async def hard_invalidate_predictions_from_date(user_id: str, invalidation_date: str) -> Dict[str, Any]:
    """
    HARD INVALIDATION: Delete ALL user_cycle_days rows with date >= invalidation_date.

    Clears the cache immediately when hard data (e.g. a logged period) supersedes predictions
    — fixes "ghost cycles" when a period is logged earlier than predicted.

    Returns:
        {
          "cache_invalidated": bool,
          "invalidation_date": str,
          "deleted_count": int,
        }
    """
    try:

        def _delete():
            return (
                supabase.table("user_cycle_days")
                .delete()
                .eq("user_id", user_id)
                .gte("date", invalidation_date)
                .execute()
            )

        deleted = await async_supabase_call(_delete)
        deleted_count = len(deleted.data) if getattr(deleted, "data", None) else 0
        if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
            logger.debug(
                "Hard invalidation: removed %s rows from %s (user_id=%s)",
                deleted_count,
                invalidation_date,
                user_id,
            )
        else:
            logger.info(
                "Hard invalidation: removed %s cache rows from %s onward",
                deleted_count,
                invalidation_date,
            )
        logger.debug(
            "Ghost-cycle guard: cache cleared from logged date so phases can be recomputed statelessly"
        )
        return {
            "cache_invalidated": True,
            "invalidation_date": invalidation_date,
            "deleted_count": deleted_count,
        }
    except Exception:
        logger.exception("hard_invalidate_predictions_from_date failed")
        return {
            "cache_invalidated": False,
            "invalidation_date": invalidation_date,
            "deleted_count": 0,
        }


async def regenerate_predictions_from_last_confirmed_period(user_id: str, days_ahead: int = 180) -> None:
    """
    Regenerate cached phase rows from first logged month through today + days_ahead.

    CPU-heavy phase calculation and optional cache writes run in worker threads so the
    event loop is not blocked (schedule via asyncio.create_task from routes).

    Args:
        user_id: User ID
        days_ahead: Days ahead from today to generate (default 180 ≈ 6 months)
    """
    try:
        first_period_date = await get_first_logged_period_date(user_id)
        if not first_period_date:
            logger.info("No logged periods; skip prediction regeneration")
            return

        await cleanup_predictions_before_first_period(user_id)

        last_confirmed_start = await asyncio.to_thread(get_last_confirmed_period_start, user_id)
        if not last_confirmed_start:
            logger.info("No confirmed period start; skip prediction regeneration")
            return

        def _fetch_user():
            return (
                supabase.table("users")
                .select("last_period_date, cycle_length, late_period_anchor_shift_days")
                .eq("id", user_id)
                .execute()
            )

        user_response = await async_supabase_call(_fetch_user)
        if not user_response.data:
            logger.info("No user row; skip prediction regeneration")
            return

        user_data = user_response.data[0]
        cycle_length = user_data.get("cycle_length", 28)
        try:
            late_shift = int(max(0, user_data.get("late_period_anchor_shift_days") or 0))
        except (TypeError, ValueError):
            late_shift = 0

        first_period_dt = datetime.strptime(first_period_date, "%Y-%m-%d")
        today = datetime.now(timezone.utc)
        start_date_obj = first_period_dt.replace(day=1)
        start_date = start_date_obj.strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
            logger.debug(
                "Regenerating prediction cache %s → %s (user_id=%s, days_ahead=%s)",
                start_date,
                end_date,
                user_id,
                days_ahead,
            )
        else:
            logger.info("Regenerating prediction cache %s → %s (days_ahead=%s)", start_date, end_date, days_ahead)

        def _compute():
            return calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=last_confirmed_start,
                cycle_length=int(cycle_length),
                period_logs=[],
                start_date=start_date,
                end_date=end_date,
                late_anchor_shift_days=late_shift,
            )

        phase_mappings = await asyncio.to_thread(_compute)

        if phase_mappings:
            from cycle_utils import store_cycle_phase_map

            await asyncio.to_thread(
                store_cycle_phase_map,
                user_id,
                phase_mappings,
                False,
            )
            logger.info("Regenerated %s prediction rows for cache merge", len(phase_mappings))
        else:
            logger.info("No phase mappings produced for cache regeneration")
    except Exception:
        logger.exception("Background prediction regeneration failed")


def schedule_regenerate_predictions(user_id: str, days_ahead: int = 180) -> None:
    """
    Fire-and-forget regeneration so HTTP handlers return immediately.
    Safe to call from an async FastAPI route (uses running loop).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(regenerate_predictions_from_last_confirmed_period(user_id, days_ahead))
        return
    loop.create_task(regenerate_predictions_from_last_confirmed_period(user_id, days_ahead))
