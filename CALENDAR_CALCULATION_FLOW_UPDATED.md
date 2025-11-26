# Calendar Days Calculation Flow - Updated Documentation (2025)

## Overview
This document explains the **updated** complete flow of how calendar days are calculated, how RapidAPI is integrated, how phase IDs are assigned, and how everything is derived from `cycle_length` and `last_period_date` using **adaptive, dynamic calculations**.

---

## 🆕 Key Updates in This Version

1. **✅ Adaptive Period Length** - No longer fixed at 5 days
2. **✅ Adaptive Luteal Phase** - Uses Bayesian smoothing with user history
3. **✅ Dynamic Ovulation Window** - Based on fertility probability, not fixed days
4. **✅ Adaptive Fertility Threshold** - Regular cycles (1-3 days) vs Irregular cycles (up to 8 days)
5. **✅ No Fixed Phase Lengths** - All calculations are date-relative and adaptive

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
4. Uses adaptive estimates for period and luteal
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
4. get_average_period_length() → Get period length (used if available, else adaptive)
5. get_cycle_phases() → Get complete timeline ⭐

If step 5 succeeds:
  - Use RapidAPI timeline as primary source
  - Add fertility probabilities (calculated locally)
  - Generate phase_day_id from phase + day_in_phase
  - Store in database with source="api", confidence=0.9
  - Return phase mappings

If step 5 fails but predicted_starts exist:
  - Use predicted_starts for cycle boundaries
  - Calculate phases locally with adaptive estimates
  - Use adaptive period_length and luteal_mean
  - Use dynamic ovulation window (fertility-based)
  - Store in database with source="adjusted", confidence=0.7
  - Return phase mappings

If complete failure:
  - Use calculate_phase_for_date_range()
  - All adaptive calculations
  - Store with source="fallback", confidence=0.4
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

#### A. `estimate_period_length()` ⭐ NEW
**Purpose**: Get adaptive period length based on user history

**Algorithm**:
```python
1. Get user's period_logs from database (last 12 periods)
2. Calculate period lengths: (end_date - start_date) + 1
3. If no observations → return prior_mean = 5.0
4. If observations exist:
   - Calculate user mean
   - Bayesian smoothing: 60% prior (5.0) + 40% user mean
   - Clamp to range [3.0, 8.0] days
5. Return estimated period length
```

**Example**:
```
User periods: [4, 5, 5, 6, 5]
User mean = 5.0
Prior mean = 5.0
Bayesian mean = 0.6 * 5.0 + 0.4 * 5.0 = 5.0
Result: 5.0 days
```

#### B. `estimate_luteal()` 
**Purpose**: Get adaptive luteal phase length (not fixed!)

**Algorithm**:
```python
1. Get user's luteal_observations from database
2. If no observations → return prior: mean=14.0, sd=2.0
3. If observations exist:
   - Calculate user mean and SD
   - Bayesian smoothing: 60% prior + 40% user mean
   - Clamp to range [10.0, 18.0] days
4. Return (mean, sd)
```

**Example**:
```
User observations: [13, 14, 15, 14]
User mean = 14.0
Prior mean = 14.0
Bayesian mean = 0.6 * 14.0 + 0.4 * 14.0 = 14.0
Result: (14.0, 2.0)
```

#### C. `predict_ovulation()`
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
ovulation_sd = sqrt(1.0² + 2.0²) = sqrt(5) ≈ 2.24
```

#### D. `get_ovulation_fertility_threshold()` ⭐ NEW
**Purpose**: Get adaptive fertility threshold for ovulation window

**Algorithm**:
```python
if ovulation_sd < 1.5:
    # Very regular: high threshold → narrow window (1-2 days)
    return 0.4
elif ovulation_sd < 2.0:
    # Regular: medium-high threshold → typical window (2-3 days)
    return 0.3
elif ovulation_sd < 3.0:
    # Somewhat irregular: medium threshold → wider window (3-5 days)
    return 0.2
else:
    # Irregular: low threshold → wide window (up to 8 days)
    return 0.1
```

**Result**:
- **Regular cycles**: threshold 0.3-0.4 → **1-3 day ovulation window**
- **Irregular cycles**: threshold 0.1-0.15 → **up to 8 day ovulation window**

#### E. `fertility_probability()`
**Purpose**: Calculate fertility probability for a day

**Formula**:
```python
# Normal distribution component (ovulation probability)
p_ov = normal_pdf(offset_from_ovulation, 0.0, ovulation_sd)

# Sperm survival kernel (5 days before ovulation)
if -5.0 <= offset_from_ovulation <= 0.0:
    p_sperm = 1.0
else:
    p_sperm = 0.0

# Weighted combination
raw_prob = 0.6 * p_ov + 0.4 * p_sperm
normalized_prob = raw_prob / norm_factor
```

### Phase Determination Logic

**Inputs**:
- `last_period_date`: 2025-11-02
- `cycle_length`: 28
- `luteal_mean`: 14.0 (from `estimate_luteal()`)
- `period_days`: 5.0 (from `estimate_period_length()`)

**For each date in range**:

1. **Calculate which cycle we're in**:
   ```
   days_since_last_period = (current_date - last_period_date).days
   cycle_offset = (days_since_last_period // cycle_length) * cycle_length
   current_cycle_start = last_period_date + cycle_offset
   days_in_current_cycle = (current_date - current_cycle_start).days
   ```

2. **Get adaptive estimates**:
   ```
   period_days = estimate_period_length(user_id)  # Adaptive, not fixed!
   luteal_mean, luteal_sd = estimate_luteal(user_id)  # Adaptive, not fixed!
   ```

3. **Predict ovulation for this cycle**:
   ```
   ovulation_date = current_cycle_start + (cycle_length - luteal_mean)
   ovulation_sd = sqrt(cycle_start_sd² + luteal_sd²)
   ```

4. **Calculate fertility probability**:
   ```
   offset_from_ov = (current_date - ovulation_date).days
   fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
   ```

5. **Get adaptive fertility threshold**:
   ```
   fertility_threshold = get_ovulation_fertility_threshold(ovulation_sd)
   # Regular cycles: 0.3-0.4 → 1-3 days
   # Irregular cycles: 0.1-0.15 → up to 8 days
   ```

6. **Determine phase** (⭐ Dynamic, not fixed!):
   ```
   if days_in_cycle <= period_days:
       phase = "Period"
   elif fert_prob >= fertility_threshold:  # Dynamic threshold!
       phase = "Ovulation"  # Window size varies: 1-8 days
   elif current_date < ovulation_date:
       phase = "Follicular"
   else:
       phase = "Luteal"
   ```

7. **Calculate phase_day_id**:
   ```
   phase_counter[phase] += 1
   day_in_phase = phase_counter[phase]
   phase_day_id = generate_phase_day_id(phase, day_in_phase)
   ```

### Complete Example Calculation

**Given**:
- `last_period_date`: 2025-11-02
- `cycle_length`: 28
- `luteal_mean`: 14.0 (adaptive)
- `period_days`: 5.0 (adaptive)
- `ovulation_sd`: 2.24 (calculated)

**Calculate for date: 2025-11-15**

```
1. days_since_last_period = (2025-11-15 - 2025-11-02) = 13 days
2. cycle_offset = (13 // 28) * 28 = 0
3. current_cycle_start = 2025-11-02 + 0 = 2025-11-02
4. days_in_current_cycle = (2025-11-15 - 2025-11-02) = 13 days
5. day_in_cycle = 13 + 1 = 14

6. ovulation_date = 2025-11-02 + (28 - 14) = 2025-11-16
7. ovulation_sd = sqrt(1.0² + 2.0²) = 2.24
8. offset_from_ov = (2025-11-15 - 2025-11-16) = -1 day
9. fert_prob = fertility_probability(-1, 2.24) ≈ 0.35
10. fertility_threshold = get_ovulation_fertility_threshold(2.24) = 0.2
    (since 2.24 is between 2.0 and 3.0)

11. day_in_cycle (14) <= period_days (5)? NO
12. fert_prob (0.35) >= threshold (0.2)? YES
13. phase = "Ovulation"

14. phase_counter["Ovulation"] = 1 (first ovulation day)
15. phase_day_id = "o1"
```

**Result**: `{date: "2025-11-15", phase: "Ovulation", phase_day_id: "o1"}`

---

## 5. Phase Lengths (Adaptive & Dynamic)

### Current Implementation

```
Period: Adaptive (from estimate_period_length(), typically 3-8 days)
Ovulation: Dynamic (based on fertility_probability >= threshold)
  - Regular cycles: 1-3 days (threshold 0.3-0.4)
  - Irregular cycles: up to 8 days (threshold 0.1-0.15)
Luteal: Adaptive (from estimate_luteal(), typically 10-18 days)
Follicular: Calculated as remainder
  follicular_days = cycle_length - period_days - ovulation_days - luteal_days
```

### Example Breakdown (28-day cycle, regular)

```
Period: Days 1-5 (5 days, adaptive)
Follicular: Days 6-13 (8 days)  ← Calculated as remainder
Ovulation: Days 14-16 (3 days)  ← Dynamic, based on fertility_prob >= 0.3
Luteal: Days 17-28 (12 days)    ← Adaptive, typically 14 days but can vary
```

### Example Breakdown (35-day cycle, irregular)

```
Period: Days 1-6 (6 days, adaptive - user has longer periods)
Follicular: Days 7-18 (12 days)  ← Calculated as remainder
Ovulation: Days 19-26 (8 days)  ← Dynamic, based on fertility_prob >= 0.1 (irregular)
Luteal: Days 27-35 (9 days)      ← Adaptive, user has shorter luteal phase
```

**Note**: All phase lengths are adaptive and dynamic - no fixed values!

---

## 6. Fallback Calculation: `calculate_phase_for_date_range()`

**When used**:
- RapidAPI is unavailable
- RapidAPI times out
- No stored predictions in database

**How it works**:

```
1. Get adaptive estimates:
   - period_days = estimate_period_length(user_id)  # Not fixed!
   - luteal_mean, luteal_sd = estimate_luteal(user_id)  # Not fixed!

2. For each date in range (start_date to end_date):
   a. Calculate which cycle the date belongs to
   b. Calculate current_cycle_start
   c. Predict ovulation for that cycle (dynamic)
   d. Calculate fertility probability
   e. Get adaptive fertility threshold
   f. Determine phase based on fertility_prob >= threshold
   g. Increment phase counter
   h. Generate phase_day_id
   i. Add to phase_mappings array

3. Return phase_mappings
```

**Key differences from RapidAPI method**:
- No external API calls
- Uses only last_period_date + cycle_length
- All calculations use adaptive estimates
- Dynamic ovulation window based on fertility
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
   - Uses adaptive period_length and luteal_mean
   - Uses dynamic ovulation window

3. If complete fallback:
   - Calculate on-the-fly
   - Store with source = "fallback", confidence = 0.4
   - All adaptive calculations
```

---

## 8. Performance Optimizations

### Date Range Limiting
```
- RapidAPI max: 180 days (6 months)
- Fallback max: 90 days (3 months)
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
Get Adaptive Estimates:
  ├─ estimate_period_length() → period_days (adaptive)
  └─ estimate_luteal() → luteal_mean, luteal_sd (adaptive)
    ↓
Try RapidAPI:
    ├─ process_cycle_data → request_id
    ├─ get_predicted_cycle_starts
    ├─ get_average_cycle_length → Update user.cycle_length
    ├─ get_average_period_length → Use if available, else adaptive
    └─ get_cycle_phases → Timeline
        ├─ Success: Use RapidAPI timeline + add fertility
        └─ Fail: Use predicted_starts + calculate phases
    ↓
For Each Date:
    ├─ Calculate cycle position
    ├─ Predict ovulation (dynamic: cycle_start + (cycle_length - luteal_mean))
    ├─ Calculate fertility_probability
    ├─ Get adaptive fertility_threshold (regular: 0.3-0.4, irregular: 0.1-0.15)
    ├─ Determine phase:
    │   ├─ Period: days_in_cycle <= period_days
    │   ├─ Ovulation: fert_prob >= threshold (dynamic window: 1-8 days)
    │   ├─ Follicular: before ovulation
    │   └─ Luteal: after ovulation
    └─ Generate phase_day_id
    ↓
Store in Database
    ↓
Return phase_map
    ↓ (if RapidAPI completely fails)
Fallback: calculate_phase_for_date_range()
    ├─ All adaptive estimates
    ├─ Dynamic ovulation window
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

### Period Length Estimation (Bayesian)
```
mean = 0.6 * prior_mean + 0.4 * user_mean
```

### Cycle Position
```
days_since_last_period = (current_date - last_period_date).days
cycle_offset = (days_since_last_period // cycle_length) * cycle_length
current_cycle_start = last_period_date + cycle_offset
days_in_cycle = (current_date - current_cycle_start).days + 1
```

### Fertility Threshold (Adaptive)
```
if ovulation_sd < 1.5: threshold = 0.4  # Very regular → 1-2 days
elif ovulation_sd < 2.0: threshold = 0.3  # Regular → 2-3 days
elif ovulation_sd < 3.0: threshold = 0.2  # Somewhat irregular → 3-5 days
else: threshold = 0.1  # Irregular → up to 8 days
```

### Phase Determination
```
Period: days_in_cycle <= period_days (adaptive)
Ovulation: fert_prob >= fertility_threshold (dynamic: 1-8 days)
Follicular: date < ovulation_date AND fert_prob < threshold
Luteal: date > ovulation_date AND fert_prob < threshold
```

---

## 12. Testing Scenarios

### Scenario 1: New User (No Data)
```
- last_period_date: 2025-11-02
- cycle_length: 28 (default)
- No stored predictions
- No period history
- No luteal observations
→ period_days = 5.0 (prior)
→ luteal_mean = 14.0 (prior)
→ ovulation_sd ≈ 2.24
→ fertility_threshold = 0.3 (regular)
→ Generate RapidAPI predictions
→ Store in database
→ Return phase_map
```

### Scenario 2: Regular User (Stable Cycles)
```
- Has 12 periods logged: all 5 days
- Has luteal observations: [14, 14, 15, 14]
- cycle_length: 28 (stable)
→ period_days = 5.0 (adaptive, matches user)
→ luteal_mean = 14.0 (adaptive)
→ ovulation_sd ≈ 2.0
→ fertility_threshold = 0.3 (regular)
→ Ovulation window: 2-3 days
```

### Scenario 3: Irregular User (Variable Cycles)
```
- Has variable periods: [4, 6, 5, 7, 5]
- Has variable luteal: [12, 15, 13, 16]
- cycle_length: varies 26-32 days
→ period_days = 5.4 (adaptive, average)
→ luteal_mean = 14.0 (adaptive, smoothed)
→ ovulation_sd ≈ 3.5 (high uncertainty)
→ fertility_threshold = 0.1 (irregular)
→ Ovulation window: up to 8 days
```

### Scenario 4: RapidAPI Unavailable
```
- RapidAPI fails/timeout
→ Fall back to calculate_phase_for_date_range()
→ Use last_period_date + cycle_length
→ Use adaptive period_length and luteal_mean
→ Use dynamic ovulation window
→ Calculate phases locally
→ Return phase_map (source: "fallback")
```

---

## 13. Key Differences from Previous Version

### ✅ What Changed

1. **Period Length**: Now adaptive (was fixed at 5 days)
2. **Luteal Phase**: Already adaptive, verified correct
3. **Ovulation Window**: Now dynamic based on fertility probability (was fixed ±1 day)
4. **Fertility Threshold**: Now adaptive based on cycle regularity (was fixed 0.2)
5. **All Calculations**: Date-relative, no fixed day numbers

### 📊 Ovulation Window Examples

**Regular Cycle (ovulation_sd = 1.8)**:
```
fertility_threshold = 0.3
Days with fert_prob >= 0.3: Days 14-16
Result: 3-day ovulation window
```

**Irregular Cycle (ovulation_sd = 3.5)**:
```
fertility_threshold = 0.1
Days with fert_prob >= 0.1: Days 12-19
Result: 8-day ovulation window
```

---

**End of Updated Documentation**

All calculations are now fully adaptive and dynamic, with no fixed phase lengths!




