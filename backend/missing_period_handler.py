"""
Missing Period Algorithm: late predicted starts without mutating phase tables.

If today is Predicted_Start + 4 days and no log exists in the expected bleed window:
- Expose a cumulative ``days_shifted`` (rate-limited) for callers to pass into
  ``calculate_phase_for_date_range(..., late_anchor_shift_days=...)``.
- Does not call ``store_cycle_phase_map`` or write ``user_cycle_days``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from database import async_supabase_call, supabase
from cycle_utils import estimate_period_length
from period_start_logs import get_period_start_logs

logger = logging.getLogger("periodcycle_ai.late_handler")

_SHIFT_GRACE_DAYS = 3  # shifting starts when days_late > this (i.e. >= 4)
_MAX_SHIFT_CAP = 60
_RATE_LIMIT_HOURS = 24


def _coerce_date(value: Union[str, date, datetime]) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if "T" in s:
            s = s.split("T", 1)[0]
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    raise TypeError(f"Unsupported date type: {type(value)!r}")


def _parse_last_shift_at(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _notification_timezone_lower(user_row: Dict[str, Any]) -> str:
    prefs = user_row.get("notification_preferences")
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}
    if not isinstance(prefs, dict):
        return ""
    return str(prefs.get("timezone") or "").lower()


def _us_supportive_messaging(user_row: Dict[str, Any]) -> bool:
    """Supportive US-style copy when language is English and tz looks US (e.g. America/Chicago for Austin)."""
    lang = str(user_row.get("language") or "en").lower()
    if not lang.startswith("en"):
        return False
    tz = _notification_timezone_lower(user_row)
    return tz.startswith("america/")


def _amenorrhea_message(days_late: int, us_supportive: bool) -> str:
    if us_supportive:
        return (
            f"It has been about {days_late} days since your predicted period start, and we have not seen a logged "
            "period in that window. This is not a diagnosis—bodies vary, and stress, travel, or other factors can "
            "affect timing. If you would like reassurance or next steps, consider chatting with our health assistant "
            "or reaching out to a clinician you trust when convenient."
        )
    return (
        f"It has been about {days_late} days since your predicted period start without a matching log in the "
        "expected window. This information is not a medical diagnosis. If you are concerned or this continues, "
        "consider speaking with a qualified healthcare professional when you are ready."
    )


def _desired_shift_days(days_late: int) -> int:
    if days_late <= _SHIFT_GRACE_DAYS:
        return 0
    return int(max(0, min(days_late - _SHIFT_GRACE_DAYS, _MAX_SHIFT_CAP)))


async def _fetch_parallel_inputs(user_id: str) -> Tuple[List[Dict], Any, Dict[str, Any]]:
    def _starts():
        return get_period_start_logs(user_id, confirmed_only=False)

    def _logs():
        return (
            supabase.table("period_logs")
            .select("date")
            .eq("user_id", user_id)
            .order("date")
            .execute()
        )

    def _user():
        return (
            supabase.table("users")
            .select(
                "late_period_anchor_shift_days, late_period_last_shift_at, language, notification_preferences"
            )
            .eq("id", user_id)
            .execute()
        )

    starts, logs_res, user_res = await asyncio.gather(
        async_supabase_call(_starts),
        async_supabase_call(_logs),
        async_supabase_call(_user),
    )
    user_row: Dict[str, Any] = {}
    if getattr(user_res, "data", None) and user_res.data:
        user_row = dict(user_res.data[0])
    return starts, logs_res, user_row


def _find_late_predicted_window(
    period_starts: List[Dict],
    period_log_dates: set,
    today: date,
    user_id: str,
) -> Optional[Tuple[date, int]]:
    """Returns (predicted_start_date, days_since_predicted) or None."""
    for start_log in sorted(period_starts, key=lambda x: x.get("start_date") or "", reverse=True):
        if start_log.get("is_confirmed") is not False:
            continue
        start_date_str = start_log.get("start_date")
        if not start_date_str:
            continue
        predicted_start = _coerce_date(start_date_str)
        days_since = (today - predicted_start).days
        if days_since < 4:
            continue

        period_length = estimate_period_length(user_id)
        period_length_days = int(round(max(3.0, min(8.0, period_length))))
        period_end = predicted_start + timedelta(days=period_length_days - 1)

        window_dates = set()
        d = predicted_start
        while d <= period_end:
            window_dates.add(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

        if not window_dates.intersection(period_log_dates):
            return predicted_start, days_since
    return None


async def _handle_missing_period_async(
    user_id: str,
    today: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not today:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_d = _coerce_date(today)

    try:
        period_starts, logs_res, user_row = await _fetch_parallel_inputs(user_id)
    except Exception:
        logger.exception("Missing period: failed to load inputs for user %s", user_id)
        return None

    log_rows = getattr(logs_res, "data", None) or []
    period_log_dates = set()
    for row in log_rows:
        ds = row.get("date")
        if ds:
            period_log_dates.add(str(ds)[:10])

    try:
        current_shift = int(max(0, user_row.get("late_period_anchor_shift_days") or 0))
    except (TypeError, ValueError):
        current_shift = 0

    if not period_starts:
        return None

    found = _find_late_predicted_window(period_starts, period_log_dates, today_d, user_id)
    if not found:
        return None

    most_recent_predicted, days_late = found
    desired_shift = _desired_shift_days(days_late)
    us_supportive = _us_supportive_messaging(user_row)

    base: Dict[str, Any] = {
        "is_late": days_late >= 14,
        "days_late": days_late,
        "days_shifted": current_shift,
        "predicted_start": most_recent_predicted.strftime("%Y-%m-%d"),
        "health_flag": "amenorrhea_risk" if days_late >= 14 else None,
    }

    if days_late >= 14:
        base["action"] = "mark_late"
        base["message"] = _amenorrhea_message(days_late, us_supportive)
        base["days_shifted"] = current_shift
        return base

    # 4 <= days_late < 14: eligible for at-most-once-per-24h increment toward desired_shift
    base["action"] = "shift_forward"
    new_predicted = most_recent_predicted + timedelta(days=1)
    base["new_predicted_start"] = new_predicted.strftime("%Y-%m-%d")

    if desired_shift <= current_shift:
        base["days_shifted"] = current_shift
        base["message"] = (
            f"Period is about {days_late} days after the predicted start; "
            "predictions are already shifted as far as the current schedule allows."
        )
        return base

    last_shift_at = _parse_last_shift_at(user_row.get("late_period_last_shift_at"))
    now = datetime.now(timezone.utc)
    if last_shift_at and (now - last_shift_at) < timedelta(hours=_RATE_LIMIT_HOURS):
        base["days_shifted"] = current_shift
        base["message"] = (
            f"Period is about {days_late} days late. An extra calendar shift will be available after the 24-hour cooldown."
        )
        return base

    new_shift = current_shift + 1
    try:
        await async_supabase_call(
            lambda: supabase.table("users")
            .update(
                {
                    "late_period_anchor_shift_days": new_shift,
                    "late_period_last_shift_at": now.isoformat(),
                }
            )
            .eq("id", user_id)
            .execute()
        )
    except Exception:
        logger.exception("Missing period: failed to persist shift for user %s", user_id)
        base["days_shifted"] = current_shift
        base["message"] = "Period is late; could not update shift schedule. Please try again later."
        return base

    base["days_shifted"] = new_shift
    base["message"] = (
        f"Period is about {days_late} days late. Nudging the predicted calendar forward by one day "
        f"(total shift now {new_shift} day(s))."
    )
    logger.info(
        "Late period shift incremented for user %s: %s -> %s (days_late=%s)",
        user_id,
        current_shift,
        new_shift,
        days_late,
    )
    return base


def handle_missing_period(user_id: str, today: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Sync entrypoint (e.g. cycle_stats). Uses asyncio when no loop is running; otherwise runs in a dedicated loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_handle_missing_period_async(user_id, today))

    # Called from within a running event loop (rare for current callers)
    new_loop = asyncio.new_event_loop()
    try:
        return new_loop.run_until_complete(_handle_missing_period_async(user_id, today))
    finally:
        new_loop.close()


async def handle_missing_period_async(
    user_id: str,
    today: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Async entrypoint for FastAPI handlers."""
    return await _handle_missing_period_async(user_id, today)
