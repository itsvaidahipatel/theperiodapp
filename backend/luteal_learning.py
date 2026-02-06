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

from typing import Optional, Tuple
from datetime import datetime
from period_start_logs import get_period_start_logs
from cycle_utils import predict_ovulation, estimate_luteal, update_luteal_estimate


def compute_observed_luteal_from_confirmed_cycles(
    user_id: str,
    new_period_start: str
) -> Optional[Tuple[float, float]]:
    """
    Compute observed luteal length from confirmed cycles only.
    
    ⚠️ CRITICAL RULES:
    1. Only compute if we have at least 2 confirmed PeriodEvents
    2. Only use ovulation that was predicted BEFORE the new period log
    3. Only use high-confidence ovulation predictions (ovulation_sd <= 1.5)
    
    Args:
        user_id: User ID
        new_period_start: New period start date (YYYY-MM-DD)
    
    Returns:
        Tuple of (observed_luteal, ovulation_sd) if valid, None otherwise
    """
    try:
        # Get confirmed PeriodStartLogs
        confirmed_starts = get_period_start_logs(user_id, confirmed_only=True)
        
        if len(confirmed_starts) < 2:
            print(f"⚠️ Need at least 2 confirmed period starts to compute observed luteal (have {len(confirmed_starts)})")
            return None
        
        # Get the previous confirmed period (before the new one)
        # The new period hasn't been confirmed yet, so we look at the second-to-last
        if len(confirmed_starts) >= 2:
            previous_period_start = confirmed_starts[-2]["start_date"]
            next_period_start = confirmed_starts[-1]["start_date"]  # Next period start (for cycle length calculation)
            
            # Parse dates
            if isinstance(previous_period_start, str):
                prev_start = datetime.strptime(previous_period_start, "%Y-%m-%d")
            else:
                prev_start = previous_period_start
            
            if isinstance(new_period_start, str):
                new_start = datetime.strptime(new_period_start, "%Y-%m-%d")
            else:
                new_start = new_period_start
            
            # Calculate cycle length for the previous cycle
            if isinstance(next_period_start, str):
                next_start = datetime.strptime(next_period_start, "%Y-%m-%d")
            else:
                next_start = next_period_start
            
            cycle_length = (next_start - prev_start).days
            
            # Get adaptive estimates
            luteal_mean, luteal_sd = estimate_luteal(user_id)
            
            # Predict ovulation for the previous cycle
            # This should have been predicted BEFORE the new period log
            predicted_ov_date_str, ovulation_sd, _ = predict_ovulation(
                previous_period_start if isinstance(previous_period_start, str) else previous_period_start.strftime("%Y-%m-%d"),
                float(cycle_length),
                luteal_mean,
                luteal_sd,
                cycle_start_sd=None,
                user_id=user_id
            )
            
            predicted_ov_date = datetime.strptime(predicted_ov_date_str, "%Y-%m-%d")
            
            # Observed luteal = new_period_start - predicted_ovulation
            observed_luteal = (new_start - predicted_ov_date).days
            
            # Validate observed luteal
            if 10 <= observed_luteal <= 18:
                # Check confidence threshold
                confidence_threshold = 1.5
                if ovulation_sd <= confidence_threshold:
                    # High confidence - safe to learn from
                    return (observed_luteal, ovulation_sd)
                else:
                    print(f"⚠️ Skipped luteal learning: low confidence ovulation prediction (ovulation_sd={ovulation_sd:.2f} > {confidence_threshold})")
                    return None
            else:
                print(f"⚠️ Skipped luteal learning: observed_luteal={observed_luteal} days outside valid range (10-18 days)")
                return None
        
        return None
    
    except Exception as e:
        print(f"Error computing observed luteal from confirmed cycles: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def learn_luteal_from_new_period(user_id: str, new_period_start: str) -> None:
    """
    Learn luteal phase length from a new period log.
    
    ⚠️ CRITICAL: Only learns from confirmed cycles with high-confidence ovulation predictions.
    
    This function:
    1. Checks if we have 2+ confirmed PeriodEvents
    2. Computes observed luteal from previous confirmed cycle
    3. Only updates if ovulation prediction was high confidence
    
    Args:
        user_id: User ID
        new_period_start: New period start date (YYYY-MM-DD)
    """
    try:
        result = compute_observed_luteal_from_confirmed_cycles(user_id, new_period_start)
        
        if result:
            observed_luteal, ovulation_sd = result
            
            # Update luteal estimate (has_markers=False for now, can be enhanced later)
            update_luteal_estimate(user_id, observed_luteal, has_markers=False)
            print(f"✅ Learned luteal length: {observed_luteal} days (ovulation_sd={ovulation_sd:.2f})")
        else:
            print(f"⚠️ Skipped luteal learning for user {user_id} (insufficient data or low confidence)")
    
    except Exception as e:
        print(f"Error learning luteal from new period: {str(e)}")
        import traceback
        traceback.print_exc()
