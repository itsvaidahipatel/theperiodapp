# Calendar Cycle System - Complete Technical Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Period Logging Flow](#period-logging-flow)
4. [Cycle Prediction Pipeline](#cycle-prediction-pipeline)
5. [Phase Calculation Logic](#phase-calculation-logic)
6. [Calendar Display & Lazy Loading](#calendar-display--lazy-loading)
7. [Edge Cases & Medical Validation](#edge-cases--medical-validation)
8. [Reset Functionality](#reset-functionality)
9. [Caching System](#caching-system)
10. [API Endpoints](#api-endpoints)
11. [Database Schema](#database-schema)
12. [Performance Optimizations](#performance-optimizations)
13. [Recent Improvements (2026)](#recent-improvements-2026)

---

## System Overview

The Calendar Cycle System is a medically-accurate menstrual cycle tracking and prediction system that:
- Tracks period starts and **optional period ends** (interval-based logging)
- Predicts future cycle phases using **adaptive algorithms** with **luteal anchoring**
- Displays phases on a calendar with visual differentiation between actual and predicted data
- Handles edge cases like missing periods, irregular cycles, past period logs, and outliers
- Maintains medical accuracy (21-45 day cycles, proper phase sequencing)
- Filters outliers to prevent one weird month from ruining predictions
- Uses **background prediction tasks** for non-blocking API responses
- Implements **lazy loading** to reduce initial API calls

### Key Principles
- **One Period Per Cycle**: Medically enforced - minimum 21 days between period starts
- **Period Start and End**: Users can log both period start (required) and end (optional) dates
- **Actual vs Predicted**: Clear visual distinction between logged periods and predictions
- **Adaptive Learning**: Cycle length, period length, and luteal phase estimates improve with more data
- **Outlier Protection**: Cycles outside Mean ± 2×SD are filtered to keep predictions stable
- **Medical Accuracy**: All calculations follow established medical research (ACOG guidelines)
- **Non-Blocking Predictions**: Heavy calculations run in background, API returns immediately
- **Lazy Loading**: Only loads months when needed, reducing initial load time

---

## Architecture

### Backend Components

```
backend/
├── cycle_utils.py          # Core phase calculation logic (luteal anchoring, cycle normalization)
├── routes/
│   ├── cycles.py           # Phase map API endpoints (background tasks, 202 responses)
│   └── periods.py          # Period logging endpoints (start + end)
├── period_start_logs.py    # Period start tracking
├── prediction_cache.py     # Prediction regeneration (hard invalidation)
├── cycle_stats.py          # Cycle statistics calculation
├── auto_close_periods.py   # Auto-close logic for forgotten periods (>10 days)
└── missing_period_handler.py  # Late period handling
```

### Frontend Components

```
frontend/src/
├── components/
│   └── PeriodCalendar.jsx  # Main calendar component (lazy loading, 9-month initial load)
├── context/
│   ├── CalendarCacheContext.jsx  # Calendar data caching (sessionStorage)
│   └── DataContext.jsx      # Global data context (auth-gated)
└── pages/
    ├── Dashboard.jsx       # Dashboard with calendar
    └── Profile.jsx         # Reset functionality
```

### Data Flow

```
User Logs Period Start
    ↓
Backend: Auto-close open periods > 10 days
    ↓
Backend: Validate & Store (period_logs table, end_date = NULL or auto-assigned)
    ↓
Backend: Sync period_start_logs
    ↓
Backend: Detect outliers (Mean ± 2×SD filter)
    ↓
Backend: Update cycle stats (excluding outliers)
    ↓
Backend: Hard invalidate predictions >= start_date
    ↓
Backend: Trigger background prediction task (non-blocking)
    ↓
Backend: Return 202 Accepted (processing status)
    ↓
Frontend: Show loading state, retry after 8s
    ↓
Backend: Calculate phases (using estimated period length if end_date is NULL)
    ↓
Backend: Store phases (user_cycle_days table)
    ↓
Frontend: Fetch updated phase map (returns stored data)
    ↓
Frontend: Display updated calendar (shows "Log Period End" button if period is open)

User Logs Period End (optional)
    ↓
Backend: Update period_logs (end_date, is_manual_end = true)
    ↓
Backend: Hard invalidate predictions from start_date
    ↓
Backend: Recalculate phases with actual period range
    ↓
Backend: Update user_cycle_days with actual period days
    ↓
Frontend: Calendar updates to show actual period range
```

---

## Period Logging Flow

### Endpoint: `POST /periods/log`

**Location**: `backend/routes/periods.py:44`

### Request Model
```python
class PeriodLogRequest(BaseModel):
    date: str  # Required: Period START date (YYYY-MM-DD)
    end_date: Optional[str] = None  # Optional: Period END date
    flow: Optional[str] = None
    notes: Optional[str] = None
```

### Step-by-Step Process

#### Step 0: Auto-Close Open Periods
```python
from auto_close_periods import auto_close_open_periods
auto_closed_periods = auto_close_open_periods(user_id)
# Closes any periods open > 10 days with estimated end_date
```

#### Step 1: Validation
```python
# 1.1: Prevent future dates
if date_obj > today:
    raise HTTPException("Cannot log period for future dates")

# 1.2: Check minimum spacing (21 days between period starts)
validation = can_log_period(user_id, date_obj)
if not validation["canLog"]:
    raise HTTPException(validation["reason"])

# 1.3: Check for anomaly (cycle length, period length, etc.)
is_anomaly = check_anomaly(user_id, date_obj)

# 1.4: Prevent logging within existing period range
for existing_log in existing_logs:
    period_start = existing_log["date"]
    period_end = existing_log.get("end_date") or (period_start + estimated_period_length)
    if period_start <= date_obj <= period_end:
        raise HTTPException("Date falls within existing period")
```

#### Step 2: Determine End Date
```python
# If user provided end_date, use it (validate >= start_date)
if log_data.end_date:
    end_date_obj = datetime.strptime(log_data.end_date, "%Y-%m-%d").date()
    if end_date_obj < date_obj:
        raise HTTPException("End date cannot be before start date")
    final_end_date = end_date_obj
    is_manual_end = True
else:
    # Auto-assign using estimated period length
    period_length = calculate_rolling_period_length(user_id)
    period_length_days = int(round(max(3.0, min(8.0, period_length))))
    final_end_date = date_obj + timedelta(days=period_length_days - 1)
    is_manual_end = False
```

#### Step 3: Save Period Log
```python
log_entry = {
    "user_id": user_id,
    "date": log_data.date,  # Period START date (REQUIRED - source of truth)
    "end_date": final_end_date.strftime("%Y-%m-%d") if final_end_date else None,
    "is_manual_end": is_manual_end,  # True if user provided, False if auto-assigned
    "flow": log_data.flow,
    "notes": log_data.notes
}

# Insert or update in period_logs table
if existing:
    response = supabase.table("period_logs").update(log_entry)...
else:
    response = supabase.table("period_logs").insert(log_entry)...
```

**Note**: If `end_date` is NULL, the system uses `estimated_period_length` for calculations. When `end_date` is set, the system uses the actual period range.

#### Step 4: Sync Period Start Logs
```python
sync_period_start_logs_from_period_logs(user_id)
# Rebuilds period_start_logs table from period_logs
# One period_log entry = one cycle start
```

#### Step 5: Detect Outliers
```python
# Calculate cycle statistics
cycle_mean = sum(cycle_lengths) / len(cycle_lengths)
cycle_sd = math.sqrt(variance)

# Outlier threshold: Mean ± 2×SD
outlier_threshold_low = cycle_mean - (2 * cycle_sd)
outlier_threshold_high = cycle_mean + (2 * cycle_sd)

# Mark cycles outside threshold as outliers
for cycle in cycles:
    if cycle_length < outlier_threshold_low or cycle_length > outlier_threshold_high:
        mark_as_outlier(cycle)  # Sets is_outlier = true in period_start_logs
```

**Impact**: Outlier cycles are excluded from Bayesian smoothing, keeping predictions stable.

#### Step 6: Update Cycle Stats (Excluding Outliers)
```python
update_user_cycle_stats(user_id)
# Recalculates:
# - Average cycle length (excluding outliers)
# - Cycle length standard deviation
# - Average period length
# - Regularity metrics
```

#### Step 7: Hard Invalidate Predictions
```python
from prediction_cache import hard_invalidate_predictions_from_date
hard_invalidate_predictions_from_date(user_id, log_data.date)
# Deletes ALL phase entries (predicted and actual) >= start_date
# This ensures no "ghost cycles" remain when actual data arrives
```

#### Step 8: Trigger Background Prediction Task
```python
# Non-blocking: Heavy calculation runs in background
background_tasks.add_task(
    _generate_phase_map_background,
    user_id,
    start_date,
    end_date,
    last_period_date_str,
    cycle_length_int
)

# Return 202 Accepted immediately
return JSONResponse(
    status_code=202,
    content={
        "status": "processing",
        "message": "Predictions are being generated in the background.",
        "phase_map": []
    }
)
```

#### Step 9: Background Prediction Generation
```python
async def _generate_phase_map_background(...):
    # Calculate phases for date range
    phase_mappings = calculate_phase_for_date_range(...)
    
    # Store in database
    if phase_mappings:
        store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
    
    # Clear prediction_in_progress flag
    del _prediction_in_progress[user_id]
```

#### Step 10: Update User Profile
```python
supabase.table("users").update({
    "last_period_date": log_data.date
}).eq("id", user_id).execute()
```

#### Step 11: Asynchronous Luteal Learning
```python
# Non-blocking: Learn from this cycle to improve future predictions
learn_luteal_from_new_period(user_id, log_data.date)
# Only updates if ovulation prediction was high-confidence (SD <= 1.5)
```

### Logging Period End

**Endpoint**: `POST /periods/log-end`

**Request**:
```json
{
    "id": "log_id",  // Period log ID
    "date": "2026-02-15"  // Period END date
}
```

**Process**:
1. Find most recent period log without `end_date` (open period)
2. Validate `end_date >= start_date`
3. Update period log with `end_date` and `is_manual_end = true`
4. Hard invalidate predictions from `start_date`
5. Recalculate phases with actual period range
6. Update `user_cycle_days` with actual period days

**Response**:
```json
{
    "message": "Period end logged successfully. Duration: 7 days.",
    "start_date": "2026-02-08",
    "end_date": "2026-02-15",
    "duration": 7
}
```

---

## Cycle Prediction Pipeline

### Overview

The cycle prediction pipeline uses a **normalized, per-cycle approach** to ensure accuracy and prevent duplicate calculations:

1. **Cycle Start Normalization**: Collect, deduplicate, and sort all cycle starts
2. **Per-Cycle Luteal Anchoring**: Calculate luteal mean and ovulation ONCE per cycle
3. **Per-Day Phase Assignment**: Assign phases using cached cycle metadata
4. **Background Processing**: Heavy calculations run asynchronously

### Step 1: Cycle Start Normalization

**Function**: `calculate_phase_for_date_range()` (`backend/cycle_utils.py:1931`)

**Process**:
```python
# Collect all potential cycle starts
cycle_starts = []

# 1. From period_logs (actual logged periods)
period_logs = get_period_logs(user_id)
for log in period_logs:
    cycle_starts.append(log["date"])

# 2. From predictions (forward/backward)
predicted_starts = predict_cycle_starts_from_period_logs(user_id, start_date, end_date)
cycle_starts.extend(predicted_starts)

# 3. Fallback (if no logs exist)
if not cycle_starts:
    cycle_starts.append(today)  # Marked as source="fallback", not persisted

# NORMALIZE: Deduplicate, sort, validate spacing
cycle_starts = sorted(set(cycle_starts))  # Deduplicate by date
cycle_starts = [cs for cs in cycle_starts if is_valid_cycle_start(cs)]  # Validate 21-day spacing

# Mark fallback cycles (not persisted)
for cycle_start in cycle_starts:
    if cycle_start == today and not period_logs:
        cycle_metadata[cycle_start] = {"source": "fallback", "is_fallback": True}
```

**Key Points**:
- Fallback cycle starts are **never persisted** to database
- All cycle starts are **deduplicated** before phase calculation
- Minimum 21-day spacing is **enforced** between cycle starts

### Step 2: Per-Cycle Luteal Anchoring

**Location**: `backend/cycle_utils.py:2187-2204`

**Process** (runs ONCE per cycle, not per day):
```python
# Pre-calculate cycle metadata cache
cycle_metadata_cache = {}

for cycle_start in cycle_starts:
    cycle_start_str = cycle_start.strftime("%Y-%m-%d")
    
    # Calculate actual cycle length for this cycle
    if cycle_index < len(cycle_starts) - 1:
        actual_cycle_length = (next_cycle_start - cycle_start).days
    else:
        actual_cycle_length = estimated_cycle_length
    
    # LUTEAL ANCHORING: Calculate ONCE per cycle
    # Formula: Predicted Ovulation = Next Period Start - avg(Last 3 Luteal Phases)
    calculated_ovulation_day = max(period_days + 1, actual_cycle_length - luteal_mean)
    
    # Fertile window calculation
    fertile_window_start = max(period_days + 1, calculated_ovulation_day - 3)
    fertile_window_end = min(int(actual_cycle_length), calculated_ovulation_day)
    
    # Validate fertile window
    if fertile_window_end < fertile_window_start:
        fertile_window_end = fertile_window_start + 1
    if fertile_window_end >= int(actual_cycle_length):
        fertile_window_end = max(fertile_window_start, int(actual_cycle_length) - 1)
    
    # Predict ovulation with uncertainty
    ovulation_date_str, ovulation_sd, ovulation_offset = predict_ovulation(
        cycle_start_str,
        actual_cycle_length,
        luteal_mean,  # Adaptive estimate (not fixed 14 days)
        luteal_sd,
        cycle_start_sd=None,
        user_id=user_id
    )
    
    # Cache all cycle-level metadata
    cycle_metadata_cache[cycle_start_str] = {
        "actual_cycle_length": actual_cycle_length,
        "calculated_ovulation_day": calculated_ovulation_day,
        "fertile_window_start": fertile_window_start,
        "fertile_window_end": fertile_window_end,
        "ovulation_date_str": ovulation_date_str,
        "ovulation_sd": ovulation_sd,
        "luteal_mean": luteal_mean  # Cache for reuse
    }
    
    # Log ONCE per cycle (not per day)
    print(f"🔬 Cycle {cycle_start_str}: luteal_mean={luteal_mean:.1f}, ovulation_day={calculated_ovulation_day}")
```

**Key Points**:
- Luteal anchoring runs **ONCE per cycle**, not in the per-day loop
- Results are **cached** in `cycle_metadata_cache` for efficient reuse
- Prevents redundant calculations and verbose logging

### Step 3: Per-Day Phase Assignment

**Process** (for each date in range):
```python
for current_date in date_range:
    # Find which cycle this date belongs to (backward search)
    current_cycle_start = None
    for i in range(len(cycle_starts) - 1, -1, -1):
        if cycle_starts[i] <= current_date:
            current_cycle_start = cycle_starts[i]
            break
    
    # Calculate day in cycle (1-indexed)
    day_in_cycle = (current_date - current_cycle_start).days + 1
    
    # Get cached cycle metadata (no recalculation)
    cycle_meta = cycle_metadata_cache[current_cycle_start.strftime("%Y-%m-%d")]
    actual_cycle_length = cycle_meta["actual_cycle_length"]
    fertile_window_start = cycle_meta["fertile_window_start"]
    fertile_window_end = cycle_meta["fertile_window_end"]
    
    # Get period range (prioritize manual end_date)
    period_start, period_end = get_effective_period_end(user_id, current_cycle_start.strftime("%Y-%m-%d"))
    if period_end:
        actual_period_days = (period_end - period_start).days + 1
    else:
        actual_period_days = estimated_period_length
    
    # Assign phase using cached metadata
    if 1 <= day_in_cycle <= actual_period_days:
        phase = "Period"
    elif day_in_cycle >= fertile_window_start and day_in_cycle <= fertile_window_end:
        phase = "Ovulation"
    elif day_in_cycle > actual_period_days and day_in_cycle < fertile_window_start:
        phase = "Follicular"
    elif day_in_cycle > fertile_window_end:
        phase = "Luteal"
    
    # Generate phase day ID
    phase_day_id = generate_phase_day_id(phase, day_in_phase)
    
    # Store phase mapping
    phase_mappings.append({
        "date": current_date.strftime("%Y-%m-%d"),
        "phase": phase,
        "phase_day_id": phase_day_id,
        ...
    })
```

**Key Points**:
- Uses **cached cycle metadata** (no recalculation in per-day loop)
- Efficient O(1) lookup for cycle metadata
- No cycle-level math inside the date loop

---

## Phase Calculation Logic

### Core Function: `calculate_phase_for_date_range()`

**Location**: `backend/cycle_utils.py:1931`

**Purpose**: Calculate phase mappings for a date range using adaptive, medically credible algorithms.

**Input Parameters**:
- `user_id`: User identifier
- `last_period_date`: Most recent period start date (YYYY-MM-DD)
- `cycle_length`: Estimated cycle length (default 28 days)
- `start_date`: Optional start date for calculation range
- `end_date`: Optional end date for calculation range

**Output**: List of dictionaries with:
```python
{
    "date": "2026-02-08",
    "phase": "Period",  # Period | Follicular | Ovulation | Luteal
    "phase_day_id": "p1",  # p1-p12, f1-f40, o1-o8, l1-l25
    "fertility_prob": 0.0,
    "predicted_ovulation_date": "2026-02-17",
    "source": "local",
    "is_predicted": true  # false if date is in logged period
}
```

### Phase Assignment Rules

#### 1. Period Phase
- **Days**: 1 to `actual_period_days` (from `end_date` if available, else `estimated_period_length`)
- **Priority**: Highest (overrides all other phases)
- **Visual**: Vibrant pink for logged, muted pink for predicted

#### 2. Follicular Phase
- **Days**: After period ends, before fertile window starts
- **Range**: `(actual_period_days + 1)` to `(fertile_window_start - 1)`
- **Visual**: Vibrant yellow for logged, muted yellow for predicted

#### 3. Ovulation Phase
- **Days**: Fertile window (3-4 days around ovulation)
- **Range**: `fertile_window_start` to `fertile_window_end`
- **Calculation**: `ovulation_day - 3` to `ovulation_day`
- **Visual**: Vibrant teal for logged, muted teal for predicted

#### 4. Luteal Phase
- **Days**: After fertile window ends, until next period
- **Range**: `(fertile_window_end + 1)` to `actual_cycle_length`
- **Length**: Adaptive (typically 10-18 days, default 14)
- **Visual**: Vibrant lavender for logged, muted lavender for predicted

### Luteal Anchoring Formula

**Formula**: `Predicted Ovulation = Next Period Start - avg(Last 3 Luteal Phases)`

**Implementation**:
```python
# Get adaptive luteal mean (from user's observed cycles)
luteal_mean = estimate_luteal(user_id)  # Default: 14 days

# Calculate ovulation day
calculated_ovulation_day = max(period_days + 1, actual_cycle_length - luteal_mean)

# Fertile window (3 days before ovulation to ovulation day)
fertile_window_start = max(period_days + 1, calculated_ovulation_day - 3)
fertile_window_end = min(int(actual_cycle_length), calculated_ovulation_day)
```

**Benefits**:
- More accurate than fixed 14-day assumption
- Adapts to user's actual cycle patterns
- Improves over time with more data

### Period Length Handling

**Function**: `get_effective_period_end()` (`backend/cycle_utils.py`)

**Process**:
```python
def get_effective_period_end(user_id: str, start_date: str) -> date:
    # 1. Check if user logged end_date (manual)
    log = get_period_log(user_id, start_date)
    if log and log.get("end_date") and log.get("is_manual_end"):
        return log["end_date"]  # Use actual end date
    
    # 2. Use estimated period length (if end_date is NULL)
    estimated_length = calculate_rolling_period_length(user_id)
    estimated_days = int(round(max(3.0, min(8.0, estimated_length))))
    return start_date + timedelta(days=estimated_days - 1)
```

**Key Points**:
- **Prioritizes manual end_date** if user logged it
- **Falls back to estimated length** if `end_date` is NULL
- **Never assumes `end_date` exists** (always checks for NULL)

---

## Calendar Display & Lazy Loading

### Initial Load Strategy

**Location**: `frontend/src/components/PeriodCalendar.jsx`

**Initial Load**: 9 months total
- **3 months past** (for historical context)
- **Current month** (today's month)
- **5 months future** (for predictions)

**Code**:
```javascript
if (isInitial) {
  const today = new Date()
  const threeMonthsPast = subMonths(today, 3)
  const fiveMonthsFuture = addMonths(today, 5)
  startDate = format(startOfMonth(threeMonthsPast), 'yyyy-MM-dd')
  endDate = format(endOfMonth(fiveMonthsFuture), 'yyyy-MM-dd')
  
  // Mark all initial months as loaded
  for (let i = -3; i <= 5; i++) {
    const monthDate = addMonths(today, i)
    const monthKey = format(monthDate, 'yyyy-MM')
    loadedMonthsRef.current.add(monthKey)
  }
}
```

### Lazy Loading on Navigation

**Function**: `lazyLoadMonths()` (`PeriodCalendar.jsx:567`)

**Process**:
```javascript
const lazyLoadMonths = useCallback(async (targetMonth) => {
  const monthsToLoad = []
  const targetMonthKey = format(targetMonth, 'yyyy-MM')
  
  // Skip if already loaded
  if (loadedMonthsRef.current.has(targetMonthKey)) return
  
  // Load target month + adjacent months (previous and next)
  for (let offset = -1; offset <= 1; offset++) {
    const monthDate = addMonths(targetMonth, offset)
    const monthKey = format(monthDate, 'yyyy-MM')
    
    if (loadedMonthsRef.current.has(monthKey)) continue
    
    monthsToLoad.push({ date: monthDate, key: monthKey })
  }
  
  // Fetch all months in parallel using Promise.all
  await Promise.all(
    monthsToLoad.map(({ date, key }) => fetchMonth(date, key))
  )
}, [phaseMap])
```

**Benefits**:
- **Reduces initial API calls** (9 months instead of all months)
- **Faster initial load** (no aggressive background prefetching)
- **Smart caching** (prevents duplicate fetches)
- **Smooth navigation** (loads adjacent months proactively)

### Month Fetching Helper

**Function**: `fetchMonth()` (`PeriodCalendar.jsx:500`)

**Process**:
```javascript
const fetchMonth = async (monthDate, monthKey) => {
  // Skip if already loaded
  if (loadedMonthsRef.current.has(monthKey)) return null
  
  // Check if data exists in phaseMap
  const hasData = Object.keys(phaseMap).some(d => d.startsWith(monthKey))
  if (hasData) {
    loadedMonthsRef.current.add(monthKey)
    return null
  }
  
  // Fetch from API
  const response = await getPhaseMap(startDate, endDate)
  
  // Handle processing status
  if (response?.status === 'processing') {
    return null  // Will retry later
  }
  
  // Merge with existing map
  setPhaseMap(prevMap => ({ ...prevMap, ...map }))
  loadedMonthsRef.current.add(monthKey)
  
  return map
}
```

### Visual Differentiation

**Actual/Logged Dates** (vibrant colors):
- Period: `#F8BBD9` (soft pastel pink)
- Follicular: `#FEF3C7` (soft pastel yellow)
- Ovulation: `#B8E6E6` (soft pastel teal)
- Luteal: `#E1BEE7` (soft pastel lavender)

**Predicted Dates** (muted colors):
- Period: `#FCE4EC` (very light pink)
- Follicular: `#FFF9E6` (very light yellow)
- Ovulation: `#E0F7FA` (very light teal)
- Luteal: `#F3E5F5` (very light lavender)

**Determination**:
```javascript
const isLogged = loggedDatesSet.has(dateStr)
const isPredicted = !isLogged
// Use vibrant colors for logged, muted for predicted
```

---

## Edge Cases & Medical Validation

### 1. Multiple Periods in One Cycle

**Problem**: User logs period start, then logs another period start <21 days later.

**Solution**:
```python
# In predict_cycle_starts_from_period_logs()
MIN_CYCLE_DAYS = 21
for i in range(1, len(dates)):
    gap = (dates[i] - dates[i-1]).days
    if gap < MIN_CYCLE_DAYS:
        # Reject - skip this date
        print(f"⚠️ Date {dates[i]} is only {gap} days from previous (minimum 21 required)")
        continue
```

**Result**: Only one period per cycle is accepted.

### 2. Past Period Logs

**Problem**: User logs a period for a month in the past.

**Solution**:
```python
# In calculate_phase_for_date_range()
# Always include last_period_date in cycle_starts if it's in or before date range
if last_period_dt <= end_date_obj:
    if last_period_dt not in predicted_cycle_starts:
        predicted_cycle_starts.append(last_period_dt)
        predicted_cycle_starts.sort()
```

**Result**: Past logged periods are included in calculations, phases are generated for that month.

### 3. Missing Periods

**Problem**: User doesn't log a period for several months (gap >45 days).

**Solution**:
```python
# In predict_cycle_starts_from_period_logs()
cycle_length = (period_starts[i] - period_starts[i-1]).days
if cycle_length > MAX_CYCLE_DAYS:  # 45 days
    missed_periods = int((cycle_length - MAX_CYCLE_DAYS) / MAX_CYCLE_DAYS) + 1
    print(f"⚠️ Long cycle: {cycle_length} days (likely {missed_periods} missed period(s))")
    # Still include it but mark for review
```

**Result**: Long cycles are detected and marked, but predictions continue.

### 4. Period End Date is NULL

**Problem**: User logs period start but not end date.

**Solution**:
```python
# In get_effective_period_end()
if log and log.get("end_date") and log.get("is_manual_end"):
    return log["end_date"]  # Use actual end date
else:
    # Use estimated period length
    estimated_length = calculate_rolling_period_length(user_id)
    estimated_days = int(round(max(3.0, min(8.0, estimated_length))))
    return start_date + timedelta(days=estimated_days - 1)
```

**Result**: System gracefully handles NULL `end_date` by using estimated period length.

### 5. Invalid Cycle Lengths

**Problem**: Calculated cycle length is <21 or >45 days.

**Solution**:
```python
# In calculate_phase_for_date_range()
actual_cycle_length = (next_cycle_start - current_cycle_start).days
if actual_cycle_length < 21 or actual_cycle_length > 45:
    # Use estimated length instead
    actual_cycle_length = float(cycle_length)
```

**Result**: Invalid cycle lengths are replaced with estimated length.

### 6. Wrong Cycle Assignment

**Problem**: Date is assigned to wrong cycle (e.g., day 30 of cycle when it should be day 1 of next cycle).

**Solution**:
```python
# Iterate BACKWARDS to find most recent cycle start
for i in range(len(cycle_starts) - 1, -1, -1):
    if cycle_starts[i] <= current_date:
        current_cycle_start = cycle_starts[i]  # Most recent <= current_date
        break
```

**Result**: Dates are always assigned to the correct cycle.

### 7. Empty Calendar (All Cycles Reset)

**Problem**: User resets all cycles, calendar should be blank.

**Solution**:
```javascript
// In PeriodCalendar.jsx
window.addEventListener('resetAllCycles', () => {
    clearCache()
    setPhaseMap({})  // Empty map = blank calendar
    setPeriodLogs([])
})
```

**Result**: Calendar shows no phases when all cycles are reset.

### 8. No Last Period Date

**Problem**: User hasn't logged any periods yet.

**Solution**:
```python
# In get_phase_map()
if not last_period_date:
    return {"phase_map": []}  # Empty calendar
```

**Result**: Calendar is blank until first period is logged.

### 9. Duplicate Cycle Starts

**Problem**: Same cycle start date appears twice in calculations.

**Solution**:
```python
# In calculate_phase_for_date_range()
# Normalize cycle starts: deduplicate, sort, validate spacing
cycle_starts = sorted(set(cycle_starts))  # Deduplicate by date
cycle_starts = [cs for cs in cycle_starts if is_valid_cycle_start(cs)]  # Validate spacing
```

**Result**: Duplicate cycle starts are removed before phase calculation.

### 10. Backend Processing Timeout

**Problem**: Heavy prediction calculations take >30s, causing frontend timeouts.

**Solution**:
```python
# Backend: Return 202 Accepted immediately
if prediction_in_progress or no_stored_data:
    return JSONResponse(
        status_code=202,
        content={"status": "processing", "phase_map": []}
    )

# Frontend: Handle 202 status, retry after 8s
if (response?.status === 'processing') {
    await new Promise(resolve => setTimeout(resolve, 8000))
    return getPhaseMap(startDate, endDate, forceRecalculate, 1)  // Retry once
}
```

**Result**: Frontend shows loading state, backend processes in background, no timeouts.

---

## Reset Functionality

### Reset All Cycles

**Endpoint**: `POST /user/reset-cycle-data`

**Process**:
1. Delete all `period_logs`
2. Delete all `period_start_logs`
3. Delete all `user_cycle_days` (phase predictions)
4. Reset `users.last_period_date` to `NULL`
5. Reset `users.cycle_length` to 28 (default)

**Frontend**:
```javascript
window.dispatchEvent(new CustomEvent('resetAllCycles'))
// Calendar shows blank (empty phaseMap)
```

### Reset Last Period

**Endpoint**: `POST /user/reset-last-period`

**Process**:
1. Get most recent period log
2. Determine period end date (use actual `end_date` if available, else estimated)
3. Delete that period log
4. Delete `user_cycle_days` entries for that period range
5. Update `last_period_date` to previous period (if any)
6. Sync `period_start_logs`
7. Update cycle stats
8. Regenerate predictions from new last period

**Frontend**:
```javascript
window.dispatchEvent(new CustomEvent('resetLastPeriod'))
// Calendar refreshes with updated predictions
```

---

## Caching System

### Backend Caching

**Database Table**: `user_cycle_days`
- Stores calculated phases for all dates
- Fast lookup: `SELECT * FROM user_cycle_days WHERE user_id = ? AND date = ?`
- Updated when:
  - Period is logged
  - Predictions are regenerated
  - Cycle data is reset

**Fast Path in API**:
```python
# In get_phase_map()
stored_data = supabase.table("user_cycle_days").select("*")
    .eq("user_id", user_id)
    .gte("date", start_date)
    .lte("date", end_date)
    .execute()

if stored_data and not force_recalculate:
    return {"phase_map": stored_data}  # FAST - no calculation
```

### Frontend Caching

**Session Storage**:
- Persists for browser session
- Keys:
  - `calendar_phase_map_cache`: Phase map data
  - `calendar_period_logs_cache`: Period logs
  - `wellness_data_cache`: Preloaded hormones/nutrition/exercise data
  - `calendar_last_load_time`: Timestamp of last load

**Cache Invalidation**:
```javascript
// Clear cache events
window.addEventListener('periodLogged', clearCache)
window.addEventListener('resetAllCycles', clearCache)
window.addEventListener('resetLastPeriod', clearCache)
window.addEventListener('calendarRefresh', clearCache)
```

**Cache Lifecycle**:
1. **Initial Load**: Check `sessionStorage`, load if exists
2. **Update**: When new data fetched, update cache
3. **Clear**: On period logged, reset, or manual refresh
4. **Preload**: Wellness data preloaded when calendar loads

---

## API Endpoints

### Phase Map

**Endpoint**: `GET /cycles/phase-map`

**Parameters**:
- `start_date`: Optional (YYYY-MM-DD)
- `end_date`: Optional (YYYY-MM-DD)
- `force_recalculate`: Optional (boolean)

**Response**:
```json
{
    "phase_map": [
        {
            "date": "2026-02-08",
            "phase": "Period",
            "phase_day_id": "p1",
            "fertility_prob": 0.0,
            "predicted_ovulation_date": "2026-02-17",
            "source": "local",
            "is_predicted": true
        }
    ]
}
```

**Fast Path**: Returns stored data from `user_cycle_days` if available
**Slow Path**: Returns `202 Accepted` if prediction is in progress, triggers background task if not started

### Current Phase

**Endpoint**: `GET /cycles/current-phase?date=YYYY-MM-DD`

**Response**:
```json
{
    "phase": "Period",
    "phase_day_id": "p1",
    "date": "2026-02-08",
    "is_actual": true  // true if date is in logged period
}
```

**Fast Path**: Looks up in `user_cycle_days` table
**Fallback**: Calculates single date if not in database

### Log Period Start

**Endpoint**: `POST /periods/log`

**Request**:
```json
{
    "date": "2026-02-08",  // Required: Period START date
    "end_date": "2026-02-15",  // Optional: Period END date
    "flow": "medium",      // Optional
    "notes": "..."         // Optional
}
```

**Response**: See [Period Logging Flow](#period-logging-flow)

**Note**: If `end_date` is not provided, system auto-assigns using `estimated_period_length`.

### Log Period End

**Endpoint**: `POST /periods/log-end`

**Request**:
```json
{
    "id": "log_id",  // Period log ID
    "date": "2026-02-15"  // Period END date
}
```

**Response**:
```json
{
    "message": "Period end logged successfully. Duration: 7 days.",
    "start_date": "2026-02-08",
    "end_date": "2026-02-15",
    "duration": 7
}
```

---

## Database Schema

### `period_logs` Table
```sql
- id: UUID (primary key)
- user_id: UUID (foreign key to users)
- date: DATE (period START date, REQUIRED - source of truth)
- end_date: DATE (nullable) - Period END date. If NULL, system uses estimated_period_length
- is_manual_end: BOOLEAN - True if user clicked "Period Ended", false if auto-assigned or auto-closed
- flow: TEXT (optional: light/medium/heavy)
- notes: TEXT (optional)
```

**Constraint**: `CHECK (end_date IS NULL OR end_date >= date)`

**Note**: When `end_date` is NULL, the system uses `estimated_period_length` to display period days. When `end_date` is set, the system uses the actual period range.

### `user_cycle_days` Table
```sql
- id: UUID (primary key)
- user_id: UUID (foreign key to users)
- date: DATE
- phase: TEXT (Period | Follicular | Ovulation | Luteal)
- phase_day_id: TEXT (p1-p12, f1-f40, o1-o8, l1-l25)
- fertility_prob: DECIMAL
- predicted_ovulation_date: DATE
- source: TEXT (local | external)
- is_actual: BOOLEAN (true if date is in logged period)
```

### `users` Table (Relevant Columns)
```sql
- id: UUID (primary key)
- last_period_date: DATE (most recent period start)
- cycle_length: INTEGER (estimated cycle length, default 28)
- luteal_mean: DECIMAL (adaptive estimate, default 14)
- luteal_sd: DECIMAL (standard deviation, default 2)
- luteal_observations: JSONB (array of observed luteal lengths)
```

### `period_start_logs` Table
```sql
- id: UUID (primary key)
- user_id: UUID (foreign key to users)
- start_date: DATE (period start date)
- confirmed: BOOLEAN (true if from period_logs)
- cycle_length: INTEGER (calculated from previous period)
- is_outlier: BOOLEAN - True if cycle length is outside Mean ± 2×SD (excluded from calculations)
```

**Note**: Cycles marked as `is_outlier = true` are excluded from Bayesian smoothing to keep predictions stable. This prevents one weird month (flu, stress, travel) from ruining predictions for the rest of the year.

---

## Performance Optimizations

### Backend
1. **Database Fast Path**: Returns stored phases if available (no calculation)
2. **Background Tasks**: Heavy calculations run asynchronously (non-blocking)
3. **202 Accepted Responses**: API returns immediately when prediction is in progress
4. **Prediction Guard**: Prevents duplicate background tasks for same user
5. **Cycle Normalization**: Deduplicates cycle starts before calculation
6. **Per-Cycle Caching**: Luteal anchoring calculated once per cycle, cached for reuse

### Frontend
1. **Session Cache**: Prevents unnecessary API calls
2. **Lazy Loading**: Only fetches 9 months initially, loads more on navigation
3. **Month Caching**: Tracks loaded months to prevent duplicate fetches
4. **Parallel Fetching**: Uses `Promise.all` for efficient batch loading
5. **Memoization**: O(1) lookups for phase info and logged dates
6. **Processing Status Handling**: Shows loading state, retries with backoff

---

## Recent Improvements (2026)

### 1. Ghost Cycle Problem Fix
**Problem**: When a user logs a period earlier than predicted, old predicted period days remained in the database, creating a "ghost cycle" visual bug.

**Solution**: Implemented **Hard Invalidation Boundary** (`hard_invalidate_predictions_from_date()`)
- When a period is logged on `Date_X`, the system executes `DELETE` for all rows in `user_cycle_days` where `date >= Date_X`
- This ensures no "ghost" predicted periods remain when actual data arrives
- Flo's approach: Any predicted state is "soft" and must be vaporized the moment "hard" data (a log) arrives

### 2. Luteal Anchoring (Per-Cycle Calculation)
**Problem**: Fixed 14-day luteal phase assumption caused inaccurate ovulation predictions. Luteal anchoring was running inside per-day loop, causing redundant calculations.

**Solution**: Implemented **Weighted Rolling Luteal Average** with per-cycle caching
- Uses adaptive `luteal_mean` from `estimate_luteal()` instead of fixed 14 days
- Formula: `Predicted Ovulation = Next Period Start - avg(Last 3 Luteal Phases)`
- **Per-Cycle Calculation**: Luteal anchoring runs ONCE per cycle, results cached in `cycle_metadata_cache`
- System learns from user's actual cycle patterns (e.g., if user consistently has 26-day cycles, luteal phase adjusts to 12 days)
- More accurate than industry-standard fixed 14-day assumption

### 3. Optional Period End Dates
**Problem**: System assumed period end dates always existed, causing errors when `end_date` was NULL.

**Solution**: Implemented **Optional End Date Support**
- Period START date is the source of truth (required)
- Period END date is optional (can be NULL)
- System gracefully handles NULL `end_date` by using `estimated_period_length`
- Function `get_effective_period_end()` prioritizes manual end_date, falls back to estimate
- All date range checks use NULL-safe logic: `IF end_date IS NOT NULL: start_date <= date <= end_date ELSE: start_date <= date < start_date + derived_period_length`

### 4. Cycle Start Normalization
**Problem**: Duplicate cycle start dates were being generated, causing incorrect phase assignments.

**Solution**: Implemented **Cycle Start Normalization**
- Collect all potential cycle starts (from logs, predictions, fallback)
- Deduplicate using date-only equality
- Sort ascending
- Validate minimum 21-day spacing
- Fallback cycle starts are marked as `source="fallback"`, never persisted

### 5. Background Prediction Tasks
**Problem**: Heavy prediction calculations blocked API responses, causing >30s timeouts and request storms.

**Solution**: Implemented **Non-Blocking Background Tasks**
- `/cycles/phase-map` returns `202 Accepted` immediately if prediction is in progress
- Heavy calculations run in `_generate_phase_map_background()` async function
- In-memory `_prediction_in_progress` guard prevents duplicate background tasks
- Frontend handles `202` status, shows loading state, retries with 8s backoff

### 6. Lazy Loading (9-Month Initial Load)
**Problem**: Calendar prefetched all months (1 year past to 2 years future), causing unnecessary API calls and slow initial load.

**Solution**: Implemented **Smart Lazy Loading**
- Initial load: 9 months (3 past + current + 5 future)
- Lazy load: Only fetches months when user navigates to them
- Month caching: Tracks loaded months to prevent duplicate fetches
- Parallel fetching: Uses `Promise.all` for efficient batch loading

### 7. Authentication Gates
**Problem**: Unauthenticated users (Register/Login screens) triggered protected API calls, causing 403 errors.

**Solution**: Implemented **Auth-Gated API Calls**
- `api.js`: Early failure check for protected endpoints if no auth token
- `dataLoader.js`: Auth token checks before loading dashboard/wellness data
- `DataContext.jsx`: Auth token checks in interval callbacks and event listeners
- Prevents cycle/period API calls from running on Register/Login routes

### 8. Logging Cleanup
**Problem**: Extremely verbose logs due to misplaced calculations (luteal anchoring in per-day loop).

**Solution**: Reduced logging verbosity
- Luteal anchoring logs ONCE per cycle (not per day)
- Per-day logs only under debug flag
- Cycle creation logs once per cycle
- Fallback usage logs once per fallback

### 9. Auto-Close Logic
**Problem**: Users forgot to log period end, leaving periods open indefinitely.

**Solution**: Implemented **Auto-Close for Forgotten Periods**
- Periods open > 10 days are automatically closed with estimated end_date
- Runs before logging new period start
- Prevents "runaway periods" from breaking cycle statistics

### 10. Outlier Detection (Sigma Filter)
**Problem**: One weird month (flu, stress, travel) could ruin predictions for the rest of the year.

**Solution**: Implemented **Outlier Detection with Mean ± 2×SD Filter**
- Cycles outside `Mean ± 2×SD` are marked as `is_outlier = true`
- Outlier cycles are excluded from Bayesian smoothing
- Keeps predictions stable despite occasional anomalies

---

## Conclusion

The Calendar Cycle System is a comprehensive, medically-accurate solution for menstrual cycle tracking. It handles all edge cases, maintains data integrity, and provides fast, responsive user experience through intelligent caching, lazy loading, and background processing.

**Key Strengths**:
- Medical accuracy (21-45 day cycles, proper phase sequencing)
- Edge case handling (missing periods, past logs, inconsistent logging, ghost cycles, outliers, NULL end dates)
- Performance (caching, lazy loading, fast database lookups, background tasks, 202 responses)
- User experience (instant updates, visual differentiation, blank calendar on reset, period start/end control)
- Adaptive learning (luteal anchoring, weighted rolling averages, outlier filtering)
- Data quality (outlier protection, auto-close logic, manual end date tracking)

**Recent Improvements**:
- ✅ Ghost cycle problem fixed (hard invalidation boundary)
- ✅ Luteal anchoring (adaptive, per-cycle calculation)
- ✅ Optional period end dates (NULL-safe handling)
- ✅ Cycle start normalization (deduplication, validation)
- ✅ Background prediction tasks (non-blocking, 202 responses)
- ✅ Lazy loading (9-month initial load, on-demand fetching)
- ✅ Authentication gates (prevent unauthenticated API calls)
- ✅ Logging cleanup (reduced verbosity)
- ✅ Auto-close logic (safety close for forgotten periods)
- ✅ Outlier detection (sigma filter)

**Future Enhancements**:
- Machine learning for cycle length prediction
- Integration with health devices (temperature, LH tests)
- Advanced anomaly detection
- Cycle pattern recognition
- Visual feedback (ghosting effect during reset)
- Optimistic UI updates (show changes before API response)
