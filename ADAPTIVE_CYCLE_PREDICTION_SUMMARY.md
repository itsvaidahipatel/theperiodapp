# Adaptive Cycle Prediction System - Implementation Summary

## Overview
The cycle prediction system has been upgraded to use **adaptive, data-driven, probabilistic** methods instead of fixed phase lengths. The system now learns from user data and provides fertility probabilities for each day.

---

## ✅ Completed Upgrades

### 1. **Adaptive Luteal Phase Estimation**
- **Function**: `estimate_luteal(user_id, user_observations=None)`
- **Method**: Bayesian smoothing with population prior
- **Formula**: `luteal_estimate = 0.6 * prior_mean + 0.4 * user_mean`
- **Prior**: Mean=14 days, SD=2 days, Range=10-18 days
- **Storage**: `users.luteal_observations` (JSON array), `users.luteal_mean`, `users.luteal_sd`

### 2. **Ovulation Prediction**
- **Function**: `predict_ovulation(cycle_start_date, cycle_length_estimate, luteal_mean, luteal_sd, cycle_start_sd)`
- **Formula**: `ovulation_date = cycle_start + (cycle_length - luteal_mean)`
- **Uncertainty**: `ovulation_sd = sqrt(cycle_start_sd^2 + luteal_sd^2)`
- **No fixed ovulation window** - calculated dynamically

### 3. **Probabilistic Fertility Window**
- **Function**: `fertility_probability(offset_from_ovulation, ovulation_sd)`
- **Model**: 
  - 60% normal distribution (ovulation probability)
  - 40% sperm survival kernel (5 days before ovulation)
- **Normalization**: Peak fertility at ovulation day
- **Output**: Probability between 0 and 1

### 4. **Phase Assignment Rules**
- **Period**: Days within period length
- **Ovulation Day**: `fertility_prob >= 0.6` (high fertility)
- **Fertile Window**: `fertility_prob >= 0.2` (moderate fertility)
- **Follicular**: Before ovulation window
- **Luteal**: After ovulation window and before next cycle start

### 5. **Day IDs** (Unchanged)
- Period → p1, p2, ...
- Follicular → f1, f2, ...
- Ovulation → o1, o2, ...
- Luteal → l1, l2, ...

### 6. **Confidence Scoring**
- **RapidAPI**: 0.9 (high confidence)
- **Adjusted** (RapidAPI predictions with manual phases): 0.7 (medium)
- **Fallback** (no RapidAPI): 0.4 (low)

### 7. **Update Rules When User Logs Period**
- **Cycle Length**: `updated = (old * 0.7) + (new * 0.3)` (Bayesian)
- **Luteal Length**: `updated = (old * 0.6) + (observed * 0.4)` (or 0.5/0.5 if markers exist)
- **Observed Luteal**: `period_start - predicted_ovulation`
- **Validation**: Only updates if observed luteal is in range 10-18 days

### 8. **Replaced Fixed Logic**
- ❌ Removed: `luteal_days = 14` (fixed)
- ❌ Removed: `ovulation_window = 6` (fixed)
- ❌ Removed: Hard-coded fertile window
- ✅ Added: Adaptive luteal estimation
- ✅ Added: Dynamic ovulation prediction
- ✅ Added: Probabilistic fertility window

### 9. **New JSON Fields**
Each day object now includes:
- `fertility_prob`: float (0.0-1.0)
- `predicted_ovulation_date`: string (YYYY-MM-DD)
- `luteal_estimate`: float (mean luteal length)
- `luteal_sd`: float (standard deviation)
- `ovulation_sd`: float (ovulation uncertainty)
- `source`: "api" | "adjusted" | "fallback"
- `confidence`: float (0.4-0.9)

---

## 📊 Key Functions

### `estimate_luteal(user_id, user_observations=None)`
```python
# Returns: (mean, sd)
# Prior: mean=14, sd=2
# User data: weighted 40%
# Clamped to range: 10-18 days
```

### `fertility_probability(offset_from_ovulation, ovulation_sd)`
```python
# offset_from_ovulation: days from predicted ovulation (negative = before)
# Returns: probability between 0 and 1
# Combines: normal distribution (60%) + sperm survival (40%)
```

### `predict_ovulation(cycle_start_date, cycle_length_estimate, luteal_mean, luteal_sd, cycle_start_sd)`
```python
# Returns: (ovulation_date_str, ovulation_sd)
# Formula: cycle_start + (cycle_length - luteal_mean)
# Uncertainty: sqrt(cycle_start_sd^2 + luteal_sd^2)
```

### `update_luteal_estimate(user_id, observed_luteal_length, has_markers=False)`
```python
# Updates user's luteal estimate when period is logged
# Weight: 40% observed (or 50% if markers exist)
# Stores last 12 observations
```

---

## 🔄 Updated Functions

### `generate_cycle_phase_map()`
- **RapidAPI Mode**: Uses `cycle_phases` timeline + adds fertility probabilities
- **Adjusted Mode**: Uses predicted cycle starts + adaptive ovulation/luteal + fertility probabilities
- **No fixed phase lengths** - all calculated adaptively

### `calculate_phase_for_date_range()`
- **Fallback Mode**: Uses adaptive luteal estimation + fertility probabilities
- **No fixed defaults** - all calculated from user data or priors

### `log_period()` (routes/periods.py)
- **New**: Calculates observed luteal length
- **New**: Updates luteal estimate using Bayesian smoothing
- **New**: Validates observed luteal (10-18 days range)

---

## 🗄️ Database Changes

### New Columns in `users` Table
- `luteal_observations`: TEXT (JSON array of observed lengths)
- `luteal_mean`: FLOAT (current estimated mean, default 14.0)
- `luteal_sd`: FLOAT (current estimated SD, default 2.0)

**Migration Script**: `database/add_luteal_fields.sql`

---

## 📈 How It Works

### Initial State (No User Data)
1. Uses population prior: luteal_mean=14, luteal_sd=2
2. Predicts ovulation: `cycle_start + (cycle_length - 14)`
3. Calculates fertility probabilities based on ovulation uncertainty

### After User Logs Periods
1. Calculates observed luteal: `period_start - predicted_ovulation`
2. Updates estimate: `(old * 0.6) + (observed * 0.4)`
3. Predictions become more accurate over time

### Fertility Probability Calculation
1. For each day, calculate offset from predicted ovulation
2. Apply normal distribution (ovulation probability)
3. Apply sperm survival kernel (5 days before ovulation)
4. Combine: 60% ovulation + 40% sperm survival
5. Normalize to peak at ovulation day

### Phase Assignment
1. Period: Days 1-5 (or user's period length)
2. High Fertility (≥0.6): Ovulation phase
3. Fertile Window (≥0.2): Ovulation phase
4. Before Ovulation: Follicular phase
5. After Ovulation: Luteal phase

---

## 🎯 Benefits

1. **No Fixed Values**: All phases adapt to user data
2. **Learning System**: Improves with each logged period
3. **Fertility Probabilities**: Each day has a fertility score
4. **Uncertainty Tracking**: SD values indicate prediction confidence
5. **Backward Compatible**: Existing frontend still works (new fields optional)

---

## 📝 Example Response

```json
{
  "phase_map": [
    {
      "date": "2025-11-16",
      "phase": "Ovulation",
      "phase_day_id": "o1",
      "fertility_prob": 0.85,
      "predicted_ovulation_date": "2025-11-16",
      "luteal_estimate": 14.2,
      "luteal_sd": 1.8,
      "ovulation_sd": 2.1,
      "source": "api",
      "confidence": 0.9
    }
  ]
}
```

---

## ✅ All Requirements Met

- ✅ No fixed phase lengths (ovulation, luteal)
- ✅ Adaptive luteal phase estimation
- ✅ Data-driven ovulation prediction
- ✅ Probabilistic fertility window
- ✅ Predictions improve with more cycles
- ✅ Fertility probability per day
- ✅ RapidAPI-first design maintained
- ✅ Perfect fallback mode
- ✅ Backward compatible
- ✅ Ready for Flutter frontend

---

The system is now fully adaptive, probabilistic, and learns from user data while maintaining perfect backward compatibility.





