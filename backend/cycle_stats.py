"""
Cycle statistics computation from PeriodStartLogs.

Cycles are derived from PeriodStartLogs, never stored permanently.
This module computes cycle statistics (mean, SD, variance) from PeriodStartLogs.

DESIGN: One log = one cycle start
Cycle length = gap between consecutive period starts
"""

import logging
import math
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Dict, List, Optional

from cycle_utils import calculate_phase_for_date_range, get_phase_bounds_for_dots, group_logs_into_episodes
from database import supabase
from period_service import (
    MIN_CYCLE_DAYS,
    MAX_CYCLE_DAYS,
    calculate_prediction_confidence,
    calculate_rolling_average,
    calculate_rolling_period_length,
)
from period_start_logs import get_cycles_from_period_starts, get_period_start_logs

logger = logging.getLogger("periodcycle_ai.stats")

# Population prior for short histories (conservative; ACOG-typical ~28 d cycle)
POPULATION_PRIOR_MEAN = 28.0
POPULATION_PRIOR_SD = 2.0


def compute_cycle_stats_from_period_starts(user_id: str, period_starts: Optional[List] = None) -> Dict:
    """
    Compute cycle statistics from PeriodStartLogs.

    With fewer than 3 valid cycles, blends observed lengths with a population prior (28 ± 2 d)
    so downstream means/SDs are conservative before strict outlier-style inference applies.
    """
    try:
        cycles = get_cycles_from_period_starts(user_id, period_starts=period_starts)

        if not cycles or len(cycles) < 1:
            return {
                "cycle_length_mean": POPULATION_PRIOR_MEAN,
                "cycle_length_sd": POPULATION_PRIOR_SD,
                "cycle_length_variance": POPULATION_PRIOR_SD**2,
                "cycle_count": 0,
                "cycle_lengths": [],
                "outlier_count": 0,
                "irregular_count": 0,
            }

        valid_cycles = [
            c
            for c in cycles
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS and not c.get("is_outlier", False)
        ]
        outliers = [c for c in cycles if c.get("is_outlier", False) or c["length"] < MIN_CYCLE_DAYS]
        irregular = [c for c in cycles if c.get("is_irregular", False) or c["length"] > MAX_CYCLE_DAYS]

        cycle_lengths = [c["length"] for c in valid_cycles]
        n = len(cycle_lengths)

        if n == 0:
            return {
                "cycle_length_mean": POPULATION_PRIOR_MEAN,
                "cycle_length_sd": POPULATION_PRIOR_SD,
                "cycle_length_variance": POPULATION_PRIOR_SD**2,
                "cycle_count": 0,
                "cycle_lengths": [],
                "outlier_count": len(outliers),
                "irregular_count": len(irregular),
            }

        mean_raw = sum(cycle_lengths) / n

        if n < 3:
            k_prior = 3 - n
            mean = (sum(cycle_lengths) + POPULATION_PRIOR_MEAN * k_prior) / (n + k_prior)
            if n > 1:
                variance_sample = sum((x - mean_raw) ** 2 for x in cycle_lengths) / (n - 1)
                sd = max(math.sqrt(variance_sample), POPULATION_PRIOR_SD * 0.5)
                variance = sd**2
            else:
                sd = POPULATION_PRIOR_SD
                variance = POPULATION_PRIOR_SD**2
        else:
            mean = mean_raw
            # Mathematical safety: sample variance is only defined for n > 1.
            # When only one cycle exists, default to conservative population prior.
            if n > 1:
                variance = sum((x - mean) ** 2 for x in cycle_lengths) / (n - 1)
                sd = math.sqrt(variance)
            else:
                sd = POPULATION_PRIOR_SD
                variance = POPULATION_PRIOR_SD**2

        return {
            "cycle_length_mean": mean,
            "cycle_length_sd": sd,
            "cycle_length_variance": variance,
            "cycle_count": n,
            "cycle_lengths": cycle_lengths,
            "outlier_count": len(outliers),
            "irregular_count": len(irregular),
        }

    except Exception:
        logger.exception("Error computing cycle stats from period starts")
        return {
            "cycle_length_mean": POPULATION_PRIOR_MEAN,
            "cycle_length_sd": POPULATION_PRIOR_SD,
            "cycle_length_variance": POPULATION_PRIOR_SD**2,
            "cycle_count": 0,
            "cycle_lengths": [],
            "outlier_count": 0,
            "irregular_count": 0,
        }


def update_user_cycle_stats(user_id: str, period_starts: Optional[List] = None) -> None:
    """Update user's cycle_length in users table based on PeriodStartLogs."""
    try:
        from cycle_utils import update_cycle_length_bayesian

        stats = compute_cycle_stats_from_period_starts(user_id, period_starts=period_starts)

        if stats["cycle_count"] > 0:
            mean_cycle_length = int(round(stats["cycle_length_mean"]))
            update_cycle_length_bayesian(user_id, mean_cycle_length)
            logger.info(
                "Updated cycle_length from PeriodStartLogs: %s days (%s valid cycles)",
                mean_cycle_length,
                stats["cycle_count"],
            )
            if stats.get("outlier_count", 0) > 0:
                logger.info(
                    "Excluded %s outlier cycles (< %s days) from average",
                    stats["outlier_count"],
                    MIN_CYCLE_DAYS,
                )
            if stats.get("irregular_count", 0) > 0:
                logger.info(
                    "Excluded %s irregular cycles (> %s days) from average",
                    stats["irregular_count"],
                    MAX_CYCLE_DAYS,
                )
        else:
            logger.info("No valid cycles to update cycle_length for user")

    except Exception:
        logger.exception("Error updating user cycle stats")


def _default_empty_stats() -> Dict:
    return {
        "totalCycles": 0,
        "averageCycleLength": 28.0,
        "averagePeriodLength": 5.0,
        "averagePeriodLengthRaw": 5.0,
        "averagePeriodLengthNormalized": 5.0,
        "isPeriodLengthOutsideRange": False,
        "cycleRegularity": "unknown",
        "longestCycle": None,
        "shortestCycle": None,
        "longestPeriod": None,
        "shortestPeriod": None,
        "lastPeriodDate": None,
        "daysSinceLastPeriod": None,
        "anomalies": 0,
        "confidence": {"level": "low", "percentage": 0, "reason": "No cycle data available"},
        "insights": ["Log at least 2 periods to see cycle history."],
        "insightsKeys": [],
        "insightsParams": [],
        "cycleLengths": [],
        "allCycles": [],
        "bleedingEpisodes": [],
        "healthAlerts": {"periodLengthOutOfRange": False},
        "periodLengthHealthAlert": False,
    }


def get_cycle_stats(user_id: str, language: str = "en") -> Dict:
    """
    Calculate comprehensive cycle statistics.

    Independent DB-heavy helpers run in a thread pool to reduce wall-clock latency for mobile.
    """
    try:
        period_starts = get_period_start_logs(user_id, confirmed_only=True)

        if not period_starts:
            logger.info("No period_start_logs; syncing from period_logs")
            from period_start_logs import sync_period_start_logs_from_period_logs

            period_starts = sync_period_start_logs_from_period_logs(user_id)
            logger.info("Synced %s period starts from period_logs", len(period_starts))

        cycles = get_cycles_from_period_starts(user_id, period_starts=period_starts)

        if not period_starts:
            logger.info("No period_start_logs after sync; returning defaults")
            return _default_empty_stats()

        def _fetch_period_logs():
            return (
                supabase.table("period_logs")
                .select("date, flow")
                .eq("user_id", user_id)
                .order("date")
                .execute()
            )

        def _roll_avg():
            return calculate_rolling_average(user_id)

        def _roll_period():
            return calculate_rolling_period_length(user_id)

        def _conf():
            return calculate_prediction_confidence(user_id, language=language)

        with ThreadPoolExecutor(max_workers=4) as pool:
            fut_logs = pool.submit(_fetch_period_logs)
            fut_avg = pool.submit(_roll_avg)
            fut_plen = pool.submit(_roll_period)
            fut_conf = pool.submit(_conf)
            period_logs_response = fut_logs.result()
            avg_cycle_length = fut_avg.result()
            avg_period_length = fut_plen.result()
            confidence = fut_conf.result()
        period_length_days = int(round(max(3.0, min(8.0, avg_period_length))))

        valid_cycles = [
            c
            for c in cycles
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS and not c.get("is_outlier", False)
        ]
        anomaly_cycles = [
            c
            for c in cycles
            if c["length"] < MIN_CYCLE_DAYS or c["length"] > MAX_CYCLE_DAYS or c.get("is_outlier", False)
        ]

        cycle_regularity = "unknown"
        if len(valid_cycles) >= 3:
            cycle_lengths_reg = [c["length"] for c in valid_cycles]
            mean = sum(cycle_lengths_reg) / len(cycle_lengths_reg)
            if len(cycle_lengths_reg) > 1:
                variance = sum((x - mean) ** 2 for x in cycle_lengths_reg) / (len(cycle_lengths_reg) - 1)
                std_dev = variance**0.5
                cv = (std_dev / mean) * 100 if mean > 0 else 100

                if cv < 8:
                    cycle_regularity = "very_regular"
                elif cv < 15:
                    cycle_regularity = "regular"
                elif cv < 25:
                    cycle_regularity = "somewhat_irregular"
                else:
                    cycle_regularity = "irregular"

        longest_cycle = max([c["length"] for c in valid_cycles]) if valid_cycles else None
        shortest_cycle = min([c["length"] for c in valid_cycles]) if valid_cycles else None

        is_period_length_outside_range = avg_period_length < 3.0 or avg_period_length > 8.0
        health_alerts = {"periodLengthOutOfRange": bool(is_period_length_outside_range)}

        period_lengths: List[float] = []
        bleeding_episodes_out: List[Dict] = []
        try:
            raw_logs = period_logs_response.data or []
            if raw_logs:
                episodes = group_logs_into_episodes(raw_logs, reference_date=date.today())
                period_lengths = [float(ep["length"]) for ep in episodes]
                bleeding_episodes_out = [
                    {
                        "startDate": ep["start_date"],
                        "endDate": ep["end_date"],
                        "length": ep["length"],
                        "isConfirmed": ep["is_confirmed"],
                    }
                    for ep in episodes
                ]
        except Exception:
            logger.exception("Error calculating period length ranges from bleeding episodes")
            if avg_period_length:
                period_lengths = [avg_period_length]

        longest_period = max(period_lengths) if period_lengths else None
        shortest_period = min(period_lengths) if period_lengths else None

        last_period_date = None
        days_since_last_period = None

        if period_starts:
            last_period_str = period_starts[-1]["start_date"]
            if isinstance(last_period_str, str):
                last_period_date = datetime.strptime(last_period_str, "%Y-%m-%d").date()
            else:
                last_period_date = last_period_str

            days_since_last_period = (datetime.now().date() - last_period_date).days

        cycle_lengths_chart = [c["length"] for c in valid_cycles[-6:]] if valid_cycles else []

        all_cycles: List[Dict] = []
        logger.debug("Building all_cycles from %s period starts", len(period_starts))

        if period_starts and len(period_starts) >= 1:
            if len(period_starts) >= 2:
                for i in range(len(period_starts) - 1):
                    cycle_start = period_starts[i]["start_date"]
                    cycle_end = period_starts[i + 1]["start_date"]

                    if isinstance(cycle_start, str):
                        cycle_start_date = datetime.strptime(cycle_start, "%Y-%m-%d").date()
                    else:
                        cycle_start_date = cycle_start

                    if isinstance(cycle_end, str):
                        cycle_end_date = datetime.strptime(cycle_end, "%Y-%m-%d").date()
                    else:
                        cycle_end_date = cycle_end

                    cycle_length = (cycle_end_date - cycle_start_date).days
                    if cycle_length <= 0:
                        logger.warning(
                            "Skipping invalid cycle length %s (start=%s end=%s)",
                            cycle_length,
                            cycle_start,
                            cycle_end,
                        )
                        continue

                    period_len, ov_day, ov_start, ov_end = get_phase_bounds_for_dots(
                        user_id, int(round(avg_cycle_length)), period_length_days
                    )
                    flagged_outlier = bool(period_starts[i].get("is_outlier", False))
                    cycle_obj = {
                        "cycleNumber": len(period_starts) - i - 1,
                        "startDate": cycle_start,
                        "endDate": cycle_end,
                        "length": cycle_length,
                        "isCurrent": False,
                        "isAnomaly": cycle_length < MIN_CYCLE_DAYS
                        or cycle_length > MAX_CYCLE_DAYS
                        or flagged_outlier,
                        "periodLength": period_len,
                        "ovulationDay": ov_day,
                        "ovulationStart": ov_start,
                        "ovulationEnd": ov_end,
                    }
                    stored = period_starts[i].get("cycle_data_json")
                    if stored:
                        cycle_obj["cycleData"] = stored
                    all_cycles.append(cycle_obj)

            last_period = period_starts[-1]["start_date"]
            if isinstance(last_period, str):
                last_period_date_obj = datetime.strptime(last_period, "%Y-%m-%d").date()
            else:
                last_period_date_obj = last_period

            today = datetime.now().date()
            current_cycle_length = (today - last_period_date_obj).days
            if current_cycle_length < 0:
                logger.warning(
                    "Current cycle length negative (%s); clamping to 0",
                    current_cycle_length,
                )
                current_cycle_length = 0

            period_len_curr, ov_day_curr, ov_start_curr, ov_end_curr = get_phase_bounds_for_dots(
                user_id, int(round(avg_cycle_length)), period_length_days
            )
            current_cycle_obj = {
                "cycleNumber": 0,
                "startDate": last_period,
                "endDate": None,
                "length": current_cycle_length,
                "isCurrent": True,
                "isAnomaly": False,
                "periodLength": period_len_curr,
                "ovulationDay": ov_day_curr,
                "ovulationStart": ov_start_curr,
                "ovulationEnd": ov_end_curr,
            }
            try:
                from missing_period_handler import handle_missing_period

                late_result = handle_missing_period(user_id)
                if late_result:
                    if late_result.get("is_late"):
                        current_cycle_obj["status"] = "late"
                        current_cycle_obj["daysLate"] = late_result.get("days_late", 0)
                    if late_result.get("health_flag") == "amenorrhea_risk":
                        current_cycle_obj["healthFlag"] = "amenorrhea_risk"
            except Exception:
                logger.warning("Could not check late status for current cycle", exc_info=True)

            all_cycles.append(current_cycle_obj)

        all_cycles.reverse()

        # Build continuous daily phase maps per month for cycle history cards.
        phase_by_date: Dict[str, str] = {}
        today = datetime.now().date()

        def _to_date(v):
            if isinstance(v, str):
                return datetime.strptime(v, "%Y-%m-%d").date()
            return v

        month_dates: List[date] = []
        for c in all_cycles:
            sd = c.get("startDate")
            if not sd:
                continue
            try:
                sd_date = _to_date(sd)
            except Exception:
                continue
            month_dates.append(date(sd_date.year, sd_date.month, 1))

        if month_dates and period_starts:
            min_month = min(month_dates)
            max_month = max(month_dates)
            max_month_last_day = monthrange(max_month.year, max_month.month)[1]
            phase_start_date = min_month.strftime("%Y-%m-%d")
            phase_end_date = date(max_month.year, max_month.month, max_month_last_day).strftime("%Y-%m-%d")
            phase_period_logs = [{"date": ps["start_date"]} for ps in period_starts if ps.get("start_date")]
            last_period_for_phase = period_starts[-1].get("start_date")
            cycle_length_for_phase = max(MIN_CYCLE_DAYS, min(MAX_CYCLE_DAYS, int(round(avg_cycle_length))))

            phase_rows = calculate_phase_for_date_range(
                user_id=user_id,
                last_period_date=last_period_for_phase,
                cycle_length=cycle_length_for_phase,
                period_logs=phase_period_logs,
                start_date=phase_start_date,
                end_date=phase_end_date,
            )
            phase_by_date = {str(r.get("date")): str(r.get("phase") or "Follicular") for r in (phase_rows or [])}

            def _daily_map_for_month(y: int, m: int) -> List[str]:
                days_in_month = monthrange(y, m)[1]
                out: List[str] = []
                for day in range(1, days_in_month + 1):
                    d = date(y, m, day)
                    if d > today:
                        out.append("Future")
                    else:
                        out.append(phase_by_date.get(d.strftime("%Y-%m-%d"), "Follicular"))
                return out

            existing_month_keys = set()
            for c in all_cycles:
                sd = c.get("startDate")
                if not sd:
                    c["daily_phase_map"] = []
                    continue
                try:
                    sd_date = _to_date(sd)
                    c["daily_phase_map"] = _daily_map_for_month(sd_date.year, sd_date.month)
                    c["isVirtual"] = bool(c.get("isVirtual", False))
                    existing_month_keys.add((sd_date.year, sd_date.month))
                except Exception:
                    c["daily_phase_map"] = []

            # Fill missing months between logged months with virtual entries for unbroken history timeline.
            virtual_entries: List[Dict] = []
            cursor = min_month
            while cursor <= max_month:
                key = (cursor.year, cursor.month)
                if key not in existing_month_keys:
                    period_len_v, ov_day_v, ov_start_v, ov_end_v = get_phase_bounds_for_dots(
                        user_id, int(round(avg_cycle_length)), period_length_days
                    )
                    virtual_entries.append(
                        {
                            "cycleNumber": None,
                            "startDate": cursor.strftime("%Y-%m-%d"),
                            "endDate": None,
                            "length": int(round(avg_cycle_length)),
                            "isCurrent": False,
                            "isAnomaly": False,
                            "isVirtual": True,
                            "periodLength": period_len_v,
                            "ovulationDay": ov_day_v,
                            "ovulationStart": ov_start_v,
                            "ovulationEnd": ov_end_v,
                            "daily_phase_map": _daily_map_for_month(cursor.year, cursor.month),
                        }
                    )
                if cursor.month == 12:
                    cursor = date(cursor.year + 1, 1, 1)
                else:
                    cursor = date(cursor.year, cursor.month + 1, 1)

            if virtual_entries:
                all_cycles.extend(virtual_entries)
                all_cycles.sort(
                    key=lambda c: _to_date(c["startDate"]) if c.get("startDate") else date.min,
                    reverse=True,
                )
        else:
            for c in all_cycles:
                c["daily_phase_map"] = []
                c["isVirtual"] = bool(c.get("isVirtual", False))

        from i18n import t

        insights: List[str] = []
        insight_keys: List[str] = []
        insight_params: List[Dict] = []

        if len(valid_cycles) < 3:
            key = "insight.log_3_cycles_more"
            insights.append(t(key, language))
            insight_keys.append(key)
            insight_params.append({})

        if cycle_regularity in ("irregular", "somewhat_irregular", "regular", "very_regular"):
            key = f"insight.regularity.{cycle_regularity}"
            insights.append(t(key, language))
            insight_keys.append(key)
            insight_params.append({})

        if len(anomaly_cycles) > 0:
            key = "insight.anomalies_count"
            params = {"anomaly_count": len(anomaly_cycles)}
            insights.append(t(key, language, params))
            insight_keys.append(key)
            insight_params.append(params)

        if is_period_length_outside_range:
            if avg_period_length < 3.0:
                key = "insight.period_short"
                params = {"period_days": f"{avg_period_length:.1f}"}
                insights.append(t(key, language, params))
                insight_keys.append(key)
                insight_params.append(params)
            elif avg_period_length > 8.0:
                key = "insight.period_long"
                params = {"period_days": f"{avg_period_length:.1f}"}
                insights.append(t(key, language, params))
                insight_keys.append(key)
                insight_params.append(params)

        if len(valid_cycles) >= 3:
            lens = [c["length"] for c in valid_cycles[-3:]]
            if len(lens) == 3:
                a, b, c = lens[0], lens[1], lens[2]
                d1, d2 = b - a, c - b
                if d1 < -2 and d2 < -2:
                    tkey = "insight.trend_detected"
                    tparams = {"trend": "progressively shorter"}
                    insights.append(t(tkey, language, tparams))
                    insight_keys.append(tkey)
                    insight_params.append(tparams)
                elif d1 > 2 and d2 > 2:
                    tkey = "insight.trend_detected"
                    tparams = {"trend": "progressively longer"}
                    insights.append(t(tkey, language, tparams))
                    insight_keys.append(tkey)
                    insight_params.append(tparams)

        if avg_cycle_length < 21:
            key = "insight.avg_cycle_short"
            insights.append(t(key, language))
            insight_keys.append(key)
            insight_params.append({})
        elif avg_cycle_length > 38:
            key = "insight.avg_cycle_long"
            insights.append(t(key, language))
            insight_keys.append(key)
            insight_params.append({})

        if not insights:
            key = "insight.continue_tracking"
            insights.append(t(key, language))
            insight_keys.append(key)
            insight_params.append({})

        return {
            "totalCycles": len(valid_cycles),
            "averageCycleLength": round(avg_cycle_length, 1),
            "averagePeriodLength": round(avg_period_length, 1),
            "averagePeriodLengthRaw": round(avg_period_length, 1),
            "averagePeriodLengthNormalized": round(float(period_length_days), 1),
            "isPeriodLengthOutsideRange": is_period_length_outside_range,
            "periodLengthHealthAlert": bool(is_period_length_outside_range),
            "healthAlerts": health_alerts,
            "cycleRegularity": cycle_regularity,
            "longestCycle": longest_cycle,
            "shortestCycle": shortest_cycle,
            "longestPeriod": longest_period,
            "shortestPeriod": shortest_period,
            "lastPeriodDate": last_period_date.strftime("%Y-%m-%d") if last_period_date else None,
            "daysSinceLastPeriod": days_since_last_period,
            "anomalies": len(anomaly_cycles),
            "confidence": confidence,
            "insights": insights,
            "insightsKeys": insight_keys,
            "insightsParams": insight_params,
            "cycleLengths": cycle_lengths_chart,
            "allCycles": all_cycles,
            "bleedingEpisodes": bleeding_episodes_out,
        }

    except Exception:
        logger.exception("Error getting cycle stats")
        out = _default_empty_stats()
        out["confidence"] = {
            "level": "Low",
            "percentage": 0,
            "reason": "Unable to calculate statistics.",
        }
        out["insights"] = ["Start logging your periods to see personalized insights."]
        return out
