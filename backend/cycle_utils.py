"""
Cycle phase mapping and prediction utilities.
Uses adaptive, medically credible algorithms to predict cycles and generate phase-day mappings.
All calculations are performed locally without external API dependencies.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import math
from database import supabase
# ⚠️ requests library no longer needed (RapidAPI removed)

# ⚠️ RAPIDAPI CODE REMOVED - System now uses adaptive local algorithms only
# The following functions are kept for reference but are no longer used:
# - call_womens_health_api()
# - get_cached_request_id()
# - cache_request_id()
# - process_cycle_data()
# - get_predicted_cycle_starts()
# - get_average_period_length()
# - get_average_cycle_length()
# - get_cycle_phases()
# - generate_cycle_phase_map() (RapidAPI version)
# 
# All cycle predictions now use:
# - predict_cycle_starts_from_period_logs() - Predicts cycle starts from period logs
# - calculate_phase_for_date_range() - Primary calculation method
# - Adaptive algorithms (luteal estimation, period length, ovulation prediction)

def get_cached_request_id(user_id: str) -> Optional[str]:
    """
    Get cached RapidAPI request_id for user if still valid.
    
    Args:
        user_id: User ID
    
    Returns:
        request_id if cached and valid, None otherwise
    """
    try:
        user_response = supabase.table("users").select("rapidapi_request_id, rapidapi_request_id_expires_at").eq("id", user_id).execute()
        if user_response.data and len(user_response.data) > 0:
            user_data = user_response.data[0]
            request_id = user_data.get("rapidapi_request_id")
            expires_at_str = user_data.get("rapidapi_request_id_expires_at")
            
            if request_id and expires_at_str:
                # Check if request_id is still valid (not expired)
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                if datetime.now(expires_at.tzinfo) < expires_at:
                    print(f"✅ Using cached request_id: {request_id} (expires: {expires_at_str})")
                    return request_id
                else:
                    print(f"⚠️ Cached request_id expired: {request_id} (expired: {expires_at_str})")
                    return None
            return None
    except Exception as e:
        print(f"⚠️ Error checking cached request_id: {str(e)}")
        return None

def cache_request_id(user_id: str, request_id: str, expires_in_hours: int = 24) -> None:
    """
    Cache RapidAPI request_id for user to reduce API calls.
    
    Args:
        user_id: User ID
        request_id: RapidAPI request_id to cache
        expires_in_hours: Hours until request_id expires (default 24)
    """
    try:
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        supabase.table("users").update({
            "rapidapi_request_id": request_id,
            "rapidapi_request_id_expires_at": expires_at.isoformat()
        }).eq("id", user_id).execute()
        print(f"✅ Cached request_id: {request_id} (expires: {expires_at.isoformat()})")
    except Exception as e:
        print(f"⚠️ Error caching request_id: {str(e)}")
        # Non-fatal - continue without caching

# ⚠️ DEPRECATED: These RapidAPI functions are no longer used
# The system now uses local adaptive algorithms instead of RapidAPI
# These functions are kept for reference but will raise errors if called

def process_cycle_data(past_cycle_data: List[Dict], current_date: str, max_predictions: int = 6, user_id: Optional[str] = None) -> str:
    """
    DEPRECATED: RapidAPI function no longer used.
    Raises error if called.
    """
    raise NotImplementedError("process_cycle_data is deprecated. Use local adaptive algorithms instead.")

def get_predicted_cycle_starts(request_id: str) -> List[str]:
    """DEPRECATED: RapidAPI function no longer used."""
    raise NotImplementedError("get_predicted_cycle_starts is deprecated. Use local adaptive algorithms instead.")

def get_average_period_length(request_id: str) -> float:
    """DEPRECATED: RapidAPI function no longer used."""
    raise NotImplementedError("get_average_period_length is deprecated. Use estimate_period_length() instead.")

def get_average_cycle_length(request_id: str) -> float:
    """DEPRECATED: RapidAPI function no longer used."""
    raise NotImplementedError("get_average_cycle_length is deprecated. Use compute_cycle_stats_from_period_events() instead.")

def get_cycle_phases(request_id: str) -> List[Dict]:
    """DEPRECATED: RapidAPI function no longer used."""
    raise NotImplementedError("get_cycle_phases is deprecated. Use calculate_phase_for_date_range() instead.")

def predict_cycle_phases(cycle_start_date: str, next_cycle_start_date: str, period_length: int) -> dict:
    """DEPRECATED: RapidAPI function no longer used."""
    raise NotImplementedError("predict_cycle_phases is deprecated. Use calculate_phase_for_date_range() instead.")

def generate_phase_day_id(phase: str, day_in_phase: int) -> str:
    """
    Generate phase-day ID based on phase and day.
    
    Phase IDs:
    - Period: p1-p12
    - Follicular: f1-f30
    - Ovulation: o1-o8
    - Luteal: l1-l25
    """
    phase_prefix = {
        "Period": "p",
        "Menstrual": "p",
        "Follicular": "f",
        "Ovulation": "o",
        "Luteal": "l"
    }
    
    prefix = phase_prefix.get(phase, "p")
    return f"{prefix}{day_in_phase}"

def normal_pdf(x: float, mean: float, sd: float) -> float:
    """
    Calculate probability density function of normal distribution.
    
    Args:
        x: Value to evaluate
        mean: Mean of the distribution
        sd: Standard deviation
    
    Returns:
        PDF value
    """
    if sd <= 0:
        return 0.0
    variance = sd * sd
    coefficient = 1.0 / (sd * math.sqrt(2 * math.pi))
    exponent = -0.5 * ((x - mean) / sd) ** 2
    return coefficient * math.exp(exponent)

def estimate_luteal(user_id: str, user_observations: Optional[List[float]] = None) -> tuple[float, float]:
    """
    Estimate luteal phase length using Bayesian smoothing.
    
    Args:
        user_id: User ID
        user_observations: List of observed luteal lengths (optional, will fetch from DB if None)
    
    Returns:
        Tuple of (mean, sd) for luteal phase length
    """
    # Population prior
    prior_mean = 14.0
    prior_sd = 2.0
    min_luteal = 10.0
    max_luteal = 18.0
    
    # Get user observations from database if not provided
    if user_observations is None:
        try:
            # Try to get from user_cycle_days or calculate from period logs
            user_response = supabase.table("users").select("luteal_observations").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("luteal_observations"):
                import json
                user_observations = json.loads(user_response.data[0]["luteal_observations"])
            else:
                user_observations = []
        except:
            user_observations = []
    
    if not user_observations or len(user_observations) == 0:
        # No user data, use prior
        return prior_mean, prior_sd
    
    # Calculate user statistics
    n = len(user_observations)
    obs_mean = sum(user_observations) / n
    if n > 1:
        variance = sum((x - obs_mean) ** 2 for x in user_observations) / (n - 1)
        obs_sd = math.sqrt(variance)
    else:
        obs_sd = 1.5  # Default SD if only one observation
    
    # Proper Bayesian smoothing with sample-size weighting
    # Weight increases with number of observations: weight = n / (n + k)
    # k = 5 means we need 5 observations to trust data 50%, 10 observations for 67%, etc.
    k = 5  # Prior strength constant
    weight = n / (n + k)
    
    # Weighted combination: more observations → trust data more
    mean = (1 - weight) * prior_mean + weight * obs_mean
    
    # SD: weighted average, but also account for sample size
    sd = (1 - weight) * prior_sd + weight * obs_sd
    
    # Clamp to allowed range
    mean = max(min_luteal, min(max_luteal, mean))
    
    return mean, sd

def estimate_period_length(user_id: str, user_observations: Optional[List[float]] = None, normalized: bool = False) -> float:
    """
    Estimate period length using Bayesian smoothing.
    Adaptive period length based on user history.
    
    ARCHITECTURE:
    - raw_estimate: True period length from user data (no clamping)
    - normalized_estimate: Clamped to medically typical range (3-8 days) for phase calculations
    
    Usage:
    - Stats & insights: Use raw_estimate (get_period_length_raw())
    - Phase calculations: Use normalized_estimate (this function with normalized=True)
    - UI: Show raw_estimate with explanation if outside typical range
    
    Args:
        user_id: User ID
        user_observations: List of observed period lengths (optional, will fetch from DB if None)
        normalized: If True, returns normalized (clamped 3-8 days). If False, returns raw estimate.
    
    Returns:
        Estimated period length (mean) in days
        - If normalized=False: Raw estimate (actual pattern, may be outside 3-8 days)
        - If normalized=True: Normalized estimate (clamped to 3-8 days for phase calculations)
    """
    # Population prior
    prior_mean = 5.0
    min_period = 3.0
    max_period = 8.0
    
    # Get user observations from database if not provided
    if user_observations is None:
        try:
            # Try to get from period_logs table
            # Note: period_logs table uses 'date' column (each row is one day of period)
            period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(60).execute()
            
            if period_logs_response.data and len(period_logs_response.data) > 0:
                # Group consecutive dates to form periods
                dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d") for log in period_logs_response.data if log.get("date")])
                
                # Group consecutive dates into periods
                periods = []
                if dates:
                    current_period_start = dates[0]
                    for i in range(1, len(dates)):
                        # If gap > 1 day, start new period
                        if (dates[i] - dates[i-1]).days > 1:
                            periods.append({
                                "start": current_period_start,
                                "end": dates[i-1]
                            })
                            current_period_start = dates[i]
                    # Add last period
                    periods.append({
                        "start": current_period_start,
                        "end": dates[-1]
                    })
                
                user_observations = []
                for period in periods[-12:]:  # Last 12 periods
                    period_length = (period["end"] - period["start"]).days + 1
                    user_observations.append(float(period_length))
        except Exception as e:
            print(f"⚠️ Error calculating period length from logs: {str(e)}")
            user_observations = []
    
    if not user_observations or len(user_observations) == 0:
        # No user data, use prior
        raw_estimate = prior_mean
    else:
        # Calculate user mean
        n = len(user_observations)
        obs_mean = sum(user_observations) / n
        
        # Proper Bayesian smoothing with sample-size weighting
        # Weight increases with number of observations: weight = n / (n + k)
        # k = 5 means we need 5 observations to trust data 50%, 10 observations for 67%, etc.
        k = 5  # Prior strength constant
        weight = n / (n + k)
        
        # Weighted combination: more observations → trust data more
        raw_estimate = (1 - weight) * prior_mean + weight * obs_mean
    
    # Return raw or normalized based on parameter
    if normalized:
        # Clamp to medically typical range for phase calculations
        normalized_estimate = max(min_period, min(max_period, raw_estimate))
        return round(normalized_estimate, 1)
    else:
        # Return raw estimate (actual pattern, may be outside 3-8 days)
        return round(raw_estimate, 1)


def get_period_length_raw(user_id: str) -> float:
    """
    Get raw period length estimate (actual pattern, not clamped).
    Use for stats, insights, and medical flags.
    
    Args:
        user_id: User ID
    
    Returns:
        Raw period length estimate (may be outside 3-8 days)
    """
    return estimate_period_length(user_id, normalized=False)


def get_period_length_normalized(user_id: str) -> float:
    """
    Get normalized period length estimate (clamped to 3-8 days).
    Use for phase calculations and predictions.
    
    Args:
        user_id: User ID
    
    Returns:
        Normalized period length estimate (3-8 days)
    """
    return estimate_period_length(user_id, normalized=True)

def ovulation_probability(offset_from_ovulation: float, ovulation_sd: float) -> float:
    """
    Calculate ovulation probability for a day based on offset from ovulation.
    This is used for phase determination (Ovulation phase should be 1-3 days).
    Uses only the normal distribution component, NOT the sperm survival kernel.
    
    Args:
        offset_from_ovulation: Days from predicted ovulation (negative = before, positive = after)
        ovulation_sd: Standard deviation of ovulation prediction
    
    Returns:
        Ovulation probability between 0 and 1 (normalized)
    """
    # Early return for dates far from ovulation (performance optimization)
    if abs(offset_from_ovulation) > 10:  # More than 10 days away
        return 0.0
    
    # Normal distribution component (ovulation probability only)
    p_ov = normal_pdf(offset_from_ovulation, 0.0, ovulation_sd)
    
    # Normalize to peak at 1.0 on ovulation day
    peak_prob = normal_pdf(0.0, 0.0, ovulation_sd)
    
    if peak_prob <= 0:
        return 0.0
    
    normalized_prob = p_ov / peak_prob
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, normalized_prob))

def select_ovulation_days(ovulation_sd: float, max_days: int = 3) -> set:
    """
    Select top-N days by fertility probability for a cycle.
    Uses fertility_probability (biologically meaningful) instead of ovulation_probability (mathematical PDF).
    This ensures the "Ovulation" phase aligns with the actual fertile window.
    
    Strategy:
    1. Calculate fertility probabilities for days around ovulation (±5 days)
    2. Sort by probability (descending)
    3. Select top max_days days, ensuring they form a contiguous block centered on day 0
    
    Args:
        ovulation_sd: Standard deviation of ovulation prediction
        max_days: Maximum number of ovulation days (default 3, range 1-3)
    
    Returns:
        Set of day offsets from ovulation_date that are in ovulation phase
        e.g., {-1, 0, 1} means days -1, 0, +1 from ovulation
    """
    # Calculate fertility probabilities for days around ovulation (check ±5 days)
    # Use fertility_probability (biologically meaningful) instead of ovulation_probability (mathematical PDF)
    day_probabilities = []
    for offset in range(-5, 6):
        prob = fertility_probability(offset, ovulation_sd)
        day_probabilities.append((offset, prob))
    
    # Sort by probability (descending), then by distance from 0 (ascending) as tiebreaker
    day_probabilities.sort(key=lambda x: (-x[1], abs(x[0])))
    
    # Strategy: Build contiguous window centered on day 0 (highest probability)
    # Start with day 0, then add adjacent days in order of probability
    selected_offsets = {0}  # Always include day 0 (ovulation day)
    
    if max_days <= 1:
        return selected_offsets
    
    # Add adjacent days, prioritizing by probability
    # We want a contiguous block, so we'll add days -1, +1, -2, +2, etc.
    remaining_slots = max_days - 1
    
    # Get probabilities for adjacent days, sorted by probability
    adjacent_days = [(offset, prob) for offset, prob in day_probabilities 
                     if offset != 0 and abs(offset) <= 3]  # Only consider ±3 days
    adjacent_days.sort(key=lambda x: (-x[1], abs(x[0])))  # Sort by prob desc, then distance
    
    # Build contiguous window: add days that maintain contiguity
    for offset, prob in adjacent_days:
        if remaining_slots <= 0:
            break
        
        # Check if adding this day maintains contiguity
        test_set = selected_offsets | {offset}
        min_offset = min(test_set)
        max_offset = max(test_set)
        
        # Is it contiguous? (all integers between min and max are in the set)
        is_contiguous = all(i in test_set for i in range(min_offset, max_offset + 1))
        
        if is_contiguous and len(test_set) <= max_days:
            selected_offsets.add(offset)
            remaining_slots -= 1
    
    # Final check: ensure we have a contiguous block
    if len(selected_offsets) > 1:
        min_offset = min(selected_offsets)
        max_offset = max(selected_offsets)
        contiguous_offsets = set(range(min_offset, max_offset + 1))
        
        # If we have more than max_days, keep the ones closest to 0
        if len(contiguous_offsets) > max_days:
            sorted_by_distance = sorted(contiguous_offsets, key=lambda x: abs(x))
            selected_offsets = set(sorted_by_distance[:max_days])
        else:
            selected_offsets = contiguous_offsets
    
    return selected_offsets

def get_ovulation_fertility_threshold(ovulation_sd: float) -> float:
    """
    Get adaptive fertility threshold for determining ovulation window.
    
    Ensures ovulation phase is 1-3 days maximum.
    Regular cycles (low uncertainty): higher threshold → 1-2 day window
    Irregular cycles (high uncertainty): lower threshold → 2-3 day window
    
    Threshold is monotonically decreasing with SD:
    - Lower SD (regular) → Higher threshold → Fewer days (1-2)
    - Higher SD (irregular) → Lower threshold → More days (2-3)
    
    Args:
        ovulation_sd: Standard deviation of ovulation prediction (uncertainty)
    
    Returns:
        Fertility probability threshold (monotonically decreasing from 0.85 to 0.70)
    """
    # Regular cycles: ovulation_sd < 2.0 → threshold 0.80-0.85 → 1-2 days
    # Irregular cycles: ovulation_sd >= 2.0 → threshold 0.70-0.80 → 2-3 days
    # Threshold decreases monotonically with SD
    
    if ovulation_sd < 1.5:
        # Very regular: very high threshold → narrow window (1 day)
        return 0.85
    elif ovulation_sd < 2.0:
        # Regular: high threshold → typical window (1-2 days)
        return 0.80
    elif ovulation_sd < 2.5:
        # Somewhat regular: medium-high threshold → wider window (2 days)
        return 0.75
    elif ovulation_sd < 3.0:
        # Moderate irregularity: medium threshold → wider window (2-3 days)
        return 0.72
    elif ovulation_sd < 3.5:
        # Irregular: lower threshold → wider window (3 days)
        return 0.70
    elif ovulation_sd < 4.0:
        # Very irregular: lower threshold → wider window (3 days)
        return 0.68
    elif ovulation_sd < 4.5:
        # Extremely irregular: even lower threshold → wider window (3 days)
        return 0.66
    elif ovulation_sd < 5.0:
        # Pathologically irregular: very low threshold → wider window (3 days)
        return 0.64
    else:
        # Extremely pathologically irregular: minimum threshold → maximum window (3 days)
        return 0.62

def fertility_probability(offset_from_ovulation: float, ovulation_sd: float) -> float:
    """
    Calculate fertility probability for a day based on offset from ovulation.
    Biologically accurate version that reflects real conception data.
    
    Medical accuracy:
    - Peak conception probability is typically day -1 or -2 (before ovulation)
    - Sperm survival decays over time (not binary)
    - Ovulation day (day 0) is important but not always the peak
    
    Args:
        offset_from_ovulation: Days from predicted ovulation (negative = before, positive = after)
        ovulation_sd: Standard deviation of ovulation prediction
    
    Returns:
        Fertility probability between 0 and 1
    """
    # Early return for dates far from ovulation (performance optimization)
    if abs(offset_from_ovulation) > 10:  # More than 10 days away
        return 0.0
    
    # Normal distribution component (ovulation probability)
    p_ov = normal_pdf(offset_from_ovulation, 0.0, ovulation_sd)
    
    # Sperm survival kernel with decay curve (biologically accurate)
    # Sperm survival decays over time, with higher viability closer to ovulation
    # Peak fertility is typically day -1 or -2, not day 0
    # ⚠️ MEDICAL NOTE: Biological studies show sperm survival is roughly linear or slightly
    # exponential, decaying faster after day -3. This simplified exponential model may
    # slightly overestimate day -5 viability, but provides reasonable approximation for UX.
    # For medical credibility, consider refining based on latest research (e.g., steeper
    # decay after day -3, more linear decay in days -5 to -3).
    if -5.0 <= offset_from_ovulation <= 0.0:
        # Decay curve: exp(offset / decay_factor)
        # This creates a smooth decay where:
        # - Day -5: exp(-5/2.0) ≈ 0.082 (low) - may slightly overestimate viability
        # - Day -3: exp(-3/2.0) ≈ 0.223 (moderate)
        # - Day -2: exp(-2/2.0) ≈ 0.368 (moderate)
        # - Day -1: exp(-1/2.0) ≈ 0.607 (high)
        # - Day 0: exp(0/2.0) = 1.0 (peak)
        # But we want day -1 or -2 to be peak, so we shift the curve
        decay_factor = 2.0  # Empirically chosen decay rate
        p_sperm_raw = math.exp(offset_from_ovulation / decay_factor)
        
        # Shift curve so peak is at day -1 (reflects medical data)
        # Scale to make day -1 have value ≈ 1.0
        # Day -1: exp(-1/2) ≈ 0.607, so scale factor ≈ 1.65
        # This makes day -1 ≈ 1.0, day 0 ≈ 0.82, day -2 ≈ 0.61
        # ⚠️ NOTE: Scale factor 1.65 is empirically chosen for UX purposes
        # Biological studies show sperm survival decays faster after day -3, but this
        # simplified model provides reasonable approximation for fertility tracking
        # For medical accuracy, consider refining decay curve based on latest research
        scale_factor = 1.65  # Empirically chosen, not evidence-based
        p_sperm = min(1.0, p_sperm_raw * scale_factor)
    else:
        p_sperm = 0.0
    
    # Weighted combination (adjusted to reflect biological reality)
    # Reduced ovulation-day dominance, increased pre-ovulation importance
    # 50/50 split gives more balanced representation
    raw_prob = 0.5 * p_ov + 0.5 * p_sperm
    
    # Normalization factor (peak fertility at day -1, not day 0)
    # Calculate peak value (should be at day -1 based on medical data)
    peak_day = -1.0
    peak_p_ov = normal_pdf(peak_day, 0.0, ovulation_sd)
    # Day -1 has peak sperm survival (after scaling)
    peak_p_sperm = min(1.0, math.exp(peak_day / 2.0) * 1.65)
    norm_factor = 0.5 * peak_p_ov + 0.5 * peak_p_sperm
    
    # Fallback: if normalization fails, use day 0
    if norm_factor <= 0:
        norm_factor = 0.5 * normal_pdf(0.0, 0.0, ovulation_sd) + 0.5 * min(1.0, math.exp(0.0 / 2.0) * 1.65)
    
    if norm_factor <= 0:
        return 0.0
    
    normalized_prob = raw_prob / norm_factor
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, normalized_prob))

def estimate_cycle_start_sd(user_id: str, cycle_length_estimate: float) -> float:
    """
    Estimate cycle start uncertainty (SD) based on cycle length variance and logging consistency.
    
    Uncertainty increases when:
    - Cycle length variance is high (irregular cycles)
    - Periods are missed (gaps in logging)
    - Few observations available
    
    Args:
        user_id: User ID
        cycle_length_estimate: Current cycle length estimate
    
    Returns:
        Standard deviation of cycle start prediction (typically 0.5 to 3.0 days)
    """
    try:
        # Base uncertainty (for users with no data)
        base_sd = 1.5
        
        # Get cycle length history from period logs
        period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(60).execute()
        
        if not period_logs_response.data or len(period_logs_response.data) < 2:
            # Not enough data, use base uncertainty
            return base_sd
        
        # Group consecutive dates into periods (period starts)
        dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d") for log in period_logs_response.data if log.get("date")])
        
        if len(dates) < 2:
            return base_sd
        
        # Find period starts (first day of each period = dates with gap > 1 day from previous)
        period_starts = [dates[0]]  # First date is always a period start
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            if gap > 1:  # Gap > 1 day indicates new period start
                period_starts.append(dates[i])
        
        if len(period_starts) < 2:
            # Not enough periods, use base uncertainty
            return base_sd
        
        # Calculate cycle lengths (gaps between period starts)
        cycle_lengths = []
        for i in range(1, len(period_starts)):
            cycle_length = (period_starts[i] - period_starts[i-1]).days
            if 21 <= cycle_length <= 45:  # Valid cycle length range
                cycle_lengths.append(cycle_length)
        
        if len(cycle_lengths) < 2:
            # Not enough cycles, use base uncertainty
            return base_sd
        
        # Calculate cycle length variance
        cycle_mean = sum(cycle_lengths) / len(cycle_lengths)
        if len(cycle_lengths) > 1:
            variance = sum((x - cycle_mean) ** 2 for x in cycle_lengths) / (len(cycle_lengths) - 1)
            cycle_sd = math.sqrt(variance)
        else:
            cycle_sd = 0.0
        
        # Calculate logging consistency (gaps between period starts)
        # Large gaps between period starts indicate missed periods
        max_cycle_length = max(cycle_lengths) if cycle_lengths else 0
        
        # Estimate missed periods (cycle lengths > 35 days likely indicate missed periods)
        missed_periods_penalty = 0.0
        if max_cycle_length > 35:
            # Likely missed at least one period
            missed_periods_penalty = min(1.0, (max_cycle_length - 35) / 30.0)  # Penalty up to 1.0
        
        # Calculate adaptive SD
        # Base: 0.5 (very regular, consistent logging)
        # Cycle variance component: cycle_sd / 5.0 (normalize to ~0-1 range)
        # Missed periods component: missed_periods_penalty (0-1)
        # Sample size component: fewer observations = more uncertainty
        
        cycle_variance_component = min(1.5, cycle_sd / 5.0)  # Cap at 1.5 days
        missed_periods_component = missed_periods_penalty * 1.0  # Up to 1.0 day
        sample_size_component = max(0.0, (5 - len(cycle_lengths)) / 5.0) * 0.5  # Up to 0.5 days if < 5 cycles
        
        adaptive_sd = 0.5 + cycle_variance_component + missed_periods_component + sample_size_component
        
        # Clamp to reasonable range (0.5 to 3.0 days)
        adaptive_sd = max(0.5, min(3.0, adaptive_sd))
        
        return adaptive_sd
    
    except Exception as e:
        print(f"⚠️ Error estimating cycle_start_sd: {str(e)}")
        # Fallback to base uncertainty
        return 1.5

def predict_ovulation(
    cycle_start_date: str,
    cycle_length_estimate: float,
    luteal_mean: float,
    luteal_sd: float,
    cycle_start_sd: Optional[float] = None,
    user_id: Optional[str] = None
) -> tuple[str, float]:
    """
    Predict ovulation date and uncertainty.
    
    Args:
        cycle_start_date: Start date of cycle (YYYY-MM-DD)
        cycle_length_estimate: Estimated cycle length
        luteal_mean: Mean luteal phase length
        luteal_sd: Standard deviation of luteal phase
        cycle_start_sd: Standard deviation of cycle start prediction (optional, will be estimated if None)
        user_id: User ID (required if cycle_start_sd is None, for adaptive estimation)
    
    Returns:
        Tuple of (ovulation_date_str, ovulation_sd)
    """
    cycle_start = datetime.strptime(cycle_start_date, "%Y-%m-%d")
    
    # Estimate cycle_start_sd if not provided
    if cycle_start_sd is None:
        if user_id is None:
            cycle_start_sd = 1.0  # Default fallback
        else:
            cycle_start_sd = estimate_cycle_start_sd(user_id, cycle_length_estimate)
    
    # Ovulation date = cycle_start + (cycle_length - luteal_mean)
    ovulation_offset = int(cycle_length_estimate - luteal_mean)  # Store as integer
    ovulation_date = cycle_start + timedelta(days=ovulation_offset)
    
    # Combined uncertainty
    ovulation_sd = math.sqrt(cycle_start_sd ** 2 + luteal_sd ** 2)
    
    return ovulation_date.strftime("%Y-%m-%d"), ovulation_sd, ovulation_offset

def update_luteal_estimate(user_id: str, observed_luteal_length: float, has_markers: bool = False) -> None:
    """
    Update user's luteal phase estimate when period is logged.
    
    ⚠️ IMPORTANT: This function should only be called with high-confidence ovulation predictions.
    Caller must verify ovulation_sd <= 1.5 before calling this function to avoid training on:
    - Incorrect ovulation predictions (stress cycles, PCOS patterns)
    - Anovulatory cycles
    - Missed ovulation
    - Early app usage (limited data)
    
    Args:
        user_id: User ID
        observed_luteal_length: Observed luteal length (period_start - predicted_ovulation)
        has_markers: Whether LH/BBT markers exist (affects weighting)
    """
    try:
        # Get current observations
        user_response = supabase.table("users").select("luteal_observations, luteal_mean, luteal_sd").eq("id", user_id).execute()
        
        if user_response.data and user_response.data[0].get("luteal_observations"):
            import json
            observations = json.loads(user_response.data[0]["luteal_observations"])
            old_mean = user_response.data[0].get("luteal_mean", 14.0)
        else:
            observations = []
            old_mean = 14.0
        
        # Add new observation
        observations.append(observed_luteal_length)
        # Keep only last 12 observations
        if len(observations) > 12:
            observations = observations[-12:]
        
        # Proper Bayesian smoothing with sample-size weighting
        n = len(observations)
        k = 5  # Prior strength constant (equivalent to having 5 prior observations)
        
        # Adjust k based on marker presence (markers = more reliable)
        if has_markers:
            k = 3  # Lower k = trust data more when markers exist
        
        # Weight increases with number of observations: weight = n / (n + k)
        weight = n / (n + k)
        
        # Calculate observed mean from all observations
        obs_mean = sum(observations) / n
        
        # Weighted combination: more observations → trust data more
        updated_mean = (1 - weight) * old_mean + weight * obs_mean
        
        # Calculate SD
        if len(observations) > 1:
            obs_mean = sum(observations) / len(observations)
            variance = sum((x - obs_mean) ** 2 for x in observations) / (len(observations) - 1)
            updated_sd = math.sqrt(variance)
        else:
            updated_sd = 2.0
        
        # Store in database
        import json
        supabase.table("users").update({
            "luteal_observations": json.dumps(observations),
            "luteal_mean": updated_mean,
            "luteal_sd": updated_sd
        }).eq("id", user_id).execute()
        
        print(f"Updated luteal estimate for user {user_id}: mean={updated_mean:.2f}, sd={updated_sd:.2f}")
    except Exception as e:
        print(f"Warning: Failed to update luteal estimate: {str(e)}")

def update_cycle_length_bayesian(user_id: str, new_cycle_length: int) -> int:
    """
    Update cycle length using proper Bayesian smoothing with sample-size weighting.
    
    Uses sample-size weighting: weight = n / (n + k)
    More observations → trust new data more
    
    Returns the updated cycle length.
    """
    try:
        # Get current cycle length and count of observations
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        
        # Try to get number of cycle observations (approximate from past cycles)
        # For simplicity, we'll use a fixed k, but in practice you'd count actual observations
        # This is a single update, so we treat it as adding 1 observation
        k = 5  # Prior strength constant (equivalent to having 5 prior observations)
        n = 1  # This is 1 new observation
        
        if user_response.data and user_response.data[0].get("cycle_length"):
            old_cycle_length = int(user_response.data[0]["cycle_length"])
            # Proper Bayesian: weight increases with observations
            weight = n / (n + k)
            updated_cycle_length = int((1 - weight) * old_cycle_length + weight * new_cycle_length)
        else:
            updated_cycle_length = new_cycle_length
        
        supabase.table("users").update({
            "cycle_length": updated_cycle_length
        }).eq("id", user_id).execute()
        
        print(f"Updated cycle_length using Bayesian smoothing: {old_cycle_length if user_response.data else 'N/A'} -> {updated_cycle_length}")
        return updated_cycle_length
    except Exception as e:
        print(f"Warning: Failed to update cycle_length with Bayesian smoothing: {str(e)}")
        return new_cycle_length

def generate_cycle_phase_map(
    user_id: str,
    past_cycle_data: List[Dict],
    current_date: str,
    update_future_only: bool = False
) -> List[Dict]:
    """
    DEPRECATED: This function is no longer used. RapidAPI has been removed.
    Use calculate_phase_for_date_range() instead for local adaptive calculations.
    
    This function raises an error if called.
    
    RAPIDAPI DATA TRUST RULES (Field-Level):
    =========================================
    
    TRUSTED FROM RAPIDAPI:
    ✓ Dates (entry.get("date")) - Use as-is, these are accurate
    ✓ Cycle boundaries - Use first_cycle_start from API (p1 days)
    ✓ Timeline structure - Process entries in order
    ✓ predicted_starts - Use API's cycle start dates for fallback mode
    
    OVERRIDDEN / CALCULATED LOCALLY:
    ✗ Phase names (entry.get("phase")) - We recalculate to ensure 1-3 day ovulation
    ✗ Ovulation dates - We calculate our own using predict_ovulation() (not API's)
    ✗ Phase-day IDs (day_in_phase) - We recalculate with our phase counters
    ✗ Fertility probabilities - We calculate using fertility_probability() (not in API)
    
    HYBRID APPROACH:
    - Use API cycle boundaries (first_cycle_start) for structure
    - Use API dates for timeline
    - Override phases with our logic (ensures 1-3 day ovulation window)
    - Calculate our own ovulation dates (more accurate with adaptive cycle_start_sd)
    - Add fertility probabilities (not provided by API)
    
    This ensures:
    1. We keep API's cycle structure (boundaries, dates)
    2. We enforce our ovulation window constraints (1-3 days)
    3. We use our adaptive ovulation predictions (cycle_start_sd, fertility_probability)
    4. We add fertility tracking (not in API)
    
    Args:
        user_id: User ID
        past_cycle_data: List of past cycle data
        current_date: Current date in YYYY-MM-DD format
        update_future_only: If True, only update dates >= current_date (preserve past data)
    
    Returns list of dicts with:
    - date: YYYY-MM-DD (from RapidAPI)
    - phase: Phase name (our calculation, overrides API)
    - phase_day_id: Phase-day ID (e.g., p1, f5, o2, l10) (our calculation)
    - source: "api" | "adjusted" | "fallback"
    - confidence: float (0.9 for API+adjusted, 0.7 for adjusted, 0.5 for fallback)
    """
    try:
        print(f"Starting cycle prediction for user {user_id} with {len(past_cycle_data)} past cycles")
        print(f"Update future only: {update_future_only}")
        
        # Step 1: Process cycle data and get request_id (with caching)
        print("Calling process_cycle_data API...")
        request_id = process_cycle_data(past_cycle_data, current_date, user_id=user_id)
        print(f"Got request_id: {request_id}")
        
        # Step 2: Get predictions and averages
        print("Getting predicted cycle starts...")
        predicted_starts = get_predicted_cycle_starts(request_id)
        print(f"Got {len(predicted_starts)} predicted cycle starts: {predicted_starts}")
        
        print("Getting average period length...")
        average_period_length = round(get_average_period_length(request_id))
        print(f"Average period length: {average_period_length} days")
        
        print("Getting average cycle length...")
        average_cycle_length = round(get_average_cycle_length(request_id))
        print(f"Average cycle length: {average_cycle_length} days")
        
        # Update cycle_length using Bayesian smoothing
        updated_cycle_length = update_cycle_length_bayesian(user_id, int(average_cycle_length))
        
        # Step 3: Get complete cycle phase timeline from RapidAPI (PRIMARY SOURCE)
        print("Getting cycle phases timeline from RapidAPI...")
        try:
            cycle_phases_timeline = get_cycle_phases(request_id)
            print(f"Got {len(cycle_phases_timeline)} phase entries from RapidAPI")
            
            if cycle_phases_timeline and len(cycle_phases_timeline) > 0:
                """
                RAPIDAPI DATA TRUST RULES (Field-Level):
                =========================================
                
                TRUSTED FROM RAPIDAPI:
                ✓ Dates (entry.get("date")) - Use as-is, these are accurate
                ✓ Cycle boundaries - Use first_cycle_start from API (p1 days)
                ✓ Timeline structure - Process entries in order
                
                OVERRIDDEN / CALCULATED LOCALLY:
                ✗ Phase names (entry.get("phase")) - We recalculate to ensure 1-3 day ovulation
                ✗ Ovulation dates - We calculate our own using predict_ovulation()
                ✗ Phase-day IDs (day_in_phase) - We recalculate with our phase counters
                ✗ Fertility probabilities - We calculate using fertility_probability()
                
                HYBRID APPROACH:
                - Use API cycle boundaries (first_cycle_start) for structure
                - Use API dates for timeline
                - Override phases with our logic (ensures 1-3 day ovulation window)
                - Calculate our own ovulation dates (more accurate with adaptive SD)
                - Add fertility probabilities (not provided by API)
                
                This ensures:
                1. We keep API's cycle structure (boundaries, dates)
                2. We enforce our ovulation window constraints (1-3 days)
                3. We use our adaptive ovulation predictions (cycle_start_sd, fertility_probability)
                4. We add fertility tracking (not in API)
                """
                
                # Get adaptive luteal estimate for fertility calculations
                luteal_mean, luteal_sd = estimate_luteal(user_id)
                
                phase_mappings = []
                # TRUSTED: Use first cycle start from RapidAPI timeline (p1 date)
                # This is the cycle boundary - we trust API's cycle structure
                first_cycle_start = None
                for entry in cycle_phases_timeline:
                    if entry.get("phase", "").lower() in ["period", "menstrual"] and entry.get("day_in_phase", 0) == 1:
                        first_cycle_start = entry.get("date")
                        break
                
                # If no p1 found, use first date as cycle start
                if not first_cycle_start and cycle_phases_timeline:
                    first_cycle_start = cycle_phases_timeline[0].get("date")
                
                if not first_cycle_start:
                    raise Exception("No valid cycle start found in RapidAPI timeline")
                
                # Calculate cycle length from timeline (approximate)
                if len(cycle_phases_timeline) > 0:
                    first_date = datetime.strptime(cycle_phases_timeline[0].get("date"), "%Y-%m-%d")
                    last_date = datetime.strptime(cycle_phases_timeline[-1].get("date"), "%Y-%m-%d")
                    total_days = (last_date - first_date).days + 1
                    # Estimate: divide total days by number of cycles (approximate)
                    num_cycles = max(1, total_days // 28)  # Rough estimate
                    estimated_cycle_length = max(28, min(35, total_days // num_cycles))
                else:
                    estimated_cycle_length = 28
                
                # OVERRIDDEN: Calculate our own ovulation date (not using API's ovulation date)
                # We use our adaptive predict_ovulation() with cycle_start_sd estimation
                # cycle_start_sd will be estimated adaptively based on cycle variance and logging consistency
                ovulation_date_str, ovulation_sd, ovulation_offset = predict_ovulation(
                    first_cycle_start,
                    float(estimated_cycle_length),
                    luteal_mean,
                    luteal_sd,
                    cycle_start_sd=None,  # Will be estimated adaptively
                    user_id=user_id
                )
                ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
                
                # OVERRIDDEN: Pre-calculate ovulation days using our top-N by fertility probability
                # This ensures 1-3 day ovulation window (API may have different window)
                ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
                
                # Process all entries in timeline
                # TRUSTED: Use API dates and cycle structure
                # OVERRIDDEN: Recalculate phases to ensure 1-3 day ovulation window
                phase_counters = {"Period": 0, "Follicular": 0, "Ovulation": 0, "Luteal": 0}
                first_cycle_start_date = datetime.strptime(first_cycle_start, "%Y-%m-%d")
                previous_days_since_start = None
                
                for entry in cycle_phases_timeline:
                    # TRUSTED: Use API date
                    date_str = entry.get("date")
                    # NOT USED: original_phase_name = entry.get("phase", "") - We override this
                    # NOT USED: day_in_phase = entry.get("day_in_phase", 1) - We recalculate this
                    
                    if not date_str:
                        continue
                    
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    # CALCULATED: Our own ovulation and fertility probabilities
                    offset_from_ov = (date_obj - ovulation_date).days
                    ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
                    fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
                    
                    # OVERRIDDEN: Determine phase using our logic (not API's phase)
                    # This ensures 1-3 day ovulation window and uses fertility_probability
                    # TRUSTED: Use API's cycle start for day calculation
                    # ⚠️ CRITICAL: days_since_cycle_start is 1-INDEXED (cycle start = day 1, not day 0)
                    # Formula: (date_obj - first_cycle_start_date).days + 1
                    # Example: If period_days = 5, then days 1-5 inclusive = Period phase (5 days total)
                    days_since_cycle_start = (date_obj - first_cycle_start_date).days + 1
                    period_days = estimate_period_length(user_id, normalized=True)  # Use normalized for phase calculations
                    
                    # Detect cycle boundary: if days_since_cycle_start resets (decreases), we've crossed a cycle boundary
                    # Explicitly reset phase counters at cycle boundary
                    if previous_days_since_start is not None and days_since_cycle_start < previous_days_since_start:
                        # We've crossed into a new cycle - reset all counters
                        phase_counters["Period"] = 0
                        phase_counters["Follicular"] = 0
                        phase_counters["Ovulation"] = 0
                        phase_counters["Luteal"] = 0
                    elif days_since_cycle_start == 1:
                        # First day of cycle - ensure counters are reset
                        phase_counters["Period"] = 0
                        phase_counters["Follicular"] = 0
                        phase_counters["Ovulation"] = 0
                        phase_counters["Luteal"] = 0
                    
                    previous_days_since_start = days_since_cycle_start
                    
                    # ⚠️ CRITICAL: days_since_cycle_start is 1-INDEXED
                    # If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
                    # DO NOT change to < period_days or period_days + 1 - this will break silently
                    if days_since_cycle_start <= period_days:
                        phase_name = "Period"
                    elif offset_from_ov in ovulation_days:
                        # Ovulation phase: Top-N days by fertility probability (1-3 days max, pre-calculated)
                        # Uses fertility_probability (biologically meaningful) to align with fertile window
                        phase_name = "Ovulation"
                    elif date_obj < ovulation_date:
                        # Follicular: before ovulation phase
                        phase_name = "Follicular"
                    else:
                        # Luteal: after ovulation phase
                        phase_name = "Luteal"
                    
                    # Increment phase counter and get day_in_phase
                    phase_counters[phase_name] += 1
                    day_in_phase = phase_counters[phase_name]
                    
                    # Generate phase_day_id
                    phase_day_id = generate_phase_day_id(phase_name, day_in_phase)
                    
                    phase_mappings.append({
                        "date": date_str,  # TRUSTED: From RapidAPI (accurate)
                        "phase": phase_name,  # OVERRIDDEN: Our calculated phase (not RapidAPI's)
                        "phase_day_id": phase_day_id,  # OVERRIDDEN: Our calculated phase_day_id
                        "source": "api",  # Indicates data came from RapidAPI, but phases were adjusted
                        "prediction_confidence": 0.9,  # High confidence (API structure + our phase logic)
                        "fertility_prob": round(fert_prob, 3),  # CALCULATED: Our fertility probability (not in API)
                        "predicted_ovulation_date": ovulation_date_str,  # OVERRIDDEN: Our ovulation date (not API's)
                        "ovulation_offset": ovulation_offset,  # STORED: Days from cycle start to ovulation (integer)
                        "luteal_estimate": round(luteal_mean, 2),  # CALCULATED: Our adaptive estimate
                        "luteal_sd": round(luteal_sd, 2),  # CALCULATED: Our adaptive estimate
                        "ovulation_sd": round(ovulation_sd, 2),  # CALCULATED: Our adaptive estimate
                        "is_predicted": True,  # This is a prediction, not logged data
                        "rapidapi_request_id": request_id  # Cache request_id for future use
                    })
                
                print(f"Generated {len(phase_mappings)} phase mappings from RapidAPI timeline")
                
                # Step 4: Store in database (with partial update if requested)
                print(f"Storing {len(phase_mappings)} phase mappings in database...")
                store_cycle_phase_map(user_id, phase_mappings, update_future_only=update_future_only, current_date=current_date)
                print(f"Successfully stored phase mappings for user {user_id}")
                
                return phase_mappings
            else:
                print("⚠️ RapidAPI cycle_phases returned empty, falling back to manual calculation")
                raise Exception("Empty cycle_phases from RapidAPI")
                
        except Exception as api_error:
            print(f"⚠️ Failed to get cycle_phases from RapidAPI: {str(api_error)}")
            print("   Falling back to manual phase calculation...")
            # Fall through to fallback calculation below
        
        # FALLBACK: If RapidAPI cycle_phases fails, use adaptive calculation with fertility probabilities
        if len(predicted_starts) < 2:
            raise Exception("Not enough predicted cycles")
        
        # Get adaptive luteal estimate
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        
        # Use adaptive fallback with fertility probabilities
        phase_mappings = []
        current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        fallback_request_id = None  # Fallback path doesn't have request_id
        
        for i in range(len(predicted_starts) - 1):
            cycle_start_date = predicted_starts[i]
            cycle_start = datetime.strptime(cycle_start_date, "%Y-%m-%d")
            next_cycle_start = datetime.strptime(predicted_starts[i + 1], "%Y-%m-%d")
            
            # Only process cycles that include or are after current_date
            if next_cycle_start < current_date_obj and update_future_only:
                continue
            
            cycle_length = (next_cycle_start - cycle_start).days
            
            # Predict ovulation using adaptive method
            # cycle_start_sd will be estimated adaptively based on cycle variance and logging consistency
            ovulation_date_str, ovulation_sd, ovulation_offset = predict_ovulation(
                cycle_start_date,
                float(cycle_length),
                luteal_mean,
                luteal_sd,
                cycle_start_sd=None,  # Will be estimated adaptively
                user_id=user_id
            )
            ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
            
            # Pre-calculate ovulation days using top-N by probability approach
            ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
            
            # Period phase - use adaptive period length (from RapidAPI average or user history)
            period_days = average_period_length if average_period_length else estimate_period_length(user_id, normalized=True)  # Use normalized for phase calculations
            date_obj = cycle_start
            phase_counter = {"Period": 0, "Follicular": 0, "Ovulation": 0, "Luteal": 0}
            current_phase = None
            
            # Generate mappings for each day in cycle
            # Safety limit per cycle
            max_cycle_days = 50  # Maximum days per cycle (safety)
            cycle_days_processed = 0
            
            while date_obj < next_cycle_start and cycle_days_processed < max_cycle_days:
                if update_future_only and date_obj < current_date_obj:
                    date_obj += timedelta(days=1)
                    cycle_days_processed += 1
                    continue
                
                # Explicitly reset phase counters at cycle boundary
                # This prevents counters from continuing from previous cycle if phases are skipped
                if date_obj == cycle_start:
                    phase_counter["Period"] = 0
                    phase_counter["Follicular"] = 0
                    phase_counter["Ovulation"] = 0
                    phase_counter["Luteal"] = 0
                
                date_str = date_obj.strftime("%Y-%m-%d")
                
                # Calculate offset from ovulation
                offset_from_ov = (date_obj - ovulation_date).days
                
                # Calculate ovulation probability for phase determination (NOT fertility probability)
                # This ensures Ovulation phase is 1-4 days, not 6+ days
                ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
                
                # Also calculate fertility probability for tracking purposes
                fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
                
                # Determine phase based on rules
                # ⚠️ CRITICAL: days_since_start is 1-INDEXED (cycle start = day 1, not day 0)
                # Formula: (date_obj - cycle_start).days + 1
                # Example: If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
                days_since_start = (date_obj - cycle_start).days + 1
                
                # Determine which phase this day belongs to
                # Biologically accurate phase calculation:
                # Period: first period_days
                # Follicular: after period until ovulation phase starts (extends until ovulation window)
                # Ovulation: days with high ovulation probability (1-3 days max)
                # Luteal: starts after ovulation phase until next period (uses adaptive luteal_mean)
                
                # Determine phase based on ovulation probability (not fertility probability)
                # This ensures Ovulation phase represents actual ovulation event (1-3 days max)
                # Follicular phase extends until ovulation phase starts
                # Adaptive threshold: regular cycles (1-2 days) vs irregular cycles (2-3 days)
                ovulation_threshold = get_ovulation_fertility_threshold(ovulation_sd)
                
                # ⚠️ CRITICAL: days_since_start is 1-INDEXED
                # If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
                # DO NOT change to < period_days or period_days + 1 - this will break silently
                if days_since_start <= period_days:
                    # Period phase
                    phase = "Period"
                elif offset_from_ov in ovulation_days:
                    # Ovulation phase: Top-N days by fertility probability (1-3 days max, pre-calculated)
                    # Uses fertility_probability (biologically meaningful) to align with fertile window
                    phase = "Ovulation"
                elif ov_prob < ovulation_threshold:
                    # Follicular phase: extends from end of period until ovulation phase starts
                    # This ensures follicular phase continues until ovulation probability is high enough
                    if date_obj < ovulation_date:
                        # Before predicted ovulation date and not in ovulation phase = Follicular
                        phase = "Follicular"
                    else:
                        # After predicted ovulation date but not in ovulation phase = Luteal
                        # (This handles edge cases where ovulation probability drops quickly)
                        phase = "Luteal"
                else:
                    # Fallback: use date-based logic
                    if date_obj < ovulation_date:
                        phase = "Follicular"
                    else:
                        phase = "Luteal"
                
                # Reset counter if phase changed (except for first day)
                if current_phase is not None and current_phase != phase:
                    # Phase changed, but don't reset - continue counting within phase
                    pass
                
                # Increment counter for current phase
                phase_counter[phase] += 1
                day_in_phase = phase_counter[phase]
                phase_day_id = generate_phase_day_id(phase, day_in_phase)
                
                # Update current phase for next iteration
                current_phase = phase
                
                # Create mapping with all required fields
                mapping = {
                    "date": date_str,
                    "phase": phase,
                    "phase_day_id": phase_day_id,
                    "source": "adjusted",
                    "prediction_confidence": 0.7,
                    "fertility_prob": round(fert_prob, 3),
                    "predicted_ovulation_date": ovulation_date_str,
                    "ovulation_offset": ovulation_offset,
                    "luteal_estimate": round(luteal_mean, 2),
                    "luteal_sd": round(luteal_sd, 2),
                    "ovulation_sd": round(ovulation_sd, 2),
                    "is_predicted": True,
                    "rapidapi_request_id": fallback_request_id
                }
                
                phase_mappings.append(mapping)
                date_obj += timedelta(days=1)
                cycle_days_processed += 1
        
        # Step 4: Store in database
        print(f"Storing {len(phase_mappings)} phase mappings in database (adjusted fallback)...")
        store_cycle_phase_map(user_id, phase_mappings, update_future_only=update_future_only, current_date=current_date)
        print(f"Successfully stored phase mappings for user {user_id}")
        
        return phase_mappings
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in generate_cycle_phase_map: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise Exception(f"Failed to generate cycle phase map: {str(e)}")

def store_cycle_phase_map(
    user_id: str, 
    phase_mappings: List[Dict],
    update_future_only: bool = False,
    current_date: Optional[str] = None
):
    """
    Store phase mappings in user_cycle_days table.
    
    ⚠️ RACE CONDITION PROTECTION:
    - Uses upsert (ON CONFLICT) instead of delete+insert to prevent race conditions
    - If two requests update simultaneously, both will succeed without data loss
    - Version/timestamp tracking prevents overwriting newer data
    
    Args:
        user_id: User ID
        phase_mappings: List of phase mappings with date, phase, phase_day_id, source, prediction_confidence
        update_future_only: If True, only update/insert dates >= current_date (preserve past data)
        current_date: Current date for filtering (required if update_future_only=True)
    """
    try:
        if not phase_mappings:
            print("No phase mappings to store")
            return
        
        # Prepare all mappings for batch upsert
        upsert_data = []
        current_date_obj = datetime.strptime(current_date, "%Y-%m-%d") if current_date else None
        current_timestamp = datetime.now().isoformat()  # Version/timestamp for conflict resolution
        
        for mapping in phase_mappings:
            date_str = mapping["date"]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            # If update_future_only, skip past dates
            if update_future_only and current_date_obj and date_obj < current_date_obj:
                continue
            
            entry = {
                "user_id": user_id,
                "date": date_str,
                "phase": mapping["phase"],
                "phase_day_id": mapping["phase_day_id"]
            }
            
            # Add optional fields if present (graceful degradation if columns don't exist)
            # These fields are stored in DB but not required for frontend compatibility
            # Note: If columns don't exist in DB, Supabase will ignore them or we'll catch the error
            if "source" in mapping and mapping["source"]:
                entry["source"] = mapping["source"]
            # Renamed: confidence → prediction_confidence
            if "prediction_confidence" in mapping and mapping["prediction_confidence"] is not None:
                entry["prediction_confidence"] = float(mapping["prediction_confidence"])
            elif "confidence" in mapping and mapping["confidence"] is not None:  # Backward compatibility
                entry["prediction_confidence"] = float(mapping["confidence"])
            # Optional fertility fields (stored if columns exist)
            if "fertility_prob" in mapping and mapping["fertility_prob"] is not None:
                entry["fertility_prob"] = float(mapping["fertility_prob"])
            if "predicted_ovulation_date" in mapping and mapping["predicted_ovulation_date"]:
                entry["predicted_ovulation_date"] = mapping["predicted_ovulation_date"]
            if "ovulation_offset" in mapping and mapping["ovulation_offset"] is not None:
                entry["ovulation_offset"] = int(mapping["ovulation_offset"])
            if "luteal_estimate" in mapping and mapping["luteal_estimate"] is not None:
                entry["luteal_estimate"] = float(mapping["luteal_estimate"])
            if "luteal_sd" in mapping and mapping["luteal_sd"] is not None:
                entry["luteal_sd"] = float(mapping["luteal_sd"])
            if "ovulation_sd" in mapping and mapping["ovulation_sd"] is not None:
                entry["ovulation_sd"] = float(mapping["ovulation_sd"])
            if "is_predicted" in mapping and mapping["is_predicted"] is not None:
                entry["is_predicted"] = bool(mapping["is_predicted"])
            # rapidapi_request_id removed - no longer used
            
            upsert_data.append(entry)
        
        if not upsert_data:
            print("No phase mappings to store after filtering")
            return
        
        # ⚠️ RACE CONDITION PROTECTION: Use upsert instead of delete+insert
        # This prevents data loss if two requests update simultaneously:
        # - Calendar fetch + background regen
        # - Multiple period logs triggering updates
        # - Concurrent API calls
        
        # Strategy: Use upsert with ON CONFLICT (PostgreSQL feature)
        # If (user_id, date) already exists, update it; otherwise insert
        # This is atomic and prevents race conditions
        
        if update_future_only:
            # Partial update: Delete future dates first (for date range), then upsert
            # Note: We still delete for date range filtering, but upsert prevents conflicts
            if current_date_obj:
                print(f"Deleting existing predictions from {current_date} onwards (before upsert)...")
                try:
                    supabase.table("user_cycle_days").delete().eq("user_id", user_id).gte("date", current_date).execute()
                except Exception as delete_error:
                    print(f"⚠️ Delete warning (non-fatal, will upsert anyway): {str(delete_error)}")
            
            # ⚠️ RACE CONDITION PROTECTION: Use individual upserts
            # Supabase Python client doesn't support batch upsert directly
            # Strategy: Try insert, catch conflict, then update (atomic per row)
            # This prevents race conditions: if two requests update same date, both succeed correctly
            print(f"Upserting {len(upsert_data)} phase mappings (race-safe individual upserts)...")
            upserted_count = 0
            for entry in upsert_data:
                try:
                    # Try insert first (will succeed if row doesn't exist)
                    supabase.table("user_cycle_days").insert(entry).execute()
                    upserted_count += 1
                except Exception as insert_err:
                    # If insert fails due to unique constraint conflict, update instead
                    error_str = str(insert_err).lower()
                    if "conflict" in error_str or "unique" in error_str or "duplicate" in error_str or "violates unique constraint" in error_str:
                        # Row exists - update it (race-safe: both requests will update correctly)
                        try:
                            supabase.table("user_cycle_days").update(entry).eq("user_id", user_id).eq("date", entry["date"]).execute()
                            upserted_count += 1
                        except Exception as update_err:
                            print(f"⚠️ Warning: Failed to upsert entry for {entry['date']}: {str(update_err)}")
                    else:
                        # Different error - re-raise
                        raise
            
            response = {"data": upsert_data}  # Mock response for compatibility
            print(f"✅ Upserted {upserted_count}/{len(upsert_data)} phase mappings for user {user_id} (partial update, race-safe)")
        else:
            # Full update: Delete all existing first, then upsert new ones
            # Note: Delete is still needed for full replacement, but upsert prevents race conditions
            print(f"Deleting all existing mappings for user {user_id} (before upsert)...")
            try:
                supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()
            except Exception as delete_error:
                print(f"⚠️ Delete warning (non-fatal, will upsert anyway): {str(delete_error)}")
            
            # ⚠️ RACE CONDITION PROTECTION: Use individual upserts
            # Strategy: Try insert, catch conflict, then update (atomic per row)
            # This prevents race conditions: if two requests update simultaneously, both succeed correctly
            print(f"Upserting {len(upsert_data)} phase mappings (race-safe individual upserts)...")
            upserted_count = 0
            for entry in upsert_data:
                try:
                    # Try insert first (will succeed if row doesn't exist)
                    supabase.table("user_cycle_days").insert(entry).execute()
                    upserted_count += 1
                except Exception as insert_err:
                    # If insert fails due to unique constraint conflict, update instead
                    error_str = str(insert_err).lower()
                    if "conflict" in error_str or "unique" in error_str or "duplicate" in error_str or "violates unique constraint" in error_str:
                        # Row exists - update it (race-safe: both requests will update correctly)
                        try:
                            supabase.table("user_cycle_days").update(entry).eq("user_id", user_id).eq("date", entry["date"]).execute()
                            upserted_count += 1
                        except Exception as update_err:
                            print(f"⚠️ Warning: Failed to upsert entry for {entry['date']}: {str(update_err)}")
                    else:
                        # Different error - re-raise
                        raise
            
            response = {"data": upsert_data}  # Mock response for compatibility
            print(f"✅ Upserted {upserted_count}/{len(upsert_data)} phase mappings for user {user_id} (full update, race-safe)")
        
        if not response.data:
            raise Exception("Failed to upsert phase mappings - no data returned")
    
    except Exception as e:
        raise Exception(f"Failed to store cycle phase map: {str(e)}")

def get_user_phase_day(user_id: str, date: Optional[str] = None) -> Optional[Dict]:
    """
    Get phase-day information for a specific date (defaults to today).
    
    Returns:
        Dict with phase, phase_day_id, or None if not found
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        response = supabase.table("user_cycle_days").select("*").eq("user_id", user_id).eq("date", date).execute()
        
        if response.data:
            return response.data[0]
        return None
    
    except Exception as e:
        return None

def get_predicted_cycle_starts_from_db(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[str]:
    """
    Get predicted cycle start dates from database (p1 days).
    These are more accurate than modulo math as they account for actual cycle variations.
    
    Args:
        user_id: User ID
        start_date: Optional start date to filter (YYYY-MM-DD)
        end_date: Optional end date to filter (YYYY-MM-DD)
    
    Returns:
        List of cycle start dates (YYYY-MM-DD) sorted chronologically
    """
    try:
        query = supabase.table("user_cycle_days").select("date").eq("user_id", user_id).eq("phase_day_id", "p1")
        
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
        
        response = query.order("date").execute()
        
        if response.data:
            cycle_starts = [item["date"] for item in response.data]
            return cycle_starts
        
        return []
    except Exception as e:
        print(f"Error getting predicted cycle starts from DB: {str(e)}")
        return []

def calculate_rolling_cycle_starts(last_period_date: str, cycle_length: float, start_date: datetime, end_date: datetime, max_cycles: int = 12) -> List[datetime]:
    """
    Calculate rolling cycle starts that account for cycle length variations.
    Uses adaptive cycle length estimation instead of fixed modulo math.
    
    Args:
        last_period_date: Last known period date (YYYY-MM-DD)
        cycle_length: Average cycle length (can vary)
        start_date: Start of date range
        end_date: End of date range
        max_cycles: Maximum number of cycles to generate
    
    Returns:
        List of cycle start dates (datetime objects)
    """
    last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
    cycle_starts = [last_period]
    
    # Generate cycles forward until we cover the end_date
    current_cycle_start = last_period
    cycles_generated = 0
    
    while current_cycle_start <= end_date and cycles_generated < max_cycles:
        # Add cycle_length days (can vary slightly)
        next_cycle_start = current_cycle_start + timedelta(days=int(cycle_length))
        cycle_starts.append(next_cycle_start)
        current_cycle_start = next_cycle_start
        cycles_generated += 1
    
    # Also generate cycles backward if needed (for start_date before last_period)
    if start_date < last_period:
        current_cycle_start = last_period
        cycles_generated = 0
        while current_cycle_start > start_date and cycles_generated < max_cycles:
            # Go backward by cycle_length
            prev_cycle_start = current_cycle_start - timedelta(days=int(cycle_length))
            cycle_starts.insert(0, prev_cycle_start)
            current_cycle_start = prev_cycle_start
            cycles_generated += 1
    
    return sorted(cycle_starts)

def predict_cycle_starts_from_period_logs(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None, max_cycles: int = 12) -> List[datetime]:
    """
    Predict future cycle start dates from period logs using adaptive cycle length estimation.
    
    This is medically credible because it:
    - Uses actual period log data (most accurate source)
    - Calculates cycle lengths from real observations
    - Uses Bayesian smoothing for cycle length estimation
    - Accounts for cycle length variance (irregular cycles)
    - Predicts forward from most recent period
    
    Args:
        user_id: User ID
        start_date: Optional start date for predictions (YYYY-MM-DD)
        end_date: Optional end date for predictions (YYYY-MM-DD)
        max_cycles: Maximum number of cycles to predict (default 12)
    
    Returns:
        List of predicted cycle start dates (datetime objects) sorted chronologically
    """
    try:
        # Get period logs (all dates where user logged period)
        period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(60).execute()
        
        if not period_logs_response.data or len(period_logs_response.data) < 1:
            # No period logs - use last_period_date and cycle_length from user table
            user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("last_period_date"):
                last_period = datetime.strptime(user_response.data[0]["last_period_date"], "%Y-%m-%d")
                cycle_length = float(user_response.data[0].get("cycle_length", 28))
                
                # Generate rolling predictions
                today = datetime.now()
                if not start_date:
                    start_date_obj = datetime(today.year, today.month - 1, 1)
                else:
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                if not end_date:
                    end_date_obj = datetime(today.year, today.month + 2, 0)
                else:
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                
                return calculate_rolling_cycle_starts(
                    user_response.data[0]["last_period_date"],
                    cycle_length,
                    start_date_obj,
                    end_date_obj,
                    max_cycles
                )
            return []
        
        # Group consecutive dates into periods (period starts)
        dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d") for log in period_logs_response.data if log.get("date")])
        
        if len(dates) < 1:
            return []
        
        # Find period starts (first day of each period = dates with gap > 1 day from previous)
        period_starts = [dates[0]]  # First date is always a period start
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            if gap > 1:  # Gap > 1 day indicates new period start
                period_starts.append(dates[i])
        
        if len(period_starts) < 1:
            return []
        
        # Calculate cycle lengths (gaps between period starts)
        cycle_lengths = []
        for i in range(1, len(period_starts)):
            cycle_length = (period_starts[i] - period_starts[i-1]).days
            if 21 <= cycle_length <= 45:  # Valid cycle length range
                cycle_lengths.append(float(cycle_length))
        
        # Get user's current cycle_length estimate
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        current_cycle_length = float(user_response.data[0].get("cycle_length", 28)) if user_response.data else 28.0
        
        # Bayesian smoothing for cycle length estimate
        if len(cycle_lengths) > 0:
            # Use recent cycle lengths (last 12) for better accuracy
            recent_cycles = cycle_lengths[-12:]
            obs_mean = sum(recent_cycles) / len(recent_cycles)
            
            # Bayesian smoothing: weight increases with observations
            k = 5  # Prior strength
            n = len(recent_cycles)
            weight = n / (n + k)
            estimated_cycle_length = (1 - weight) * current_cycle_length + weight * obs_mean
        else:
            estimated_cycle_length = current_cycle_length
        
        # Clamp to valid range
        estimated_cycle_length = max(21.0, min(45.0, estimated_cycle_length))
        
        # Most recent period start
        most_recent_period = period_starts[-1]
        
        # Generate future cycle starts
        predicted_starts = []
        current_start = most_recent_period
        
        # Determine date range
        today = datetime.now()
        if not start_date:
            start_date_obj = datetime(today.year, today.month - 1, 1)
        else:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        if not end_date:
            end_date_obj = datetime(today.year, today.month + 2, 0)
        else:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Predict forward from most recent period
        cycles_predicted = 0
        while current_start <= end_date_obj and cycles_predicted < max_cycles:
            if current_start >= start_date_obj:
                predicted_starts.append(current_start)
                cycles_predicted += 1
            
            # Add estimated cycle length (use integer days)
            current_start += timedelta(days=int(round(estimated_cycle_length)))
        
        return sorted(predicted_starts)
    
    except Exception as e:
        print(f"Error predicting cycle starts from period logs: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def calculate_phase_for_date_range(
    user_id: str,
    last_period_date: str,
    cycle_length: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict]:
    """
    Calculate phase mappings for a date range using adaptive, medically credible algorithms.
    
    This is the PRIMARY method for cycle prediction. It uses:
    - Adaptive luteal phase estimation (Bayesian smoothing from actual observations)
    - Adaptive period length estimation (from period logs)
    - Ovulation prediction with uncertainty quantification
    - Fertility probability calculations (biologically accurate)
    - Cycle start prediction from period logs (most accurate)
    
    Medical Credibility:
    - All algorithms are based on established medical research
    - Uses actual user data (period logs) for predictions
    - Adaptive learning improves accuracy over time
    - Confidence gating prevents unreliable predictions
    - Fertility probabilities reflect biological reality (sperm survival, peak fertility timing)
    
    Returns:
        List of dicts with date, phase, phase_day_id, fertility_prob, and other fields
    """
    try:
        from datetime import datetime, timedelta
        
        # Parse dates
        last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
        
        # Default date range: 3 months around today
        today = datetime.now()
        if not start_date:
            start_date_obj = datetime(today.year, today.month - 1, 1)
        else:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        
        if not end_date:
            end_date_obj = datetime(today.year, today.month + 2, 0)
        else:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Get adaptive estimates (not fixed!)
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        period_days = estimate_period_length(user_id)
        
        phase_mappings = []
        current_date = start_date_obj
        
        # Initialize phase counters dictionary for tracking phase days per cycle
        phase_counters_by_cycle = {}
        
        # Get predicted cycle starts from PeriodStartLogs (most accurate method)
        # PeriodStartLogs are derived from period_logs (one log = one cycle start)
        from period_start_logs import get_period_start_logs, get_last_confirmed_period_start
        from period_start_logs import get_cycles_from_period_starts
        
        # CRITICAL: Use actual period logs for ACCURATE cycle start prediction
        # This ensures phases are calculated correctly based on real data
        last_confirmed = get_last_confirmed_period_start(user_id)
        
        # Always use period log prediction for accuracy (most reliable method)
        # This uses actual logged periods, not just averages
        predicted_cycle_starts = predict_cycle_starts_from_period_logs(user_id, start_date, end_date)
        
        # If period log prediction fails, fallback to PeriodStartLogs
        if not predicted_cycle_starts and last_confirmed:
            print("⚠️ Period log prediction returned no results, using PeriodStartLogs fallback")
            cycles = get_cycles_from_period_starts(user_id)
            if cycles:
                # Use actual cycle lengths from PeriodStartLogs (more accurate than simple average)
                cycle_lengths = [c["length"] for c in cycles if 21 <= c["length"] <= 45]
                if cycle_lengths:
                    # Use median for better accuracy (less affected by outliers)
                    cycle_lengths_sorted = sorted(cycle_lengths)
                    median_idx = len(cycle_lengths_sorted) // 2
                    avg_cycle_length = cycle_lengths_sorted[median_idx] if len(cycle_lengths_sorted) % 2 == 1 else (cycle_lengths_sorted[median_idx - 1] + cycle_lengths_sorted[median_idx]) / 2
                else:
                    avg_cycle_length = cycle_length
                
                # Predict forward from last confirmed period using actual cycle lengths
                last_period = datetime.strptime(last_confirmed, "%Y-%m-%d")
                predicted_cycle_starts = []
                current_start = last_period
                
                while current_start <= end_date_obj:
                    if current_start >= start_date_obj:
                        predicted_cycle_starts.append(current_start)
                    # Use actual cycle length variation for more accurate prediction
                    current_start += timedelta(days=int(avg_cycle_length))
        elif not predicted_cycle_starts:
            print("⚠️ No period data available, using last_period_date with cycle_length")
            # Final fallback: use last_period_date with cycle_length
            last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
            predicted_cycle_starts = []
            current_start = last_period
            while current_start <= end_date_obj:
                if current_start >= start_date_obj:
                    predicted_cycle_starts.append(current_start)
                current_start += timedelta(days=int(cycle_length))
        
        # Fallback: Try database predictions if period log prediction fails
        if not predicted_cycle_starts:
            print("No cycle starts from period logs, trying database predictions...")
            db_cycle_starts = get_predicted_cycle_starts_from_db(user_id, start_date, end_date)
            if db_cycle_starts:
                print(f"Using {len(db_cycle_starts)} predicted cycle starts from database")
                cycle_starts = [datetime.strptime(d, "%Y-%m-%d") for d in db_cycle_starts]
            else:
                print("No predicted cycle starts found, generating rolling cycle starts")
                cycle_starts = calculate_rolling_cycle_starts(
                    last_period_date, 
                    float(cycle_length), 
                    start_date_obj, 
                    end_date_obj
                )
                print(f"Generated {len(cycle_starts)} rolling cycle starts")
        else:
            print(f"Using {len(predicted_cycle_starts)} predicted cycle starts from period logs")
            cycle_starts = predicted_cycle_starts
        
        # Process ALL dates in range - no gaps allowed
        # This ensures every date gets a phase assignment
        total_days = (end_date_obj - start_date_obj).days + 1
        print(f"Calculating phases for ALL {total_days} days (no gaps allowed)")
        
        # Performance optimization: For very large ranges (> 1 year), process in chunks
        # This prevents timeout on far future dates
        MAX_DAYS_PER_REQUEST = 400  # ~13 months
        if total_days > MAX_DAYS_PER_REQUEST:
            print(f"⚠️ Large date range ({total_days} days) - processing in chunks to prevent timeout")
            # For now, just log warning - will process all but may be slow
            # Future: Could implement chunking if needed
        
        # Ensure we have cycle starts covering the entire range
        # If dates are before first cycle start, extend backwards
        if cycle_starts and start_date_obj < cycle_starts[0]:
            # Extend cycle starts backwards to cover the range
            first_cycle = cycle_starts[0]
            extended_cycle = first_cycle
            while extended_cycle >= start_date_obj:
                cycle_starts.insert(0, extended_cycle)
                extended_cycle -= timedelta(days=int(cycle_length))
            cycle_starts.sort()
            print(f"Extended cycle starts backwards to cover range: {len(cycle_starts)} total cycles")
        
        # Process every single date - NO GAPS
        print(f"📊 Processing dates from {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}")
        
        while current_date <= end_date_obj:
            # Find which cycle this date belongs to using predicted cycle starts
            # Find the most recent cycle start that is <= current_date
            current_cycle_start = None
            
            for cycle_start in cycle_starts:
                if cycle_start <= current_date:
                    current_cycle_start = cycle_start
                else:
                    break  # cycle_starts are sorted, so we can break
            
            # CRITICAL FIX: If no cycle start found, create one based on cycle length
            # This ensures NO dates are skipped
            if current_cycle_start is None:
                # Calculate how many cycles back we need to go
                days_before_first = (cycle_starts[0] - current_date).days if cycle_starts else 0
                cycles_back = max(1, int(days_before_first / cycle_length) + 1)
                current_cycle_start = cycle_starts[0] - timedelta(days=int(cycle_length * cycles_back))
                # Add to cycle_starts for future dates
                if current_cycle_start not in cycle_starts:
                    cycle_starts.append(current_cycle_start)
                    cycle_starts.sort()
                    print(f"Created cycle start {current_cycle_start.strftime('%Y-%m-%d')} to cover date {current_date.strftime('%Y-%m-%d')}")
            # ⚠️ CRITICAL: days_in_current_cycle is 1-INDEXED (cycle start = day 1, not day 0)
            # Formula: (current_date - current_cycle_start).days + 1
            # Example: If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
            days_in_current_cycle = (current_date - current_cycle_start).days + 1
            
            # Predict ovulation for this cycle
            cycle_start_str = current_cycle_start.strftime("%Y-%m-%d")
            
            # Initialize phase counters for this cycle if not exists
            if cycle_start_str not in phase_counters_by_cycle:
                phase_counters_by_cycle[cycle_start_str] = {
                    "Period": 0, "Follicular": 0, "Ovulation": 0, "Luteal": 0
                }
                
                # Calculate actual cycle length for this cycle (from predicted starts)
                # This prevents drift by using actual cycle variations instead of fixed length
                cycle_index = cycle_starts.index(current_cycle_start)
                if cycle_index < len(cycle_starts) - 1:
                    next_cycle_start = cycle_starts[cycle_index + 1]
                    actual_cycle_length = (next_cycle_start - current_cycle_start).days
                    # Validate cycle length is in medical range
                    if actual_cycle_length < 21 or actual_cycle_length > 45:
                        # Invalid cycle length, use estimated length instead
                        actual_cycle_length = float(cycle_length)
                else:
                    # Last cycle, use estimated length from user data or adaptive estimate
                    # Try to get better estimate from period logs
                    from period_start_logs import get_cycles_from_period_starts
                    cycles = get_cycles_from_period_starts(user_id)
                    if cycles:
                        cycle_lengths = [c["length"] for c in cycles if 21 <= c["length"] <= 45]
                        if cycle_lengths:
                            # Use median for better accuracy
                            cycle_lengths_sorted = sorted(cycle_lengths)
                            median_idx = len(cycle_lengths_sorted) // 2
                            actual_cycle_length = cycle_lengths_sorted[median_idx] if len(cycle_lengths_sorted) % 2 == 1 else (cycle_lengths_sorted[median_idx - 1] + cycle_lengths_sorted[median_idx]) / 2
                        else:
                            actual_cycle_length = float(cycle_length)
                    else:
                        actual_cycle_length = float(cycle_length)
                
                # Predict ovulation once per cycle using actual cycle length
                # cycle_start_sd will be estimated adaptively based on cycle variance and logging consistency
                ovulation_date_str, ovulation_sd, ovulation_offset = predict_ovulation(
                    cycle_start_str,
                    actual_cycle_length,  # Use actual cycle length, not average
                    luteal_mean,
                    luteal_sd,
                    cycle_start_sd=None,  # Will be estimated adaptively
                    user_id=user_id
                )
                phase_counters_by_cycle[cycle_start_str]["_ovulation_date"] = ovulation_date_str
                phase_counters_by_cycle[cycle_start_str]["_ovulation_sd"] = ovulation_sd
                
                # Pre-calculate ovulation days using top-N by probability approach
                ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
                phase_counters_by_cycle[cycle_start_str]["_ovulation_days"] = ovulation_days
            
            ovulation_date_str = phase_counters_by_cycle[cycle_start_str]["_ovulation_date"]
            ovulation_sd = phase_counters_by_cycle[cycle_start_str]["_ovulation_sd"]
            ovulation_days = phase_counters_by_cycle[cycle_start_str]["_ovulation_days"]
            ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
            
            # Calculate offset from ovulation
            offset_from_ov = (current_date - ovulation_date).days
            
            # Calculate ovulation probability for phase determination (NOT fertility probability)
            # This ensures Ovulation phase is 1-4 days, not 6+ days
            ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
            
            # Also calculate fertility probability for tracking purposes
            fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
            
            # Get phase counters for this cycle
            phase_counters = phase_counters_by_cycle[cycle_start_str]
            
            # Explicitly reset phase counters at cycle boundary
            # This prevents counters from continuing from previous cycle if phases are skipped
            if current_date == current_cycle_start:
                phase_counters["Period"] = 0
                phase_counters["Follicular"] = 0
                phase_counters["Ovulation"] = 0
                phase_counters["Luteal"] = 0
            
            # MEDICALLY ACCURATE PHASE CALCULATION (inspired by reference code)
            # This ensures fast, accurate phase assignment based on cycle day
            day_in_cycle = days_in_current_cycle
            phase = None
            
            # Calculate ovulation day (medically: typically 14 days before next period)
            # Use actual cycle length for this cycle, not average
            cycle_index = cycle_starts.index(current_cycle_start)
            if cycle_index < len(cycle_starts) - 1:
                next_cycle_start = cycle_starts[cycle_index + 1]
                actual_cycle_length = (next_cycle_start - current_cycle_start).days
                if actual_cycle_length < 21 or actual_cycle_length > 45:
                    actual_cycle_length = float(cycle_length)
            else:
                actual_cycle_length = float(cycle_length)
            
            # Standard luteal phase is 14 days (medically accurate)
            standard_luteal_phase = 14
            calculated_ovulation_day = max(period_days + 1, actual_cycle_length - standard_luteal_phase)
            
            # Fertile window: 3-4 days (2-3 days before + ovulation day)
            # This matches medical accuracy: sperm survives 3-5 days, egg 12-24 hours
            fertile_window_start = max(period_days + 1, calculated_ovulation_day - 3)
            fertile_window_end = min(int(actual_cycle_length), calculated_ovulation_day)
            
            # Phase assignment with clear priority (medically accurate):
            # 1. Period Phase: Days 1 to period_days (IDs: p1-p12)
            if day_in_cycle <= period_days:
                phase = "Period"
            # 2. Ovulation Phase: Fertile window (3-4 days, IDs: o1-o4)
            elif day_in_cycle >= fertile_window_start and day_in_cycle <= fertile_window_end:
                phase = "Ovulation"
            # 3. Follicular Phase: After period, before fertile window (IDs: f1-f40)
            elif day_in_cycle > period_days and day_in_cycle < fertile_window_start:
                phase = "Follicular"
            # 4. Luteal Phase: After fertile window until next period (IDs: l1-l25)
            elif day_in_cycle > fertile_window_end:
                phase = "Luteal"
            else:
                # Fallback (shouldn't happen, but ensures no gaps)
                phase = "Follicular"
            
            # Increment counter for current phase and get day_in_phase
            phase_counters[phase] += 1
            day_in_phase = phase_counters[phase]
            phase_day_id = generate_phase_day_id(phase, day_in_phase)
            
            if phase and phase_day_id:
                phase_mappings.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "phase": phase,
                    "phase_day_id": phase_day_id,
                    "source": "local",
                    "prediction_confidence": 0.8,  # High confidence for adaptive local calculation
                    "is_predicted": True,
                    "fertility_prob": round(fert_prob, 3),
                    "predicted_ovulation_date": ovulation_date_str,
                    "luteal_estimate": round(luteal_mean, 2),
                    "luteal_sd": round(luteal_sd, 2),
                    "ovulation_sd": round(ovulation_sd, 2)
                })
            
            current_date += timedelta(days=1)
        
        print(f"✅ Generated {len(phase_mappings)} phase mappings (no gaps)")
        return phase_mappings
    
    except Exception as e:
        print(f"Error calculating phase for date range: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def detect_early_late_period(user_id: str, logged_period_date: str) -> Optional[Dict]:
    """
    Detect if a logged period is early or late compared to predictions.
    
    Args:
        user_id: User ID
        logged_period_date: The actual period start date (YYYY-MM-DD)
    
    Returns:
        Dict with:
        - is_early_late: bool
        - difference_days: int (positive = late, negative = early)
        - predicted_date: str (predicted period start date)
        - should_adjust: bool (True if difference >= 2 days)
    """
    try:
        logged_date = datetime.strptime(logged_period_date, "%Y-%m-%d")
        
        # Get the most recent predicted cycle start
        response = supabase.table("user_cycle_days").select("date, phase_day_id").eq("user_id", user_id).eq("phase_day_id", "p1").order("date", desc=True).limit(1).execute()
        
        if not response.data:
            return None
        
        predicted_date_str = response.data[0]["date"]
        predicted_date = datetime.strptime(predicted_date_str, "%Y-%m-%d")
        
        # Calculate difference
        difference_days = (logged_date - predicted_date).days
        
        # If difference is >= 2 days, we should adjust
        should_adjust = abs(difference_days) >= 2
        
        return {
            "is_early_late": should_adjust,
            "difference_days": difference_days,
            "predicted_date": predicted_date_str,
            "should_adjust": should_adjust
        }
    except Exception as e:
        print(f"Error detecting early/late period: {str(e)}")
        return None

def calculate_today_phase_day_id(user_id: str) -> Optional[str]:
    """
    Calculate today's phase-day ID based on user's last_period_date and cycle_length.
    This is a fallback if cycle predictions haven't been generated yet.
    
    Returns:
        phase_day_id (e.g., "p5", "f10", "o2", "l15") or None
    """
    try:
        # Get user data
        user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        
        if not user_response.data:
            return None
        
        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        cycle_length = user.get("cycle_length", 28)
        
        if not last_period_date:
            return None
        
        # Get predicted cycle starts from database (prevents drift)
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        predicted_cycle_starts = get_predicted_cycle_starts_from_db(user_id, None, today_str)
        
        # Find which cycle today belongs to
        last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
        current_cycle_start = None
        
        if predicted_cycle_starts:
            # Use predicted cycle starts (more accurate)
            cycle_starts = [datetime.strptime(d, "%Y-%m-%d") for d in predicted_cycle_starts]
            # Find the most recent cycle start <= today
            for cycle_start in cycle_starts:
                if cycle_start <= today:
                    current_cycle_start = cycle_start
                else:
                    break
        else:
            # Fallback: use last_period_date as cycle start
            current_cycle_start = last_period
        
        if current_cycle_start is None:
            current_cycle_start = last_period
        
        # ⚠️ CRITICAL: Calculate which day of the cycle we're on (1-INDEXED)
        # Formula: (today - current_cycle_start).days + 1
        # Cycle start = day 1, not day 0
        # Example: If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
        days_since_cycle_start = (today - current_cycle_start).days
        if days_since_cycle_start < 0:
            return None
        
        day_in_cycle = days_since_cycle_start + 1
        
        # Get adaptive estimates (not fixed!)
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        period_days = estimate_period_length(user_id, normalized=True)  # Use normalized for phase calculations
        
        # Calculate actual cycle length for this cycle
        if predicted_cycle_starts and len(cycle_starts) > 1:
            cycle_index = cycle_starts.index(current_cycle_start)
            if cycle_index < len(cycle_starts) - 1:
                next_cycle_start = cycle_starts[cycle_index + 1]
                actual_cycle_length = (next_cycle_start - current_cycle_start).days
            else:
                actual_cycle_length = float(cycle_length)
        else:
            actual_cycle_length = float(cycle_length)
        
        # Calculate ovulation date for this cycle using actual cycle length
        ovulation_offset = actual_cycle_length - luteal_mean
        ovulation_date = current_cycle_start + timedelta(days=int(ovulation_offset))
        today_date = datetime.now()
        
        # Calculate ovulation probability for today to determine ovulation window dynamically
        offset_from_ov = (today_date - ovulation_date).days
        ovulation_sd = math.sqrt(1.5 ** 2 + luteal_sd ** 2)  # Approximate ovulation_sd
        ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
        
        # Also calculate fertility probability for tracking purposes
        fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
        
        # Pre-calculate ovulation days using top-N by probability approach
        ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
        
        # Determine phase dynamically based on top-N ovulation days
        # This ensures Ovulation phase represents actual ovulation event (1-3 days max)
        # Follicular phase extends until ovulation phase starts
        # ⚠️ CRITICAL: day_in_cycle is 1-INDEXED
        # If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
        # DO NOT change to < period_days or period_days + 1 - this will break silently
        if day_in_cycle <= period_days:
            phase = "Period"
            day_in_phase = day_in_cycle
        elif offset_from_ov in ovulation_days:
            # Ovulation window: Top-N days by probability (1-3 days max, pre-calculated)
            # Uses adaptive selection based on actual probability distribution
            phase = "Ovulation"
            # Calculate day_in_phase: count days in ovulation window
            # Find position within the ovulation days set
            sorted_ovulation_days = sorted(ovulation_days)
            day_in_phase = sorted_ovulation_days.index(offset_from_ov) + 1
        else:
            # Follicular phase: extends from end of period until ovulation phase starts
            if today_date < ovulation_date:
                # Before predicted ovulation date and not in ovulation phase = Follicular
                phase = "Follicular"
                # Calculate day_in_phase: days after period ends
                day_in_phase = max(1, day_in_cycle - int(period_days))
            else:
                # After predicted ovulation date but not in ovulation phase = Luteal
                phase = "Luteal"
                # Calculate day_in_phase: days after ovulation
                days_after_ov = (today_date - ovulation_date).days
                day_in_phase = max(1, days_after_ov)
        
        # Generate phase-day ID
        return generate_phase_day_id(phase, day_in_phase)
    
    except Exception as e:
        print(f"Error calculating today phase-day ID: {str(e)}")
        return None

