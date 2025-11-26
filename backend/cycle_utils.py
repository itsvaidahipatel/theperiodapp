"""
Cycle phase mapping and prediction utilities.
Integrates with Women's Health API to predict cycles and generate phase-day mappings.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import math
from config import settings
from database import supabase

def call_womens_health_api(endpoint: str, method: str = "GET", payload: Optional[dict] = None) -> dict:
    """Call Women's Health API endpoint."""
    if not settings.RAPIDAPI_KEY:
        raise Exception("RAPIDAPI_KEY is not configured. Please set it in your .env file to generate cycle predictions.")
    
    headers = {
        "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
        "X-RapidAPI-Host": "womens-health-menstrual-cycle-phase-predictions-insights.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    url = f"{settings.RAPIDAPI_BASE_URL}{endpoint}"
    
    try:
        # Set timeout to prevent hanging (10 seconds connect, 30 seconds read)
        timeout = (10, 30)
        if method == "POST":
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            response = requests.get(url, headers=headers, timeout=timeout)
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.Timeout as e:
        raise Exception(f"API call timed out: {str(e)}")
    except requests.exceptions.HTTPError as e:
        error_detail = f"HTTP {e.response.status_code}"
        try:
            error_body = e.response.json()
            # Try to get detailed error message
            if "detail" in error_body:
                error_detail = error_body["detail"]
            elif "message" in error_body:
                error_detail = error_body["message"]
            elif "error" in error_body:
                error_detail = error_body["error"]
            else:
                error_detail = str(error_body)
        except:
            error_detail = e.response.text[:200] if hasattr(e, 'response') else str(e)
        raise Exception(f"RapidAPI call failed (HTTP {e.response.status_code}): {error_detail}")
    except Exception as e:
        raise Exception(f"API call failed: {str(e)}")

def process_cycle_data(past_cycle_data: List[Dict], current_date: str, max_predictions: int = 6) -> str:
    """
    Process past cycle data and get request_id.
    
    Args:
        past_cycle_data: List of dicts with 'cycle_start_date' and 'period_length'
        current_date: Current date in YYYY-MM-DD format
        max_predictions: Maximum number of cycle predictions (default 6, max 12)
    
    Returns:
        request_id: Request ID for subsequent API calls
    """
    payload = {
        "current_date": current_date,
        "past_cycle_data": past_cycle_data,
        "max_cycle_predictions": max_predictions
    }
    
    response = call_womens_health_api("/process_cycle_data", "POST", payload)
    return response["request_id"]

def get_predicted_cycle_starts(request_id: str) -> List[str]:
    """Get predicted cycle start dates."""
    response = call_womens_health_api(f"/get_data/{request_id}/predicted_cycle_starts")
    return response["predicted_cycle_starts"]

def get_average_period_length(request_id: str) -> float:
    """Get average period length."""
    response = call_womens_health_api(f"/get_data/{request_id}/average_period_length")
    return float(response["average_period_length"])

def get_average_cycle_length(request_id: str) -> float:
    """Get average cycle length."""
    response = call_womens_health_api(f"/get_data/{request_id}/average_cycle_length")
    return float(response["average_cycle_length"])

def get_cycle_phases(request_id: str) -> List[Dict]:
    """
    Get complete cycle phase timeline from RapidAPI.
    
    Returns list of dicts with:
    - date: YYYY-MM-DD
    - phase: Phase name
    - day_in_phase: Day number within the phase
    """
    response = call_womens_health_api(f"/get_data/{request_id}/cycle_phases")
    return response.get("cycle_phases", [])

def predict_cycle_phases(cycle_start_date: str, next_cycle_start_date: str, period_length: int) -> dict:
    """Predict cycle phases between two cycle start dates."""
    payload = {
        "cycle_start_date": cycle_start_date,
        "next_cycle_start_date": next_cycle_start_date,
        "period_length": period_length
    }
    
    return call_womens_health_api("/predict_cycle_phases", "POST", payload)

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
    obs_mean = sum(user_observations) / len(user_observations)
    if len(user_observations) > 1:
        variance = sum((x - obs_mean) ** 2 for x in user_observations) / (len(user_observations) - 1)
        obs_sd = math.sqrt(variance)
    else:
        obs_sd = 1.5  # Default SD if only one observation
    
    # Bayesian smoothing: 60% prior, 40% user mean
    mean = 0.6 * prior_mean + 0.4 * obs_mean
    sd = (prior_sd + obs_sd) / 2.0  # Average of prior and user SD
    
    # Clamp to allowed range
    mean = max(min_luteal, min(max_luteal, mean))
    
    return mean, sd

def estimate_period_length(user_id: str, user_observations: Optional[List[float]] = None) -> float:
    """
    Estimate period length using Bayesian smoothing.
    Adaptive period length based on user history.
    
    Args:
        user_id: User ID
        user_observations: List of observed period lengths (optional, will fetch from DB if None)
    
    Returns:
        Estimated period length (mean) in days
    """
    # Population prior
    prior_mean = 5.0
    min_period = 3.0
    max_period = 8.0
    
    # Get user observations from database if not provided
    if user_observations is None:
        try:
            # Try to get from period_logs table
            period_logs = supabase.table("period_logs").select("start_date, end_date").eq("user_id", user_id).order("start_date", desc=True).limit(12).execute()
            
            if period_logs.data and len(period_logs.data) > 0:
                user_observations = []
                for log in period_logs.data:
                    start = datetime.strptime(log["start_date"], "%Y-%m-%d")
                    end = datetime.strptime(log["end_date"], "%Y-%m-%d")
                    period_length = (end - start).days + 1
                    user_observations.append(float(period_length))
        except:
            user_observations = []
    
    if not user_observations or len(user_observations) == 0:
        # No user data, use prior
        return prior_mean
    
    # Calculate user mean
    obs_mean = sum(user_observations) / len(user_observations)
    
    # Bayesian smoothing: 60% prior, 40% user mean
    mean = 0.6 * prior_mean + 0.4 * obs_mean
    
    # Clamp to allowed range
    mean = max(min_period, min(max_period, mean))
    
    return round(mean, 1)

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

def get_ovulation_fertility_threshold(ovulation_sd: float) -> float:
    """
    Get adaptive fertility threshold for determining ovulation window.
    
    Ensures ovulation phase is 1-3 days maximum.
    Regular cycles (low uncertainty): higher threshold → 1-2 day window
    Irregular cycles (high uncertainty): lower threshold → 2-3 day window
    
    Args:
        ovulation_sd: Standard deviation of ovulation prediction (uncertainty)
    
    Returns:
        Fertility probability threshold (0.75 to 0.9)
    """
    # Regular cycles: ovulation_sd < 2.0 → threshold 0.8-0.9 → 1-3 days
    # Irregular cycles: ovulation_sd >= 2.0 → threshold 0.75-0.85 → 2-3 days
    
    if ovulation_sd < 1.5:
        # Very regular: very high threshold → narrow window (1 day)
        return 0.9
    elif ovulation_sd < 2.0:
        # Regular: high threshold → typical window (2 days)
        return 0.8
    elif ovulation_sd < 3.0:
        # Somewhat irregular: medium-high threshold → wider window (2-3 days)
        return 0.75
    else:
        # Irregular: very high threshold → wider window (3 days max)
        return 0.85

def fertility_probability(offset_from_ovulation: float, ovulation_sd: float) -> float:
    """
    Calculate fertility probability for a day based on offset from ovulation.
    Optimized version with early returns for performance.
    
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
    
    # Sperm survival kernel (5 days before ovulation)
    if -5.0 <= offset_from_ovulation <= 0.0:
        p_sperm = 1.0
    else:
        p_sperm = 0.0
    
    # Weighted combination
    raw_prob = 0.6 * p_ov + 0.4 * p_sperm
    
    # Normalization factor (peak fertility at ovulation day)
    # Cache this calculation if needed for performance
    norm_factor = 0.6 * normal_pdf(0.0, 0.0, ovulation_sd) + 0.4
    
    if norm_factor <= 0:
        return 0.0
    
    normalized_prob = raw_prob / norm_factor
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, normalized_prob))

def predict_ovulation(
    cycle_start_date: str,
    cycle_length_estimate: float,
    luteal_mean: float,
    luteal_sd: float,
    cycle_start_sd: float = 1.0
) -> tuple[str, float]:
    """
    Predict ovulation date and uncertainty.
    
    Args:
        cycle_start_date: Start date of cycle (YYYY-MM-DD)
        cycle_length_estimate: Estimated cycle length
        luteal_mean: Mean luteal phase length
        luteal_sd: Standard deviation of luteal phase
        cycle_start_sd: Standard deviation of cycle start prediction (default 1.0)
    
    Returns:
        Tuple of (ovulation_date_str, ovulation_sd)
    """
    cycle_start = datetime.strptime(cycle_start_date, "%Y-%m-%d")
    
    # Ovulation date = cycle_start + (cycle_length - luteal_mean)
    ovulation_offset = cycle_length_estimate - luteal_mean
    ovulation_date = cycle_start + timedelta(days=int(ovulation_offset))
    
    # Combined uncertainty
    ovulation_sd = math.sqrt(cycle_start_sd ** 2 + luteal_sd ** 2)
    
    return ovulation_date.strftime("%Y-%m-%d"), ovulation_sd

def update_luteal_estimate(user_id: str, observed_luteal_length: float, has_markers: bool = False) -> None:
    """
    Update user's luteal phase estimate when period is logged.
    
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
        
        # Calculate updated mean with weighting
        if has_markers:
            # More weight to observed value if markers exist
            weight_observed = 0.5
        else:
            weight_observed = 0.4
        
        updated_mean = (1 - weight_observed) * old_mean + weight_observed * observed_luteal_length
        
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
    Update cycle length using Bayesian smoothing.
    
    Formula: updated = (old * 0.7) + (new * 0.3)
    
    Returns the updated cycle length.
    """
    try:
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        if user_response.data and user_response.data[0].get("cycle_length"):
            old_cycle_length = int(user_response.data[0]["cycle_length"])
            updated_cycle_length = int((old_cycle_length * 0.7) + (new_cycle_length * 0.3))
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
    Generate daily phase-day mappings using RapidAPI cycle_phases endpoint.
    
    Args:
        user_id: User ID
        past_cycle_data: List of past cycle data
        current_date: Current date in YYYY-MM-DD format
        update_future_only: If True, only update dates >= current_date (preserve past data)
    
    Returns list of dicts with:
    - date: YYYY-MM-DD
    - phase: Phase name
    - phase_day_id: Phase-day ID (e.g., p1, f5, o2, l10)
    - source: "api" | "adjusted" | "fallback"
    - confidence: float (1.0 for API, 0.7 for adjusted, 0.5 for fallback)
    """
    try:
        print(f"Starting cycle prediction for user {user_id} with {len(past_cycle_data)} past cycles")
        print(f"Update future only: {update_future_only}")
        
        # Step 1: Process cycle data and get request_id
        print("Calling process_cycle_data API...")
        request_id = process_cycle_data(past_cycle_data, current_date)
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
                # Use RapidAPI timeline as primary source, but add fertility probabilities
                # Get adaptive luteal estimate for fertility calculations
                luteal_mean, luteal_sd = estimate_luteal(user_id)
                
                phase_mappings = []
                # Simplified: Use first cycle start from timeline and process all entries
                # Find first cycle start (p1 date)
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
                
                # Predict ovulation once for the timeline
                ovulation_date_str, ovulation_sd = predict_ovulation(
                    first_cycle_start,
                    float(estimated_cycle_length),
                    luteal_mean,
                    luteal_sd,
                    cycle_start_sd=1.0
                )
                ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
                
                # Process all entries in timeline (simplified - use single ovulation prediction)
                # Override phases with our own calculation to ensure 1-3 day ovulation window
                phase_counters = {"Period": 0, "Follicular": 0, "Ovulation": 0, "Luteal": 0}
                ovulation_threshold = get_ovulation_fertility_threshold(ovulation_sd)
                
                for entry in cycle_phases_timeline:
                    date_str = entry.get("date")
                    original_phase_name = entry.get("phase", "")
                    day_in_phase = entry.get("day_in_phase", 1)
                    
                    if not date_str:
                        continue
                    
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    # Calculate ovulation probability for phase determination
                    offset_from_ov = (date_obj - ovulation_date).days
                    ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
                    
                    # Also calculate fertility probability for tracking
                    fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
                    
                    # Determine phase using our logic (override RapidAPI phase to ensure 1-3 day ovulation)
                    # Check if it's period first (use original phase for period detection)
                    days_since_cycle_start = (date_obj - datetime.strptime(first_cycle_start, "%Y-%m-%d")).days
                    period_days = estimate_period_length(user_id)
                    
                    if days_since_cycle_start < period_days:
                        phase_name = "Period"
                    elif ov_prob >= ovulation_threshold:
                        # Ovulation phase: 1-3 days max
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
                        "date": date_str,
                        "phase": phase_name,  # Use our calculated phase, not RapidAPI's
                        "phase_day_id": phase_day_id,
                        "source": "api",
                        "confidence": 0.9,  # High confidence for API
                        "fertility_prob": round(fert_prob, 3),
                        "predicted_ovulation_date": ovulation_date_str,
                        "luteal_estimate": round(luteal_mean, 2),
                        "luteal_sd": round(luteal_sd, 2),
                        "ovulation_sd": round(ovulation_sd, 2)
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
        
        for i in range(len(predicted_starts) - 1):
            cycle_start_date = predicted_starts[i]
            cycle_start = datetime.strptime(cycle_start_date, "%Y-%m-%d")
            next_cycle_start = datetime.strptime(predicted_starts[i + 1], "%Y-%m-%d")
            
            # Only process cycles that include or are after current_date
            if next_cycle_start < current_date_obj and update_future_only:
                continue
            
            cycle_length = (next_cycle_start - cycle_start).days
            
            # Predict ovulation using adaptive method
            ovulation_date_str, ovulation_sd = predict_ovulation(
                cycle_start_date,
                float(cycle_length),
                luteal_mean,
                luteal_sd,
                cycle_start_sd=1.0
            )
            ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
            
            # Period phase - use adaptive period length (from RapidAPI average or user history)
            period_days = average_period_length if average_period_length else estimate_period_length(user_id)
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
                
                date_str = date_obj.strftime("%Y-%m-%d")
                
                # Calculate offset from ovulation
                offset_from_ov = (date_obj - ovulation_date).days
                
                # Calculate ovulation probability for phase determination (NOT fertility probability)
                # This ensures Ovulation phase is 1-4 days, not 6+ days
                ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
                
                # Also calculate fertility probability for tracking purposes
                fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
                
                # Determine phase based on rules
                days_since_start = (date_obj - cycle_start).days
                
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
                
                if days_since_start < period_days:
                    # Period phase
                    phase = "Period"
                elif ov_prob >= ovulation_threshold:  # Use ovulation probability, not fertility
                    # Ovulation window: days with ovulation probability >= threshold
                    # Regular cycles: threshold 0.5-0.6 → 1-2 days
                    # Irregular cycles: threshold 0.3-0.4 → 2-3 days
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
                    "confidence": 0.7,
                    "fertility_prob": round(fert_prob, 3),
                    "predicted_ovulation_date": ovulation_date_str,
                    "luteal_estimate": round(luteal_mean, 2),
                    "luteal_sd": round(luteal_sd, 2),
                    "ovulation_sd": round(ovulation_sd, 2)
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
    
    Args:
        user_id: User ID
        phase_mappings: List of phase mappings with date, phase, phase_day_id, source, confidence
        update_future_only: If True, only update/insert dates >= current_date (preserve past data)
        current_date: Current date for filtering (required if update_future_only=True)
    """
    try:
        if not phase_mappings:
            print("No phase mappings to store")
            return
        
        # Prepare all mappings for batch insert/update
        insert_data = []
        update_data = []
        current_date_obj = datetime.strptime(current_date, "%Y-%m-%d") if current_date else None
        
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
            if "confidence" in mapping and mapping["confidence"] is not None:
                entry["confidence"] = float(mapping["confidence"])
            # Optional fertility fields (stored if columns exist)
            if "fertility_prob" in mapping and mapping["fertility_prob"] is not None:
                entry["fertility_prob"] = float(mapping["fertility_prob"])
            if "predicted_ovulation_date" in mapping and mapping["predicted_ovulation_date"]:
                entry["predicted_ovulation_date"] = mapping["predicted_ovulation_date"]
            if "luteal_estimate" in mapping and mapping["luteal_estimate"] is not None:
                entry["luteal_estimate"] = float(mapping["luteal_estimate"])
            if "luteal_sd" in mapping and mapping["luteal_sd"] is not None:
                entry["luteal_sd"] = float(mapping["luteal_sd"])
            if "ovulation_sd" in mapping and mapping["ovulation_sd"] is not None:
                entry["ovulation_sd"] = float(mapping["ovulation_sd"])
            
            # Check if entry already exists
            if update_future_only:
                # For partial updates, use upsert (insert or update)
                insert_data.append(entry)
            else:
                # For full updates, collect all for batch insert
                insert_data.append(entry)
        
        if not insert_data:
            print("No phase mappings to store after filtering")
            return
        
        if update_future_only:
            # Partial update: Delete future dates first, then insert new ones
            if current_date_obj:
                print(f"Deleting existing predictions from {current_date} onwards...")
                supabase.table("user_cycle_days").delete().eq("user_id", user_id).gte("date", current_date).execute()
            
            # Insert new predictions (with optional source/confidence fields)
            try:
                response = supabase.table("user_cycle_days").insert(insert_data).execute()
                print(f"Stored {len(insert_data)} phase mappings for user {user_id} (partial update)")
            except Exception as insert_error:
                # If insert fails due to unknown columns, retry without optional fields
                if "column" in str(insert_error).lower() or "does not exist" in str(insert_error).lower():
                    print(f"⚠️ Insert failed with optional columns, retrying without optional fields...")
                    insert_data_simple = []
                    optional_fields = ["source", "confidence", "fertility_prob", "predicted_ovulation_date", "luteal_estimate", "ovulation_sd"]
                    for item in insert_data:
                        simple_item = {k: v for k, v in item.items() if k not in optional_fields}
                        insert_data_simple.append(simple_item)
                    response = supabase.table("user_cycle_days").insert(insert_data_simple).execute()
                    print(f"Stored {len(insert_data_simple)} phase mappings for user {user_id} (partial update, without optional fields)")
                else:
                    raise
        else:
            # Full update: Delete all existing, then insert new
            print(f"Deleting all existing mappings for user {user_id}...")
            supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()
            
            # Batch insert all mappings at once (with optional source/confidence fields)
            try:
                response = supabase.table("user_cycle_days").insert(insert_data).execute()
                print(f"Stored {len(insert_data)} phase mappings for user {user_id} (full update)")
            except Exception as insert_error:
                # If insert fails due to unknown columns, retry without optional fields
                if "column" in str(insert_error).lower() or "does not exist" in str(insert_error).lower():
                    print(f"⚠️ Insert failed with optional columns, retrying without optional fields...")
                    insert_data_simple = []
                    optional_fields = ["source", "confidence", "fertility_prob", "predicted_ovulation_date", "luteal_estimate", "ovulation_sd"]
                    for item in insert_data:
                        simple_item = {k: v for k, v in item.items() if k not in optional_fields}
                        insert_data_simple.append(simple_item)
                    response = supabase.table("user_cycle_days").insert(insert_data_simple).execute()
                    print(f"Stored {len(insert_data_simple)} phase mappings for user {user_id} (full update, without optional fields)")
                else:
                    raise
        
        if not response.data:
            raise Exception("Failed to insert phase mappings - no data returned")
    
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

def calculate_phase_for_date_range(
    user_id: str,
    last_period_date: str,
    cycle_length: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict]:
    """
    Calculate phase mappings for a date range using adaptive, fertility-based logic.
    This is the fallback when RapidAPI is completely unavailable.
    
    Uses adaptive luteal estimation and fertility probabilities.
    
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
        
        # Calculate cycles starting from last_period_date
        cycle_start = last_period
        cycle_number = 0
        
        # Safety limit to prevent infinite loops and performance issues
        max_days = min(180, (end_date_obj - start_date_obj).days + 1)  # Max 180 days or date range, whichever is smaller
        days_processed = 0
        
        print(f"Calculating phases for {max_days} days (limited from {(end_date_obj - start_date_obj).days + 1} days)")
        
        while current_date <= end_date_obj and days_processed < max_days:
            # Calculate which cycle we're in
            days_since_last_period = (current_date - last_period).days
            
            if days_since_last_period < 0:
                # Before last period date, skip
                current_date += timedelta(days=1)
                continue
            
            # Determine current cycle start
            cycle_offset = (days_since_last_period // cycle_length) * cycle_length
            current_cycle_start = last_period + timedelta(days=cycle_offset)
            days_in_current_cycle = (current_date - current_cycle_start).days
            
            # Predict ovulation for this cycle
            cycle_start_str = current_cycle_start.strftime("%Y-%m-%d")
            
            # Initialize phase counters for this cycle if not exists
            if cycle_start_str not in phase_counters_by_cycle:
                phase_counters_by_cycle[cycle_start_str] = {
                    "Period": 0, "Follicular": 0, "Ovulation": 0, "Luteal": 0
                }
                # Predict ovulation once per cycle
                ovulation_date_str, ovulation_sd = predict_ovulation(
                    cycle_start_str,
                    float(cycle_length),
                    luteal_mean,
                    luteal_sd,
                    cycle_start_sd=1.5  # Higher uncertainty in fallback mode
                )
                phase_counters_by_cycle[cycle_start_str]["_ovulation_date"] = ovulation_date_str
                phase_counters_by_cycle[cycle_start_str]["_ovulation_sd"] = ovulation_sd
            
            ovulation_date_str = phase_counters_by_cycle[cycle_start_str]["_ovulation_date"]
            ovulation_sd = phase_counters_by_cycle[cycle_start_str]["_ovulation_sd"]
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
            
            # Determine phase based on rules
            day_in_cycle = days_in_current_cycle + 1
            phase = None
            
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
            
            if day_in_cycle <= period_days:
                phase = "Period"
            elif ov_prob >= ovulation_threshold:  # Use ovulation probability, not fertility
                # Ovulation window: days with ovulation probability >= threshold
                # Regular cycles: threshold 0.5-0.6 → 1-2 days
                # Irregular cycles: threshold 0.3-0.4 → 2-3 days
                phase = "Ovulation"
            elif ov_prob < ovulation_threshold:
                # Follicular phase: extends from end of period until ovulation phase starts
                # This ensures follicular phase continues until ovulation probability is high enough
                if current_date < ovulation_date:
                    # Before predicted ovulation date and not in ovulation phase = Follicular
                    phase = "Follicular"
                else:
                    # After predicted ovulation date but not in ovulation phase = Luteal
                    # (This handles edge cases where ovulation probability drops quickly)
                    phase = "Luteal"
            else:
                # Fallback: use date-based logic
                if current_date < ovulation_date:
                    phase = "Follicular"
                else:
                    phase = "Luteal"
            
            # Increment counter for current phase and get day_in_phase
            phase_counters[phase] += 1
            day_in_phase = phase_counters[phase]
            phase_day_id = generate_phase_day_id(phase, day_in_phase)
            
            if phase and phase_day_id:
                phase_mappings.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "phase": phase,
                    "phase_day_id": phase_day_id,
                    "source": "fallback",
                    "confidence": 0.4,  # Lower confidence for fallback
                    "fertility_prob": round(fert_prob, 3),
                    "predicted_ovulation_date": ovulation_date_str,
                    "luteal_estimate": round(luteal_mean, 2),
                    "luteal_sd": round(luteal_sd, 2),
                    "ovulation_sd": round(ovulation_sd, 2)
                })
            
            current_date += timedelta(days=1)
            days_processed += 1
        
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
        
        # Calculate days since last period
        last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
        today = datetime.now()
        days_since = (today - last_period).days
        
        # Handle negative days (future date)
        if days_since < 0:
            return None
        
        # Calculate which day of the cycle we're on
        # If days_since = 0, we're on day 1 (the first day of period)
        # If days_since = 5, we're on day 6 (the 6th day of period)
        day_in_cycle = days_since + 1
        
        # Handle cycle wrapping (if we've passed one full cycle)
        if day_in_cycle > cycle_length:
            day_in_cycle = ((day_in_cycle - 1) % cycle_length) + 1
        
        # Get adaptive estimates (not fixed!)
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        period_days = estimate_period_length(user_id)  # Adaptive period length
        
        # Calculate ovulation date for this cycle (dynamic, not fixed!)
        ovulation_offset = cycle_length - luteal_mean
        cycle_start = last_period + timedelta(days=((days_since // cycle_length) * cycle_length))
        ovulation_date = cycle_start + timedelta(days=int(ovulation_offset))
        today_date = datetime.now()
        
        # Calculate ovulation probability for today to determine ovulation window dynamically
        offset_from_ov = (today_date - ovulation_date).days
        ovulation_sd = math.sqrt(1.5 ** 2 + luteal_sd ** 2)  # Approximate ovulation_sd
        ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
        
        # Also calculate fertility probability for tracking purposes
        fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
        
        # Determine phase dynamically based on ovulation probability (not fertility probability!)
        # This ensures Ovulation phase represents actual ovulation event (1-3 days max)
        # Follicular phase extends until ovulation phase starts
        # Adaptive threshold: regular cycles (1-2 days) vs irregular cycles (2-3 days)
        ovulation_threshold = get_ovulation_fertility_threshold(ovulation_sd)
        
        if day_in_cycle <= period_days:
            phase = "Period"
            day_in_phase = day_in_cycle
        elif ov_prob >= ovulation_threshold:  # Use ovulation probability, not fertility
            # Ovulation window: days with ovulation probability >= threshold
            # Regular cycles: threshold 0.5-0.6 → 1-2 days
            # Irregular cycles: threshold 0.3-0.4 → 2-3 days
            phase = "Ovulation"
            # Calculate day_in_phase: count days in ovulation window
            # Start counting from first day with ov_prob >= threshold before ovulation
            # For simplicity, use offset from ovulation date
            day_in_phase = max(1, abs(offset_from_ov) + 1)
        elif ov_prob < ovulation_threshold:
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
        else:
            # Fallback: use date-based logic
            if today_date < ovulation_date:
                phase = "Follicular"
                day_in_phase = max(1, day_in_cycle - int(period_days))
            else:
                phase = "Luteal"
                days_after_ov = (today_date - ovulation_date).days
                day_in_phase = max(1, days_after_ov)
        
        # Generate phase-day ID
        return generate_phase_day_id(phase, day_in_phase)
    
    except Exception as e:
        print(f"Error calculating today phase-day ID: {str(e)}")
        return None

