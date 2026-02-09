# Period Start/End and Outlier Detection - Implementation Summary

## Overview
This document summarizes the implementation of:
1. **Outlier/Anomaly Detection** - Standard deviation filter to prevent one weird month from ruining predictions
2. **Period Start and End Date Logging** - Users can log both period start and end dates
3. **Auto-Close Logic** - Automatically closes periods open > 10 days

---

## 1. Outlier/Anomaly Detection ✅

### Problem
If a user has a flu or high stress and their period is 15 days late, that one weird month shouldn't ruin predictions for the rest of the year.

### Solution
**Standard Deviation Filter** - Mark cycles as outliers if outside `Mean ± 2×SD`

**Location**: `backend/cycle_utils.py:1707-1750`

**Logic**:
```python
# Calculate statistics
cycle_mean = sum(cycle_lengths) / len(cycle_lengths)
cycle_sd = math.sqrt(variance)

# Outlier threshold: Mean ± 2×SD
outlier_threshold_low = cycle_mean - (2 * cycle_sd)
outlier_threshold_high = cycle_mean + (2 * cycle_sd)

# Filter out outliers
for cycle in cycles:
    is_outlier = cycle_length < outlier_threshold_low or cycle_length > outlier_threshold_high
    if is_outlier:
        # Mark as outlier in period_start_logs
        supabase.table("period_start_logs").update({"is_outlier": True})...
    else:
        # Include in Bayesian smoothing
        non_outlier_cycles.append(cycle_length)
```

**Impact**:
- Outlier cycles are marked with `is_outlier = true` in `period_start_logs` table
- Bayesian smoothing **ignores** cycles marked as outliers
- Keeps the "Rolling Average" stable even with occasional anomalies

**Database Schema**:
```sql
ALTER TABLE period_start_logs
ADD COLUMN is_outlier BOOLEAN DEFAULT FALSE;
```

---

## 2. Period Start and End Date Logging ✅

### Problem
Users want to log both when their period starts AND when it ends, not just the start date.

### Solution
**Interval-Based Period Logging** - Treat period as an interval (start_date, end_date) rather than a single event.

### Database Schema Update

**Migration**: `database/add_period_end_date_and_outliers.sql`

```sql
ALTER TABLE period_logs
ADD COLUMN end_date DATE DEFAULT NULL;

ALTER TABLE period_logs
ADD COLUMN is_manual_end BOOLEAN DEFAULT FALSE;
```

**Updated `period_logs` Table**:
- `date`: Period START date (primary trigger for cycle start)
- `end_date`: Period END date (nullable) - If NULL, system uses `estimated_period_length`
- `is_manual_end`: Boolean - Set to `true` once user clicks "Period Ended"

### Logic Flow

#### A. When "Period Started" is clicked:
1. **Create/Update Log**: Set `start_date = selected_date` and `end_date = NULL`
2. **AI Estimation**: Immediately set calendar phases using `estimated_period_length` (e.g., if average is 5 days, color days 1–5 as "Actual Period")
3. **UI State**: Change button from "Period Started" to "Period Ended"

**Endpoint**: `POST /periods/log`
- Accepts `date` (period start date)
- Sets `end_date = NULL`, `is_manual_end = false`

#### B. When "Period Ended" is clicked:
1. **Update Log**: Set `end_date = selected_date` and `is_manual_end = true`
2. **Recalculate Length**: `actual_duration = (end_date - start_date) + 1`
3. **Hard Invalidation**: Trigger `hard_invalidate_predictions_from_date(start_date)`
4. **Phase Update**: Update `user_cycle_days` table to reflect actual number of days bled

**Endpoint**: `POST /periods/log-end`
- Accepts `date` (period end date)
- Finds most recent period log without `end_date`
- Updates it with `end_date` and `is_manual_end = true`
- Recalculates phases with actual period range

**Example**: If AI predicted 5 days but user clicked "Ended" on day 7, calendar colors days 6 and 7 as "Actual Period" instead of "Follicular".

### Integration into `cycle_utils.py`

**New Function**: `get_period_range(user_id, cycle_start)`

```python
def get_period_range(user_id: str, cycle_start: str) -> tuple:
    """
    Get period range (start and end dates) for a cycle start date.
    
    Prioritizes manual end date if user clicked "Period Ended".
    Otherwise uses AI estimate (estimated_period_length).
    """
    log = get_log_for_start_date(user_id, cycle_start)
    
    if log.end_date:
        # User manually told us when it ended
        return log.start_date, log.end_date
    else:
        # User hasn't clicked "Ended" yet, use AI estimate
        estimated_len = estimate_period_length(user_id)
        return log.start_date, log.start_date + timedelta(days=estimated_len - 1)
```

**Updated**: `is_date_in_logged_period()` now uses actual end dates when available.

---

## 3. Auto-Close Logic ✅

### Problem
Users often forget to click "Period Ended." The app shouldn't think they've been bleeding for 30 days.

### Solution
**Safety Close** - Auto-fill `end_date` if period has been open > 10 days.

**Location**: `backend/auto_close_periods.py`

**Logic**:
```python
def auto_close_open_periods(user_id: str):
    """
    Threshold: If current_date > start_date + 10 days and end_date is still NULL:
    Action: Auto-fill end_date with start_date + estimated_period_length
    Reason: Prevents "runaway period" from breaking cycle statistics
    """
    open_periods = get_periods_without_end_date(user_id)
    
    for period in open_periods:
        days_open = (today - period.start_date).days
        if days_open > 10:
            # Auto-close with estimated period length
            estimated_len = estimate_period_length(user_id)
            auto_end_date = period.start_date + timedelta(days=estimated_len - 1)
            
            update_period_log(period.id, {
                "end_date": auto_end_date,
                "is_manual_end": False  # Auto-closed, not manually ended
            })
```

**Integration**: Called automatically when user logs a new period start to clean up any forgotten open periods.

---

## 4. Frontend Changes Needed

### Buttons
1. **"Log Period Start"** button - Calls `POST /periods/log`
2. **"Log Period End"** button - Calls `POST /periods/log-end` (only shown when there's an open period)

### UI State Management
- When period is logged with `end_date = NULL`: Show "Period Ended" button
- When period is logged with `end_date`: Hide "Period Ended" button (period is complete)
- Show visual indicator for periods that are auto-closed vs manually ended

### Calendar Display
- Use actual `end_date` when available (from `get_period_range()`)
- Fall back to `estimated_period_length` when `end_date` is NULL
- Color actual period days differently from predicted period days

---

## 5. Benefits

### Personalized Accuracy
- App learns exactly how long each period lasted
- Helps refine "Period Length Estimation" Bayesian average
- More accurate predictions over time

### User Control
- Users feel more in control when they can "close" their period
- Reduces anxiety about "forgetting" to log

### Clean Data
- By having a distinct `end_date`, we can distinguish between:
  - "I am still bleeding" (end_date = NULL)
  - "The AI thinks I am still bleeding" (end_date = estimated)
  - "I manually told you when it ended" (is_manual_end = true)

### Outlier Protection
- One weird month (flu, stress) doesn't ruin predictions
- Rolling average stays stable
- Better long-term accuracy

---

## 6. Testing Scenarios

### Test Case 1: Outlier Detection
1. Log 5 periods with 28-day cycles
2. Log 1 period with 45-day cycle (outlier)
3. **Expected**: 45-day cycle marked as `is_outlier = true`, not included in cycle length calculation

### Test Case 2: Period Start and End
1. Click "Log Period Start" for today
2. **Expected**: Calendar shows period days 1-5 (estimated)
3. Click "Log Period End" for 7 days later
4. **Expected**: Calendar updates to show period days 1-7 (actual)

### Test Case 3: Auto-Close
1. Log period start 15 days ago
2. Don't log period end
3. Log new period start today
4. **Expected**: Old period auto-closed with estimated end date

### Test Case 4: Manual vs Auto-Closed
1. Log period start
2. Wait 12 days (auto-close threshold)
3. **Expected**: Period auto-closed, `is_manual_end = false`
4. Log new period, end it manually
5. **Expected**: `is_manual_end = true`

---

## 7. Files Modified

### Backend
1. `backend/cycle_utils.py`
   - Added outlier detection logic in `predict_cycle_starts_from_period_logs()`
   - Added `get_period_range()` function
   - Updated `is_date_in_logged_period()` to use actual end dates

2. `backend/routes/periods.py`
   - Updated `log_period()` to set `end_date = NULL` initially
   - Added `POST /periods/log-end` endpoint
   - Added `PeriodEndRequest` model

3. `backend/auto_close_periods.py` (NEW)
   - Auto-close logic for periods open > 10 days

### Database
1. `database/add_period_end_date_and_outliers.sql` (NEW)
   - Migration to add `end_date`, `is_manual_end`, and `is_outlier` columns

---

## 8. Next Steps

1. ✅ Outlier Detection - **COMPLETED**
2. ✅ Period Start/End Logging - **COMPLETED**
3. ✅ Auto-Close Logic - **COMPLETED**
4. ⏳ Frontend Implementation - **PENDING**
   - Add "Log Period End" button
   - Update UI to show period state (open vs closed)
   - Integrate with calendar display

---

## Conclusion

All backend improvements have been implemented:
- ✅ Outlier detection prevents one weird month from ruining predictions
- ✅ Period start/end logging provides user control and accuracy
- ✅ Auto-close logic prevents runaway periods

Frontend integration is pending and can be implemented to complete the user experience.
