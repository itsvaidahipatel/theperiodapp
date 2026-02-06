# Period Length Architecture

## 🔑 Recommended Architecture

The system uses a **dual-value approach** for period length:

### Raw Estimate (Actual Pattern)
- **Purpose**: Stats, insights, medical flags
- **Value**: `raw_estimate = bayesian_average(...)` (no clamping)
- **Shows**: Your true pattern, even if outside 3-8 days
- **Used for**: Statistics, insights, detecting patterns outside typical range

### Normalized Estimate (Medically Typical Range)
- **Purpose**: Phase calculations and predictions
- **Value**: `normalized_estimate = clamp(raw_estimate, 3.0, 8.0)`
- **Shows**: Clamped to medically typical range (3-8 days)
- **Used for**: Phase calculations, ovulation predictions, fertility calculations

## How It Works

### 1. Adaptive Calculation (`estimate_period_length()`)

The system calculates period length from **your actual logged periods**:

```python
1. Gets your period_logs (dates where you logged period)
2. Groups consecutive dates into periods
3. Calculates period length = (end_date - start_date) + 1
4. Uses last 12 periods for statistics
5. Applies Bayesian smoothing to adapt to your pattern
6. Returns raw estimate (actual pattern, may be outside 3-8 days)
```

### 2. Dual Values

**Raw Estimate** (for stats & insights):
- No clamping - shows your actual pattern
- Can be < 3 days or > 8 days
- Used in statistics, insights, medical flags
- Detected and reflected in insights if outside typical range

**Normalized Estimate** (for phase calculations):
- Clamped to 3.0 - 8.0 days (medically typical range)
- Used for phase calculations, predictions
- Ensures medically safe calculations

### 3. Reference Range: 3-8 Days

- **Typical Range**: 3.0 - 8.0 days (medically normal)
- **Default/Prior**: 5.0 days (used if you haven't logged enough periods yet)
- **Outside Range**: Still detected and shown in stats/insights

### 3. Bayesian Smoothing

The system uses **Bayesian smoothing** to adapt to your pattern:

- **With few periods logged**: Uses more of the default (5.0 days)
- **With more periods logged**: Trusts your actual data more
- **Formula**: `weight = n / (n + 5)` where n = number of periods
  - 1 period: 17% your data, 83% default
  - 5 periods: 50% your data, 50% default
  - 10 periods: 67% your data, 33% default
  - 20+ periods: ~80% your data, 20% default

## Why You Might See 3 Days

If you're seeing 3 days, it could be:

1. **You actually have 3-day periods** (normal!)
   - System calculated from your logged periods
   - If you consistently log 3-day periods, it will adapt to 3 days

2. **You haven't logged enough periods yet**
   - System is still using default (5.0) but something might be clamping it
   - **Solution**: Log more periods - it will adapt as you log more

3. **Period grouping issue**
   - If periods aren't being grouped correctly, it might calculate wrong
   - **Check**: Make sure you log consecutive days of your period

## How to Ensure It Adapts Correctly

### ✅ Log Periods Correctly

1. **Log each day of your period** (consecutive dates)
   - Example: If period is Jan 1-5, log: Jan 1, Jan 2, Jan 3, Jan 4, Jan 5

2. **Log consistently** (at least 3-5 periods for good adaptation)

3. **The system will automatically**:
   - Group consecutive dates into periods
   - Calculate period length from your data
   - Adapt over time as you log more periods

### Example Adaptation

**Scenario**: You have 7-day periods

1. **After 1 period logged**: 
   - System: 17% your data (7 days) + 83% default (5 days) = ~5.3 days
   - Still close to default

2. **After 5 periods logged**:
   - System: 50% your data (7 days) + 50% default (5 days) = 6.0 days
   - Getting closer to your actual pattern

3. **After 10 periods logged**:
   - System: 67% your data (7 days) + 33% default (5 days) = ~6.3 days
   - Much closer to your actual 7-day pattern

4. **After 20+ periods logged**:
   - System: ~80% your data (7 days) + ~20% default (5 days) = ~6.6 days
   - Very close to your actual 7-day pattern

## Current Implementation

### Code Location
- **Function**: `estimate_period_length()` in `backend/cycle_utils.py`
- **Raw Estimate**: `get_period_length_raw()` - actual pattern (no clamping)
- **Normalized Estimate**: `get_period_length_normalized()` - clamped to 3-8 days
- **Prior**: 5.0 days (default)
- **Adaptation**: Bayesian smoothing with k=5

### Where Each Value Is Used

**Raw Estimate** (actual pattern):
- ✅ Cycle statistics (`get_cycle_stats()`)
- ✅ Insights and medical flags
- ✅ Period length ranges (min/max)
- ✅ UI display with explanation if outside range

**Normalized Estimate** (3-8 days):
- ✅ Phase calculations (`calculate_phase_for_date_range()`)
- ✅ Ovulation date calculations
- ✅ Fertility probability calculations
- ✅ Calendar predictions
- ✅ Phase day ID generation (p1, p2, etc.)

## Potential Improvements

If you want to support longer periods (> 8 days):

1. **Increase max_period** (currently 8.0):
   ```python
   max_period = 10.0  # or higher if needed
   ```

2. **Note**: 8 days is medically normal upper bound, but some women have longer periods

3. **Consider**: Making max_period configurable or removing the hard limit

## Summary

✅ **Dual-value architecture**: Raw (actual) + Normalized (3-8 days)
✅ **Fully adaptive**: Learns from your logged periods
✅ **Medically safe**: Phase calculations use normalized (3-8 days)
✅ **Transparent**: Stats show raw estimate with explanation if outside range
✅ **Pattern detection**: Values outside 3-8 days are detected and reflected in insights

### Key Benefits

1. **Honest Statistics**: Shows your actual pattern, even if outside typical range
2. **Safe Calculations**: Phase calculations use normalized range for medical accuracy
3. **Pattern Detection**: System detects and flags periods outside 3-8 days
4. **User Transparency**: UI explains when values are outside typical range

### Example

**User with 10-day periods:**
- **Raw estimate**: 10.0 days (shown in stats)
- **Normalized estimate**: 8.0 days (used for phase calculations)
- **UI shows**: "10.0 days ⚠️ (outside typical range 3-8 days)"
- **Insight**: "Your period length (10.0 days) is longer than typical (3-8 days). This is detected from your logged data."
- **Phase calculations**: Use 8.0 days (normalized) for safety
