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


def compute_cycle_stats_from_period_starts(user_id: str) -> Dict:
    """
    Compute cycle statistics from PeriodStartLogs.
    
    Cycles are derived from PeriodStartLogs:
    - Cycle.start = PeriodStartLog[n].start_date
    - Cycle.length = PeriodStartLog[n+1].start_date - PeriodStartLog[n].start_date
    
    Only includes valid cycle lengths (21-45 days per ACOG guidelines) in averages.
    Outliers (< 21 days) and irregular cycles (> 45 days) are excluded.
    
    Args:
        user_id: User ID
    
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
        cycles = get_cycles_from_period_starts(user_id)
        
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
        valid_cycles = [c for c in cycles if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS]
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


def update_user_cycle_stats(user_id: str) -> None:
    """
    Update user's cycle_length in users table based on PeriodStartLogs.
    
    Uses Bayesian smoothing to update cycle_length estimate.
    Only uses valid cycle lengths (21-45 days per ACOG guidelines) in the average.
    
    Args:
        user_id: User ID
    """
    try:
        from database import supabase
        from cycle_utils import update_cycle_length_bayesian
        
        stats = compute_cycle_stats_from_period_starts(user_id)
        
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


def get_cycle_stats(user_id: str) -> Dict:
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
        # Get cycles
        cycles = get_cycles_from_period_starts(user_id)
        
        # Get period starts (confirmed only for stats, but we'll also check period_logs if empty)
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        # DEBUG: Log what we found
        print(f"📊 Cycle Stats Debug for user {user_id}:")
        print(f"   - Period starts from period_start_logs: {len(period_starts)}")
        print(f"   - Cycles from period_starts: {len(cycles)}")
        
        # FALLBACK: If period_start_logs is empty, try to sync from period_logs
        if not period_starts:
            print("⚠️ No period_start_logs found, attempting to sync from period_logs...")
            from period_start_logs import sync_period_start_logs_from_period_logs
            sync_period_start_logs_from_period_logs(user_id)
            # Try again after sync
            period_starts = get_period_start_logs(user_id, confirmed_only=True)
            cycles = get_cycles_from_period_starts(user_id)
            print(f"   - After sync: {len(period_starts)} period starts, {len(cycles)} cycles")
        
        # If still empty, check period_logs directly as last resort
        if not period_starts:
            print("⚠️ Still no period_start_logs, checking period_logs directly...")
            from database import supabase
            logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date").execute()
            if logs_response.data:
                print(f"   - Found {len(logs_response.data)} period_logs entries")
                # Create period_starts from period_logs directly
                period_starts = []
                for log in logs_response.data:
                    date_str = log.get("date")
                    if date_str:
                        period_starts.append({
                            "start_date": date_str,
                            "is_confirmed": True
                        })
                print(f"   - Created {len(period_starts)} period starts from period_logs")
        
        # Calculate rolling averages
        avg_cycle_length = calculate_rolling_average(user_id)
        avg_period_length = calculate_rolling_period_length(user_id)
        
        # Get confidence
        confidence = calculate_prediction_confidence(user_id)
        
        # Filter valid cycles (21-45 days)
        valid_cycles = [c for c in cycles if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS]
        anomaly_cycles = [c for c in cycles if c["length"] < MIN_CYCLE_DAYS or c["length"] > MAX_CYCLE_DAYS]
        
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
                    
                    # Include all cycles, not just valid ones (for history display)
                    all_cycles.append({
                        "cycleNumber": len(period_starts) - i - 1,  # Most recent = 1
                        "startDate": cycle_start,
                        "endDate": cycle_end,
                        "length": cycle_length,
                        "isCurrent": False,  # Completed cycles
                        "isAnomaly": cycle_length < MIN_CYCLE_DAYS or cycle_length > MAX_CYCLE_DAYS
                    })
            
            # Always add current cycle (from last period start to today)
            # This ensures we show at least 1 cycle even with just 1 period logged
            last_period = period_starts[-1]["start_date"]
            if isinstance(last_period, str):
                last_period_date_obj = datetime.strptime(last_period, "%Y-%m-%d").date()
            else:
                last_period_date_obj = last_period
            
            today = datetime.now().date()
            current_cycle_length = (today - last_period_date_obj).days
            
            all_cycles.append({
                "cycleNumber": 0,  # Current cycle
                "startDate": last_period,
                "endDate": None,  # Current cycle hasn't ended
                "length": current_cycle_length,
                "isCurrent": True,
                "isAnomaly": False  # Don't mark current cycle as anomaly
            })
        
        # Reverse to show most recent first (current cycle will be first)
        all_cycles.reverse()
        
        print(f"✅ Built {len(all_cycles)} cycles for history view")
        for i, cycle in enumerate(all_cycles):
            print(f"   Cycle {i+1}: {cycle.get('startDate')} - {cycle.get('endDate') or 'current'}, {cycle.get('length')} days, isCurrent={cycle.get('isCurrent')}")
        
        # Generate insights
        insights = []
        
        if len(valid_cycles) < 3:
            insights.append("Log at least 3 cycles for more accurate predictions and insights.")
        
        if cycle_regularity == "irregular":
            insights.append("Your cycles show high variability. Consider consulting a healthcare provider if this pattern continues.")
        elif cycle_regularity == "somewhat_irregular":
            insights.append("Your cycles show moderate variability. Continue tracking to identify patterns.")
        elif cycle_regularity == "regular":
            insights.append("Your cycles are regular. Great job tracking!")
        elif cycle_regularity == "very_regular":
            insights.append("Your cycles are very regular. Excellent consistency!")
        
        if len(anomaly_cycles) > 0:
            insights.append(f"You have {len(anomaly_cycles)} cycle(s) outside the normal range (21-45 days).")
        
        # Add insight if period length is outside typical range
        if is_period_length_outside_range:
            if avg_period_length < 3.0:
                insights.append(f"Your period length ({avg_period_length:.1f} days) is shorter than typical (3-8 days). This is detected from your logged data.")
            elif avg_period_length > 8.0:
                insights.append(f"Your period length ({avg_period_length:.1f} days) is longer than typical (3-8 days). This is detected from your logged data.")
        
        if avg_cycle_length < 21:
            insights.append("Your average cycle length is shorter than typical. Consider discussing with a healthcare provider.")
        elif avg_cycle_length > 35:
            insights.append("Your average cycle length is longer than typical. Consider discussing with a healthcare provider.")
        
        if not insights:
            insights.append("Continue tracking your periods for personalized insights.")
        
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
