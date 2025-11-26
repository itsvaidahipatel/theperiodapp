# Calendar Days Calculation Flow - Complete Documentation

## Overview
This document explains the complete flow of how calendar days are calculated, how RapidAPI is integrated, how phase IDs are assigned, and how everything is derived from `cycle_length` and `last_period_date`.

---

## 1. API Endpoint Flow: `/cycles/phase-map`

### Request Flow
```
Frontend Request → GET /cycles/phase-map?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

### Step-by-Step Process

#### Step 1: Check Database for Stored Predictions
```
1. Query `user_cycle_days` table for user_id + date range
2. If stored data exists → Return immediately (fast path)
3. If no stored data → Continue to generation
```

#### Step 2: Get User Data
```
1. Query `users` table for:
   - last_period_date (required)
   - cycle_length (defaults to 28 if not set)
2. Validate dates are in correct format (YYYY-MM-DD)
3. If no last_period_date → Return empty phase_map
```

#### Step 3: Try RapidAPI Generation (Primary Method)
```
1. Build past_cycle_data array:
   - Generate 5 cycles going backwards from last_period_date
   - Each cycle: {cycle_start_date, period_length: 5}
   - Example: If last_period_date = 2025-11-02, cycle_length = 28
     - Cycle 1: 2025-11-02
     - Cycle 2: 2025-10-05 (28 days before)
     - Cycle 3: 2025-09-07 (56 days before)
     - Cycle 4: 2025-08-10 (84 days before)
     - Cycle 5: 2025-07-13 (112 days before)

2. Call generate_cycle_phase_map() with:
   - user_id
   - past_cycle_data
   - current_date (today)

3. If successful → Fetch stored predictions from database
4. If fails → Fall back to local calculation
```

#### Step 4: Fallback to Local Calculation
```
1. Call calculate_phase_for_date_range()
2. Uses only last_period_date + cycle_length
3. No external API calls
```

---

## 2. RapidAPI Integration Flow

### RapidAPI Endpoints Used

#### A. `process_cycle_data` (POST)
**Purpose**: Submit past cycle data and get a request_id

**Request**:
```json
{
  "current_date": "2025-11-15",
  "past_cycle_data": [
    {"cycle_start_date": "2025-11-02", "period_length": 5},
    {"cycle_start_date": "2025-10-05", "period_length": 5},
    ...
  ],
  "max_cycle_predictions": 6
}
```

**Response**:
```json
{
  "request_id": "abc123xyz"
}
```

#### B. `get_data/{request_id}/predicted_cycle_starts` (GET)
**Purpose**: Get predicted future cycle start dates

**Response**:
```json
{
  "predicted_cycle_starts": [
    "2025-11-02",
    "2025-11-30",
    "2025-12-28",
    ...
  ]
}
```

#### C. `get_data/{request_id}/average_cycle_length` (GET)
**Purpose**: Get average cycle length calculated from past data

**Response**:
```json
{
  "average_cycle_length": 28.5
}
```

#### D. `get_data/{request_id}/average_period_length` (GET)
**Purpose**: Get average period length

**Response**:
```json
{
  "average_period_length": 5.2
}
```

#### E. `get_data/{request_id}/cycle_phases` (GET) ⭐ PRIMARY
**Purpose**: Get complete daily phase timeline

**Response**:
```json
{
  "cycle_phases": [
    {
      "date": "2025-11-02",
      "phase": "Period",
      "day_in_phase": 1
    },
    {
      "date": "2025-11-03",
      "phase": "Period",
      "day_in_phase": 2
    },
    {
      "date": "2025-11-15",
      "phase": "Follicular",
      "day_in_phase": 10
    },
    ...
  ]
}
```

### RapidAPI Flow in `generate_cycle_phase_map()`

```
1. process_cycle_data() → Get request_id
2. get_predicted_cycle_starts() → Get future cycle starts
3. get_average_cycle_length() → Update user's cycle_length (Bayesian smoothing)
4. get_average_period_length() → Get period length
5. get_cycle_phases() → Get complete timeline ⭐

If step 5 succeeds:
  - Use RapidAPI timeline as primary source
  - Add fertility probabilities (calculated locally)
  - Generate phase_day_id from phase + day_in_phase
  - Store in database
  - Return phase mappings

If step 5 fails:
  - Fall back to local calculation using predicted_starts
  - Calculate phases manually
  - Store in database
  - Return phase mappings
```

---

## 3. Phase ID Assignment Logic

### Phase Day ID Format
```
Format: {prefix}{day_number}

Prefixes:
- Period: "p" (p1, p2, p3, ...)
- Follicular: "f" (f1, f2, f3, ...)
- Ovulation: "o" (o1, o2, o3, ...)
- Luteal: "l" (l1, l2, l3, ...)
```

### Function: `generate_phase_day_id(phase, day_in_phase)`

```python
def generate_phase_day_id(phase: str, day_in_phase: int) -> str:
    phase_prefix = {
        "Period": "p",
        "Menstrual": "p",  # Alias
        "Follicular": "f",
        "Ovulation": "o",
        "Luteal": "l"
    }
    prefix = phase_prefix.get(phase, "p")
    return f"{prefix}{day_in_phase}"
```

### How `day_in_phase` is Calculated

#### Method 1: From RapidAPI Timeline
```
RapidAPI provides day_in_phase directly:
- Entry: {"phase": "Period", "day_in_phase": 3}
- Result: phase_day_id = "p3"
```

#### Method 2: From Phase Counters (Local Calculation)
```
For each cycle, maintain counters:
phase_counter = {
    "Period": 0,
    "Follicular": 0,
    "Ovulation": 0,
    "Luteal": 0
}

For each day in cycle:
1. Determine phase (Period/Follicular/Ovulation/Luteal)
2. Increment counter for that phase
3. day_in_phase = phase_counter[phase]
4. Generate phase_day_id = generate_phase_day_id(phase, day_in_phase)

Example:
- Day 1: Period → counter["Period"] = 1 → "p1"
- Day 2: Period → counter["Period"] = 2 → "p2"
- Day 6: Follicular → counter["Follicular"] = 1 → "f1"
- Day 7: Follicular → counter["Follicular"] = 2 → "f2"
- Day 14: Ovulation → counter["Ovulation"] = 1 → "o1"
- Day 15: Ovulation → counter["Ovulation"] = 2 → "o2"
- Day 16: Luteal → counter["Luteal"] = 1 → "l1"
```

**Important**: Counters reset for each new cycle!

---

## 4. Calculation from `cycle_length` and `last_period_date`

### Core Calculation Functions

#### A. `predict_ovulation()`
**Purpose**: Calculate when ovulation occurs in a cycle

**Formula**:
```python
ovulation_offset = cycle_length - luteal_mean
ovulation_date = cycle_start + timedelta(days=ovulation_offset)
ovulation_sd = sqrt(cycle_start_sd² + luteal_sd²)
```

**Example**:
```
cycle_start = 2025-11-02
cycle_length = 28
luteal_mean = 14.0

ovulation_offset = 28 - 14 = 14 days
ovulation_date = 2025-11-02 + 14 days = 2025-11-16
```

#### B. `estimate_luteal()`
**Purpose**: Get adaptive luteal phase length (not fixed!)

**Algorithm**:
```
1. Get user's luteal_observations from database (if exists)
2. If no observations:
   - Return prior: mean=14.0, sd=2.0
3. If observations exist:
   - Calculate user mean and SD
   - Bayesian smoothing: 60% prior + 40% user mean
   - Clamp to range [10, 18] days
   - Return (mean, sd)
```

**Example**:
```
User observations: [13, 14, 15, 14]
User mean = 14.0
Prior mean = 14.0
Bayesian mean = 0.6 * 14.0 + 0.4 * 14.0 = 14.0
Result: (14.0, 2.0)
```

#### C. Phase Determination Logic

**Inputs**:
- `last_period_date`: 2025-11-02
- `cycle_length`: 28
- `luteal_mean`: 14.0 (from `estimate_luteal()`)
- `period_days`: 5 (default)

**For each date in range**:

1. **Calculate which cycle we're in**:
   ```
   days_since_last_period = (current_date - last_period_date).days
   cycle_offset = (days_since_last_period // cycle_length) * cycle_length
   current_cycle_start = last_period_date + cycle_offset
   days_in_current_cycle = (current_date - current_cycle_start).days
   ```

2. **Predict ovulation for this cycle**:
   ```
   ovulation_date = current_cycle_start + (cycle_length - luteal_mean)
   ovulation_window_start = ovulation_date - 1 day
   ovulation_window_end = ovulation_date + 1 day
   ```

3. **Determine phase**:
   ```
   if days_in_cycle <= period_days:
       phase = "Period"
   elif ovulation_window_start <= current_date <= ovulation_window_end:
       phase = "Ovulation"  # 2-3 day window
   elif current_date < ovulation_window_start:
       phase = "Follicular"
   else:
       phase = "Luteal"
   ```

4. **Calculate phase_day_id**:
   ```
   phase_counter[phase] += 1
   day_in_phase = phase_counter[phase]
   phase_day_id = generate_phase_day_id(phase, day_in_phase)
   ```

### Complete Example Calculation

**Given**:
- `last_period_date`: 2025-11-02
- `cycle_length`: 28
- `luteal_mean`: 14.0
- `period_days`: 5

**Calculate for date: 2025-11-15**

```
1. days_since_last_period = (2025-11-15 - 2025-11-02) = 13 days
2. cycle_offset = (13 // 28) * 28 = 0
3. current_cycle_start = 2025-11-02 + 0 = 2025-11-02
4. days_in_current_cycle = (2025-11-15 - 2025-11-02) = 13 days
5. day_in_cycle = 13 + 1 = 14

6. ovulation_date = 2025-11-02 + (28 - 14) = 2025-11-16
7. ovulation_window = [2025-11-15, 2025-11-16, 2025-11-17]

8. day_in_cycle (14) <= period_days (5)? NO
9. 2025-11-15 in ovulation_window? YES (it's day before ovulation)
10. phase = "Ovulation"

11. phase_counter["Ovulation"] = 1 (first ovulation day)
12. phase_day_id = "o1"
```

**Result**: `{date: "2025-11-15", phase: "Ovulation", phase_day_id: "o1"}`

---

## 5. Phase Lengths (Biologically Accurate)

### Current Implementation

```
Period: 5 days (fixed, from average_period_length if available)
Ovulation: 2-3 days (day before, ovulation day, day after)
Luteal: Adaptive (from estimate_luteal(), typically 10-18 days)
Follicular: Calculated as remainder
  follicular_days = cycle_length - period_days - ovulation_days - luteal_days
```

### Example Breakdown (28-day cycle)

```
Period: Days 1-5 (5 days)
Follicular: Days 6-13 (8 days)  ← Calculated: 28 - 5 - 3 - 14 = 6, but ovulation window starts at day 14
Ovulation: Days 14-16 (3 days)  ← Day 14 (before), Day 15 (ovulation), Day 16 (after)
Luteal: Days 17-28 (12 days)    ← Adaptive, typically 14 days but can vary
```

**Note**: Follicular phase gets the remaining days after accounting for Period, Ovulation window, and Luteal phase.

---

## 6. Fallback Calculation: `calculate_phase_for_date_range()`

**When used**:
- RapidAPI is unavailable
- RapidAPI times out
- No stored predictions in database

**How it works**:

```
1. Get adaptive luteal_mean from estimate_luteal()
2. For each date in range (start_date to end_date):
   a. Calculate which cycle the date belongs to
   b. Calculate current_cycle_start
   c. Predict ovulation for that cycle
   d. Determine phase based on date relative to ovulation
   e. Increment phase counter
   f. Generate phase_day_id
   g. Add to phase_mappings array
3. Return phase_mappings
```

**Key differences from RapidAPI method**:
- No external API calls
- Uses only last_period_date + cycle_length
- Calculates phases day-by-day
- Lower confidence (0.4 vs 0.9)
- Source: "fallback" vs "api"

---

## 7. Data Storage

### Table: `user_cycle_days`

**Schema**:
```sql
- user_id (UUID)
- date (DATE)
- phase (TEXT) - "Period", "Follicular", "Ovulation", "Luteal"
- phase_day_id (TEXT) - "p1", "f5", "o2", "l10"
- source (TEXT) - "api", "adjusted", "fallback"
- confidence (FLOAT) - 0.4 to 0.9
- fertility_prob (FLOAT) - 0.0 to 1.0
- predicted_ovulation_date (DATE)
- luteal_estimate (FLOAT)
- luteal_sd (FLOAT)
- ovulation_sd (FLOAT)
```

**Storage Strategy**:
```
1. If RapidAPI succeeds:
   - Delete all existing predictions for user
   - Insert new predictions (full update)
   - source = "api", confidence = 0.9

2. If RapidAPI fails but predicted_starts available:
   - Delete all existing predictions
   - Insert calculated predictions
   - source = "adjusted", confidence = 0.7

3. If complete fallback:
   - Calculate on-the-fly
   - Don't store (or store with source = "fallback", confidence = 0.4)
```

---

## 8. Performance Optimizations

### Date Range Limiting
```
- RapidAPI: Max 180 days (6 months)
- Fallback: Max 90 days (3 months)
- Safety limit: 180 days total calculation
```

### Caching Strategy
```
1. Check database first (fast path)
2. Only generate if no stored data
3. Store results for future requests
4. Update only future dates if update_future_only=True
```

### Timeout Handling
```
- RapidAPI calls: 10s connect, 30s read timeout
- If timeout → Fall back to local calculation
- Never block user request
```

---

## 9. Error Handling

### Scenarios Handled

1. **No last_period_date**:
   - Return empty phase_map
   - Log warning

2. **RapidAPI fails**:
   - Catch exception
   - Fall back to local calculation
   - Continue processing

3. **Invalid dates**:
   - Validate format
   - Return empty phase_map if invalid

4. **Database errors**:
   - Non-fatal, continue to calculation
   - Log error

5. **Empty results**:
   - Return empty phase_map array
   - Don't raise exception

---

## 10. Summary Flow Diagram

```
Frontend Request
    ↓
Check Database
    ↓ (if empty)
Get User Data (last_period_date, cycle_length)
    ↓
Try RapidAPI:
    ├─ process_cycle_data → request_id
    ├─ get_predicted_cycle_starts
    ├─ get_average_cycle_length → Update user cycle_length
    ├─ get_average_period_length
    └─ get_cycle_phases → Timeline
        ├─ Success: Use RapidAPI timeline + add fertility
        └─ Fail: Use predicted_starts + calculate phases
    ↓
Store in Database
    ↓
Return phase_map
    ↓ (if RapidAPI completely fails)
Fallback: calculate_phase_for_date_range()
    ├─ Get adaptive luteal_mean
    ├─ For each date:
    │   ├─ Calculate cycle position
    │   ├─ Predict ovulation
    │   ├─ Determine phase
    │   └─ Generate phase_day_id
    └─ Return phase_map
```

---

## 11. Key Formulas

### Ovulation Date
```
ovulation_date = cycle_start + (cycle_length - luteal_mean)
```

### Luteal Estimation (Bayesian)
```
mean = 0.6 * prior_mean + 0.4 * user_mean
sd = (prior_sd + user_sd) / 2
```

### Cycle Position
```
days_since_last_period = (current_date - last_period_date).days
cycle_offset = (days_since_last_period // cycle_length) * cycle_length
current_cycle_start = last_period_date + cycle_offset
days_in_cycle = (current_date - current_cycle_start).days + 1
```

### Phase Determination
```
Period: days_in_cycle <= period_days
Ovulation: date in [ovulation_date - 1, ovulation_date + 1]
Follicular: date < ovulation_window_start
Luteal: date > ovulation_window_end
```

---

## 12. Testing Scenarios

### Scenario 1: New User (No Data)
```
- last_period_date: 2025-11-02
- cycle_length: 28 (default)
- No stored predictions
→ Generate RapidAPI predictions
→ Store in database
→ Return phase_map
```

### Scenario 2: Existing User (Stored Data)
```
- Has stored predictions in database
→ Return immediately (fast path)
```

### Scenario 3: RapidAPI Unavailable
```
- RapidAPI fails/timeout
→ Fall back to calculate_phase_for_date_range()
→ Use last_period_date + cycle_length
→ Calculate phases locally
→ Return phase_map (source: "fallback")
```

### Scenario 4: User with Luteal Observations
```
- User has logged periods
- luteal_observations: [13, 14, 15]
→ estimate_luteal() uses user data
→ More accurate luteal phase prediction
→ Better ovulation prediction
```

---

**End of Documentation**




