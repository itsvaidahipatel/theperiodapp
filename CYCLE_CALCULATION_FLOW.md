# Complete Flow: Calendar Phase Colors, Dates, and Phase ID Assignment (UPGRADED)

## Overview
This document explains the complete flow of how the app calculates calendar phase colors, assigns phase IDs, uses RapidAPI for predictions, and utilizes `last_period_date` and `cycle_length`.

**⚠️ IMPORTANT**: This system has been upgraded to use RapidAPI's `cycle_phases` endpoint as the primary data source, with improved fallback logic, partial updates, and adaptive adjustments.

---

## 1. Data Sources

### User Data (from `users` table)
- **`last_period_date`**: The date of the user's last menstrual period start (YYYY-MM-DD format)
- **`cycle_length`**: Average length of the user's menstrual cycle in days (default: 28 days)
- These are stored when user registers or logs a period

### RapidAPI Integration
- **API**: Women's Health Menstrual Cycle Phase Predictions API (via RapidAPI)
- **Base URL**: `https://womens-health-menstrual-cycle-phase-predictions-insights.p.rapidapi.com`
- **Authentication**: Requires `RAPIDAPI_KEY` in environment variables

---

## 2. Phase ID Format

Phase IDs follow this pattern: `{prefix}{day_number}`

| Phase | Prefix | Range | Example |
|-------|--------|-------|---------|
| Period | `p` | p1-p12 | p1, p2, p3, ... p12 |
| Follicular | `f` | f1-f30 | f1, f2, f3, ... f30 |
| Ovulation | `o` | o1-o8 | o1, o2, o3, ... o8 |
| Luteal | `l` | l1-l25 | l1, l2, l3, ... l25 |

**Example**: `p3` = Day 3 of Period phase, `f10` = Day 10 of Follicular phase

---

## 3. Complete Flow: Calendar Phase Calculation

### Step 1: User Opens Dashboard
When user opens the Dashboard page, the frontend requests phase map data:

```javascript
// Frontend: Dashboard.jsx
const response = await getPhaseMap(startDate, endDate)
// startDate = 1 month before active month
// endDate = 1 month after active month
```

### Step 2: Backend Receives Request
Backend endpoint: `GET /cycles/phase-map?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

**Location**: `backend/routes/cycles.py` → `get_phase_map()`

### Step 3: Check Database for Existing Predictions
```python
# Try to get from database first (RapidAPI predictions)
query = supabase.table("user_cycle_days").select("*").eq("user_id", user_id)
response = query.order("date").execute()
stored_data = response.data or []
```

**If stored data exists**: Return it immediately (fast path)
- Data comes from previous RapidAPI predictions
- Already has `date`, `phase`, and `phase_day_id` for each day

### Step 4: If No Stored Data, Generate RapidAPI Predictions

#### 4.1 Get User Data
```python
user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
last_period_date = user.get("last_period_date")  # e.g., "2025-11-02"
cycle_length = user.get("cycle_length", 28)      # e.g., 28
```

#### 4.2 Build Past Cycle Data for RapidAPI
```python
# Generate 5 cycles going backwards from last_period_date
past_cycle_data = []
last_period_dt = datetime.strptime(last_period_date_str, "%Y-%m-%d")
for i in range(5):
    cycle_date = last_period_dt - timedelta(days=cycle_length * i)
    past_cycle_data.append({
        "cycle_start_date": cycle_date.strftime("%Y-%m-%d"),
        "period_length": 5  # Default period length
    })
```

**Example**:
- If `last_period_date = "2025-11-02"` and `cycle_length = 28`:
  - Cycle 1: 2025-11-02 (last period)
  - Cycle 2: 2025-10-05 (28 days before)
  - Cycle 3: 2025-09-07 (56 days before)
  - Cycle 4: 2025-08-10 (84 days before)
  - Cycle 5: 2025-07-13 (112 days before)

### Step 5: Call RapidAPI

#### 5.1 Process Cycle Data
```python
# Location: backend/cycle_utils.py → process_cycle_data()
payload = {
    "current_date": "2025-11-16",  # Today's date
    "past_cycle_data": past_cycle_data,
    "max_cycle_predictions": 6
}
response = call_womens_health_api("/process_cycle_data", "POST", payload)
request_id = response["request_id"]
```

**What this does**: Sends past cycle data to RapidAPI and gets a `request_id` for subsequent calls.

#### 5.2 Get Predicted Cycle Starts
```python
# Location: backend/cycle_utils.py → get_predicted_cycle_starts()
predicted_starts = get_predicted_cycle_starts(request_id)
# Returns: ["2025-11-02", "2025-11-30", "2025-12-28", ...]
```

**What this does**: Gets future cycle start dates predicted by RapidAPI.

#### 5.3 Get Average Period and Cycle Lengths
```python
average_period_length = get_average_period_length(request_id)  # e.g., 5 days
average_cycle_length = get_average_cycle_length(request_id)    # e.g., 28 days
```

**Important**: The calculated `average_cycle_length` is updated using **Bayesian smoothing**:
```python
# Location: backend/cycle_utils.py → update_cycle_length_bayesian()
updated_cycle_length = (old_cycle_length * 0.7) + (average_cycle_length * 0.3)
supabase.table("users").update({
    "cycle_length": int(updated_cycle_length)
}).eq("id", user_id).execute()
```

**Why Bayesian?**: Smooths cycle length over time, preventing sudden jumps (70% old value, 30% new value).

#### 5.4 Get Complete Cycle Phase Timeline (NEW - PRIMARY SOURCE)
```python
# Location: backend/cycle_utils.py → get_cycle_phases()
cycle_phases_timeline = get_cycle_phases(request_id)
# Returns: [
#   {"date": "2025-11-02", "phase": "Period", "day_in_phase": 1},
#   {"date": "2025-11-03", "phase": "Period", "day_in_phase": 2},
#   {"date": "2025-11-07", "phase": "Follicular", "day_in_phase": 1},
#   {"date": "2025-11-16", "phase": "Ovulation", "day_in_phase": 1},
#   ...
# ]
```

**What this does**: Gets the complete day-by-day phase timeline directly from RapidAPI. This is the **PRIMARY** and **MOST ACCURATE** source.

**Key Advantage**: Phase boundaries come directly from RapidAPI's calculations, not manual estimates.

### Step 6: Generate Phase Mappings from RapidAPI Timeline (PRIMARY METHOD)

**Location**: `backend/cycle_utils.py` → `generate_cycle_phase_map()`

#### 6.1 Use RapidAPI Timeline (Primary Method)

If RapidAPI `cycle_phases` endpoint succeeds:

```python
phase_mappings = []
for entry in cycle_phases_timeline:
    date_str = entry.get("date")           # "2025-11-02"
    phase_name = entry.get("phase")        # "Period"
    day_in_phase = entry.get("day_in_phase", 1)  # 1
    
    # Generate phase_day_id from phase name and day_in_phase
    phase_day_id = generate_phase_day_id(phase_name, day_in_phase)  # "p1"
    
    phase_mappings.append({
        "date": date_str,
        "phase": phase_name,
        "phase_day_id": phase_day_id,
        "source": "api",           # NEW: Track data source
        "confidence": 1.0          # NEW: Confidence score (1.0 = highest)
    })
```

**Key Points**:
- ✅ No manual phase length calculations needed
- ✅ Phase boundaries come directly from RapidAPI
- ✅ Most accurate method
- ✅ Confidence = 1.0 (highest)

#### 6.2 Fallback: Manual Calculation (If API Fails)

If RapidAPI `cycle_phases` endpoint fails, system falls back to improved manual calculation:

```python
# Improved biologically accurate defaults
period_days = average_period_length      # From RapidAPI (e.g., 5)
luteal_days = 14                         # Fixed (biologically accurate)
ovulation_window = 6                     # Fixed (biologically accurate)
follicular_days = cycle_length - period_days - luteal_days - ovulation_window

# Generate phases with improved distribution
for cycle in predicted_cycles:
    # Period phase (p1-p5)
    for day in range(period_days):
        phase_mappings.append({
            "date": date_str,
            "phase": "Period",
            "phase_day_id": f"p{day+1}",
            "source": "adjusted",      # NEW: Track as adjusted
            "confidence": 0.7          # NEW: Lower confidence (0.7)
        })
    
    # Follicular phase (f1-fX)
    for day in range(follicular_days):
        phase_mappings.append({
            "date": date_str,
            "phase": "Follicular",
            "phase_day_id": f"f{day+1}",
            "source": "adjusted",
            "confidence": 0.7
        })
    
    # Ovulation phase (o1-o6)
    for day in range(ovulation_window):
        phase_mappings.append({
            "date": date_str,
            "phase": "Ovulation",
            "phase_day_id": f"o{day+1}",
            "source": "adjusted",
            "confidence": 0.7
        })
    
    # Luteal phase (l1-l14)
    for day in range(luteal_days):
        phase_mappings.append({
            "date": date_str,
            "phase": "Luteal",
            "phase_day_id": f"l{day+1}",
            "source": "adjusted",
            "confidence": 0.7
        })
```

**Key Improvements**:
- ✅ Biologically accurate defaults (luteal=14, ovulation=6)
- ✅ Better phase distribution algorithm
- ✅ Confidence = 0.7 (medium)

### Step 7: Store in Database

**Location**: `backend/cycle_utils.py` → `store_cycle_phase_map()`

#### 7.1 Full Update (Default)
```python
# Delete all existing mappings
supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()

# Insert new mappings with source and confidence
insert_data = []
for mapping in phase_mappings:
    insert_data.append({
        "user_id": user_id,
        "date": "2025-11-02",
        "phase": "Period",
        "phase_day_id": "p1",
        "source": "api",        # NEW: "api" | "adjusted" | "fallback"
        "confidence": 1.0       # NEW: 1.0 | 0.7 | 0.5
    })

supabase.table("user_cycle_days").insert(insert_data).execute()
```

#### 7.2 Partial Update (NEW - Preserves Past Data)
```python
# Only delete future dates (preserve past predictions)
current_date = "2025-11-16"
supabase.table("user_cycle_days").delete().eq("user_id", user_id).gte("date", current_date).execute()

# Insert only future mappings
insert_data = [mapping for mapping in phase_mappings if mapping["date"] >= current_date]
supabase.table("user_cycle_days").insert(insert_data).execute()
```

**When Partial Update is Used**:
- Early/late period detected (difference >= 2 days)
- User logs a period → only future dates recalculated
- Preserves historical predictions

**Database Table**: `user_cycle_days`
- `user_id`: UUID
- `date`: DATE (YYYY-MM-DD)
- `phase`: TEXT ("Period", "Follicular", "Ovulation", "Luteal")
- `phase_day_id`: TEXT (e.g., "p1", "f5", "o2", "l10")
- `source`: VARCHAR(20) [OPTIONAL] - "api" | "adjusted" | "fallback"
- `confidence`: FLOAT [OPTIONAL] - 1.0 | 0.7 | 0.5

### Step 8: Fallback Calculation (If RapidAPI Completely Fails)

**Location**: `backend/cycle_utils.py` → `calculate_phase_for_date_range()`

If RapidAPI is completely unavailable (no API key, network error, etc.), the system uses an **improved fallback calculation**:

```python
# Improved biologically accurate defaults
period_days = 5           # Average period length
luteal_days = 14          # Fixed luteal phase (biologically accurate)
ovulation_window = 6       # Ovulation window (biologically accurate)
follicular_days = cycle_length - period_days - luteal_days - ovulation_window

# Calculate days since last_period_date
days_since_last_period = (current_date - last_period_date).days

# Calculate which day of the cycle (wrapping if needed)
day_in_cycle = (days_since_last_period % cycle_length) + 1

# Assign phase based on day_in_cycle with improved distribution
if day_in_cycle <= period_days:
    phase = "Period"
    phase_day_id = f"p{day_in_cycle}"
    confidence = 0.5
elif day_in_cycle <= period_days + follicular_days:
    phase = "Follicular"
    day_in_phase = day_in_cycle - period_days
    phase_day_id = f"f{day_in_phase}"
    confidence = 0.5
elif day_in_cycle <= period_days + follicular_days + ovulation_window:
    phase = "Ovulation"
    day_in_phase = day_in_cycle - period_days - follicular_days
    phase_day_id = f"o{day_in_phase}"
    confidence = 0.5
else:
    phase = "Luteal"
    day_in_phase = day_in_cycle - period_days - follicular_days - ovulation_window
    phase_day_id = f"l{day_in_phase}"
    confidence = 0.5
```

**Example**:
- `last_period_date = "2025-11-02"`
- `cycle_length = 28`
- `current_date = "2025-11-16"`
- `days_since = 14`
- `day_in_cycle = 15`
- Calculation:
  - `period_days = 5`
  - `follicular_days = 28 - 5 - 14 - 6 = 3` (but minimum 1, so adjusted)
  - `day_in_cycle = 15`
  - `15 > 5` (period) and `15 > 5 + 3 = 8` (follicular) and `15 > 8 + 6 = 14` (ovulation)
  - Result: `phase = "Luteal"`, `day_in_phase = 15 - 5 - 3 - 6 = 1`, `phase_day_id = "l1"`, `confidence = 0.5`

**Key Improvements**:
- ✅ Biologically accurate defaults (luteal=14, ovulation=6)
- ✅ Better phase distribution
- ✅ Returns `source="fallback"` and `confidence=0.5`

---

## 4. Frontend: Calendar Display

### Step 1: Receive Phase Map Data
```javascript
// Dashboard.jsx
const response = await getPhaseMap(startDate, endDate)
// Response: { phase_map: [{ date: "2025-11-02", phase: "Period", phase_day_id: "p1" }, ...] }
```

### Step 2: Process and Store Phase Map
```javascript
const map = {}
response.phase_map.forEach(item => {
    map[item.date] = {
        phase: item.phase,
        phase_day_id: item.phase_day_id
    }
})
setCalendarPhaseMap(map)
```

### Step 3: Assign Colors to Calendar Dates

**Color Mapping** (defined in `Dashboard.jsx`):
```javascript
const getPhaseCircleColor = (phase) => {
    switch(phase?.toLowerCase()) {
        case 'period': return '#F8BBD9'      // Pink
        case 'follicular': return '#90EE90'  // Light Green
        case 'ovulation': return '#FFD700'    // Gold
        case 'luteal': return '#BA68C8'      // Purple
        default: return '#D3D3D3'            // Grey (no data)
    }
}
```

### Step 4: Render Calendar with Colors

For each date in the calendar:
```javascript
const phaseData = calendarPhaseMap[dateString]  // e.g., "2025-11-02"
const color = getPhaseCircleColor(phaseData?.phase)
const phaseDayId = phaseData?.phase_day_id || ''  // e.g., "p1"

// Render colored circle with date number and phase_day_id
<div style={{ backgroundColor: color }}>
    <div>{dayNumber}</div>
    <div>{phaseDayId}</div>
</div>
```

---

## 5. How `last_period_date` and `cycle_length` Are Used

### When User Logs a Period (UPGRADED)
1. User logs period date → stored in `period_logs` table
2. **NEW**: Calculate new cycle length from previous period:
   ```python
   new_cycle_length = (current_period_date - previous_period_date).days
   ```
3. **NEW**: Update `cycle_length` using Bayesian smoothing:
   ```python
   updated_cycle_length = (old_cycle_length * 0.7) + (new_cycle_length * 0.3)
   ```
4. **NEW**: Detect early/late period:
   ```python
   difference = actual_period_date - predicted_period_date
   if abs(difference) >= 2 days:
       should_adjust = True  # Triggers partial update
   ```
5. `last_period_date` in `users` table is updated
6. If RapidAPI is available, new predictions are generated:
   - **Partial update** if early/late detected (only future dates)
   - **Full update** if normal period

### When User Registers
1. User provides `last_period_date` and `cycle_length` (default: 28)
2. Stored in `users` table
3. RapidAPI predictions are generated automatically (if `RAPIDAPI_KEY` is set)
4. **NEW**: Cycle length updated using Bayesian smoothing after RapidAPI calculation

### When Calendar is Opened
1. System checks if predictions exist in `user_cycle_days` table
2. If stored data exists → return immediately (fast path)
3. If no stored data, uses `last_period_date` and `cycle_length` to:
   - Build past cycle data for RapidAPI
   - Call RapidAPI `cycle_phases` endpoint (PRIMARY)
   - OR calculate phases using improved fallback method

### When RapidAPI Updates `cycle_length` (UPGRADED)
- RapidAPI calculates average cycle length from past cycles
- **NEW**: Updates `users.cycle_length` using **Bayesian smoothing**:
  ```python
  updated = (old * 0.7) + (rapidapi_calculated * 0.3)
  ```
- Future calculations use this smoothed value
- Prevents sudden jumps in cycle length predictions

---

## 6. Complete Example Flow (UPGRADED)

### Scenario: User opens calendar on November 16, 2025

1. **User Data**:
   - `last_period_date = "2025-11-02"`
   - `cycle_length = 28` (default)

2. **Frontend Request**:
   - Requests phase map from `2025-10-01` to `2025-12-31`

3. **Backend Check**:
   - Checks `user_cycle_days` table → No data found

4. **Generate Past Cycle Data**:
   ```python
   past_cycle_data = [
       {"cycle_start_date": "2025-11-02", "period_length": 5},
       {"cycle_start_date": "2025-10-05", "period_length": 5},
       {"cycle_start_date": "2025-09-07", "period_length": 5},
       {"cycle_start_date": "2025-08-10", "period_length": 5},
       {"cycle_start_date": "2025-07-13", "period_length": 5}
   ]
   ```

5. **RapidAPI Calls**:
   - `POST /process_cycle_data` → Returns `request_id = "abc123"`
   - `GET /get_data/abc123/predicted_cycle_starts` → Returns `["2025-11-02", "2025-11-30", "2025-12-28"]`
   - `GET /get_data/abc123/average_period_length` → Returns `5`
   - `GET /get_data/abc123/average_cycle_length` → Returns `28`
   - **NEW**: `GET /get_data/abc123/cycle_phases` → Returns complete timeline:
     ```json
     [
       {"date": "2025-11-02", "phase": "Period", "day_in_phase": 1},
       {"date": "2025-11-03", "phase": "Period", "day_in_phase": 2},
       {"date": "2025-11-07", "phase": "Follicular", "day_in_phase": 1},
       {"date": "2025-11-16", "phase": "Ovulation", "day_in_phase": 1},
       {"date": "2025-11-23", "phase": "Luteal", "day_in_phase": 1},
       ...
     ]
     ```

6. **Update Cycle Length (Bayesian)**:
   ```python
   old_cycle_length = 28
   rapidapi_cycle_length = 28
   updated_cycle_length = (28 * 0.7) + (28 * 0.3) = 28
   # Stored in database
   ```

7. **Generate Phase Mappings (PRIMARY METHOD - RapidAPI Timeline)**:
   ```python
   # Use cycle_phases timeline directly (no manual calculation)
   for entry in cycle_phases_timeline:
       phase_mappings.append({
           "date": entry["date"],
           "phase": entry["phase"],
           "phase_day_id": generate_phase_day_id(entry["phase"], entry["day_in_phase"]),
           "source": "api",        # Track as API source
           "confidence": 1.0       # Highest confidence
       })
   ```
   
   **Result**:
   - Nov 2: Period, p1, source=api, confidence=1.0
   - Nov 3: Period, p2, source=api, confidence=1.0
   - Nov 7: Follicular, f1, source=api, confidence=1.0
   - Nov 16: Ovulation, o1, source=api, confidence=1.0
   - Nov 23: Luteal, l1, source=api, confidence=1.0

8. **Store in Database**:
   - All mappings stored in `user_cycle_days` table with `source` and `confidence`
   - Full update (all dates stored)

9. **Return to Frontend** (source/confidence not exposed for compatibility):
   ```json
   {
     "phase_map": [
       {"date": "2025-11-02", "phase": "Period", "phase_day_id": "p1"},
       {"date": "2025-11-03", "phase": "Period", "phase_day_id": "p2"},
       {"date": "2025-11-16", "phase": "Ovulation", "phase_day_id": "o1"},
       ...
     ]
   }
   ```

10. **Frontend Display**:
    - Nov 2: Pink circle (#F8BBD9) with "2" and "p1"
    - Nov 16: Gold circle (#FFD700) with "16" and "o1"
    - Nov 24: Purple circle (#BA68C8) with "24" and "l1"

### Scenario: User Logs Period Early (NEW)

1. **User logs period on Nov 28** (predicted: Nov 30)
   - Difference: -2 days (early)

2. **Early/Late Detection**:
   ```python
   difference = -2 days
   should_adjust = True  # abs(-2) >= 2
   ```

3. **Calculate New Cycle Length**:
   ```python
   previous_period = "2025-11-02"
   current_period = "2025-11-28"
   new_cycle_length = 26 days
   ```

4. **Update Cycle Length (Bayesian)**:
   ```python
   old_cycle_length = 28
   updated_cycle_length = (28 * 0.7) + (26 * 0.3) = 27.4 → 27
   ```

5. **Generate Predictions (Partial Update)**:
   ```python
   generate_cycle_phase_map(
       user_id=user_id,
       past_cycle_data=past_cycles,
       current_date="2025-11-28",
       update_future_only=True  # Only update dates >= Nov 28
   )
   ```

6. **Database Update**:
   - Past dates (Nov 2-27): **PRESERVED** (not deleted)
   - Future dates (Nov 28+): **RECALCULATED** and updated
   - Historical predictions remain intact

---

## 7. Key Points (UPGRADED)

1. **RapidAPI `cycle_phases` is Primary**: System uses RapidAPI's complete phase timeline as the most accurate source
2. **No Static Phase Lengths**: When RapidAPI succeeds, phase boundaries come directly from API (not manual estimates)
3. **Improved Fallback**: If RapidAPI fails, uses biologically accurate defaults (luteal=14, ovulation=6)
4. **Partial Updates**: Only future dates updated when early/late period detected (preserves past data)
5. **Early/Late Detection**: Automatically detects and adjusts when user logs period 2+ days early/late
6. **Bayesian Smoothing**: Cycle length updates are smoothed (70% old, 30% new) to prevent sudden jumps
7. **Confidence Tracking**: Each prediction has confidence score (1.0=API, 0.7=adjusted, 0.5=fallback)
8. **Source Tracking**: Each prediction tracks its source (api, adjusted, fallback)
9. **Database Caching**: Predictions are stored in `user_cycle_days` table to avoid repeated API calls
10. **Auto-Update**: `cycle_length` is updated using Bayesian smoothing after RapidAPI calculations
11. **Phase Day IDs**: Always follow pattern `{prefix}{day_number}` (e.g., p1, f5, o2, l10)
12. **Colors**: Assigned based on phase name, not phase_day_id
13. **Date Range**: Calendar requests data for 3 months (1 before, current, 1 after) for smooth navigation
14. **Backward Compatible**: Frontend API contract unchanged, optional fields not exposed

---

## 8. Files Involved (UPGRADED)

### Backend
- `backend/routes/cycles.py` - API endpoints for phase map (improved fallback)
- `backend/cycle_utils.py` - Core calculation logic, RapidAPI integration (UPGRADED)
  - `get_cycle_phases()` - NEW: Get complete phase timeline from RapidAPI
  - `generate_cycle_phase_map()` - UPGRADED: Uses RapidAPI timeline, supports partial updates
  - `store_cycle_phase_map()` - UPGRADED: Supports partial updates, stores confidence/source
  - `update_cycle_length_bayesian()` - NEW: Bayesian smoothing for cycle length
  - `detect_early_late_period()` - NEW: Early/late period detection
  - `calculate_phase_for_date_range()` - UPGRADED: Improved fallback with accurate defaults
- `backend/routes/periods.py` - Period logging (UPGRADED: early/late detection, Bayesian updates)
- `backend/routes/auth.py` - Registration (triggers predictions)

### Frontend
- `frontend/src/pages/Dashboard.jsx` - Calendar display, color assignment (unchanged)
- `frontend/src/utils/api.js` - API calls to backend (unchanged)

### Database
- `users` table - Stores `last_period_date` and `cycle_length` (updated via Bayesian smoothing)
- `user_cycle_days` table - Stores phase mappings:
  - `date`, `phase`, `phase_day_id` (required)
  - `source` (optional) - "api" | "adjusted" | "fallback"
  - `confidence` (optional) - 1.0 | 0.7 | 0.5
- `period_logs` table - Stores logged period dates
- `database/add_confidence_source_columns.sql` - NEW: Migration script for optional columns

---

## 9. Error Handling (UPGRADED)

1. **No `last_period_date`**: Returns empty phase map, user must log period
2. **RapidAPI Key Missing**: Falls back to improved calculation (confidence=0.5)
3. **RapidAPI `cycle_phases` Fails**: Falls back to improved calculation using predicted_starts (confidence=0.7)
4. **RapidAPI Completely Fails**: Falls back to improved calculation using last_period_date (confidence=0.5)
5. **No Data in Database**: Generates new predictions automatically (tries RapidAPI first)
6. **Invalid Date Range**: Returns empty phase map
7. **Database Columns Missing**: Gracefully handles missing `source`/`confidence` columns (retries without them)

## 10. Confidence Scores and Sources

### Confidence Levels

| Source | Confidence | When Used | Accuracy |
|--------|-----------|-----------|----------|
| `api` | 1.0 | RapidAPI `cycle_phases` endpoint succeeds | Highest - Direct from API |
| `adjusted` | 0.7 | RapidAPI predictions available but using manual phase distribution | Medium - Based on API predictions |
| `fallback` | 0.5 | RapidAPI unavailable, using `last_period_date` + `cycle_length` | Lower - Estimated calculation |

### How Sources Are Assigned

1. **`source = "api"`** (confidence = 1.0):
   - RapidAPI `cycle_phases` endpoint returns complete timeline
   - Phase boundaries come directly from API
   - Most accurate method

2. **`source = "adjusted"`** (confidence = 0.7):
   - RapidAPI provides predicted cycle starts
   - But `cycle_phases` endpoint fails or unavailable
   - System uses predicted starts with improved manual phase distribution
   - Still based on API predictions, but phase boundaries are estimated

3. **`source = "fallback"`** (confidence = 0.5):
   - RapidAPI completely unavailable (no key, network error, etc.)
   - System uses `last_period_date` and `cycle_length` only
   - Uses improved biologically accurate defaults
   - Least accurate but still functional

## 11. RapidAPI Integration Details

### API Endpoints Used

1. **`POST /process_cycle_data`**
   - **Input**: Past cycle data, current date, max predictions
   - **Output**: `request_id` for subsequent calls
   - **Purpose**: Initialize prediction session

2. **`GET /get_data/{request_id}/predicted_cycle_starts`**
   - **Output**: List of predicted cycle start dates
   - **Purpose**: Get future cycle predictions

3. **`GET /get_data/{request_id}/average_period_length`**
   - **Output**: Average period length in days
   - **Purpose**: Get period duration

4. **`GET /get_data/{request_id}/average_cycle_length`**
   - **Output**: Average cycle length in days
   - **Purpose**: Get cycle duration (used for Bayesian update)

5. **`GET /get_data/{request_id}/cycle_phases`** ⭐ **NEW - PRIMARY**
   - **Output**: Complete day-by-day phase timeline
   - **Format**: `[{"date": "YYYY-MM-DD", "phase": "PhaseName", "day_in_phase": N}, ...]`
   - **Purpose**: Get exact phase boundaries for each day (most accurate)

### RapidAPI Flow

```
1. Send past cycle data → Get request_id
   ↓
2. Get predicted cycle starts
   ↓
3. Get average period/cycle lengths
   ↓
4. ⭐ Get complete cycle_phases timeline (PRIMARY)
   ↓
5. Use timeline directly (no manual calculation)
   ↓
6. If timeline fails → Use predicted starts with manual distribution
   ↓
7. If all fails → Use fallback calculation
```

## 12. How `last_period_date` and `cycle_length` Are Used in Detail

### `last_period_date` Usage

1. **Building Past Cycle Data**:
   ```python
   # Generate 5 cycles going backwards
   for i in range(5):
       cycle_date = last_period_date - timedelta(days=cycle_length * i)
       past_cycle_data.append({
           "cycle_start_date": cycle_date,
           "period_length": 5
       })
   ```

2. **Fallback Calculation**:
   ```python
   # Calculate which day of cycle
   days_since = (current_date - last_period_date).days
   day_in_cycle = (days_since % cycle_length) + 1
   ```

3. **Early/Late Detection**:
   ```python
   # Compare logged period vs predicted
   predicted_p1 = get_most_recent_p1_date()
   difference = logged_period_date - predicted_p1
   ```

### `cycle_length` Usage

1. **Building Past Cycles**:
   - Used to calculate previous cycle start dates
   - Formula: `previous_start = last_period_date - (cycle_length * i)`

2. **Fallback Calculation**:
   - Used to determine phase boundaries
   - Formula: `follicular_days = cycle_length - period - luteal - ovulation`

3. **Bayesian Updates**:
   - Updated when RapidAPI calculates average
   - Updated when user logs period
   - Formula: `updated = (old * 0.7) + (new * 0.3)`

4. **Cycle Wrapping**:
   - Used to wrap day calculations across multiple cycles
   - Formula: `day_in_cycle = (days_since % cycle_length) + 1`

## 13. Phase ID Assignment Logic

### Phase Prefixes

| Phase | Prefix | Day Range | Example IDs |
|-------|--------|-----------|-------------|
| Period | `p` | p1-p12 | p1, p2, p3, ..., p12 |
| Follicular | `f` | f1-f30 | f1, f2, f3, ..., f30 |
| Ovulation | `o` | o1-o8 | o1, o2, o3, ..., o8 |
| Luteal | `l` | l1-l25 | l1, l2, l3, ..., l25 |

### Assignment Methods

#### Method 1: From RapidAPI Timeline (Primary)
```python
# RapidAPI provides day_in_phase directly
phase_day_id = generate_phase_day_id(phase_name, day_in_phase)
# Example: phase="Period", day_in_phase=3 → "p3"
```

#### Method 2: From Manual Calculation (Fallback)
```python
# Calculate day_in_phase based on cycle position
if day_in_cycle <= period_days:
    day_in_phase = day_in_cycle
    phase_day_id = f"p{day_in_phase}"
elif day_in_cycle <= period_days + follicular_days:
    day_in_phase = day_in_cycle - period_days
    phase_day_id = f"f{day_in_phase}"
# ... etc
```

### Phase Day ID Generation Function

```python
def generate_phase_day_id(phase: str, day_in_phase: int) -> str:
    phase_prefix = {
        "Period": "p",
        "Menstrual": "p",
        "Follicular": "f",
        "Ovulation": "o",
        "Luteal": "l"
    }
    prefix = phase_prefix.get(phase, "p")
    return f"{prefix}{day_in_phase}"
```

## 14. Calendar Color Assignment (Frontend)

### Color Mapping

**Location**: `frontend/src/pages/Dashboard.jsx`

```javascript
const getPhaseCircleColor = (phase) => {
    switch(phase?.toLowerCase()) {
        case 'period': return '#F8BBD9'      // Pink
        case 'follicular': return '#90EE90'  // Light Green
        case 'ovulation': return '#FFD700'    // Gold
        case 'luteal': return '#BA68C8'      // Purple
        default: return '#D3D3D3'            // Grey (no data)
    }
}
```

### Rendering Logic

For each calendar date:
1. Get phase data from `calendarPhaseMap[dateString]`
2. Extract `phase` and `phase_day_id`
3. Get color: `getPhaseCircleColor(phase)`
4. Render colored circle with:
   - Date number (top)
   - Phase day ID (bottom, e.g., "p1", "f5", "o2", "l10")

---

This completes the full flow of calendar phase calculation, color assignment, and phase ID generation in the upgraded app.

