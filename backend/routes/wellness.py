from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from database import supabase
from routes.auth import get_current_user

router = APIRouter()

@router.get("/hormones")
async def get_hormones(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID (e.g., p1, f5, o2, l10). If not provided, uses today's phase-day ID"),
    days: int = Query(5, description="Number of days to fetch (default 5: last 4 days + today)"),
    current_user: dict = Depends(get_current_user)
):
    """Get hormone data for a specific phase day. Defaults to today's phase-day ID. Can fetch multiple days for graphs."""
    try:
        user_id = current_user["id"]
        language = current_user.get("language", "en")
        
        # If phase_day_id not provided, get today's phase-day ID
        if not phase_day_id:
            from cycle_utils import get_user_phase_day, calculate_today_phase_day_id
            from datetime import datetime, timedelta
            
            # Try to get from stored predictions (prefer actual, fallback to predicted)
            today_phase = get_user_phase_day(user_id, datetime.now().strftime("%Y-%m-%d"), prefer_actual=True)
            if today_phase and today_phase.get("phase_day_id"):
                today_phase_day_id = today_phase["phase_day_id"]
                print(f"✅ Got phase_day_id from stored predictions: '{today_phase_day_id}'")
            else:
                # Fallback: calculate from last_period_date (predicted)
                today_phase_day_id = calculate_today_phase_day_id(user_id)
                print(f"✅ Calculated phase_day_id from last_period_date: '{today_phase_day_id}'")
        else:
            today_phase_day_id = phase_day_id
            print(f"✅ Using provided phase_day_id: '{today_phase_day_id}'")
        
        if not today_phase_day_id:
            raise HTTPException(
                status_code=404,
                detail="No phase-day ID available. Please set your last period date."
            )
        
        # If days > 1, fetch data for last (days-1) phase-day IDs + today
        if days > 1:
            from cycle_utils import generate_phase_day_id
            
            # Parse today's phase-day ID to get phase and day number
            def parse_phase_day_id(phase_day_id):
                """Parse phase-day ID like 'f7' into phase ('f') and day (7)"""
                if not phase_day_id or len(phase_day_id) < 2:
                    return None, None
                phase_prefix = phase_day_id[0].lower()
                try:
                    day_num = int(phase_day_id[1:])
                    return phase_prefix, day_num
                except:
                    return None, None
            
            def get_previous_phase_day_ids(current_phase_day_id, count=4):
                """Get previous phase-day IDs based on current one"""
                try:
                    phase_prefix, day_num = parse_phase_day_id(current_phase_day_id)
                    if not phase_prefix or day_num is None:
                        print(f"⚠️ Could not parse phase_day_id: {current_phase_day_id}")
                        return [current_phase_day_id]  # Return at least the current one
                    
                    phase_day_ids = []
                    
                    # Phase limits
                    phase_limits = {
                        'p': 12,  # Period: p1-p12
                        'f': 30,  # Follicular: f1-f30
                        'o': 8,   # Ovulation: o1-o8
                        'l': 25   # Luteal: l1-l25
                    }
                    
                    # Phase order and transitions
                    phase_order = ['p', 'f', 'o', 'l']
                    
                    current_day = day_num
                    current_phase = phase_prefix
                    
                    # Start with current phase-day ID
                    phase_day_ids.append(current_phase_day_id)
                    
                    # Get previous (count-1) phase-day IDs
                    for i in range(count - 1):
                        current_day -= 1
                        
                        # If we've gone below day 1, move to previous phase
                        if current_day < 1:
                            # Find current phase index
                            try:
                                phase_index = phase_order.index(current_phase)
                                # Move to previous phase
                                if phase_index > 0:
                                    current_phase = phase_order[phase_index - 1]
                                else:
                                    # Wrap around to last phase
                                    current_phase = phase_order[-1]
                                
                                # Set day to last day of that phase
                                current_day = phase_limits.get(current_phase, 1)
                            except ValueError:
                                print(f"⚠️ Phase '{current_phase}' not found in phase_order")
                                break
                            except Exception as e:
                                print(f"⚠️ Error in phase transition: {str(e)}")
                                break
                        
                        # Check if day is within phase limits
                        phase_limit = phase_limits.get(current_phase, 1)
                        if current_day > phase_limit:
                            current_day = phase_limit
                        if current_day < 1:
                            current_day = 1
                        
                        # Generate phase-day ID
                        try:
                            phase_name = {'p': 'Period', 'f': 'Follicular', 'o': 'Ovulation', 'l': 'Luteal'}.get(current_phase, 'Period')
                            prev_phase_day_id = generate_phase_day_id(phase_name, current_day)
                            phase_day_ids.insert(0, prev_phase_day_id)  # Insert at beginning
                        except Exception as e:
                            print(f"⚠️ Error generating phase_day_id for phase={phase_name}, day={current_day}: {str(e)}")
                            break
                    
                    return phase_day_ids
                except Exception as e:
                    print(f"❌ Error in get_previous_phase_day_ids: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Return at least the current phase_day_id
                    return [current_phase_day_id] if current_phase_day_id else []
            
            # Get list of phase-day IDs (last 4 + today = 5 total)
            phase_day_ids_list = get_previous_phase_day_ids(today_phase_day_id, days - 1)
            
            hormone_history = []
            for phase_day_id_for_date in phase_day_ids_list:
                # Fetch hormone data for this phase_day_id
                # In hormones_data table, the phase_day_id is stored in the 'id' column (text)
                # Normalize phase_day_id to lowercase for consistent matching
                normalized_phase_day_id_for_date = phase_day_id_for_date.lower() if phase_day_id_for_date else None
                hormone_response = supabase.table("hormones_data").select("*").eq("id", normalized_phase_day_id_for_date).execute()
                
                # If no match, try case variations
                if not hormone_response.data and phase_day_id_for_date:
                    hormone_response = supabase.table("hormones_data").select("*").eq("id", phase_day_id_for_date.upper()).execute()
                    if not hormone_response.data:
                        hormone_response = supabase.table("hormones_data").select("*").eq("id", phase_day_id_for_date).execute()
                if hormone_response.data:
                    hormone_data = hormone_response.data[0]
                    # Hormone values are TEXT in schema, convert to float for graphs
                    def parse_hormone_value(value):
                        if value is None or value == '':
                            return 0
                        try:
                            return float(value)
                        except:
                            return 0
                    
                    hormone_history.append({
                        "phase_day_id": phase_day_id_for_date,
                        "estrogen": parse_hormone_value(hormone_data.get("estrogen")),
                        "progesterone": parse_hormone_value(hormone_data.get("progesterone")),
                        "fsh": parse_hormone_value(hormone_data.get("fsh")),
                        "lh": parse_hormone_value(hormone_data.get("lh")),
                    })
            
            # Get today's full data
            # In hormones_data table, the phase_day_id is stored in the 'id' column (text)
            # Normalize phase_day_id to lowercase for consistent matching
            normalized_phase_day_id = today_phase_day_id.lower() if today_phase_day_id else None
            print(f"🔍 Querying hormones_data for today phase_day_id: '{today_phase_day_id}' (normalized: '{normalized_phase_day_id}')")
            
            # Try exact match first
            today_response = supabase.table("hormones_data").select("*").eq("id", normalized_phase_day_id).execute()
            
            # If no match, try case-insensitive search
            if not today_response.data and today_phase_day_id:
                print(f"⚠️ No exact match found for today, trying case variations...")
                # Try uppercase
                today_response = supabase.table("hormones_data").select("*").eq("id", today_phase_day_id.upper()).execute()
                if not today_response.data:
                    # Try original case
                    today_response = supabase.table("hormones_data").select("*").eq("id", today_phase_day_id).execute()
            
            print(f"📊 Today query result: {len(today_response.data) if today_response.data else 0} rows found")
            if today_response.data:
                print(f"✅ Found hormone data for today phase_day_id: {today_response.data[0].get('id')}")
            else:
                # Debug: Check what phase_day_ids actually exist in the database
                try:
                    sample_response = supabase.table("hormones_data").select("id").limit(10).execute()
                    if sample_response.data:
                        sample_ids = [item.get("id") for item in sample_response.data]
                        print(f"🔍 Sample phase_day_ids in hormones_data table (id column): {sample_ids}")
                    else:
                        print(f"⚠️ hormones_data table appears to be empty")
                except Exception as debug_err:
                    print(f"⚠️ Could not query sample phase_day_ids: {str(debug_err)}")
            
            today_data = None
            if today_response.data:
                hormone_data = today_response.data[0]
                # Schema: id contains phase_day_id (text), hormones are TEXT, mood/energy/best_work_type/brain_note are JSONB
                phase_day_id_from_db = hormone_data.get("id")  # The 'id' column contains the phase_day_id
                today_data = {
                    "id": phase_day_id_from_db,  # Return phase_day_id for compatibility
                    "phase_day_id": phase_day_id_from_db,  # Also include phase_day_id explicitly
                    "phase_id": hormone_data.get("phase_id"),
                    "day_number": hormone_data.get("day_number"),
                    "estrogen": hormone_data.get("estrogen"),  # TEXT
                    "estrogen_trend": hormone_data.get("estrogen_trend"),
                    "progesterone": hormone_data.get("progesterone"),  # TEXT
                    "progesterone_trend": hormone_data.get("progesterone_trend"),
                    "fsh": hormone_data.get("fsh"),  # TEXT
                    "fsh_trend": hormone_data.get("fsh_trend"),
                    "lh": hormone_data.get("lh"),  # TEXT
                    "lh_trend": hormone_data.get("lh_trend"),
                    "mood": hormone_data.get("mood"),  # JSONB
                    "energy": hormone_data.get("energy"),  # JSONB
                    "best_work_type": hormone_data.get("best_work_type"),  # JSONB
                    "brain_note": hormone_data.get("brain_note"),  # JSONB
                    "energy_level": hormone_data.get("energy", {}).get("level") if isinstance(hormone_data.get("energy"), dict) else None,
                    "emotional_summary": hormone_data.get("mood", {}).get("summary") if isinstance(hormone_data.get("mood"), dict) else None,
                    "physical_summary": hormone_data.get("brain_note", {}).get("summary") if isinstance(hormone_data.get("brain_note"), dict) else None
                }
            
            # Return data even if today_data is None, so frontend can show helpful message
            return {
                "today": today_data,
                "history": hormone_history,
                "language": language,
                "phase_day_id": today_phase_day_id  # Include phase_day_id so frontend knows what's expected
            }
        
        # Single day response (backward compatibility)
        # In hormones_data table, the phase_day_id is stored in the 'id' column (text)
        # Normalize phase_day_id to lowercase for consistent matching
        normalized_phase_day_id = today_phase_day_id.lower() if today_phase_day_id else None
        print(f"🔍 Querying hormones_data for phase_day_id: '{today_phase_day_id}' (normalized: '{normalized_phase_day_id}')")
        
        # Try exact match first
        response = supabase.table("hormones_data").select("*").eq("id", normalized_phase_day_id).execute()
        
        # If no match, try case-insensitive search (check both lowercase and uppercase)
        if not response.data and today_phase_day_id:
            print(f"⚠️ No exact match found, trying case variations...")
            # Try uppercase
            response = supabase.table("hormones_data").select("*").eq("id", today_phase_day_id.upper()).execute()
            if not response.data:
                # Try original case
                response = supabase.table("hormones_data").select("*").eq("id", today_phase_day_id).execute()
        
        print(f"📊 Query result: {len(response.data) if response.data else 0} rows found")
        if response.data:
            print(f"✅ Found hormone data for phase_day_id: {response.data[0].get('id')}")
        else:
            # Debug: Check what phase_day_ids actually exist in the database
            try:
                sample_response = supabase.table("hormones_data").select("id").limit(10).execute()
                if sample_response.data:
                    sample_ids = [item.get("id") for item in sample_response.data]
                    print(f"🔍 Sample phase_day_ids in hormones_data table (id column): {sample_ids}")
                else:
                    print(f"⚠️ hormones_data table appears to be empty")
            except Exception as debug_err:
                print(f"⚠️ Could not query sample phase_day_ids: {str(debug_err)}")
        
        if response.data:
            hormone_data = response.data[0]
            # Schema: id contains phase_day_id (text), hormones are TEXT, mood/energy/best_work_type/brain_note are JSONB
            phase_day_id_from_db = hormone_data.get("id")  # The 'id' column contains the phase_day_id
            return {
                "id": phase_day_id_from_db,  # Return phase_day_id for compatibility
                "phase_day_id": phase_day_id_from_db,  # Also include phase_day_id explicitly
                "phase_id": hormone_data.get("phase_id"),
                "day_number": hormone_data.get("day_number"),
                "estrogen": hormone_data.get("estrogen"),  # TEXT
                "estrogen_trend": hormone_data.get("estrogen_trend"),
                "progesterone": hormone_data.get("progesterone"),  # TEXT
                "progesterone_trend": hormone_data.get("progesterone_trend"),
                "fsh": hormone_data.get("fsh"),  # TEXT
                "fsh_trend": hormone_data.get("fsh_trend"),
                "lh": hormone_data.get("lh"),  # TEXT
                "lh_trend": hormone_data.get("lh_trend"),
                "mood": hormone_data.get("mood"),  # JSONB
                "energy": hormone_data.get("energy"),  # JSONB
                "best_work_type": hormone_data.get("best_work_type"),  # JSONB
                "brain_note": hormone_data.get("brain_note"),  # JSONB
                "energy_level": hormone_data.get("energy", {}).get("level") if isinstance(hormone_data.get("energy"), dict) else None,
                "emotional_summary": hormone_data.get("mood", {}).get("summary") if isinstance(hormone_data.get("mood"), dict) else None,
                "physical_summary": hormone_data.get("brain_note", {}).get("summary") if isinstance(hormone_data.get("brain_note"), dict) else None,
                "phase_day_id": today_phase_day_id
            }
        # Return structure with phase_day_id even if no data, so frontend knows what's expected
        return {
            "phase_day_id": today_phase_day_id,
            "message": f"No hormone data available for phase-day ID: {today_phase_day_id}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ ERROR in get_hormones endpoint:")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch hormones data: {str(e)}"
        )

@router.get("/nutrition")
async def get_nutrition(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID. If not provided, uses today's phase-day ID"),
    language: str = Query("en", description="Language code"),
    cuisine: Optional[str] = Query(None, description="Cuisine filter"),
    current_user: dict = Depends(get_current_user)
):
    """Get nutrition data for a specific phase day. Defaults to today's phase-day ID."""
    try:
        user_id = current_user["id"]
        
        # If phase_day_id not provided, get today's phase-day ID
        if not phase_day_id:
            from cycle_utils import get_user_phase_day, calculate_today_phase_day_id
            from datetime import datetime
            
            # Try to get from stored predictions (prefer actual, fallback to predicted)
            today_phase = get_user_phase_day(user_id, datetime.now().strftime("%Y-%m-%d"), prefer_actual=True)
            if today_phase and today_phase.get("phase_day_id"):
                phase_day_id = today_phase["phase_day_id"]
            else:
                # Fallback: calculate from last_period_date (predicted)
                phase_day_id = calculate_today_phase_day_id(user_id)
        
        if not phase_day_id:
            return {"recipes": [], "wholefoods": []}
        
        # nutrition_* tables use hormone_id column (not phase_day_id)
        normalized_phase_day_id = phase_day_id.lower() if phase_day_id else None
        
        table_name = f"nutrition_{language}"
        
        # Schema: nutrition_* uses hormone_id column to store phase_day_id value
        # Try lowercase first
        query = supabase.table(table_name).select("*").eq("hormone_id", normalized_phase_day_id)
        
        # If no match, try case variations
        if phase_day_id:
            test_response = query.execute()
            if not test_response.data:
                # Try uppercase
                query = supabase.table(table_name).select("*").eq("hormone_id", phase_day_id.upper())
                test_response = query.execute()
                if not test_response.data:
                    # Try original case
                    query = supabase.table(table_name).select("*").eq("hormone_id", phase_day_id)
        
        if cuisine:
            # Use cuisine directly (no mapping needed)
            db_cuisine = cuisine
            query = query.eq("cuisine", db_cuisine)
        
        recipes_response = query.execute()
        
        # Note: There's no wholefoods table in the schema, so we return empty
        return {
            "recipes": recipes_response.data or [],
            "wholefoods": []
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ ERROR in get_nutrition endpoint:")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch nutrition data: {str(e)}"
        )

@router.get("/exercises")
async def get_exercises(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID. If not provided, uses today's phase-day ID"),
    language: str = Query("en", description="Language code"),
    category: Optional[str] = Query(None, description="Exercise category"),
    current_user: dict = Depends(get_current_user)
):
    """Get exercise data for a specific phase day. Defaults to today's phase-day ID."""
    try:
        user_id = current_user["id"]
        
        # If phase_day_id not provided, get today's phase-day ID
        if not phase_day_id:
            from cycle_utils import get_user_phase_day, calculate_today_phase_day_id
            from datetime import datetime
            
            # Try to get from stored predictions (prefer actual, fallback to predicted)
            today_phase = get_user_phase_day(user_id, datetime.now().strftime("%Y-%m-%d"), prefer_actual=True)
            if today_phase and today_phase.get("phase_day_id"):
                phase_day_id = today_phase["phase_day_id"]
            else:
                # Fallback: calculate from last_period_date (predicted)
                phase_day_id = calculate_today_phase_day_id(user_id)
        
        if not phase_day_id:
            return {"exercises": []}
        
        # exercises_* tables use hormone_id column (not phase_day_id)
        normalized_phase_day_id = phase_day_id.lower() if phase_day_id else None
        
        table_name = f"exercises_{language}"
        
        # Schema: exercises_* uses hormone_id column to store phase_day_id value
        # Try lowercase first
        query = supabase.table(table_name).select("*").eq("hormone_id", normalized_phase_day_id)
        
        # If no match, try case variations
        if phase_day_id:
            test_response = query.execute()
            if not test_response.data:
                # Try uppercase
                query = supabase.table(table_name).select("*").eq("hormone_id", phase_day_id.upper())
                test_response = query.execute()
                if not test_response.data:
                    # Try original case
                    query = supabase.table(table_name).select("*").eq("hormone_id", phase_day_id)
        
        response = query.execute()
        
        return {
            "exercises": response.data or []
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ ERROR in get_exercises endpoint:")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch exercise data: {str(e)}"
        )

