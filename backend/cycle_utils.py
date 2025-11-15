"""
Cycle phase mapping and prediction utilities.
Integrates with Women's Health API to predict cycles and generate phase-day mappings.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
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
        if method == "POST":
            response = requests.post(url, json=payload, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        error_detail = f"HTTP {e.response.status_code}"
        try:
            error_body = e.response.json()
            error_detail = error_body.get("message", error_detail)
        except:
            pass
        raise Exception(f"API call failed: {error_detail}")
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

def generate_cycle_phase_map(
    user_id: str,
    past_cycle_data: List[Dict],
    current_date: str
) -> List[Dict]:
    """
    Generate daily phase-day mappings between consecutive cycle start dates.
    
    Returns list of dicts with:
    - date: YYYY-MM-DD
    - phase: Phase name
    - phase_day_id: Phase-day ID (e.g., p1, f5, o2, l10)
    """
    try:
        print(f"Starting cycle prediction for user {user_id} with {len(past_cycle_data)} past cycles")
        
        # Step 1: Process cycle data and get request_id
        print("Calling process_cycle_data API...")
        request_id = process_cycle_data(past_cycle_data, current_date)
        print(f"Got request_id: {request_id}")
        
        # Step 2: Get predictions
        print("Getting predicted cycle starts...")
        predicted_starts = get_predicted_cycle_starts(request_id)
        print(f"Got {len(predicted_starts)} predicted cycle starts: {predicted_starts}")
        
        print("Getting average period length...")
        average_period_length = round(get_average_period_length(request_id))
        print(f"Average period length: {average_period_length} days")
        
        print("Getting average cycle length...")
        average_cycle_length = round(get_average_cycle_length(request_id))
        print(f"Average cycle length: {average_cycle_length} days")
        
        # Update user's cycle_length in database (calculated from RapidAPI)
        try:
            supabase.table("users").update({
                "cycle_length": int(average_cycle_length)
            }).eq("id", user_id).execute()
            print(f"Updated cycle_length to {average_cycle_length} for user {user_id}")
        except Exception as e:
            print(f"Warning: Failed to update cycle_length: {str(e)}")
        
        if len(predicted_starts) < 2:
            raise Exception("Not enough predicted cycles")
        
        # Step 3: Generate phase mappings for each cycle
        phase_mappings = []
        
        for i in range(len(predicted_starts) - 1):
            cycle_start = datetime.strptime(predicted_starts[i], "%Y-%m-%d")
            next_cycle_start = datetime.strptime(predicted_starts[i + 1], "%Y-%m-%d")
            
            # Calculate phase lengths
            period_days = average_period_length
            cycle_length = (next_cycle_start - cycle_start).days
            
            # Estimate phase lengths (these can be adjusted based on API response)
            follicular_days = max(1, cycle_length - period_days - 8 - 14)  # Rough estimate
            ovulation_days = 8
            luteal_days = 14
            
            # Adjust if cycle is shorter
            if cycle_length < period_days + follicular_days + ovulation_days + luteal_days:
                total_other = cycle_length - period_days
                follicular_days = max(1, int(total_other * 0.5))
                ovulation_days = max(1, int(total_other * 0.2))
                luteal_days = max(1, total_other - follicular_days - ovulation_days)
            
            current_date_obj = cycle_start
            day_counter = 1
            
            # Period phase (p1-p12)
            # Day 1 = cycle_start date (p1)
            # Day 2 = cycle_start + 1 day (p2)
            # etc.
            for day in range(1, period_days + 1):
                if current_date_obj >= next_cycle_start:
                    break
                phase_mappings.append({
                    "date": current_date_obj.strftime("%Y-%m-%d"),
                    "phase": "Period",
                    "phase_day_id": generate_phase_day_id("Period", day)  # day starts at 1, so p1, p2, p3...
                })
                current_date_obj += timedelta(days=1)
                day_counter += 1
            
            # Follicular phase (f1-f30)
            for day in range(1, follicular_days + 1):
                if current_date_obj >= next_cycle_start:
                    break
                phase_mappings.append({
                    "date": current_date_obj.strftime("%Y-%m-%d"),
                    "phase": "Follicular",
                    "phase_day_id": generate_phase_day_id("Follicular", day)
                })
                current_date_obj += timedelta(days=1)
                day_counter += 1
            
            # Ovulation phase (o1-o8)
            for day in range(1, ovulation_days + 1):
                if current_date_obj >= next_cycle_start:
                    break
                phase_mappings.append({
                    "date": current_date_obj.strftime("%Y-%m-%d"),
                    "phase": "Ovulation",
                    "phase_day_id": generate_phase_day_id("Ovulation", day)
                })
                current_date_obj += timedelta(days=1)
                day_counter += 1
            
            # Luteal phase (l1-l25)
            while current_date_obj < next_cycle_start:
                day_in_luteal = (current_date_obj - cycle_start).days - period_days - follicular_days - ovulation_days + 1
                phase_mappings.append({
                    "date": current_date_obj.strftime("%Y-%m-%d"),
                    "phase": "Luteal",
                    "phase_day_id": generate_phase_day_id("Luteal", day_in_luteal)
                })
                current_date_obj += timedelta(days=1)
        
        # Step 4: Store in database
        print(f"Storing {len(phase_mappings)} phase mappings in database...")
        store_cycle_phase_map(user_id, phase_mappings)
        print(f"Successfully stored all phase mappings for user {user_id}")
        
        return phase_mappings
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in generate_cycle_phase_map: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise Exception(f"Failed to generate cycle phase map: {str(e)}")

def store_cycle_phase_map(user_id: str, phase_mappings: List[Dict]):
    """Store phase mappings in user_cycle_days table."""
    try:
        # Delete existing mappings for this user
        supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()
        
        # Prepare all mappings for batch insert
        insert_data = []
        for mapping in phase_mappings:
            insert_data.append({
                "user_id": user_id,
                "date": mapping["date"],
                "phase": mapping["phase"],
                "phase_day_id": mapping["phase_day_id"]
            })
        
        # Batch insert all mappings at once (more efficient)
        if insert_data:
            # Supabase supports batch insert by passing a list
            response = supabase.table("user_cycle_days").insert(insert_data).execute()
            print(f"Stored {len(insert_data)} phase mappings for user {user_id}")
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
        
        # Estimate phase lengths (can be adjusted based on API data)
        period_days = 5  # Average period length
        follicular_days = max(1, cycle_length - period_days - 8 - 14)  # Rough estimate
        ovulation_days = 8
        luteal_days = 14
        
        # Determine phase and day within phase
        if day_in_cycle <= period_days:
            phase = "Period"
            day_in_phase = day_in_cycle
        elif day_in_cycle <= period_days + follicular_days:
            phase = "Follicular"
            day_in_phase = day_in_cycle - period_days
        elif day_in_cycle <= period_days + follicular_days + ovulation_days:
            phase = "Ovulation"
            day_in_phase = day_in_cycle - period_days - follicular_days
        else:
            phase = "Luteal"
            day_in_phase = day_in_cycle - period_days - follicular_days - ovulation_days
        
        # Generate phase-day ID
        return generate_phase_day_id(phase, day_in_phase)
    
    except Exception as e:
        print(f"Error calculating today phase-day ID: {str(e)}")
        return None

