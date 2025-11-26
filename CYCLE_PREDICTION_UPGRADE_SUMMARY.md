# Cycle Prediction Logic Upgrade - Summary

## Overview
The cycle prediction system has been significantly upgraded to use RapidAPI's `cycle_phases` endpoint as the primary data source, with improved fallback logic and adaptive prediction adjustments.

---

## ✅ Completed Upgrades

### 1. **New RapidAPI Endpoint Integration**
- **Added**: `get_cycle_phases(request_id)` function in `cycle_utils.py`
- **Endpoint**: `/get_data/{request_id}/cycle_phases`
- **Returns**: Complete day-by-day phase timeline with:
  - `date`: YYYY-MM-DD
  - `phase`: Phase name
  - `day_in_phase`: Day number within phase
- **Usage**: Primary source for phase mappings (replaces manual calculation)

### 2. **Updated Prediction Flow**
**File**: `backend/cycle_utils.py` → `generate_cycle_phase_map()`

**New Flow**:
1. Process past cycle data → get `request_id`
2. Get predicted cycle starts
3. Get average period/cycle lengths
4. **NEW**: Get complete `cycle_phases` timeline from RapidAPI
5. Use timeline directly (no manual phase distribution)
6. If API fails → fallback to improved manual calculation

**Key Changes**:
- Removed static phase length calculations when API succeeds
- Phase boundaries come directly from RapidAPI
- Added `update_future_only` parameter for partial updates

### 3. **Partial Update Logic**
**Feature**: Only update future dates, preserve past predictions

**Implementation**:
- `update_future_only=True` parameter in `generate_cycle_phase_map()`
- `store_cycle_phase_map()` deletes only dates >= current_date
- Preserves historical data when recalculating

**When Used**:
- Early/late period detection triggers partial update
- User logs period → only future dates recalculated

### 4. **Early/Late Period Detection**
**Function**: `detect_early_late_period(user_id, logged_period_date)`

**Logic**:
```python
difference = actual_start - predicted_start
if abs(difference) >= 2 days:
    should_adjust = True
    # Triggers partial update of future predictions
```

**Integration**:
- Called in `routes/periods.py` when period is logged
- If detected → triggers `update_future_only=True`
- Adjusts future predictions based on actual period date

### 5. **Improved Fallback Logic**
**File**: `backend/cycle_utils.py` → `calculate_phase_for_date_range()`

**New Defaults** (biologically accurate):
- `period_days = 5`
- `luteal_days = 14` (fixed)
- `ovulation_window = 6`
- `follicular_days = cycle_length - (period + luteal + ovulation)`

**Confidence Scores**:
- `source = "fallback"`
- `confidence = 0.5`

### 6. **Bayesian Cycle Length Update**
**Function**: `update_cycle_length_bayesian(user_id, new_cycle_length)`

**Formula**:
```python
updated_cycle_length = (old_cycle_length * 0.7) + (new_cycle_length * 0.3)
```

**When Used**:
- After RapidAPI calculates average cycle length
- When user logs a period (calculates from previous period)
- Smooths cycle length over time (70% old, 30% new)

### 7. **Confidence and Source Tracking**
**Database Fields** (optional):
- `source`: `"api"` | `"adjusted"` | `"fallback"`
- `confidence`: `1.0` (API) | `0.7` (adjusted) | `0.5` (fallback)

**Storage**:
- Stored in `user_cycle_days` table
- Graceful degradation if columns don't exist
- Not exposed to frontend (backward compatibility)

**Migration Script**: `database/add_confidence_source_columns.sql`

---

## 📊 Confidence Scores

| Source | Confidence | When Used |
|--------|-----------|-----------|
| `api` | 1.0 | RapidAPI `cycle_phases` endpoint succeeds |
| `adjusted` | 0.7 | RapidAPI predictions available but using manual phase distribution |
| `fallback` | 0.5 | RapidAPI unavailable, using `last_period_date` + `cycle_length` |

---

## 🔄 Updated Functions

### `generate_cycle_phase_map()`
**New Parameters**:
- `update_future_only: bool = False`

**Returns**:
- Added `source` and `confidence` fields to each mapping

**Behavior**:
1. Tries RapidAPI `cycle_phases` first (primary)
2. Falls back to improved manual calculation if API fails
3. Supports partial updates (future dates only)

### `store_cycle_phase_map()`
**New Parameters**:
- `update_future_only: bool = False`
- `current_date: Optional[str] = None`

**Behavior**:
- If `update_future_only=True`: Deletes only dates >= current_date
- If `update_future_only=False`: Deletes all, then inserts all (full update)
- Gracefully handles missing `source`/`confidence` columns

### `calculate_phase_for_date_range()`
**Improvements**:
- Uses biologically accurate defaults
- Returns `source="fallback"` and `confidence=0.5`
- Better phase distribution algorithm

### `update_cycle_length_bayesian()`
**New Function**:
- Smooths cycle length updates
- Formula: `(old * 0.7) + (new * 0.3)`
- Prevents sudden jumps in cycle length

### `detect_early_late_period()`
**New Function**:
- Compares logged period vs predicted period
- Returns difference and adjustment recommendation
- Triggers partial update if difference >= 2 days

---

## 🔧 Updated Routes

### `routes/periods.py` → `log_period()`
**New Features**:
1. Calculates new cycle length from previous period
2. Updates cycle length using Bayesian smoothing
3. Detects early/late periods
4. Triggers partial update if early/late detected

**Flow**:
```
User logs period
  ↓
Calculate cycle length (current - previous)
  ↓
Update cycle_length using Bayesian smoothing
  ↓
Detect early/late period
  ↓
If early/late: update_future_only=True
  ↓
Generate new predictions (partial or full)
```

### `routes/cycles.py` → `get_phase_map()`
**Improvements**:
- Uses improved `calculate_phase_for_date_range()` for fallback
- Returns formatted data (removes source/confidence for frontend compatibility)
- Better error handling

---

## 🗄️ Database Changes

### Optional Columns (Migration Required)
**File**: `database/add_confidence_source_columns.sql`

```sql
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT NULL;

ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT NULL;
```

**Note**: 
- Columns are optional
- Code works without them (graceful degradation)
- Existing records will have NULL values
- Run migration when ready to track confidence

---

## 🎯 Key Improvements

### Accuracy
1. **RapidAPI Primary**: Uses actual phase timeline from API
2. **No Static Phases**: Phase boundaries come from API data
3. **Adaptive**: Adjusts when user logs early/late periods
4. **Bayesian Smoothing**: Cycle length updates are smoothed

### Data Preservation
1. **Partial Updates**: Past predictions preserved
2. **Historical Data**: Only future dates updated on recalculation
3. **Graceful Degradation**: Works without optional columns

### Backward Compatibility
1. **Frontend Unchanged**: API response format unchanged
2. **Optional Fields**: `source`/`confidence` not exposed to frontend
3. **Existing Data**: Works with existing database records

---

## 📝 Usage Examples

### Full Prediction Update
```python
generate_cycle_phase_map(
    user_id=user_id,
    past_cycle_data=past_cycles,
    current_date="2025-11-16",
    update_future_only=False  # Full update
)
```

### Partial Update (Early/Late Period)
```python
# When user logs period 2 days early
generate_cycle_phase_map(
    user_id=user_id,
    past_cycle_data=past_cycles,
    current_date="2025-11-16",
    update_future_only=True  # Only update future dates
)
```

### Bayesian Cycle Length Update
```python
# After RapidAPI or period log
update_cycle_length_bayesian(user_id, new_cycle_length)
# Example: old=28, new=30 → updated=28.6
```

---

## 🚀 Next Steps

1. **Run Migration** (optional):
   ```sql
   -- Execute: database/add_confidence_source_columns.sql
   ```

2. **Test RapidAPI Integration**:
   - Verify `cycle_phases` endpoint works
   - Check phase timeline accuracy

3. **Monitor Logs**:
   - Watch for early/late period detections
   - Verify partial updates work correctly
   - Check Bayesian cycle length updates

---

## ⚠️ Important Notes

1. **Database Migration**: Optional but recommended for confidence tracking
2. **RapidAPI Key**: Required for primary prediction method
3. **Fallback**: System works without RapidAPI (uses improved calculation)
4. **Frontend**: No changes required (backward compatible)
5. **Existing Data**: Preserved during partial updates

---

## 📁 Files Modified

1. `backend/cycle_utils.py` - Core prediction logic
2. `backend/routes/periods.py` - Period logging with early/late detection
3. `backend/routes/cycles.py` - Phase map endpoint improvements
4. `database/add_confidence_source_columns.sql` - Optional migration

---

## ✅ All Requirements Met

- ✅ RapidAPI `cycle_phases` endpoint integrated
- ✅ Static phase lengths removed (when API succeeds)
- ✅ Phase boundaries from RapidAPI
- ✅ Improved fallback with accurate defaults
- ✅ Partial updates (future dates only)
- ✅ Early/late period detection
- ✅ Bayesian cycle length update
- ✅ Confidence scores added
- ✅ Source tracking added
- ✅ Frontend compatibility maintained
- ✅ No breaking changes

---

The system is now significantly more accurate and adaptive while maintaining full backward compatibility.





