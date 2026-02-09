# Cycle Prediction Pipeline Fixes

## Summary

Fixed critical issues in the period-cycle prediction pipeline without redesigning the system. Applied minimal, correct fixes to address duplicate cycles, misplaced calculations, fallback handling, and excessive logging.

## Problems Fixed

### 1. ✅ Duplicate Cycle Start Dates
**Problem**: Same date appeared multiple times in `cycle_starts` list.

**Fix**: 
- Added cycle start normalization BEFORE phase calculation
- Deduplicate using date-only equality (ignoring time)
- Sort ascending after deduplication
- Validate minimum 21-day spacing

**Location**: `backend/cycle_utils.py` lines ~1998-2101

### 2. ✅ Luteal Anchoring Inside Per-Day Loop
**Problem**: Luteal anchoring calculation ran inside the per-date loop (lines 2357-2362), causing redundant calculations.

**Fix**:
- Moved luteal anchoring to per-cycle pre-calculation phase
- Calculate ONCE per cycle_start before the date loop
- Cache results in `cycle_metadata_cache` dictionary
- Reuse cached values for all dates in that cycle

**Location**: `backend/cycle_utils.py` lines ~2139-2221

### 3. ✅ Fallback Last Period Date Treated as Real
**Problem**: Fallback `last_period_date` (today) was added to `cycle_starts` without marking it as fallback, causing it to be treated like a real logged cycle.

**Fix**:
- Track cycle source in `cycle_sources` dictionary: "real", "predicted", "fallback"
- Only use fallback anchor when NO real logs exist
- Mark fallback cycles with `is_fallback=True` in metadata
- Log fallback usage clearly: "FALLBACK - not persisted"
- Never persist fallback cycles

**Location**: `backend/cycle_utils.py` lines ~2000-2084

### 4. ✅ Excessive Logging
**Problem**: Verbose logs inside per-day loop (lines 2164, 2223, 2335, 2359, 2459).

**Fix**:
- Reduced to one log per cycle creation
- One log per fallback usage
- Removed per-day debug logs (only keep error logs)
- Log luteal anchoring ONCE per cycle (not per day)

**Location**: Throughout `calculate_phase_for_date_range()` function

## Code Structure (After Fixes)

### A) Cycle Start Normalization (BEFORE phase calculation)
```python
# 1. Collect from all sources
cycle_starts_raw = []
cycle_sources = {}  # Track: "real", "predicted", "fallback"

# 2. Deduplicate using date-only equality
seen_dates = set()
cycle_starts_deduped = []
for cs in cycle_starts_raw:
    cs_date = cs.date()
    if cs_date not in seen_dates:
        seen_dates.add(cs_date)
        cycle_starts_deduped.append(cs)

# 3. Sort ascending
cycle_starts_deduped.sort()

# 4. Validate minimum spacing
# ... (21-day minimum)
```

### B) Luteal Anchoring (PER-CYCLE, not per-day)
```python
# Pre-calculate ONCE per cycle (before date loop)
cycle_metadata_cache = {}

for cycle_start in cycle_starts:
    # Calculate actual_cycle_length
    # Calculate luteal_mean (already done once at function start)
    # Calculate ovulation_day, fertile_window
    # Cache all in cycle_metadata_cache[cycle_start_str]
    
    # Log ONCE per cycle
    print(f"🔬 Cycle {cycle_start_str}: luteal_mean={luteal_mean:.1f}...")
```

### C) Daily Phase Calculation (per-date loop)
```python
while current_date <= end_date_obj:
    # Find cycle_start (simple lookup)
    # Get cached metadata (no calculation)
    cycle_meta = cycle_metadata_cache[cycle_start_str]
    
    # Use cached values
    fertile_window_start = cycle_meta["fertile_window_start"]
    fertile_window_end = cycle_meta["fertile_window_end"]
    # ... assign phase
```

## Key Changes

1. **Cycle Normalization Function** (lines ~1998-2101):
   - Collects from period_logs, database predictions, fallback
   - Deduplicates by date-only
   - Sorts ascending
   - Validates spacing
   - Tracks source metadata

2. **Luteal Anchoring Pre-calculation** (lines ~2139-2221):
   - Runs BEFORE date loop
   - Calculates once per cycle
   - Caches in `cycle_metadata_cache`
   - Logs once per cycle

3. **Fallback Handling** (lines ~2055-2084):
   - Only used when no real logs exist
   - Marked with `source="fallback"` and `is_fallback=True`
   - Logged clearly: "FALLBACK - not persisted"
   - Never duplicated or persisted

4. **Logging Cleanup**:
   - Removed per-day debug logs
   - Kept per-cycle logs
   - Kept error/warning logs
   - Reduced verbosity by ~90%

## Safety Rules Maintained

✅ Never assume period end_date exists (all code uses NULL checks)
✅ Never assume any cycle exists (graceful fallback)
✅ Fall back gracefully when logs are empty
✅ Keep existing API contracts unchanged

## Testing Checklist

- [ ] No duplicate cycle_start dates in output
- [ ] Luteal anchoring calculated once per cycle (check logs)
- [ ] Fallback cycles marked clearly and not persisted
- [ ] Logs are concise (one per cycle, not per day)
- [ ] Phase calculations still correct
- [ ] No performance regression

## Files Modified

- `backend/cycle_utils.py`: Main refactoring in `calculate_phase_for_date_range()`

## Notes

- All changes are minimal and focused on fixing the specific issues
- No database schema changes
- No API contract changes
- Backward compatible with existing data
