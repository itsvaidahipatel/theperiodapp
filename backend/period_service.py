"""
Period Service - Core period tracking and prediction logic.

This module provides medically accurate period tracking, cycle prediction,
and validation functions following ACOG guidelines.
"""

import math
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from database import supabase
from period_start_logs import get_period_start_logs, get_cycles_from_period_starts

# Core Constants (ACOG Guidelines)
MIN_CYCLE_DAYS = 21
MAX_CYCLE_DAYS = 45
MIN_DAYS_BETWEEN_PERIODS = 10
DEFAULT_CYCLE_DAYS = 28
DEFAULT_PERIOD_DAYS = 5
MIN_PERIOD_DAYS = 2
MAX_PERIOD_DAYS = 8


# Bayesian prior strength; align with cycle_utils.update_cycle_length_bayesian (k=3)
_ROLLING_AVERAGE_K = 3


def calculate_rolling_average(user_id: str) -> float:
    """
    Weighted rolling average of cycle length favoring the most recent cycle.
    Uses last 3 valid cycles with weights 1, 2, 3 (oldest to newest) so the app
    is more responsive to changes. Aligns with k=3 Bayesian logic in cycle_utils.
    Excludes cycles outside 21-45 day range.
    Falls back to profile default if insufficient data.
    
    Args:
        user_id: User ID
    
    Returns:
        Weighted average cycle length (float)
    """
    try:
        cycles = get_cycles_from_period_starts(user_id)
        
        if not cycles:
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("cycle_length"):
                return float(user_response.data[0]["cycle_length"])
            return float(DEFAULT_CYCLE_DAYS)
        
        valid_cycles = [
            c for c in cycles
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS
            and not c.get("is_anomaly", False)
            and not c.get("is_outlier", False)
        ]
        
        if not valid_cycles:
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("cycle_length"):
                return float(user_response.data[0]["cycle_length"])
            return float(DEFAULT_CYCLE_DAYS)
        
        recent_cycles = valid_cycles[-3:]
        # Weights 1, 2, 3 (oldest to newest) so most recent cycle has highest influence
        weights = list(range(1, len(recent_cycles) + 1))
        total_w = sum(weights)
        weighted_sum = sum(c["length"] * w for c, w in zip(recent_cycles, weights))
        avg = weighted_sum / total_w
        return round(avg, 1)
    
    except Exception as e:
        print(f"Error calculating rolling average: {str(e)}")
        return float(DEFAULT_CYCLE_DAYS)


def calculate_rolling_period_length(user_id: str) -> float:
    """
    Calculate rolling average of period length.
    
    Uses estimate_period_length() which calculates from period_logs by grouping
    consecutive dates into periods and applying Bayesian smoothing.
    
    Args:
        user_id: User ID
    
    Returns:
        Rolling average period length (float)
    """
    try:
        # Use estimate_period_length which calculates from period_logs
        # by grouping consecutive dates and applying Bayesian smoothing
        # Use raw estimate for stats (not normalized/clamped)
        from cycle_utils import get_period_length_raw
        period_length = get_period_length_raw(user_id)
        return float(period_length)
    
    except Exception as e:
        print(f"Error calculating rolling period length: {str(e)}")
        return float(DEFAULT_PERIOD_DAYS)


def calculate_ovulation_day(user_id: str, cycle_length: int) -> int:
    """
    Ovulation day using adaptive luteal phase estimation (cycle_utils.estimate_luteal).
    Replaces fixed 12/14/16-day rule with user-specific luteal mean for consistency
    with the calendar phase logic.
    
    Args:
        user_id: User ID (for estimate_luteal)
        cycle_length: Cycle length in days
    
    Returns:
        Ovulation day (1-indexed, day 1 = period start)
    """
    try:
        from cycle_utils import estimate_luteal
        luteal_mean, _ = estimate_luteal(user_id)
        ovulation_day = cycle_length - int(round(luteal_mean))
    except Exception:
        # Fallback if estimate_luteal unavailable
        luteal_mean = 14.0
        ovulation_day = cycle_length - int(round(luteal_mean))
    
    ovulation_day = max(8, min(ovulation_day, cycle_length - 1))
    return ovulation_day


def calculate_prediction_confidence(user_id: str, language: str = "en") -> Dict:
    """
    Calculate confidence level (High/Medium/Low) based on:
    - Number of logged cycles (more = higher confidence)
    - Cycle regularity (variance/standard deviation)
    - Ovulation uncertainty (ovulation_sd): high SD lowers confidence and reason mentions cycle variance
    - Recency of data
    
    Args:
        user_id: User ID
    
    Returns:
        Dict with: {level: str, percentage: int, reason: str}
    """
    try:
        cycles = get_cycles_from_period_starts(user_id)
        
        from i18n import t

        if not cycles or len(cycles) < 1:
            return {
                "level": "Low",
                "level_key": "low",
                "percentage": 0,
                "reason_key": "confidence.no_cycle_data",
                "reason_params": {},
                "reason": t("confidence.no_cycle_data", language),
            }
        
        valid_cycles = [
            c for c in cycles
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS
            and not c.get("is_outlier", False)
        ]
        
        if len(valid_cycles) < 2:
            return {
                "level": "Low",
                "level_key": "low",
                "percentage": 25,
                "reason_key": "confidence.insufficient_data",
                "reason_params": {},
                "reason": t("confidence.insufficient_data", language),
            }
        
        cycle_lengths = [c["length"] for c in valid_cycles]
        mean = sum(cycle_lengths) / len(cycle_lengths)
        
        if len(cycle_lengths) > 1:
            variance = sum((x - mean) ** 2 for x in cycle_lengths) / (len(cycle_lengths) - 1)
            std_dev = math.sqrt(variance)
        else:
            std_dev = 0.0
        
        cv = (std_dev / mean) * 100 if mean > 0 else 100
        
        # Adaptive confidence: lower score when ovulation_sd is high (cycle variance)
        try:
            from cycle_utils import estimate_cycle_start_sd, estimate_luteal
            cycle_start_sd = estimate_cycle_start_sd(user_id, float(mean))
            _, luteal_sd = estimate_luteal(user_id)
            ovulation_sd = math.sqrt(cycle_start_sd ** 2 + luteal_sd ** 2)
        except Exception:
            ovulation_sd = 2.0
        
        cycle_count_score = min(100, len(valid_cycles) * 15)
        
        if cv < 8:
            regularity_score = 30
        elif cv < 15:
            regularity_score = 25
        elif cv < 25:
            regularity_score = 15
        else:
            regularity_score = 5
        
        # Penalize high ovulation uncertainty (irregular cycles)
        if ovulation_sd > 4.0:
            regularity_score = max(0, regularity_score - 15)
        elif ovulation_sd > 3.0:
            regularity_score = max(0, regularity_score - 8)
        
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        recency_score = 20
        
        if period_starts:
            last_period_str = period_starts[-1]["start_date"]
            if isinstance(last_period_str, str):
                last_period = datetime.strptime(last_period_str, "%Y-%m-%d").date()
            else:
                last_period = last_period_str
            days_since = (datetime.now().date() - last_period).days
            if days_since <= 45:
                recency_score = 20
            elif days_since <= 90:
                recency_score = 10
            else:
                recency_score = 5
        
        total_score = cycle_count_score + regularity_score + recency_score
        total_score = min(100, max(0, total_score))
        
        if total_score >= 70:
            level = "High"
            level_key = "high"
        elif total_score >= 50:
            level = "Medium"
            level_key = "medium"
        else:
            level = "Low"
            level_key = "low"
        
        reason_key = "confidence.good_regularity_count"
        reason_params = {"cycle_count": len(valid_cycles)}
        if len(valid_cycles) < 3:
            reason_key = "confidence.log_3_cycles_count"
            reason_params = {"cycle_count": len(valid_cycles)}
        elif ovulation_sd > 4.0:
            reason_key = "confidence.high_variance"
            reason_params = {}
        elif ovulation_sd > 3.0:
            reason_key = "confidence.moderate_variance_count"
            reason_params = {"cycle_count": len(valid_cycles)}
        elif cv >= 25:
            reason_key = "confidence.irregular_cv"
            reason_params = {"cv": f"{cv:.1f}"}
        elif cv >= 15:
            reason_key = "confidence.somewhat_irregular"
            reason_params = {}
        else:
            reason_key = "confidence.good_regularity_count"
            reason_params = {"cycle_count": len(valid_cycles)}
        
        return {
            "level": level,  # backward compatible display string
            "level_key": level_key,  # stable key for clients
            "percentage": int(total_score),
            "reason_key": reason_key,
            "reason_params": reason_params,
            "reason": t(reason_key, language, reason_params),
        }
    
    except Exception as e:
        print(f"Error calculating prediction confidence: {str(e)}")
        from i18n import t
        return {
            "level": "Low",
            "level_key": "low",
            "percentage": 0,
            "reason_key": "confidence.unable",
            "reason_params": {},
            "reason": t("confidence.unable", language),
        }


def get_predictions(user_id: str, count: int = 6) -> List[Dict]:
    """
    Generate predictions for next N cycles.
    Each prediction includes:
    - predictedStart: Predicted period start date
    - predictedEnd: Predicted period end date (based on avg period length)
    - ovulation: Ovulation date (cycle_length - luteal_phase)
    - fertileWindow: {start, end} - 3 days before ovulation to ovulation day
    - confidence: Confidence level object
    
    Args:
        user_id: User ID
        count: Number of predictions to generate (default 6)
    
    Returns:
        List of prediction dicts
    """
    try:
        # Get last confirmed period start
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        if not period_starts:
            # No period data, return empty predictions
            return []
        
        last_period_str = period_starts[-1]["start_date"]
        if isinstance(last_period_str, str):
            last_period = datetime.strptime(last_period_str, "%Y-%m-%d").date()
        else:
            last_period = last_period_str
        
        # Calculate rolling average cycle length
        avg_cycle_length = calculate_rolling_average(user_id)
        avg_period_length = calculate_rolling_period_length(user_id)
        
        # Validate averages
        if avg_cycle_length < MIN_CYCLE_DAYS or avg_cycle_length > MAX_CYCLE_DAYS:
            avg_cycle_length = DEFAULT_CYCLE_DAYS
        if avg_period_length < MIN_PERIOD_DAYS or avg_period_length > MAX_PERIOD_DAYS:
            avg_period_length = DEFAULT_PERIOD_DAYS
        
        # Get confidence
        confidence = calculate_prediction_confidence(user_id)
        
        # Validate count
        count = max(1, min(count, 12))  # Limit to 1-12 predictions
        
        predictions = []
        current_start = last_period
        
        # One-time imports for adaptive ovulation/fertile window
        from cycle_utils import estimate_luteal, estimate_cycle_start_sd, select_ovulation_days
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        cycle_start_sd = estimate_cycle_start_sd(user_id, avg_cycle_length)
        ovulation_sd = math.sqrt(cycle_start_sd ** 2 + luteal_sd ** 2)
        
        for i in range(count):
            cycle_length = int(round(avg_cycle_length))
            cycle_length = max(MIN_CYCLE_DAYS, min(cycle_length, MAX_CYCLE_DAYS))
            next_start = current_start + timedelta(days=cycle_length)
            
            # Ovulation day using adaptive luteal (same as calendar)
            ovulation_day = calculate_ovulation_day(user_id, cycle_length)
            ovulation_date = current_start + timedelta(days=ovulation_day - 1)
            
            min_ovulation_date = current_start + timedelta(days=7)
            if ovulation_date < min_ovulation_date:
                ovulation_date = min_ovulation_date
                ovulation_day = 8
            max_ovulation_date = next_start - timedelta(days=1)
            if ovulation_date > max_ovulation_date:
                ovulation_date = max_ovulation_date
                ovulation_day = cycle_length - 1
            
            # Fertile window = Ovulation Phase window (3–5 days) from backend for API/UI consistency
            max_ov_days = 5 if ovulation_sd >= 2.5 else 3
            ovulation_days = select_ovulation_days(ovulation_sd, max_days=max_ov_days)
            if ovulation_days:
                fertile_start = ovulation_date + timedelta(days=min(ovulation_days))
                fertile_end = ovulation_date + timedelta(days=max(ovulation_days))
            else:
                fertile_start = fertile_end = ovulation_date
            if fertile_start < current_start:
                fertile_start = current_start
            
            # Predicted period end (based on avg period length)
            period_length = int(round(avg_period_length))
            period_length = max(MIN_PERIOD_DAYS, min(period_length, MAX_PERIOD_DAYS))
            predicted_end = current_start + timedelta(days=period_length - 1)
            
            predictions.append({
                "predictedStart": current_start.strftime("%Y-%m-%d"),
                "predictedEnd": predicted_end.strftime("%Y-%m-%d"),
                "ovulation": ovulation_date.strftime("%Y-%m-%d"),
                "fertileWindow": {
                    "start": fertile_start.strftime("%Y-%m-%d"),
                    "end": fertile_end.strftime("%Y-%m-%d")
                },
                "confidence": confidence
            })
            
            # Move to next cycle
            current_start = next_start
        
        return predictions
    
    except Exception as e:
        print(f"Error generating predictions: {str(e)}")
        return []


def can_log_period(user_id: str, date_to_check: date) -> Dict:
    """
    Validate if a period can be logged.
    Prevents overlapping periods.
    Ensures minimum 10 days between period starts.
    
    Args:
        user_id: User ID
        date_to_check: Date to check (date object)
    
    Returns:
        Dict with: {canLog: bool, reason?: str}
    """
    try:
        # Get all period logs
        period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).execute()
        
        if not period_logs_response.data:
            # No existing logs, can always log
            return {"canLog": True}
        
        # Get period start dates
        period_starts = get_period_start_logs(user_id, confirmed_only=False)
        
        if not period_starts:
            return {"canLog": True}
        
        # Check for exact duplicate
        for start_log in period_starts:
            start_date_str = start_log["start_date"]
            if isinstance(start_date_str, str):
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                start_date = start_date_str
            
            if start_date == date_to_check:
                return {
                    "canLog": False,
                    "reason": "Period already logged for this date."
                }
        
        # Check minimum spacing (10 days between period starts)
        for start_log in period_starts:
            start_date_str = start_log["start_date"]
            if isinstance(start_date_str, str):
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                start_date = start_date_str
            
            days_diff = abs((date_to_check - start_date).days)
            
            if days_diff < MIN_DAYS_BETWEEN_PERIODS:
                return {
                    "canLog": False,
                    "reason": f"It is too soon to log another period start. Periods must be at least {MIN_DAYS_BETWEEN_PERIODS} days apart."
                }
        
        return {"canLog": True}
    
    except Exception as e:
        print(f"Error checking if period can be logged: {str(e)}")
        # On error, allow logging (fail open)
        return {"canLog": True}


def check_anomaly(user_id: str, date_to_check: date) -> bool:
    """
    Check if cycle length is outside normal range (21-45 days).
    Compares with previous period start date.
    
    Args:
        user_id: User ID
        date_to_check: Date to check (date object)
    
    Returns:
        True if anomaly, False otherwise
    """
    try:
        # Get last confirmed period start
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        if not period_starts or len(period_starts) < 1:
            # No previous period, can't determine anomaly
            return False
        
        last_period_str = period_starts[-1]["start_date"]
        if isinstance(last_period_str, str):
            last_period = datetime.strptime(last_period_str, "%Y-%m-%d").date()
        else:
            last_period = last_period_str
        
        # Calculate cycle length
        cycle_length = (date_to_check - last_period).days
        
        # Check if outside normal range
        if cycle_length < MIN_CYCLE_DAYS or cycle_length > MAX_CYCLE_DAYS:
            return True
        
        return False
    
    except Exception as e:
        print(f"Error checking anomaly: {str(e)}")
        return False
