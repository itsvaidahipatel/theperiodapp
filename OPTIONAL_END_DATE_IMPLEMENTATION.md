# Optional Period End Date Implementation

## Summary

This document describes the implementation of optional period end dates while maintaining the "start-date-first" philosophy. The system now supports:

- **Period START date**: REQUIRED (source of truth)
- **Period END date**: OPTIONAL (can be NULL)

## Database Schema Changes

### Migration: `database/add_period_end_date_constraint.sql`
- Added CHECK constraint: `end_date IS NULL OR end_date >= date`
- Ensures data integrity when end_date is provided

### Existing Migration: `database/add_period_end_date_and_outliers.sql`
- Already adds `end_date DATE DEFAULT NULL`
- Already adds `is_manual_end BOOLEAN DEFAULT FALSE`

## Code Changes

### 1. Pydantic Models (`backend/routes/periods.py`)

**PeriodLogRequest**:
```python
class PeriodLogRequest(BaseModel):
    date: str  # Period start date (REQUIRED - source of truth)
    end_date: Optional[str] = None  # Period end date (OPTIONAL)
    flow: Optional[str] = None
    notes: Optional[str] = None
```

**PeriodLogUpdate**:
```python
class PeriodLogUpdate(BaseModel):
    date: Optional[str] = None
    end_date: Optional[str] = None  # Can update or clear end_date
    flow: Optional[str] = None
    notes: Optional[str] = None
```

### 2. Registration Flow (`backend/routes/auth.py`)

**RegisterRequest**:
```python
class RegisterRequest(BaseModel):
    last_period_date: str  # Required - period start date
    last_period_end_date: Optional[str] = None  # Optional - period end date
    # ... other fields
```

**Registration Logic**:
- Validates `end_date >= start_date` if provided
- Auto-assigns end_date (5 days default) if not provided
- Creates `period_logs` entry with optional end_date

### 3. Period Logging (`backend/routes/periods.py`)

**log_period()**:
- Accepts optional `end_date` in request
- Validates `end_date >= start_date` if provided
- Auto-assigns end_date using estimated period length if not provided
- Never fails if end_date is NULL

### 4. Date Range Checks (Safe Pattern)

All code uses this safe pattern:

```python
# SAFETY: Use actual end_date if available, else estimate
if period_log.get("end_date"):
    # Use actual end date
    period_end = datetime.strptime(period_log["end_date"], "%Y-%m-%d").date()
else:
    # Use estimated period length (fallback)
    period_length = estimate_period_length(user_id, normalized=True)
    period_length_days = int(round(max(3.0, min(8.0, period_length))))
    period_end = period_start + timedelta(days=period_length_days - 1)
```

**Files using this pattern**:
- `backend/cycle_utils.py`: `is_date_in_logged_period()`, `calculate_phase_for_date_range()`
- `backend/routes/user.py`: `reset_last_period()`
- `backend/routes/periods.py`: `update_period_log()`

### 5. Reset Logic (`backend/routes/user.py`)

**reset_all_cycles()**:
- Deletes all `period_logs` (regardless of end_date)
- Clears predictions
- Falls back to registration `last_period_date` or today

**reset_last_period()**:
- Handles both `start_date only` and `start_date + end_date`
- Uses actual end_date if available, else estimates
- Safely deletes period range predictions

### 6. Update Logic (`backend/routes/periods.py`)

**update_period_log()**:
- Validates `end_date >= start_date` if updating end_date
- Handles clearing end_date (sets to NULL)
- Uses actual end_date for old period range deletion

## Safety Rules Implemented

✅ **Never throw hard errors if end_date is NULL**
- All code gracefully falls back to estimated period length

✅ **Never assume end_date exists**
- All queries use `.get("end_date")` with NULL checks

✅ **Always fall back gracefully**
- Uses `estimate_period_length()` when end_date is NULL

✅ **Keep logs informative but non-spammy**
- Logs when using actual vs estimated end_date

## Testing Checklist

- [ ] Log period with only start_date → end_date auto-assigned
- [ ] Log period with start_date + end_date → end_date saved
- [ ] Reset all cycles → all period_logs deleted, predictions cleared
- [ ] Reset last period (with end_date) → correct range deleted
- [ ] Reset last period (without end_date) → estimated range deleted
- [ ] Update period log end_date → validation works
- [ ] Clear period log end_date → sets to NULL
- [ ] Registration with end_date → validates correctly
- [ ] Registration without end_date → auto-assigns

## Migration Steps

1. Run `database/add_period_end_date_and_outliers.sql` (if not already run)
2. Run `database/add_period_end_date_constraint.sql` (new)
3. Deploy backend code changes
4. Test all reset and update flows

## Notes

- The system maintains backward compatibility: existing rows without end_date continue to work
- All predictions work correctly whether end_date is NULL or provided
- The CHECK constraint prevents invalid data at the database level
- Frontend can optionally show "Log Period End" button when end_date is NULL
