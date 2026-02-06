# Calendar View & Period Logging - Complete Documentation

## 🧠 Core Principle (The Key Insight)

**Periods are events. Bleeding days are a derived range.**

The system is designed around this fundamental principle:
- **User logs only ONE thing:** Period start date
- **System derives everything else:** Bleeding range, cycle length, phases
- **No daily prompts:** No "are you bleeding today?" spam
- **Late/wrong/duplicate logs don't break cycles:** System handles all edge cases gracefully

### What This Means

1. **User Action:** "I started my period today" (one date)
2. **System Creates:** Period episode with predicted bleeding range (5-7 days)
3. **Calendar Renders:** Bleeding days dynamically from start + predicted length
4. **System-Derived Storage:** Bleeding days (p1-p5) are SYSTEM-DERIVED PREDICTIONS stored in `user_cycle_days` for performance/statistics, NOT user-entered data

This is how real apps (like Flo) work. It's medically correct, low-friction, and handles edge cases naturally.

---

## Table of Contents
1. [Core Principle & Design](#core-principle--design)
2. [What User Logs](#what-user-logs)
3. [How System Derives Bleeding Range](#how-system-derives-bleeding-range)
4. [Calendar View Overview](#calendar-view-overview)
5. [Phase Calculation System](#phase-calculation-system)
6. [Period Logging Flow](#period-logging-flow)
7. [What Happens When User Logs a Period](#what-happens-when-user-logs-a-period)
8. [Edge Cases & Special Handling](#edge-cases--special-handling)
9. [Data Flow Diagrams](#data-flow-diagrams)
10. [Database Schema](#database-schema)
11. [API Endpoints](#api-endpoints)

---

## Core Principle & Design

### The Mental Model

```
User Logs: Period Start Date (one action)
    ↓
System Derives: Period Episode
    ├─→ start_date (user provided)
    ├─→ end_date (system predicted)
    └─→ bleeding_range (system-derived predictions, stored in user_cycle_days)
    ↓
Calendar Renders: Bleeding days dynamically
    for (date in calendar) {
        if (date >= start_date && date <= predicted_end_date) {
            showBleeding = true  // System-derived prediction, stored in user_cycle_days
        }
    }
```

### Key Design Decisions

1. **One Log = One Cycle Start**
   - Each period log represents a cycle start date
   - No end date required from user
   - No daily bleeding tracking

2. **Bleeding Days Are System-Derived Predictions**
   - NOT user-entered: User only logs period START date
   - System DERIVES bleeding days (p1-p5) from: `start_date + predicted_length`
   - Stored in `user_cycle_days` as SYSTEM-DERIVED PREDICTIONS (not user-entered data)
   - `user_cycle_days` is a deterministic, regeneratable prediction cache derived exclusively from `period_logs`
   - Used for calendar display, statistics, and queries

3. **Predict, Don't Ask**
   - System predicts bleeding length (5-7 days)
   - User doesn't need to confirm end date
   - Adapts over time based on cycle patterns

4. **Late Logging Support**
   - User can log past dates (retroactive)
   - System recalculates cycles and predictions
   - Never rejects logs

### Data Storage Model: User-Entered vs System-Derived

**Critical Distinction:**

| Data Type | Table | Source | Purpose | Regeneratable? |
|-----------|-------|--------|---------|----------------|
| Period Start Dates | `period_logs` | **USER-ENTERED** | Source of truth for cycle starts | No (user must log) |
| Bleeding Days (p1-p5) | `user_cycle_days` | **SYSTEM-DERIVED** | Predictions for calendar/statistics | Yes (from `period_logs`) |
| All Phase Predictions | `user_cycle_days` | **SYSTEM-DERIVED** | Predictions for calendar/statistics | Yes (from `period_logs`) |

**Mental Model:**
1. User logs ONLY period start date → `period_logs` (USER-ENTERED)
2. System calculates bleeding days (p1-p5) → `user_cycle_days` (SYSTEM-DERIVED PREDICTIONS)
3. System calculates all other phases → `user_cycle_days` (SYSTEM-DERIVED PREDICTIONS)
4. `user_cycle_days` is a **deterministic, regeneratable prediction cache derived exclusively from `period_logs`**

**Why Store Predictions?**
- Performance: Fast calendar queries without recalculation
- Statistics: Historical phase data for analytics
- Consistency: Same predictions across all views
- Cache: Can be invalidated and regenerated when new period is logged

---

## What User Logs

### User Action (Only ONE Thing)

**User clicks:** "I started my period today"

**That's it.** No end date. No range. No guessing.

### What Gets Stored

```python
# period_logs table (one row per cycle start)
{
    "user_id": "uuid",
    "date": "2026-01-15",  # Period start date (user provided)
    "flow": "medium",      # Optional: flow level
    "notes": "Normal"      # Optional: user notes
}
```

**Important:** This is a cycle start event, not a daily bleeding log.

### What Does NOT Get Stored

- ❌ Individual bleeding days (p2, p3, p4, p5)
- ❌ Period end date (derived, not stored)
- ❌ Daily bleeding status (system-derived predictions, stored in user_cycle_days)

---

## How System Derives Bleeding Range

### ⚠️ Critical: Avoiding Split-Brain Risk

**What is Split-Brain?**
When calculations and display use different period lengths, they can diverge:
- Calendar shows follicular starting on day 6 (if display is capped at 5 days)
- Backend calculates ovulation assuming period is 6-7 days (adaptive length)
- Result: Phase mismatches, fertility dots appearing at wrong times, confusing `phase_day_id` jumps

**Example of the Problem:**
```python
# ❌ WRONG: Split-brain approach
period_days_display = 5  # Fixed for calendar
period_days_calc = 7     # Different for calculations

# Calendar shows: p1-p5, then f1 starts on day 6
# But backend thinks: p1-p7, so f1 should start on day 8
# Result: Fertility dots appear 2 days too early!
```

**The Solution:**
Use adaptive length for ALL calculations, cap only the visual display.

**The Problem:** Using different period lengths for calculations vs display creates inconsistencies:
- Calendar shows follicular starting on day 6 (if period is 5 days)
- Backend calculates ovulation assuming period is 6-7 days
- Result: Phase mismatches, fertility dots appearing at wrong times, confusing `phase_day_id` jumps

**The Solution:** Use adaptive length internally for ALL calculations, cap visual display at 5 days.

```python
# RECOMMENDED APPROACH (prevents split-brain)
period_days_calc = estimate_period_length(user_id)  # Adaptive: 5-7 days (from user history)
period_days_display = min(period_days_calc, 5)      # Capped at 5 for visual consistency

# Use period_days_calc for:
# - Phase calculations (Period, Follicular, Ovulation, Luteal)
# - Ovulation date calculations
# - Fertility probability calculations
# - All backend math

# Use period_days_display for:
# - Calendar visual rendering only
# - Period episode end date display
```

**Benefits:**
- ✅ Math is consistent (one source of truth)
- ✅ UI is predictable (capped at 5 days)
- ✅ No conceptual split between calculation and display
- ✅ Ovulation/fertility calculations align with visual phases

### Implementation Pattern

**Backend Phase Calculations:**
```python
# All calculations use adaptive length
period_days = estimate_period_length(user_id)  # 5-7 days based on history

# Calculate phases using adaptive length
for day in range(1, period_days + 1):
    phase = "Period"
    phase_day_id = f"p{day}"  # p1, p2, ..., p5, p6, or p7 (adaptive)
    # Store in user_cycle_days with full adaptive range
```

**Calendar Display:**
```python
# Display capped at 5 days for visual consistency
period_days_display = min(period_days, 5)  # Cap at 5

# Calendar shows p1-p5, but backend knows actual period length
# This ensures:
# - Ovulation calculations use correct period length
# - Fertility dots appear at correct times
# - Phase transitions align with calculations
```

**Period Episodes Endpoint:**
```python
# backend/routes/periods.py - get_period_episodes()
period_days_calc = estimate_period_length(user_id)  # Adaptive: 5-7 days
period_days_display = min(period_days_calc, 5)      # Capped at 5 for display

predicted_end_date = start_date + timedelta(days=period_days_display - 1)
# Visual end date is capped, but calculations use full adaptive length
```

### Example Calculation

**Scenario:**
- User logs: Start = March 10
- User's historical average: 6 days

**System Calculates:**
```python
start_date = "2026-03-10"
period_days_calc = estimate_period_length(user_id)  # Adaptive: 6 days (from history)
period_days_display = min(period_days_calc, 5)      # Capped at 5 for display

# Backend stores ALL 6 days in user_cycle_days:
# Mar 10: p1, Mar 11: p2, Mar 12: p3, Mar 13: p4, Mar 14: p5, Mar 15: p6

# Calendar displays only first 5 days:
predicted_end_display = start_date + 4 days = "2026-03-14"  # 5 days (inclusive)
```

**Calendar Shows (Visual):**
```
🩸 Mar 10 (p1) - Mar 14 (p5)
```

**Backend Stores (Full Adaptive Range):**
- Mar 10: `p1` (Period, day 1)
- Mar 11: `p2` (Period, day 2)
- Mar 12: `p3` (Period, day 3)
- Mar 13: `p4` (Period, day 4)
- Mar 14: `p5` (Period, day 5)
- Mar 15: `p6` (Period, day 6) ← Stored but not shown in calendar
- Mar 16: `f1` (Follicular, day 1) ← Calculated using correct period length

**Key Point:** 
- All calculations (ovulation, fertility, phases) use the full adaptive length (6 days)
- Calendar display is capped at 5 days for visual consistency
- This prevents split-brain: math and display stay aligned

**All system-derived predictions - stored in `user_cycle_days` table as regeneratable cache!**

### What If Period Ends Earlier/Later?

#### Case A: Next Period Starts Early

**User logs:**
- March 10: Period start
- April 5: Next period start (early)

**System Behavior:**
```python
# Retroactively updates previous cycle
previous_cycle_end = April 5 - 1 day = April 4
actual_bleeding_length = (April 4 - March 10).days + 1 = 26 days

# But wait - this is cycle length, not bleeding length!
# Bleeding length is still predicted (5-7 days)
# Cycle length = 26 days (recalculated)
```

**No user interaction needed.** System adapts automatically.

#### Case B: Period Lasted Longer Than Predicted

**Two Options (Flo-style):**

**Option 1: Passive Correction (Recommended)**
```python
# Next cycle start recalculates averages
# Bleeding length slowly adapts over time
# No user prompt needed
```

**Option 2: Optional Soft Prompt (NOT Daily)**
```python
# After predicted end date:
if today > predicted_end_date and today <= predicted_end_date + 2:
    show_soft_prompt = True
    message = "Your period usually ends around today. Want to adjust?"
    
# User can ignore → system still works
# If user confirms → update bleeding length for future predictions
```

---

## Calendar View Overview

### Frontend Components

#### 1. **Period Calendar Component** (`frontend/src/components/PeriodCalendar.jsx`)

The main calendar component using `react-calendar` library with custom styling and phase visualization.

**Key Features:**
- **Today's Phase Display**: Shows current phase in header (e.g., "Today's Phase: Follicular (f12)")
- **Instant Loading**: Loads 7 months instantly (3 past + current + 3 future)
- **Background Prefetching**: Automatically loads remaining months, cycle stats, and cycle history in parallel
- **Performance Optimized**: Uses Map/Set for O(1) lookups, memoization for fast rendering
- **Pastel Color Scheme**: Soft, theme-consistent colors for all phases

**Layout Structure:**
```
┌─────────────────────────────────┐
│ Cycle Calendar                   │
│ Today's Phase: Follicular (f12) │ ← New: Today's phase display
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Calendar Component              │
│ (7 months loaded instantly)     │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Selected Date & Log Button      │ ← Moved above legend
│ (Only shows when date selected) │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Phase Legend                    │
│ (Reference guide)               │
└─────────────────────────────────┘
```

**Visual Elements:**
- **Period Phase**: Pastel pink (`#F8BBD9`) for actual, lighter (`#FCE4EC`) for predicted
- **Follicular Phase**: Pastel yellow/cream (`#FEF3C7`) for actual, lighter (`#FFF9E6`) for predicted
- **Ovulation Phase**: Pastel teal/cyan (`#B8E6E6`) for actual, lighter (`#E0F7FA`) for predicted
- **Luteal Phase**: Pastel lavender (`#E1BEE7`) for actual, lighter (`#F3E5F5`) for predicted
- **Logged Periods**: Vibrant pink (`#E91E63`) with stronger border and shadow
- **Fertile Days**: Small cyan dot indicator when `fertility_prob >= 0.3`

**Data Fetching Strategy:**
```javascript
// Initial Load: 7 months instantly
const fetchPhaseMap = async (isInitial = true) => {
  if (isInitial) {
    // Load 3 months past + current + 3 months future (7 months)
    const threeMonthsPast = subMonths(today, 3)
    const threeMonthsFuture = addMonths(today, 3)
    startDate = format(startOfMonth(threeMonthsPast), 'yyyy-MM-dd')
    endDate = format(endOfMonth(threeMonthsFuture), 'yyyy-MM-dd')
  }
  // Fetch with dynamic timeout (45s for large ranges, 30s for small)
  const response = await getPhaseMap(startDate, endDate)
}

// Background Prefetching: Parallel loading
useEffect(() => {
  // After initial load, prefetch in parallel:
  Promise.all([
    prefetchMonths(),      // Remaining months (1 year past to 2 years future)
    prefetchCycleStats(),  // Cycle statistics
    prefetchCycleHistory() // Cycle history data
  ])
}, [loading])
```

**Performance Optimizations:**
- **O(1) Lookups**: Uses `Map` for phase data, `Set` for logged dates
- **Memoization**: `useMemo` for phase info map and logged dates set
- **Batch Prefetching**: Loads months in batches of 5 with 200ms delays
- **Proactive Prefetching**: Prefetches adjacent months when user navigates
- **Timeout Handling**: Dynamic timeouts (45s for initial load, 30s for navigation)

#### 2. **Calendar Component** (`frontend/src/components/Calendar.jsx`)

A simpler calendar component used in other pages, displaying phase information with color-coded tiles.

---

## Phase Calculation System

### Backend Phase Calculation (`backend/cycle_utils.py`)

#### Core Function: `calculate_phase_for_date_range()`

This is the main function that calculates phases for a date range.

**Input Parameters:**
- `user_id`: User identifier
- `last_period_date`: Last known period start date (YYYY-MM-DD)
- `cycle_length`: Estimated cycle length (days)
- `start_date`: Start of date range to calculate
- `end_date`: End of date range to calculate

**Calculation Steps:**

1. **Get User Data:**
   - Fetch `last_period_date` and `cycle_length` from `users` table
   - Get adaptive estimates: `luteal_mean`, `luteal_sd`, `cycle_start_sd`

2. **Predict Cycle Starts:**
   ```python
   cycle_starts = predict_cycle_starts_from_period_logs(
       user_id, start_date, end_date, max_cycles=12
   )
   ```
   - Uses actual period logs to predict future cycle starts
   - Uses Bayesian smoothing for cycle length estimation
   - Accounts for cycle length variance

3. **For Each Cycle:**
   - **Calculate Ovulation Date:**
     ```python
     ov_date_str, ovulation_sd, _ = predict_ovulation(
         cycle_start_date,
         cycle_length,
         luteal_mean,
         luteal_sd,
         cycle_start_sd,
         user_id
     )
     ```
   - **Select Ovulation Days:**
     ```python
     ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
     # Returns list of day offsets: [-2, -1, 0] or [-1, 0, 1] etc.
     ```
   - **Calculate Fertility Probability:**
     ```python
     fertility_prob = fertility_probability(
         offset_from_ov,
         ovulation_sd,
         sperm_survival_days=5
     )
     ```

4. **Assign Phase to Each Day:**
   - **Period Phase (p1-pN):** First N days of cycle, where N = `estimate_period_length(user_id)` (adaptive: 5-7 days)
     - All calculations use full adaptive length
     - Calendar display capped at 5 days for visual consistency
     - Prevents split-brain: math and display stay aligned
     ```python
     # Predict bleeding length using hierarchy
     period_days = estimate_period_length(user_id)
     # Priority 1: User's historical average (last 6 cycles)
     # Priority 2: Default 5 days (if no history)
     # Priority 3: Cap at 7 days (safety limit)
     
     # Generate SYSTEM-DERIVED bleeding day predictions (p1-p5)
     for day in range(1, period_days + 1):
         phase = "Period"
         phase_day_id = f"p{day}"  # p1, p2, p3, p4, p5
         # These are SYSTEM-DERIVED PREDICTIONS - calculated from start_date + predicted_length
         # Stored in user_cycle_days as regeneratable prediction cache
     ```
   - **Follicular Phase (f1-fN):** Days after period, before ovulation
   - **Ovulation Phase (o1-o3):** Days in ovulation window (1-3 days)
   - **Luteal Phase (l1-l14):** Days after ovulation

5. **Store Predictions in Database:**
   - All phase mappings stored in `user_cycle_days` table as SYSTEM-DERIVED PREDICTIONS
   - **Period phase rows (p1-p5) are SYSTEM-DERIVED PREDICTIONS** - calculated from period start date + predicted length
   - Each row contains: `date`, `phase`, `phase_day_id`, `fertility_prob`, `prediction_confidence`, `ovulation_offset`, `is_predicted`
   - **Key Distinction:**
     - `period_logs` = USER-ENTERED data (period start dates only)
     - `user_cycle_days` = SYSTEM-DERIVED predictions (all phases, including bleeding days)
     - `user_cycle_days` is a deterministic, regeneratable prediction cache derived exclusively from `period_logs`
     - Bleeding days (p1-p5) are NOT user-entered, but ARE stored as predictions for querying/statistics

### Phase Day ID Format

- **Period:** `p1`, `p2`, `p3`, ..., `pN` where N = `estimate_period_length(user_id)` (adaptive: 5-7 days)
  - Backend stores full adaptive range (p1-pN)
  - Calendar display capped at p1-p5 for visual consistency
  - All calculations (ovulation, fertility) use full adaptive length
- **Follicular:** `f1`, `f2`, `f3`, ... `fN` (days before ovulation)
- **Ovulation:** `o1`, `o2`, `o3` (1-3 day window)
- **Luteal:** `l1`, `l2`, `l3`, ... `l14` (days after ovulation)

### Fertility Probability Calculation

```python
def fertility_probability(offset_from_ov: int, ovulation_sd: float, sperm_survival_days: int = 5) -> float:
    """
    Calculate fertility probability based on:
    - Distance from ovulation (offset_from_ov)
    - Sperm survival decay curve
    - Normalization to peak at day -1 or -2
    """
    # Sperm survival: exponential decay
    p_sperm = exp(offset_from_ov / 2.0) if offset_from_ov <= 0 else 0
    
    # Ovulation probability: normal distribution
    p_ovulation = exp(-0.5 * (offset_from_ov / ovulation_sd) ** 2)
    
    # Combined fertility probability
    fertility = p_sperm * p_ovulation
    
    # Normalize so day -1 or -2 peaks
    # (empirical scaling factor 1.65)
    return min(1.0, fertility * 1.65)
```

**Key Points:**
- Fertility window: 5-6 days before ovulation
- Peak fertility: Day -1 or -2 before ovulation
- Sperm survival: Exponential decay (not binary)
- Ovulation uncertainty: Normal distribution with `ovulation_sd`

---

## Period Logging Flow

### Frontend: Period Log Modal (`frontend/src/components/PeriodLogModal.jsx`)

**User Actions:**
1. User clicks on a calendar date
2. Modal opens with date picker
3. User selects date (can be past or present, **NOT future**)
4. User optionally adds flow level and notes
5. User clicks "Log Period" button

**Validation:**
- **Frontend Validation**: Prevents logging future dates
- **Backend Validation**: Double-checks and rejects future dates
- **Error Message**: "Cannot log period for future dates. Please log periods that have already occurred."

**API Call:**
```javascript
const response = await logPeriod({
  date: selectedDate, // YYYY-MM-DD format
  flow: flowLevel,   // Optional: 'light', 'medium', 'heavy'
  notes: notes       // Optional: user notes
})
```

### Backend: Period Logging Endpoint (`backend/routes/periods.py`)

**Endpoint:** `POST /periods/log`

**Request Body:**
```json
{
  "date": "2026-01-15",
  "flow": "medium",
  "notes": "Normal flow"
}
```

**Response:**
```json
{
  "message": "Period logged successfully",
  "log": {
    "id": "uuid",
    "user_id": "uuid",
    "date": "2026-01-15",
    "flow": "medium",
    "notes": "Normal flow"
  },
  "user": {
    "id": "uuid",
    "last_period_date": "2026-01-15",
    ...
  }
}
```

---

## What Happens When User Logs a Period

### Step-by-Step Flow

#### **Step 1: Save Period Start Log (Cycle Start Event)**
```python
# backend/routes/periods.py - log_period()
log_entry = {
    "user_id": user_id,
    "date": log_data.date,  # Period START date (not daily bleeding)
    "flow": log_data.flow,   # Optional: flow level
    "notes": log_data.notes  # Optional: user notes
}

# Upsert: Update if exists, insert if new
if existing.data:
    response = supabase.table("period_logs").update(log_entry)...
else:
    response = supabase.table("period_logs").insert(log_entry)...
```

**Database Table:** `period_logs`
- **Stores:** Period START dates only (cycle start events)
- **NOT stored:** Individual bleeding days (p2, p3, p4, p5)
- **One row per cycle start** (one log = one cycle start)
- `UNIQUE(user_id, date)` constraint prevents duplicate starts on same date

**Key Point:** This is a cycle start event, not a daily bleeding log. Bleeding days are derived later.

#### **Step 2: Rebuild PeriodStartLogs**
```python
from period_start_logs import sync_period_start_logs_from_period_logs
sync_period_start_logs_from_period_logs(user_id)
```

**What This Does:**
1. Fetches all `period_logs` for the user
2. Extracts unique dates (one log = one cycle start)
3. Determines `is_confirmed`:
   - `True` if date <= today (past dates)
   - `False` if date > today (future dates)
4. **Current Approach:** Deletes all existing `period_start_logs` for user, then inserts new ones
5. Inserts new `period_start_logs` with updated data

**⚠️ Current Limitations (Future Improvement Opportunity):**

The current delete-all-then-insert approach works but has some drawbacks:
- **Loses `created_at` history**: Original timestamps are lost when records are deleted
- **Harder to audit**: Can't track when a period start was first logged vs when it was updated
- **Unnecessary writes**: Rewrites all records even if only one new period was logged
- **Potential race conditions**: Brief window where no period_start_logs exist

**🔧 Recommended Future Improvement (Not Required Now):**

Use incremental upsert instead of delete-all:

```python
# FUTURE IMPROVEMENT: Incremental upsert
def sync_period_start_logs_from_period_logs(user_id: str) -> None:
    # Get current period_start_logs
    existing = get_period_start_logs(user_id, confirmed_only=False)
    existing_dates = {log["start_date"] for log in existing}
    
    # Get all period_logs
    period_logs = get_period_logs(user_id)
    log_dates = {log["date"] for log in period_logs}
    
    # Find new/changed dates
    new_dates = log_dates - existing_dates
    removed_dates = existing_dates - log_dates
    
    # Upsert new/changed (preserves created_at for existing)
    for date in new_dates:
        upsert_period_start_log(user_id, date, is_confirmed=(date <= today))
    
    # Delete removed (only if period_log was deleted)
    for date in removed_dates:
        delete_period_start_log(user_id, date)
    
    # Update is_confirmed status for dates that changed from future to past
    for date in log_dates & existing_dates:
        update_is_confirmed_if_needed(user_id, date)
```

**Benefits of Incremental Approach:**
- ✅ Preserves `created_at` timestamps
- ✅ Better audit trail
- ✅ Fewer database writes
- ✅ No race condition window
- ✅ More efficient for large datasets

**Note:** Current delete-all approach is functionally correct and acceptable for now. This improvement is a future optimization, not a bug fix.

**Database Table:** `period_start_logs`
- Stores cycle start dates only (no end dates, no duration)
- `is_confirmed`: Whether the period has actually occurred
- Used as anchor points for cycle calculations

**Key Principle:** One log = one cycle start

#### **Step 3: Recompute Cycle Statistics**
```python
from cycle_stats import update_user_cycle_stats
update_user_cycle_stats(user_id)
```

**What This Does:**
1. Derives cycles from `period_start_logs`:
   - Cycle length = gap between consecutive period starts
   - Only uses confirmed period starts
2. Filters valid cycles:
   - Valid: 15-60 days
   - Outliers: < 15 days (excluded from averages)
   - Irregular: > 60 days (excluded from averages)
3. Calculates statistics:
   - Mean cycle length
   - Standard deviation
   - Variance
4. Updates `users.cycle_length` using Bayesian smoothing:
   ```python
   update_cycle_length_bayesian(user_id, mean_cycle_length)
   ```

**Database Table:** `users`
- `cycle_length`: Updated with new mean (Bayesian smoothed)
- Used for future predictions

#### **Step 4: Invalidate Predictions**
```python
from prediction_cache import invalidate_predictions_after_period
invalidate_predictions_after_period(user_id, period_start_date=None)
```

**What This Does:**
1. Gets last confirmed period start date
2. Deletes all predictions in `user_cycle_days` table where:
   - `date >= last_confirmed_period_start`
   - This ensures we regenerate everything from the last confirmed period

**Why:** When a new period is logged, all future predictions become stale and must be recalculated.

**Database Table:** `user_cycle_days`
- Cache of phase predictions
- Can be fully regenerated
- Deleted rows: All dates >= last confirmed period start

#### **Step 5: Regenerate Predictions (Including System-Derived Bleeding Days)**
```python
from prediction_cache import regenerate_predictions_from_last_confirmed_period
regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=90)
```

**What This Does:**
1. Gets last confirmed period start
2. Calculates date range:
   - Start: Last confirmed period start
   - End: Today + 90 days
3. Calls `calculate_phase_for_date_range()`:
   - **Predicts bleeding length** using `estimate_period_length()`:
     - Priority 1: User's historical average (last 6 cycles)
     - Priority 2: Default 5 days (if no history)
     - Priority 3: Cap at 7 days (safety limit)
   - **Generates system-derived bleeding day predictions** using adaptive length:
     ```python
     # CRITICAL: Use adaptive length for ALL calculations
     period_days_calc = estimate_period_length(user_id)  # Adaptive: 5-7 days (e.g., 6 days)
     
     # Store ALL days in user_cycle_days (full adaptive range)
     for day in range(1, period_days_calc + 1):
         phase = "Period"
         phase_day_id = f"p{day}"  # p1, p2, p3, p4, p5, p6 (or p7 if adaptive length is 7)
         # These are SYSTEM-DERIVED PREDICTIONS - calculated from start + adaptive length
         # Stored in user_cycle_days as regeneratable prediction cache
     
     # Calendar display capped at 5 days (visual only, doesn't affect calculations)
     period_days_display = min(period_days_calc, 5)  # Cap at 5 for visual consistency
     ```
     
   - **Key Point:** All phase calculations (ovulation, fertility, phase transitions) use the full adaptive length. Calendar display is capped at 5 days for visual consistency only. This prevents split-brain issues where calculations and display diverge.
   - Calculates ovulation dates
   - Calculates fertility probabilities
   - Assigns phases (Period, Follicular, Ovulation, Luteal)
4. Stores in `user_cycle_days` table:
   ```python
   store_cycle_phase_map(user_id, phase_mappings, update_future_only=False)
   ```

**Database Table:** `user_cycle_days`
- New rows inserted for all dates in range as SYSTEM-DERIVED PREDICTIONS
- **Period phase rows (p1-p5) are SYSTEM-DERIVED PREDICTIONS** - calculated from period start date + predicted length
- Each row contains: `date`, `phase`, `phase_day_id`, `fertility_prob`, `prediction_confidence`, `ovulation_offset`, `is_predicted`
- **Key Distinction:**
  - NOT user-entered: User never directly logs p2, p3, p4, p5
  - IS stored: System stores these as predictions for performance/statistics
  - Source of truth: `period_logs` (user-entered start dates)
  - Derived data: `user_cycle_days` (system-calculated predictions)
  - `user_cycle_days` is a deterministic, regeneratable prediction cache derived exclusively from `period_logs`

#### **Step 6: Asynchronous Luteal Learning** (Non-blocking)
```python
from luteal_learning import learn_luteal_from_new_period
learn_luteal_from_new_period(user_id, log_data.date)
```

**What This Does:**
1. Checks if we have 2+ confirmed period starts
2. Computes observed luteal length:
   - Previous period start → Predicted ovulation → New period start
   - Observed luteal = (New period start - Predicted ovulation) days
3. Validates:
   - Observed luteal must be 10-18 days (valid range)
   - Ovulation prediction must be high confidence (`ovulation_sd <= 1.5`)
4. If valid, updates luteal estimate:
   ```python
   update_luteal_estimate(user_id, observed_luteal, has_markers=False)
   ```

**Why Non-blocking:** Luteal learning is a background process that doesn't affect user experience. Errors are logged but don't fail the period logging.

**Database Table:** `users`
- `luteal_mean`: Updated with new observed luteal length (Bayesian smoothed)
- `luteal_sd`: Updated based on variance

#### **Step 7: Update User's Last Period Date**
```python
supabase.table("users").update({
    "last_period_date": log_data.date
}).eq("id", user_id).execute()
```

**Database Table:** `users`
- `last_period_date`: Updated to the logged date
- Used for quick reference and fallback calculations

---

## Data Flow Diagrams

### Period Logging Flow

```
User Action (Frontend)
    ↓
POST /periods/log
    ↓
[Step 1] Save to period_logs table
    ↓
[Step 2] sync_period_start_logs_from_period_logs()
    ├─→ Delete all existing period_start_logs (current approach)
    └─→ Insert new period_start_logs (one per cycle start)
    ⚠️ Note: Future improvement could use incremental upsert to preserve timestamps
    ↓
[Step 3] update_user_cycle_stats()
    ├─→ get_cycles_from_period_starts() (derive cycles)
    ├─→ Calculate mean, SD, variance
    └─→ Update users.cycle_length (Bayesian)
    ↓
[Step 4] invalidate_predictions_after_period()
    └─→ DELETE from user_cycle_days WHERE date >= last_confirmed_period
    ↓
[Step 5] regenerate_predictions_from_last_confirmed_period()
    ├─→ calculate_phase_for_date_range()
    │   ├─→ predict_cycle_starts_from_period_logs()
    │   ├─→ predict_ovulation() for each cycle
    │   ├─→ select_ovulation_days()
    │   ├─→ fertility_probability() for each day
    │   └─→ Assign phases (Period, Follicular, Ovulation, Luteal)
    └─→ store_cycle_phase_map() → INSERT into user_cycle_days
    ↓
[Step 6] learn_luteal_from_new_period() (async, non-blocking)
    ├─→ compute_observed_luteal_from_confirmed_cycles()
    └─→ update_luteal_estimate() → Update users.luteal_mean, luteal_sd
    ↓
[Step 7] Update users.last_period_date
    ↓
Response to Frontend
    ↓
Frontend refreshes calendar data
```

### Calendar Rendering Flow

```
Dashboard Component Mounts
    ↓
useEffect() → fetchPhaseMapForMonth()
    ├─→ For each visible month:
    │   ├─→ GET /cycles/phase-map?start_date=...&end_date=...
    │   └─→ Store in calendarPhaseMap state
    ↓
Calendar Component Renders
    ├─→ tileContent() called for each date
    │   ├─→ Lookup phaseData from calendarPhaseMap[dateStr]
    │   │   └─→ phaseData contains SYSTEM-DERIVED bleeding day predictions (p1-p5)
    │   │       └─→ Calculated from: start_date + predicted_length
    │   │       └─→ Stored in user_cycle_days as regeneratable prediction cache
    │   ├─→ Render phase_day_id (p1, f5, o2, l10)
    │   ├─→ Apply phase color (red, teal, yellow, purple)
    │   └─→ Show fertile indicator if fertility_prob >= 0.3
    └─→ User clicks date → Opens PeriodLogModal
```

**Key Point:** Calendar renders bleeding days from system-derived predictions stored in `user_cycle_days`. Bleeding days (p1-p5) are SYSTEM-DERIVED PREDICTIONS - calculated from period start + predicted length, stored for performance/statistics, and fully regeneratable from `period_logs`.

### Phase Calculation Flow

```
calculate_phase_for_date_range(user_id, last_period_date, cycle_length, start_date, end_date)
    ↓
Get user data (luteal_mean, luteal_sd, cycle_start_sd)
    ↓
predict_cycle_starts_from_period_logs()
    ├─→ Get period_logs from database (cycle START dates only)
    ├─→ Group consecutive dates into period starts
    ├─→ Calculate cycle lengths
    └─→ Predict future cycle starts using Bayesian smoothing
    ↓
For each cycle:
    ├─→ estimate_period_length(user_id)  # Predict bleeding length
    │   ├─→ Priority 1: User's historical average (last 6 cycles)
    │   ├─→ Priority 2: Default 5 days (if no history)
    │   └─→ Priority 3: Cap at 7 days (safety limit)
    ├─→ predict_ovulation(cycle_start, cycle_length, luteal_mean, luteal_sd)
    │   └─→ Returns: (ovulation_date, ovulation_sd, confidence)
    ├─→ select_ovulation_days(ovulation_sd, max_days=3)
    │   └─→ Returns: [-2, -1, 0] or [-1, 0, 1] etc.
    └─→ For each day in cycle:
        ├─→ Calculate offset_from_ov = (day_date - ovulation_date).days
        ├─→ fertility_probability(offset_from_ov, ovulation_sd)
        └─→ Assign phase:
            ├─→ Day 1 to period_days: Period (p1-p5)  # SYSTEM-DERIVED PREDICTIONS
            ├─→ Day in ovulation_days: Ovulation (o1-o3)
            ├─→ Day < ovulation: Follicular (f1-fN)
            └─→ Day > ovulation: Luteal (l1-l14)
    ↓
Return list of phase mappings (including SYSTEM-DERIVED bleeding day predictions)
    ↓
store_cycle_phase_map() → INSERT/UPDATE user_cycle_days
    └─→ Period phase rows (p1-p5) are SYSTEM-DERIVED PREDICTIONS
        └─→ Stored in user_cycle_days as regeneratable prediction cache
```

---

## Database Schema

### `period_logs` Table
```sql
CREATE TABLE period_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    date DATE NOT NULL,  -- Period START date (cycle start event)
    flow TEXT,  -- Optional: 'light', 'medium', 'heavy'
    notes TEXT,  -- Optional: user notes
    UNIQUE(user_id, date)
);
```

**Purpose:** Stores period START dates only (cycle start events).

**Key Points:**
- **NOT stored:** Individual bleeding days (p2, p3, p4, p5)
- **One row per cycle start** (one log = one cycle start)
- Bleeding days are derived later from start date + predicted length

### `period_start_logs` Table
```sql
CREATE TABLE period_start_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    start_date DATE NOT NULL,
    is_confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, start_date)
);
```

**Purpose:** Stores cycle start dates (one per cycle). Derived from `period_logs`.

### `user_cycle_days` Table
```sql
CREATE TABLE user_cycle_days (
    user_id UUID REFERENCES users(id),
    date DATE NOT NULL,
    phase TEXT,  -- 'Period', 'Follicular', 'Ovulation', 'Luteal'
    phase_day_id TEXT,  -- 'p1', 'f5', 'o2', 'l10'
    fertility_prob FLOAT,
    prediction_confidence FLOAT,
    ovulation_offset INTEGER,
    is_predicted BOOLEAN,
    PRIMARY KEY (user_id, date)
);
```

**Purpose:** Cache of SYSTEM-DERIVED phase predictions (including bleeding day predictions p1-p5). `user_cycle_days` is a deterministic, regeneratable prediction cache derived exclusively from `period_logs`.

**Key Points:**
- **Period phase rows (p1-p5) are SYSTEM-DERIVED PREDICTIONS** - calculated from period start date + predicted length
- **Stored as predictions** - they're phase predictions stored for performance/statistics
- Bleeding days are calculated from: `start_date + estimate_period_length(user_id)` (adaptive: 5-7 days)
- Calendar display capped at 5 days for visual consistency (doesn't affect calculations)
- Calendar renders these system-derived predictions from `user_cycle_days` table
- Fully regeneratable: Can be deleted and rebuilt from `period_logs` at any time

### `users` Table (Relevant Columns)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    last_period_date DATE,
    cycle_length FLOAT,  -- Mean cycle length (Bayesian smoothed)
    luteal_mean FLOAT,   -- Mean luteal length (Bayesian smoothed)
    luteal_sd FLOAT,     -- Standard deviation of luteal length
    ...
);
```

**Purpose:** Stores user's cycle statistics and adaptive estimates.

---

## API Endpoints

### `GET /cycles/phase-map`
**Purpose:** Get phase mappings for a date range.

**Query Parameters:**
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `force_recalculate` (optional): Force regeneration

**Response:**
```json
{
  "phase_map": [
    {
      "date": "2026-01-15",
      "phase": "Period",
      "phase_day_id": "p1"
    },
    {
      "date": "2026-01-16",
      "phase": "Period",
      "phase_day_id": "p2"
    },
    ...
  ]
}
```

**Flow:**
1. Check if data exists in `user_cycle_days` table
2. If exists and not `force_recalculate`, return stored data
3. If not exists or `force_recalculate`, call `calculate_phase_for_date_range()`
4. Store results in `user_cycle_days`
5. Return phase mappings

### `POST /periods/log`
**Purpose:** Log a period entry.

**Request Body:**
```json
{
  "date": "2026-01-15",
  "flow": "medium",
  "notes": "Normal flow"
}
```

**Validation:**
- **Future Dates**: Rejected with error "Cannot log period for future dates"
- **Minimum Spacing**: Enforced to prevent overlapping periods
- **Date Format**: Must be YYYY-MM-DD format

**Response:**
```json
{
  "message": "Period logged successfully",
  "log": { ... },
  "user": { ... }
}
```

**Flow:** See [What Happens When User Logs a Period](#what-happens-when-user-logs-a-period)

### `GET /periods/episodes`
**Purpose:** Get period episodes (start dates + predicted end dates) for calendar rendering.

**Response:**
```json
[
  {
    "start_date": "2026-01-15",
    "predicted_end_date": "2026-01-19",
    "predicted_length": 5,
    "is_confirmed": true
  }
]
```

**Key Points:**
- **Display Length**: Capped at 5 days for calendar visual consistency
- **Calculation Length**: Uses adaptive `estimate_period_length(user_id)` (5-7 days) for all phase calculations
- **Predicted End**: Display end calculated as `start_date + min(period_days_calc, 5) - 1`
- **Confirmed Status**: `true` for past dates, `false` for future dates
- **Prevents Split-Brain**: All calculations use adaptive length, display is capped for UI consistency

---

## Key Design Principles

### 1. **One Log = One Cycle Start**
- Each period log represents a cycle start date
- No tracking of period end dates or duration
- Medically valid (doctors track LMP - Last Menstrual Period)

### 2. **Derived Cycles**
- Cycles are never stored permanently
- Calculated on-the-fly from `period_start_logs`
- Cycle length = gap between consecutive period starts

### 3. **Prediction Cache**
- `user_cycle_days` is treated as a cache
- Can be fully regenerated at any time
- Invalidated when new period is logged
- Regenerated from last confirmed period

### 4. **Adaptive Learning**
- Cycle length: Updated using Bayesian smoothing
- Luteal length: Updated from confirmed cycles only
- High-confidence requirements: Only learn from reliable predictions

### 5. **Late Logging Support**
- Users can log past dates (retroactive)
- System recalculates cycles and predictions
- Past cycles can change when new data is added

### 6. **Future Logging Support**
- Users can log future dates (predictions)
- Marked as `is_confirmed=false` in `period_start_logs`
- Not used for cycle calculations until confirmed

---

## Edge Cases & Special Handling

### 1. **Two Periods Logged in One Month**

**Scenario:** User logs period starts on Jan 3 and Jan 29

**System Behavior:**
```python
# Totally normal - month boundaries are irrelevant
cycle_length = Jan 29 - Jan 3 = 26 days

# System doesn't care about months
# Only cares about cycle-to-cycle distance
```

**Key Point:** Month boundaries mean nothing. Only cycle-to-cycle distance matters.

### 2. **Late Logging (User Logs Days Later)**

**Scenario:** Today is March 8, user logs "I started on March 5"

**System Behavior:**
```python
# Accepts it - never rejects logs
log_date = "2026-03-05"  # Past date

# Backfills predicted bleeding range
predicted_end = log_date + predicted_length
# Calendar shows: Mar 5 (p1) - Mar 9 (p5)

# Recalculates cycle start anchor
# Updates all future predictions
```

**Key Point:** System accepts late logs and recalculates everything. Never rejects.

### 3. **Accidental / Fake Log**

**Scenario:** User logs by mistake or tests the app

**System Behavior:**

**Option A: Allow Undo/Delete**
```python
# User can delete log
DELETE FROM period_logs WHERE id = log_id

# System reverts to previous cycle
# Recalculates predictions
```

**Option B: Treat Logs Within 24h as Editable**
```python
if (now - log.created_at) < 24 hours:
    allow_edit = True
    # User can modify or delete
```

**Option C: Flag Outliers**
```python
# If cycle length < 15 days or > 60 days
# Mark as outlier, exclude from averages
# But still store it
```

### 4. **User Logs Twice by Mistake (Same Day)**

**Scenario:** User logs period start twice on the same date

**System Behavior:**
```python
# Prevented by UNIQUE(user_id, date) constraint
# Latest log overwrites previous
# No duplicate cycles created
```

### 5. **Very Short Cycles (< 15 days)**

**Scenario:** User logs period starts 10 days apart

**System Behavior:**
```python
cycle_length = 10 days  # < 15 days

# Marked as outlier
is_outlier = True
should_exclude_from_average = True

# Still stored but flagged
# Excluded from cycle length averages
# Reason: "Very short cycle (< 15 days) - likely mistake or fake log"
```

**Key Point:** System stores it but doesn't use it for predictions.

### 6. **Very Long Cycles (> 60 days)**

**Scenario:** User logs period starts 90 days apart

**System Behavior:**
```python
cycle_length = 90 days  # > 60 days

# Marked as irregular
is_irregular = True
should_exclude_from_average = True

# Still stored but flagged
# Excluded from cycle length averages
# Reason: "Very long cycle (> 60 days) - irregular, gap, or skipped month"
```

**Key Point:** May indicate gaps, skipped months, or medical issues. System flags it.

### 7. **No Period Logs**

**Scenario:** New user, no period history

**System Behavior:**
```python
# Uses fallback values
last_period_date = users.last_period_date  # From registration
cycle_length = 28  # Default
bleeding_length = 5  # Default

# Generates predictions using defaults
# Adapts as user logs more periods
```

### 8. **Low-Confidence Ovulation Predictions**

**Scenario:** Ovulation prediction has high uncertainty

**System Behavior:**
```python
if ovulation_sd > 1.5:
    # Low confidence - skip luteal learning
    skip_luteal_learning = True
    # Prevents training on unreliable data
```

### 9. **Invalid Luteal Observations**

**Scenario:** Observed luteal length outside valid range

**System Behavior:**
```python
if observed_luteal < 10 or observed_luteal > 18:
    # Invalid - skip learning
    skip_luteal_update = True
    # Prevents training on stress cycles or anovulatory cycles
```

### 10. **Period Ends Earlier Than Predicted**

**Scenario:** System predicted 6 days, but next period starts early (only 4 days later)

**System Behavior:**
```python
# Next period start recalculates cycle
actual_cycle_length = next_start - previous_start

# Bleeding length adapts passively
# No user interaction needed
# System learns over time
```

### 11. **Period Lasts Longer Than Predicted**

**Scenario:** System predicted 5 days, but period actually lasted 8 days

**System Behavior:**

**Option A: Passive Correction (Default)**
```python
# Next cycle start recalculates averages
# Bleeding length slowly adapts over time
# No user prompt needed
```

**Option B: Optional Soft Prompt**
```python
# After predicted end date + 2 days
if today > predicted_end_date + 2:
    show_soft_prompt = True
    message = "Your period usually ends around today. Want to adjust?"
    
# User can ignore → system still works
# If user confirms → update bleeding length for future
```

### 12. **Gaps (Skipped Months)**

**Scenario:** User logs Jan 5, then May 20 (135 days gap)

**System Behavior:**
```python
cycle_length = 135 days  # > 60 days

# Marked as irregular
is_irregular = True
excluded_from_average = True

# Still stored
# System continues with other cycles
# Predictions use remaining valid cycles
```

**Key Point:** System handles gaps gracefully. Doesn't break predictions.

---

## Recent UI/UX Improvements (v3.2)

### 1. Today's Phase Display
- **Location**: Calendar header, below title
- **Format**: "Today's Phase: [Phase Name] ([phase_day_id])"
- **Example**: "Today's Phase: Follicular (f12)"
- **Updates**: Automatically refreshes when period is logged
- **Purpose**: Provides immediate visibility of current cycle phase

### 2. Improved Layout Structure
- **Selected Date & Log Button**: Moved above phase legend for better visibility
- **Visual Hierarchy**: 
  1. Calendar (main focus)
  2. Selected date/log button (action area)
  3. Phase legend (reference)
- **User Experience**: More intuitive flow, actions are more prominent

### 3. Performance Optimizations
- **Instant Loading**: 7 months load immediately on first visit
- **Parallel Background Tasks**: Months, cycle stats, and cycle history load simultaneously
- **O(1) Lookups**: Map/Set data structures for fast phase and logged date lookups
- **Memoization**: `useMemo` prevents unnecessary recalculations
- **Batch Prefetching**: Remaining months loaded in batches of 5
- **Proactive Prefetching**: Adjacent months prefetched when user navigates

### 4. Enhanced Error Handling
- **Future Date Validation**: Both frontend and backend prevent logging future dates
- **Timeout Handling**: Dynamic timeouts based on date range size
- **Graceful Degradation**: Calendar remains functional even if one request fails
- **User-Friendly Messages**: Clear error messages without technical jargon

### 5. Visual Improvements
- **Pastel Color Scheme**: Soft, theme-consistent colors for all phases
- **Distinct Visual Styles**: 
  - Logged dates: Vibrant colors with stronger borders and shadows
  - Predicted dates: Muted colors with dashed borders
- **Better Contrast**: Improved readability with proper color choices
- **Compact Design**: Reduced calendar tile sizes for better space utilization

### 6. Background Loading Strategy
```javascript
// After initial 7-month load completes:
Promise.all([
  prefetchMonths(),      // 1 year past to 2 years future
  prefetchCycleStats(),  // Cycle statistics
  prefetchCycleHistory() // Cycle history data
])
// All three tasks run in parallel for maximum efficiency
```

---

## Performance Considerations

### 1. **Caching Strategy**
- Phase mappings cached in `user_cycle_days` table
- Reduces recalculation on every calendar view
- Cache invalidated only when new period is logged

### 2. **PeriodStartLogs Rebuilding**
- **Current Approach:** Delete-all-then-insert (works correctly)
- **Limitations:**
  - Loses `created_at` history on rebuild
  - Unnecessary writes (rewrites all records even if only one changed)
  - Brief race condition window during deletion
- **Future Improvement:** Incremental upsert would preserve timestamps and reduce writes
  - Not required now, but worth noting for future optimization
  - See [Step 2: Rebuild PeriodStartLogs](#step-2-rebuild-periodstartlogs) for details

### 2. **Date Range Limiting & Loading Strategy**
- **Initial Load**: 7 months instantly (3 past + current + 3 future)
- **Background Prefetching**: Remaining months loaded in parallel batches
- **Backend Limits**: 1 year ahead maximum for future predictions
- **Dynamic Timeouts**: 45s for large ranges (initial load), 30s for navigation
- **Parallel Loading**: Months, cycle stats, and cycle history load simultaneously

### 3. **Asynchronous Processing**
- Luteal learning is non-blocking
- Doesn't delay period logging response
- Errors logged but don't fail the request

### 4. **Upsert Pattern**
- Uses `INSERT ... ON CONFLICT UPDATE` for `user_cycle_days`
- Prevents race conditions
- Atomic updates

---

## Medical Accuracy & Safety

### 1. **Ovulation Window**
- 1-3 day uncertainty window (not a single day)
- Based on `ovulation_sd` (standard deviation)
- Labeled as "Estimated Ovulation" in UI

### 2. **Fertility Window**
- 5-6 days before ovulation
- Peak fertility: Day -1 or -2
- Sperm survival decay curve (not binary)

### 3. **Luteal Phase**
- Valid range: 10-18 days
- Clamped to prevent invalid values
- Only learned from high-confidence predictions

### 4. **Confidence Gating**
- Low-confidence predictions suppressed in UI
- `prediction_confidence` stored for each day
- Used to determine data quality

### 5. **Medical Disclaimers**
- UI includes safety disclaimers
- Not for contraception or diagnosis
- Encourages consulting healthcare providers

---

## Version History

- **v1.0** (Initial): Basic period logging and calendar display
- **v2.0** (RapidAPI Removal): Transitioned to local adaptive algorithms
- **v3.0** (Simplified Design): One log = one cycle start model
- **v3.1**: Enhanced calendar visualization with fertile indicators
- **v3.2** (Current): 
  - Adaptive period length for calculations (5-7 days), capped at 5 days for calendar display
  - Prevents split-brain: all calculations use adaptive length, display is capped for UI consistency
  - Today's phase display in calendar header
  - Improved layout (selected date/log button above legend)
  - Parallel background loading (months, stats, history)
  - Performance optimizations (O(1) lookups, memoization)
  - Future date validation (frontend + backend)
  - Dynamic timeout handling
  - Pastel color scheme for better UX

---

## Related Documentation

- `COMPLETE_SYSTEM_DOCUMENTATION.md` - Overall system architecture
- `SIMPLIFIED_DESIGN.md` - Design principles and rationale
- `CYCLE_CALCULATION_FLOW.md` - Detailed cycle calculation logic
- `RAPIDAPI_REMOVAL_SUMMARY.md` - Transition to local algorithms

---

## Questions & Troubleshooting

### Q: Why does the calendar show "Insufficient Data"?
**A:** The calendar requires at least one period log to display phases. Log at least one period to see predictions.

### Q: Why do phases change after logging a period?
**A:** When a new period is logged, all future predictions are invalidated and regenerated based on the updated cycle statistics.

### Q: Can I log past periods?
**A:** Yes! The system supports retroactive logging. Past cycles will be recalculated when you add new data.

### Q: Why are some cycles marked as "outlier" or "irregular"?
**A:** Cycles < 15 days are outliers (likely mistakes). Cycles > 60 days are irregular (gaps/skipped months). Both are excluded from averages but still stored.

### Q: How accurate are ovulation predictions?
**A:** Predictions use adaptive algorithms based on your cycle history. Accuracy improves with more logged periods. The system shows a 1-3 day uncertainty window.

---

---

## Summary: Why This Design Works

### The Core Insight

**Periods are events. Bleeding days are a derived range.**

This principle makes the system:
- ✅ **Medically correct:** Aligns with clinical definitions (doctors track LMP - Last Menstrual Period)
- ✅ **Low friction:** User logs one thing (start date), system handles the rest
- ✅ **Resilient:** Late/wrong/duplicate logs don't break cycles
- ✅ **Adaptive:** System learns from patterns over time
- ✅ **Clean:** No daily "are you bleeding?" spam

### What Makes It Work

1. **One Log = One Cycle Start**
   - Each period log = cycle start event
   - No end date required
   - No daily tracking needed

2. **System-Derived Bleeding Days**
   - Bleeding days (p1-p5) are **SYSTEM-DERIVED PREDICTIONS**, stored in `user_cycle_days`
   - Calculated from: `start_date + predicted_length`
   - Rendered dynamically in calendar
   - Adapts based on user history

3. **Prediction Hierarchy**
   - Priority 1: User's historical average
   - Priority 2: Default 5 days
   - Priority 3: Safety cap at 7 days

4. **Edge Case Handling**
   - Late logs: Accepted and recalculated
   - Duplicates: Prevented by unique constraint
   - Outliers: Flagged but stored
   - Gaps: Handled gracefully

5. **Passive Adaptation**
   - System learns from cycle patterns
   - No user prompts needed
   - Bleeding length adapts over time

### Comparison to Other Approaches

| Aspect | This System | Daily Logging | Range Logging |
|--------|-------------|--------------|--------------|
| User friction | Low (1 action) | High (daily prompts) | Medium (2 dates) |
| Medical validity | High (LMP tracking) | High | Medium |
| Edge case handling | Excellent | Good | Poor |
| Cognitive load | Minimal | High | Medium |
| Adaptability | High | Low | Medium |

### Why Your "1 Day Logging" Rule is Perfect

You accidentally chose the best UX decision:

✅ **Zero cognitive load** - User doesn't need to think about end dates  
✅ **No medical guessing** - System predicts based on data  
✅ **Works for irregular cycles** - Adapts to patterns  
✅ **Aligns with clinical definitions** - Doctors ask "when did your period start?"  
✅ **Even Flo only requires start day** - Industry standard  

Everything else is inference.

---

**Last Updated:** 2026-01-25
**Document Version:** 3.2 (Updated to reflect recent UI/UX improvements, performance optimizations, and fixed 5-day period display)
