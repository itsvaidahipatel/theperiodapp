"""
Luteal phase learning from confirmed PeriodEvents.

⚠️ CRITICAL: Only compute observed luteal when:
1. Two confirmed PeriodEvents exist
2. Ovulation was predicted BEFORE the new period log
3. The ovulation prediction was high confidence (ovulation_sd <= 1.5)

This prevents training on:
- Shifted predictions from partial updates
- Low-confidence ovulation predictions
- Stress cycles, PCOS patterns, anovulatory cycles
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Optional, Tuple, Union

from cycle_utils import estimate_luteal, predict_ovulation, update_luteal_estimate
from period_start_logs import get_period_start_logs

logger = logging.getLogger("periodcycle_ai.luteal")

# Short inter-bleed intervals are often anovulatory or unreliable for luteal inference.
_MIN_CYCLE_DAYS_FOR_LUTEAL_LEARNING = 21


def _coerce_period_datetime(value: Union[str, date, datetime]) -> datetime:
    """Normalize period dates from API/DB (str, date, or datetime) to midnight UTC-naive datetime."""
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        s = value.strip()
        if "T" in s:
            s = s.split("T", 1)[0]
        return datetime.strptime(s[:10], "%Y-%m-%d")
    raise TypeError(f"Unsupported period date type: {type(value)!r}")


def compute_observed_luteal_from_confirmed_cycles(
    user_id: str,
    new_period_start: Union[str, date, datetime],
) -> Optional[Tuple[float, float]]:
    """
    Compute observed luteal length from confirmed cycles only.

    ⚠️ CRITICAL RULES:
    1. Only compute if we have at least 2 confirmed PeriodEvents
    2. Only use ovulation that was predicted BEFORE the new period log
    3. Only use high-confidence ovulation predictions (ovulation_sd <= 1.5)

    Returns:
        Tuple of (observed_luteal rounded to 1 decimal, ovulation_sd) if valid, None otherwise.
    """
    try:
        confirmed_starts = get_period_start_logs(user_id, confirmed_only=True)

        if len(confirmed_starts) < 2:
            logger.debug(
                "Need at least 2 confirmed period starts to compute observed luteal (have %s)",
                len(confirmed_starts),
            )
            return None

        previous_period_start = confirmed_starts[-2]["start_date"]
        next_period_start = confirmed_starts[-1]["start_date"]

        prev_start = _coerce_period_datetime(previous_period_start)
        new_start = _coerce_period_datetime(new_period_start)
        next_start = _coerce_period_datetime(next_period_start)

        prior_interval_days = (next_start - prev_start).days
        closing_interval_days = (new_start - next_start).days

        if prior_interval_days <= 0 or closing_interval_days <= 0:
            logger.warning(
                "Skipping luteal learning: non-positive interval (prior=%s closing=%s)",
                prior_interval_days,
                closing_interval_days,
            )
            return None

        if prior_interval_days < _MIN_CYCLE_DAYS_FOR_LUTEAL_LEARNING:
            logger.info(
                "Skipping luteal learning: prior confirmed cycle length %s days <%s (anovulatory/unreliable)",
                prior_interval_days,
                _MIN_CYCLE_DAYS_FOR_LUTEAL_LEARNING,
            )
            return None

        if closing_interval_days < _MIN_CYCLE_DAYS_FOR_LUTEAL_LEARNING:
            logger.info(
                "Skipping luteal learning: closing cycle length %s days <%s (anovulatory/unreliable)",
                closing_interval_days,
                _MIN_CYCLE_DAYS_FOR_LUTEAL_LEARNING,
            )
            return None

        cycle_length = prior_interval_days

        luteal_mean, luteal_sd = estimate_luteal(user_id)

        prev_start_str = prev_start.strftime("%Y-%m-%d")

        predicted_ov_date_str, ovulation_sd, _ = predict_ovulation(
            prev_start_str,
            float(cycle_length),
            luteal_mean,
            luteal_sd,
            cycle_start_sd=None,
            user_id=user_id,
        )

        predicted_ov_date = datetime.strptime(predicted_ov_date_str, "%Y-%m-%d")
        observed_luteal = round(float((new_start - predicted_ov_date).days), 1)

        if 10 <= observed_luteal <= 18:
            confidence_threshold = 1.5
            if ovulation_sd <= confidence_threshold:
                return (observed_luteal, ovulation_sd)
            logger.info(
                "Skipped luteal learning: low confidence ovulation prediction (ovulation_sd=%.2f > %s)",
                ovulation_sd,
                confidence_threshold,
            )
            return None

        logger.info(
            "Skipped luteal learning: observed_luteal=%s days outside valid range (10-18 days)",
            observed_luteal,
        )
        return None

    except Exception:
        logger.exception("Error computing observed luteal from confirmed cycles")
        return None


def _learn_luteal_from_new_period_impl(
    user_id: str,
    new_period_start: Union[str, date, datetime],
) -> None:
    result = compute_observed_luteal_from_confirmed_cycles(user_id, new_period_start)

    if not result:
        logger.debug(
            "Skipped luteal learning for user %s (insufficient data, short cycle, low confidence, or bounds)",
            user_id,
        )
        return

    observed_luteal, ovulation_sd = result
    luteal_mean, _ = estimate_luteal(user_id)

    if round(float(luteal_mean), 1) == observed_luteal:
        logger.debug(
            "Skipping luteal DB update: observed %s matches current luteal_mean",
            observed_luteal,
        )
        return

    update_luteal_estimate(user_id, observed_luteal, has_markers=False)
    logger.info(
        "Learned luteal length: %s days (ovulation_sd=%.2f)",
        observed_luteal,
        ovulation_sd,
    )


def learn_luteal_from_new_period(
    user_id: str,
    new_period_start: Union[str, date, datetime],
) -> None:
    """
    Learn luteal phase length from a new period log (blocking).

    Safe to schedule with FastAPI ``BackgroundTasks``; Starlette runs sync callables in a thread pool.
    For async routes that prefer ``asyncio``, use ``learn_luteal_from_new_period_async``.
    """
    try:
        _learn_luteal_from_new_period_impl(user_id, new_period_start)
    except Exception:
        logger.exception("Error learning luteal from new period")


async def learn_luteal_from_new_period_async(
    user_id: str,
    new_period_start: Union[str, date, datetime],
) -> None:
    """Non-blocking wrapper: runs luteal learning in a worker thread."""
    try:
        await asyncio.to_thread(_learn_luteal_from_new_period_impl, user_id, new_period_start)
    except Exception:
        logger.exception("Error learning luteal from new period (async)")
