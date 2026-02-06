"""
Period Service - Core period tracking and prediction logic.

This module provides medically accurate period tracking, cycle prediction,
and validation functions following ACOG guidelines.
"""

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


def calculate_rolling_average(user_id: str) -> float:
    """
    Calculate rolling average of cycle length from last 3 non-anomaly cycles.
    Excludes cycles outside 21-45 day range.
    Falls back to profile default if insufficient data.
    
    Args:
        user_id: User ID
    
    Returns:
        Rolling average cycle length (float)
    """
    try:
        # Get cycles from period starts
        cycles = get_cycles_from_period_starts(user_id)
        
        if not cycles:
            # Fallback to user's cycle_length from profile
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("cycle_length"):
                return float(user_response.data[0]["cycle_length"])
            return float(DEFAULT_CYCLE_DAYS)
        
        # Filter valid cycles (21-45 days, non-anomaly)
        valid_cycles = [
            c for c in cycles 
            if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS 
            and not c.get("is_anomaly", False)
        ]
        
        if not valid_cycles:
            # No valid cycles, use profile default
            user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("cycle_length"):
                return float(user_response.data[0]["cycle_length"])
            return float(DEFAULT_CYCLE_DAYS)
        
        # Get last 3 valid cycles
        recent_cycles = valid_cycles[-3:]
        cycle_lengths = [c["length"] for c in recent_cycles]
        
        # Calculate average
        avg = sum(cycle_lengths) / len(cycle_lengths)
        return round(avg, 1)
    
    except Exception as e:
        print(f"Error calculating rolling average: {str(e)}")
        # Fallback to default
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


def calculate_ovulation_day(cycle_length: int) -> int:
    """
    Medically accurate ovulation calculation.
    Uses luteal phase consistency (12-16 days, usually 14).
    Adjusts for cycle length:
    - Short cycles (< MIN_CYCLE_DAYS): 12-day luteal phase (auto-marked as anomaly)
    - Normal cycles (21-35 days): 14-day luteal phase
    - Long cycles (>35 days): 16-day luteal phase
    Ensures ovulation doesn't occur during period (minimum day 8).
    
    Note: Cycles < MIN_CYCLE_DAYS (21 days) are allowed but auto-marked as anomalies.
    They are excluded from averages but can still be used for individual predictions.
    
    Args:
        cycle_length: Cycle length in days
    
    Returns:
        Ovulation day (1-indexed, day 1 = period start)
    """
    # Determine luteal phase length based on cycle length
    # Note: Cycles < MIN_CYCLE_DAYS are allowed but marked as anomalies
    if cycle_length < MIN_CYCLE_DAYS:
        luteal_phase = 12
    elif cycle_length > 35:
        luteal_phase = 16
    else:
        luteal_phase = 14
    
    # Ovulation day = cycle_length - luteal_phase
    ovulation_day = cycle_length - luteal_phase
    
    # Ensure ovulation doesn't occur during period (minimum day 8)
    # This is a safety check - in practice, ovulation should be well after period
    ovulation_day = max(8, ovulation_day)
    
    return ovulation_day


def calculate_prediction_confidence(user_id: str) -> Dict:
    """
    Calculate confidence level (High/Medium/Low) based on:
    - Number of logged cycles (more = higher confidence)
    - Cycle regularity (variance/standard deviation)
    - Recency of data
    
    Args:
        user_id: User ID
    
    Returns:
        Dict with: {level: str, percentage: int, reason: str}
    """
    try:
        cycles = get_cycles_from_period_starts(user_id)
        
        if not cycles or len(cycles) < 1:
            return {
                "level": "Low",
                "percentage": 0,
                "reason": "No cycle data available. Log at least 3 cycles for accurate predictions."
            }
        
        # Filter valid cycles
        valid_cycles = [c for c in cycles if MIN_CYCLE_DAYS <= c["length"] <= MAX_CYCLE_DAYS]
        
        if len(valid_cycles) < 2:
            return {
                "level": "Low",
                "percentage": 25,
                "reason": "Insufficient data. Log at least 3 cycles for better predictions."
            }
        
        # Calculate cycle length statistics
        cycle_lengths = [c["length"] for c in valid_cycles]
        mean = sum(cycle_lengths) / len(cycle_lengths)
        
        if len(cycle_lengths) > 1:
            variance = sum((x - mean) ** 2 for x in cycle_lengths) / (len(cycle_lengths) - 1)
            std_dev = variance ** 0.5
        else:
            std_dev = 0.0
        
        # Calculate coefficient of variation (CV)
        cv = (std_dev / mean) * 100 if mean > 0 else 100
        
        # Base confidence from number of cycles
        cycle_count_score = min(100, len(valid_cycles) * 15)  # 15 points per cycle, max 100
        
        # Regularity score (lower CV = higher score)
        if cv < 8:
            regularity_score = 30  # Very regular
        elif cv < 15:
            regularity_score = 25  # Regular
        elif cv < 25:
            regularity_score = 15  # Somewhat irregular
        else:
            regularity_score = 5   # Irregular
        
        # Recency score (check if last period is recent)
        period_starts = get_period_start_logs(user_id, confirmed_only=True)
        recency_score = 20  # Default
        
        if period_starts:
            last_period_str = period_starts[-1]["start_date"]
            if isinstance(last_period_str, str):
                last_period = datetime.strptime(last_period_str, "%Y-%m-%d").date()
            else:
                last_period = last_period_str
            
            days_since = (datetime.now().date() - last_period).days
            if days_since <= 45:
                recency_score = 20  # Recent
            elif days_since <= 90:
                recency_score = 10  # Somewhat recent
            else:
                recency_score = 5   # Not recent
        
        # Total confidence score
        total_score = cycle_count_score + regularity_score + recency_score
        total_score = min(100, max(0, total_score))
        
        # Determine level
        if total_score >= 70:
            level = "High"
        elif total_score >= 50:
            level = "Medium"
        else:
            level = "Low"
        
        # Generate reason
        if len(valid_cycles) < 3:
            reason = f"Log at least 3 cycles for better predictions. Currently have {len(valid_cycles)} cycle(s)."
        elif cv >= 25:
            reason = f"Cycles are irregular (variance: {cv:.1f}%). More data will improve accuracy."
        elif cv >= 15:
            reason = f"Cycles are somewhat irregular. Tracking more cycles will improve accuracy."
        else:
            reason = f"Based on {len(valid_cycles)} cycle(s) with good regularity."
        
        return {
            "level": level,
            "percentage": int(total_score),
            "reason": reason
        }
    
    except Exception as e:
        print(f"Error calculating prediction confidence: {str(e)}")
        return {
            "level": "Low",
            "percentage": 0,
            "reason": "Unable to calculate confidence. Please log more periods."
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
        
        for i in range(count):
            # Calculate next cycle start
            cycle_length = int(round(avg_cycle_length))
            # Ensure cycle length is within valid range
            cycle_length = max(MIN_CYCLE_DAYS, min(cycle_length, MAX_CYCLE_DAYS))
            
            next_start = current_start + timedelta(days=cycle_length)
            
            # Calculate ovulation day for this cycle
            ovulation_day = calculate_ovulation_day(cycle_length)
            ovulation_date = current_start + timedelta(days=ovulation_day - 1)  # -1 because day 1 = current_start
            
            # Ensure ovulation doesn't occur before day 8 (safety check)
            min_ovulation_date = current_start + timedelta(days=7)  # Day 8 minimum
            if ovulation_date < min_ovulation_date:
                ovulation_date = min_ovulation_date
                ovulation_day = 8
            
            # Ensure ovulation doesn't occur after cycle end
            max_ovulation_date = next_start - timedelta(days=1)
            if ovulation_date > max_ovulation_date:
                ovulation_date = max_ovulation_date
                ovulation_day = cycle_length - 1
            
            # Fertile window: 5 days before ovulation to ovulation day (medically accurate)
            # Sperm can survive up to 5 days, egg viable for 24 hours after ovulation
            # Total fertile window: 5 days before + ovulation day = 6 days total
            fertile_start = ovulation_date - timedelta(days=5)
            fertile_end = ovulation_date
            
            # Ensure fertile window doesn't start before period start
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
                    "reason": f"Periods must be at least {MIN_DAYS_BETWEEN_PERIODS} days apart. Last period was {days_diff} days ago."
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
