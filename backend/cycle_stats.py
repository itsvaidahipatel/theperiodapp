"""
Cycle statistics computation from PeriodStartLogs.

Cycles are derived from PeriodStartLogs, never stored permanently.
This module computes cycle statistics (mean, SD, variance) from PeriodStartLogs.

DESIGN: One log = one cycle start
Cycle length = gap between consecutive period starts
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from period_start_logs import get_cycles_from_period_starts, get_period_start_logs
from period_service import (
    calculate_rolling_average,
    calculate_rolling_period_length,
    calculate_prediction_confidence,
    MIN_CYCLE_DAYS,
    MAX_CYCLE_DAYS
)
from database import supabase


def compute_cycle_stats_from_period_starts(user_id: str, period_starts: Optional[List] = None) -> Dict:
    """
    Compute cycle statistics from PeriodStartLogs.
    
    Cycles are derived from PeriodStartLogs:
    - Cycle.start = PeriodStartLog[n].start_date
    - Cycle.length = PeriodStartLog[n+1].start_date - PeriodStartLog[n].start_date
    
    Only includes valid cycle lengths (21-45 days per ACOG guidelines) in averages.
    Outliers (< 21 days) and irregular cycles (> 45 days) are excluded.
    
    Args:
        user_id: User ID
        period_starts: Optional list from sync_period_start_logs_from_period_logs return. Use to avoid DB read after sync.
    
    Returns:
        Dict with:
        - cycle_length_mean: Mean cycle length (valid cycles only)
        - cycle_length_sd: Standard deviation of cycle length
        - cycle_length_variance: Variance of cycle length
        - cycle_count: Number of valid cycles
        - cycle_lengths: List of valid cycle lengths
        - outlier_count: Number of outlier cycles (< 21 days)
        - irregular_count: Number of irregular cycles (> 45 days)
    """
    try:
        cycles = get_cycles_from_period_starts(user_id, period_starts=period_starts)
        
        if not cycles or len(cycles) < 1:
            return {
                "cycle_length_mean": 28.0,
                "cycle_length_sd": 2.0,
                "cycle_length_variance": 4.0,
                "cycle_count": 0,
                "cycle_lengths": [],
                "outlier_count": 0,
                "irregular_count": 0
            }
        
        # Separate valid cycles from outliers/irregular (ACOG guidelines: 21-45 days)
        # Exclude DB/user-flagged is_outlier from rolling stats (Bayesian inputs).
        valid_cycles = [
            c for c in cycles
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS
            and not c.get("is_outlier", False)
        ]
        outliers = [c for c in cycles if c.get("is_outlier", False) or c["length"] < MIN_CYCLE_DAYS]
        irregular = [c for c in cycles if c.get("is_irregular", False) or c["length"] > MAX_CYCLE_DAYS]
        
        cycle_lengths = [c["length"] for c in valid_cycles]
        
        # Calculate statistics
        n = len(cycle_lengths)
        
        # Prevent division by zero if no valid cycles
        if n == 0:
            return {
                "cycle_length_mean": 28.0,
                "cycle_length_sd": 2.0,
                "cycle_length_variance": 4.0,
                "cycle_count": 0,
                "cycle_lengths": [],
                "outlier_count": len(outliers),
                "irregular_count": len(irregular)
            }
        
        mean = sum(cycle_lengths) / n
        
        if n > 1:
            variance = sum((x - mean) ** 2 for x in cycle_lengths) / (n - 1)
            sd = variance ** 0.5
        else:
            variance = 0.0
            sd = 0.0
        
        return {
            "cycle_length_mean": mean,
            "cycle_length_sd": sd,
            "cycle_length_variance": variance,
            "cycle_count": n,
            "cycle_lengths": cycle_lengths,
            "outlier_count": len(outliers),
            "irregular_count": len(irregular)
        }
    
    except Exception as e:
        print(f"Error computing cycle stats from period starts: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "cycle_length_mean": 28.0,
            "cycle_length_sd": 2.0,
            "cycle_length_variance": 4.0,
            "cycle_count": 0,
            "cycle_lengths": [],
            "outlier_count": 0,
            "irregular_count": 0
        }


def update_user_cycle_stats(user_id: str, period_starts: Optional[List] = None) -> None:
    """
    Update user's cycle_length in users table based on PeriodStartLogs.
    
    Uses Bayesian smoothing to update cycle_length estimate.
    Only uses valid cycle lengths (21-45 days per ACOG guidelines) in the average.
    
    Args:
        user_id: User ID
        period_starts: Optional list from sync_period_start_logs_from_period_logs return.
            When provided, no DB read is performed (stops COMPLETE REBUILD verification loop).
    """
    try:
        from database import supabase
        from cycle_utils import update_cycle_length_bayesian
        
        # Use passed period_starts when available (e.g. after sync) to avoid querying period_start_logs again
        stats = compute_cycle_stats_from_period_starts(user_id, period_starts=period_starts)
        
        if stats["cycle_count"] > 0:
            # Update cycle_length using Bayesian smoothing
            mean_cycle_length = int(round(stats["cycle_length_mean"]))
            update_cycle_length_bayesian(user_id, mean_cycle_length)
            print(f"✅ Updated cycle_length from PeriodStartLogs: {mean_cycle_length} days (from {stats['cycle_count']} valid cycles)")
            if stats.get("outlier_count", 0) > 0:
                print(f"   ⚠️ Excluded {stats['outlier_count']} outlier cycles (< {MIN_CYCLE_DAYS} days) from average")
            if stats.get("irregular_count", 0) > 0:
                print(f"   ⚠️ Excluded {stats['irregular_count']} irregular cycles (> {MAX_CYCLE_DAYS} days) from average")
        else:
            print(f"⚠️ No valid cycles available to update cycle_length for user {user_id}")
    
    except Exception as e:
        print(f"Error updating user cycle stats: {str(e)}")
        import traceback
        traceback.print_exc()


def _get_phase_bounds(user_id: str, cycle_length: int, avg_period_length: float) -> tuple:
    """
    Return (period_length, ovulation_day, ovulation_start, ovulation_end) for phase dots.
    Matches cycle_utils calculate_phase_for_date_range logic.
    """
    try:
        from cycle_utils import estimate_luteal, estimate_period_length

        luteal_mean, _ = estimate_luteal(user_id)
        period_days_raw = estimate_period_length(user_id, normalized=True)
        period_length_days = int(round(max(3.0, min(8.0, period_days_raw))))
        actual_cl = max(21, min(45, cycle_length))
        ov_day = int(max(period_length_days + 1, actual_cl - luteal_mean))
        ov_start = max(period_length_days + 1, ov_day - 1)  # ovulation_days typically {-1,0,1}
        ov_end = min(actual_cl, ov_day + 1)
        return (period_length_days, ov_day, ov_start, ov_end)
    except Exception as e:
        print(f"⚠️ _get_phase_bounds fallback: {e}")
        pl = int(round(max(3, min(8, avg_period_length))))
        cl = max(21, min(45, cycle_length))
        ov = max(pl + 1, cl - 14)
        return (pl, ov, max(pl + 1, ov - 1), min(cl, ov + 1))


def get_cycle_stats(user_id: str, language: str = "en") -> Dict:
    """
    Calculate comprehensive cycle statistics.
    
    Returns:
        Dict with:
        - totalCycles: Number of valid cycles (21-45 days) used for statistics (not total historical)
        - averageCycleLength: Rolling average from last 3 valid cycles (falls back to mean of all valid cycles if < 3, or profile default if none)
        - averagePeriodLength: Rolling average from period logs (consecutive dates)
        - cycleRegularity: "very_regular", "regular", "somewhat_irregular", "irregular", "unknown"
        - longestCycle / shortestCycle: Range of cycle lengths
        - longestPeriod / shortestPeriod: Range of period lengths
        - lastPeriodDate: Most recent period start
        - daysSinceLastPeriod: Days since last period
        - anomalies: Count of anomaly cycles
        - confidence: Prediction confidence object
        - insights: Array of personalized insights
        - cycleLengths: Array of last 6 cycle lengths (for chart)
    """
    try:
        # Get period starts (confirmed only for stats, but we'll also check period_logs if empty)
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        # If period_start_logs is empty, sync from period_logs before proceeding
        if not period_starts:
            print(f"⚠️ No period_start_logs found for user {user_id}. Syncing from period_logs...")
            from period_start_logs import sync_period_start_logs_from_period_logs
            period_starts = sync_period_start_logs_from_period_logs(user_id)
            print(f"✅ Synced {len(period_starts)} period starts from period_logs")
        
        # Get cycles (after sync if needed)
        cycles = get_cycles_from_period_starts(user_id, period_starts=period_starts)
        
        # If still no period_starts after sync, return default stats
        if not period_starts:
            print(f"⚠️ No period_start_logs found for user {user_id} after sync. Returning default stats.")
            return {
                "totalCycles": 0,
                "averageCycleLength": 28.0,
                "averagePeriodLength": 5.0,
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
                "cycleLengths": [],
                "allCycles": []
            }
        
        # Calculate rolling averages
        avg_cycle_length = calculate_rolling_average(user_id)
        avg_period_length = calculate_rolling_period_length(user_id)
        
        # Get confidence
        # Localize backend-generated strings for mobile/web consumers.
        # Also return stable keys so clients can localize if desired.
        confidence = calculate_prediction_confidence(user_id, language=language)
        
        # Filter valid cycles (21-45 days), excluding user/statistical outliers flagged in period_start_logs
        valid_cycles = [
            c for c in cycles
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS
            and not c.get("is_outlier", False)
        ]
        anomaly_cycles = [
            c for c in cycles
            if c["length"] < MIN_CYCLE_DAYS or c["length"] > MAX_CYCLE_DAYS or c.get("is_outlier", False)
        ]
        
        # Calculate cycle regularity (coefficient of variation)
        cycle_regularity = "unknown"
        if len(valid_cycles) >= 2:
            cycle_lengths = [c["length"] for c in valid_cycles]
            mean = sum(cycle_lengths) / len(cycle_lengths)
            if len(cycle_lengths) > 1:
                variance = sum((x - mean) ** 2 for x in cycle_lengths) / (len(cycle_lengths) - 1)
                std_dev = variance ** 0.5
                cv = (std_dev / mean) * 100 if mean > 0 else 100
                
                if cv < 8:
                    cycle_regularity = "very_regular"
                elif cv < 15:
                    cycle_regularity = "regular"
                elif cv < 25:
                    cycle_regularity = "somewhat_irregular"
                else:
                    cycle_regularity = "irregular"
        
        # Get cycle length ranges
        longest_cycle = max([c["length"] for c in valid_cycles]) if valid_cycles else None
        shortest_cycle = min([c["length"] for c in valid_cycles]) if valid_cycles else None
        
        # Get period length ranges from period logs (raw, not normalized)
        # Calculate by grouping consecutive dates in period_logs
        avg_period_length = calculate_rolling_period_length(user_id)  # Raw estimate for stats
        period_lengths = []
        
        # Check if period length is outside typical range (3-8 days)
        is_period_length_outside_range = avg_period_length < 3.0 or avg_period_length > 8.0
        
        try:
            # Get period logs and group consecutive dates to calculate actual period lengths
            from database import supabase
            period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date").execute()
            
            if period_logs_response.data and len(period_logs_response.data) > 0:
                # Group consecutive dates into periods
                dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d").date() if isinstance(log["date"], str) else log["date"] for log in period_logs_response.data if log.get("date")])
                
                if dates:
                    current_period_start = dates[0]
                    for i in range(1, len(dates)):
                        # If gap > 1 day, end current period and start new one
                        if (dates[i] - dates[i-1]).days > 1:
                            period_length = (dates[i-1] - current_period_start).days + 1
                            period_lengths.append(period_length)
                            current_period_start = dates[i]
                    # Add last period
                    period_length = (dates[-1] - current_period_start).days + 1
                    period_lengths.append(period_length)
        except Exception as e:
            print(f"Error calculating period length ranges: {str(e)}")
            # Fallback to average if calculation fails
            if avg_period_length:
                period_lengths = [avg_period_length]
        
        longest_period = max(period_lengths) if period_lengths else None
        shortest_period = min(period_lengths) if period_lengths else None
        
        # Get last period date
        last_period_date = None
        days_since_last_period = None
        
        if period_starts:
            last_period_str = period_starts[-1]["start_date"]
            if isinstance(last_period_str, str):
                last_period_date = datetime.strptime(last_period_str, "%Y-%m-%d").date()
            else:
                last_period_date = last_period_str
            
            days_since_last_period = (datetime.now().date() - last_period_date).days
        
        # Get last 6 cycle lengths for chart
        cycle_lengths_chart = [c["length"] for c in valid_cycles[-6:]] if valid_cycles else []
        
        # Get all cycles with dates for history view
        # FIXED: Show cycles even with just 1 period (show current cycle)
        all_cycles = []
        print(f"📊 Building all_cycles from {len(period_starts)} period starts")
        if period_starts and len(period_starts) >= 1:
            # Calculate cycles between consecutive period starts
            if len(period_starts) >= 2:
                # Multiple periods - calculate cycles between them
                for i in range(len(period_starts) - 1):
                    cycle_start = period_starts[i]["start_date"]
                    cycle_end = period_starts[i + 1]["start_date"]
                    
                    # Parse dates if needed
                    if isinstance(cycle_start, str):
                        cycle_start_date = datetime.strptime(cycle_start, "%Y-%m-%d").date()
                    else:
                        cycle_start_date = cycle_start
                    
                    if isinstance(cycle_end, str):
                        cycle_end_date = datetime.strptime(cycle_end, "%Y-%m-%d").date()
                    else:
                        cycle_end_date = cycle_end
                    
                    cycle_length = (cycle_end_date - cycle_start_date).days
                    
                    # Phase boundaries for dots (match cycle_utils calculate_phase_for_date_range)
                    period_len, ov_day, ov_start, ov_end = _get_phase_bounds(
                        user_id, cycle_length, avg_period_length
                    )
                    flagged_outlier = bool(period_starts[i].get("is_outlier", False))
                    cycle_obj = {
                        "cycleNumber": len(period_starts) - i - 1,
                        "startDate": cycle_start,
                        "endDate": cycle_end,
                        "length": cycle_length,
                        "isCurrent": False,
                        "isAnomaly": cycle_length < MIN_CYCLE_DAYS or cycle_length > MAX_CYCLE_DAYS or flagged_outlier,
                        "periodLength": period_len,
                        "ovulationDay": ov_day,
                        "ovulationStart": ov_start,
                        "ovulationEnd": ov_end,
                    }
                    # Attach stored cycle_data_json (source of truth for past cycles)
                    stored = period_starts[i].get("cycle_data_json")
                    if stored:
                        cycle_obj["cycleData"] = stored
                    all_cycles.append(cycle_obj)
            
            # Always add current cycle (from last period start to today)
            # This ensures we show at least 1 cycle even with just 1 period logged
            last_period = period_starts[-1]["start_date"]
            if isinstance(last_period, str):
                last_period_date_obj = datetime.strptime(last_period, "%Y-%m-%d").date()
            else:
                last_period_date_obj = last_period
            
            today = datetime.now().date()
            current_cycle_length = (today - last_period_date_obj).days
            
            # For current cycle, use estimated length (median of recent or avg)
            est_length = avg_cycle_length
            if valid_cycles:
                lengths = [c["length"] for c in valid_cycles[-6:] if 21 <= c["length"] <= 45]
                if lengths:
                    s = sorted(lengths)
                    est_length = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
            period_len_curr, ov_day_curr, ov_start_curr, ov_end_curr = _get_phase_bounds(
                user_id, int(est_length), avg_period_length
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
            # Check if current cycle is late via missing_period_handler
            try:
                from missing_period_handler import handle_missing_period
                late_result = handle_missing_period(user_id)
                if late_result and late_result.get("is_late"):
                    current_cycle_obj["status"] = "late"
                    current_cycle_obj["daysLate"] = late_result.get("days_late", 0)
            except Exception as e:
                print(f"⚠️ Could not check late status for current cycle: {e}")

            # Current cycle: Don't compute phase map here (Dashboard already has it via phase-map API)
            # Frontend will slice phaseMap for current cycle dates
            all_cycles.append(current_cycle_obj)
        
        # Reverse to show most recent first (current cycle will be first)
        all_cycles.reverse()
        
        print(f"✅ Built {len(all_cycles)} cycles for history view")
        for i, cycle in enumerate(all_cycles):
            print(f"   Cycle {i+1}: {cycle.get('startDate')} - {cycle.get('endDate') or 'current'}, {cycle.get('length')} days, isCurrent={cycle.get('isCurrent')}")
        
        # Generate insights
        from i18n import t

        insights = []
        insight_keys = []
        insight_params = []
        
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
        
        # Add insight if period length is outside typical range
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
        
        if avg_cycle_length < 21:
            key = "insight.avg_cycle_short"
            insights.append(t(key, language))
            insight_keys.append(key)
            insight_params.append({})
        elif avg_cycle_length > 35:
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
            "averagePeriodLengthRaw": round(avg_period_length, 1),  # Raw estimate (actual pattern)
            "averagePeriodLengthNormalized": round(max(3.0, min(8.0, avg_period_length)), 1),  # Normalized for phase calculations
            "isPeriodLengthOutsideRange": is_period_length_outside_range,  # Flag if outside 3-8 days
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
            # Stable keys for clients that want local mapping
            "insightsKeys": insight_keys,
            "insightsParams": insight_params,
            "cycleLengths": cycle_lengths_chart,
            "allCycles": all_cycles  # All cycles with dates for history view
        }
    
    except Exception as e:
        print(f"Error getting cycle stats: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return default stats
        return {
            "totalCycles": 0,
            "averageCycleLength": 28.0,
            "averagePeriodLength": 5.0,
            "cycleRegularity": "unknown",
            "longestCycle": None,
            "shortestCycle": None,
            "longestPeriod": None,
            "shortestPeriod": None,
            "lastPeriodDate": None,
            "daysSinceLastPeriod": None,
            "anomalies": 0,
            "confidence": {
                "level": "Low",
                "percentage": 0,
                "reason": "Unable to calculate statistics."
            },
            "insights": ["Start logging your periods to see personalized insights."],
            "cycleLengths": [],
            "allCycles": []  # Ensure allCycles is always returned, even in error case
        }
