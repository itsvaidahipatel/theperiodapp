# Cycle Statistics Analysis & Fixes

## Overview
This document explains how cycle statistics are calculated, displayed, and the fixes applied to ensure correct values.

## How Cycle Stats Work

### 1. Data Source: PeriodStartLogs
- **Core Truth**: A cycle is always anchored to a confirmed period start date
- Cycles are derived from `period_start_logs` table (never stored permanently)
- Cycle length = gap between consecutive period start dates
- Only confirmed period starts (past dates) are used for cycle calculations

### 2. Cycle Statistics Calculation

#### `compute_cycle_stats_from_period_starts(user_id)`
Calculates basic statistics from PeriodStartLogs:
- **Valid cycles**: 21-45 days (ACOG guidelines)
- **Outliers**: < 21 days (excluded from averages)
- **Irregular**: > 45 days (excluded from averages)
- Returns: mean, SD, variance, counts

#### `get_cycle_stats(user_id)`
Comprehensive statistics for frontend display:
- **Total Valid Cycles**: Number of cycles within 21-45 days used for statistics (not total historical cycles)
- **Average Cycle Length**: Rolling average from last 3 valid cycles (falls back to mean of all valid cycles if < 3, or profile default if none)
- **Average Period Length**: Calculated from period logs (consecutive dates)
- **Cycle Regularity**: Coefficient of Variation (CV)
  - CV < 8%: Very Regular
  - CV < 15%: Regular
  - CV < 25%: Somewhat Irregular
  - CV >= 25%: Irregular
- **Longest/Shortest Cycle**: Range of valid cycle lengths
- **Longest/Shortest Period**: Range of period lengths (from consecutive dates)
- **Last Period Date**: Most recent confirmed period start
- **Days Since Last Period**: Days since last confirmed period
- **Anomalies**: Count of cycles outside 21-45 day range
- **Confidence**: Prediction confidence level
- **Insights**: Personalized insights based on patterns
- **Cycle Lengths**: Last 6 cycle lengths for chart
- **All Cycles**: Complete cycle history with dates

### 3. Period Length Calculation

**Fixed**: Now properly calculates from period logs by grouping consecutive dates:
1. Get all period logs (dates where user logged period)
2. Group consecutive dates (gap <= 1 day) into periods
3. Calculate period length = (end_date - start_date) + 1
4. Use last 12 periods for statistics
5. Apply Bayesian smoothing for average

**Previous Issue**: Was just returning default (5 days) instead of calculating from logs.

### 4. Cycle Regularity (Coefficient of Variation)

Formula: `CV = (SD / Mean) × 100`

This is a standard medical measure of cycle variability:
- Lower CV = more regular cycles
- Higher CV = more irregular cycles

## Issues Fixed

### ✅ Issue 1: Documentation Mismatch
**Problem**: Docstring said "15-60 days" but code used 21-45 days (ACOG guidelines)
**Fix**: Updated all documentation to match actual implementation (21-45 days)

### ✅ Issue 2: Period Length Calculation
**Problem**: `calculate_rolling_period_length()` just returned default (5 days)
**Fix**: Now uses `estimate_period_length()` which calculates from period logs by grouping consecutive dates

### ✅ Issue 3: Period Length Range
**Problem**: Only showed average, not actual min/max range
**Fix**: Now calculates actual period lengths from consecutive dates and shows range

### ✅ Issue 4: Inconsistent Thresholds
**Problem**: Some places mentioned 15/60, others 21/45
**Fix**: Standardized to 21-45 days (ACOG guidelines) everywhere

## Frontend Display

### CycleStats Component (`frontend/src/components/CycleStats.jsx`)
Displays:
- Prediction confidence badge
- Average cycle length with range
- Average period length with range
- Cycle regularity status
- Last period date and days since
- Cycle length chart (last 6 cycles)
- Personalized insights
- Anomaly warnings

### API Endpoint
- **Route**: `GET /periods/stats`
- **Handler**: `get_cycle_stats(user_id)` in `cycle_stats.py`
- **Returns**: All statistics in camelCase format

## Data Flow

```
Period Logs (period_logs table)
    ↓
PeriodStartLogs (period_start_logs table) - synced incrementally
    ↓
get_cycles_from_period_starts() - derives cycles
    ↓
get_cycle_stats() - calculates comprehensive statistics
    ↓
Frontend Display (CycleStats.jsx)
```

## Key Functions

### Backend
1. **`get_cycles_from_period_starts(user_id)`** - Derives cycles from PeriodStartLogs
2. **`compute_cycle_stats_from_period_starts(user_id)`** - Basic statistics
3. **`get_cycle_stats(user_id)`** - Comprehensive statistics for frontend
4. **`calculate_rolling_average(user_id)`** - Rolling average of cycle length
5. **`calculate_rolling_period_length(user_id)`** - Rolling average of period length (now fixed)
6. **`update_user_cycle_stats(user_id)`** - Updates user's cycle_length in profile

### Frontend
1. **`getCycleStats()`** - API call to `/periods/stats`
2. **`CycleStats` component** - Displays all statistics

## Validation

### Cycle Length Validation
- **Valid**: 21-45 days (included in averages)
- **Outlier**: < 21 days (excluded, likely mistake)
- **Irregular**: > 45 days (excluded, gap/skipped month)

### Period Length Reference Range
- **Reference Range**: 3-8 days (medically normal, but not excluded if outside range)
- Calculated from consecutive dates in period_logs
- All period lengths are included in calculations (no exclusion based on range)

## Testing Checklist

- [x] Cycle statistics calculate correctly from PeriodStartLogs
- [x] Period length calculates from consecutive dates (not just default)
- [x] Cycle regularity uses coefficient of variation correctly
- [x] Outlier/irregular thresholds consistent (21-45 days)
- [x] Frontend displays all statistics correctly
- [x] Range calculations show min/max values
- [x] Confidence levels calculated correctly
- [x] Insights generated based on patterns

## Notes

- All cycles must be anchored to confirmed period start dates
- Everything else is a prediction
- Statistics only use confirmed period starts (past dates)
- Future period starts are marked as `is_confirmed=false` and excluded from calculations
- Cycle length = gap between consecutive period starts
- Period length = consecutive dates grouped together

## Edge Cases Handled

### Single Period Start (No Cycles Yet)
- **Requirement**: Need at least 2 period starts to calculate a cycle
- **Behavior**: 
  - `get_cycles_from_period_starts()` returns empty list if < 2 period starts
  - `compute_cycle_stats_from_period_starts()` returns defaults (mean=28, SD=2, count=0)
  - `get_cycle_stats()` shows "unknown" regularity, uses profile defaults for averages
  - Confidence reflects low data availability (Low confidence, 0-25%)
  - No division by zero errors (checked for n=0 before calculations)

### Insufficient Valid Cycles
- If all cycles are outliers/irregular (< 21 or > 45 days):
  - `cycle_count = 0`, returns defaults
  - No division by zero (explicit check for n=0)
  - Confidence reflects insufficient data

### Rolling Average Fallback
- If < 3 valid cycles: uses mean of all valid cycles
- If no valid cycles: uses profile `cycle_length` or default (28 days)
- If no profile data: uses default (28 days)
