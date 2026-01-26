# **PeriodCycle.AI - Complete System Documentation**

## **⚠️ MEDICAL ACCURACY DISCLAIMER**

**CRITICAL: Understanding "Ovulation Phase" vs Biological Reality**

This documentation uses the term **"Ovulation Phase"** as a system abstraction. It is essential to understand:

1. **Biological Reality:**
   - Ovulation is a **single event** lasting approximately **12-24 hours**
   - Only **one ovulation event** occurs per menstrual cycle
   - The egg is released from the ovary during this brief window

2. **Fertile Window (Biological Reality):**
   - The **fertile window** is approximately **5-6 days** per cycle
   - Includes: 5 days before ovulation (sperm survival) + ovulation day + 1 day after (egg viability)

3. **System Abstraction:**
   - **"Ovulation Phase"** = **"Probable Ovulation Window (Uncertainty Band)"**
   - Represents prediction uncertainty around the estimated ovulation date
   - Does **NOT** represent multiple ovulation events
   - Meaning: "We predict ovulation occurred somewhere within these 1-3 days"

4. **Why This Matters:**
   - The system correctly models a **single ovulation event** with prediction uncertainty
   - The 1-3 day "Ovulation Phase" represents **prediction confidence**, not biological duration
   - This avoids medical misinformation about multiple ovulation events

**Throughout this document:**
- "Ovulation Phase" = Prediction uncertainty band (UX abstraction)
- "Ovulation" = Single biological event (12-24 hours)
- "Fertile Window" = 5-6 days (sperm survival + ovulation + egg viability)

**Fertility Probability Accuracy:**
- Peak fertility is at day -1 or -2 (before ovulation), not day 0
- Sperm survival decays over time (not binary on/off)
- Formula reflects real conception data from medical studies

---

## **Table of Contents**

1. System Architecture Overview
2. Phase Determination Logic
3. Core Calculations & Formulas
4. Data Flow & API Integration
5. Calendar Display System
6. Assumptions & Defaults
7. Phase-Day ID System
8. Medical Safety & Liability Protections

---

## **⚠️ MEDICAL SAFETY & LIABILITY**

**CRITICAL: Medical Safety Requirements**

This application provides cycle predictions and fertility information. To ensure medical safety and legal compliance:

1. **UI Disclaimers**: All pages must display disclaimers stating:
   - ⚠️ NOT FOR CONTRACEPTION
   - ⚠️ NOT FOR DIAGNOSIS
   - Educational purposes only

2. **Confidence-Based Suppression**: Fertility probabilities are suppressed when confidence < 0.5 to prevent reliance on inaccurate predictions

3. **Medical Language**: All predictions use "Estimated", "Predicted", "Likely" wording (never "Actual", "Confirmed", "Definite")

**See `MEDICAL_SAFETY_REQUIREMENTS.md` for complete medical safety documentation.**

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

PeriodCycle.AI follows a **three-tier architecture**:

```
┌─────────────────┐
│   Frontend      │  React SPA (Vite)
│   (Vercel)      │  └─ Calendar, Dashboard, Chat
└────────┬────────┘
         │ HTTP/REST
┌────────▼────────┐
│   Backend       │  FastAPI (Python 3.11.9)
│   (Railway)     │  └─ Routes, Business Logic
└────────┬────────┘
         │
┌────────▼────────┐
│   Database       │  PostgreSQL (Supabase)
│                 │  └─ Users, Cycles, Wellness Data
└─────────────────┘
         │
┌────────▼────────┐
│  External APIs  │  RapidAPI (Cycle Predictions)
│                 │  Google Gemini (AI Chat)
└─────────────────┘
```

### 1.2 Technology Stack

**Backend:**
- **Framework**: FastAPI 0.115.0
- **Language**: Python 3.11.9 (see `PYTHON_VERSION_COMPATIBILITY.md` for version considerations)
- **Database**: Supabase (PostgreSQL)
- **Authentication**: JWT tokens (7-day expiration)
- **Password Security**: pbkdf2_sha256 hashing

**⚠️ Python Version Note:**
- **Production**: Python 3.11.9 (configured in `runtime.txt`)
- **Not Recommended**: Python 3.13 (too new, library compatibility risks)
- **See**: `PYTHON_VERSION_COMPATIBILITY.md` for detailed compatibility information

**Frontend:**
- **Framework**: React 19.1.1
- **Build Tool**: Vite 7.1.7
- **Routing**: React Router DOM 7.9.3
- **Styling**: Tailwind CSS 3.4.18
- **Calendar**: React Calendar 5.1.0

**External Services:**
- **RapidAPI**: Women's Health Menstrual Cycle Phase Predictions API
- **Google Gemini**: AI-powered health chatbot (gemini-2.5-flash)

### 1.3 Core Components

**Backend Modules:**
- `cycle_utils.py`: Core prediction algorithms and phase calculations
- `routes/cycles.py`: Cycle prediction endpoints
- `routes/periods.py`: Period logging with adaptive updates
- `routes/wellness.py`: Hormone, nutrition, exercise data
- `routes/ai_chat.py`: AI chatbot integration
- `database.py`: Supabase client with retry logic
- `auth_utils.py`: JWT and password utilities

**Frontend Components:**
- `Dashboard.jsx`: Main user dashboard
- `Calendar.jsx`: Interactive calendar with phase visualization
- `Chat.jsx`: AI health chatbot interface
- `DataContext.jsx`: Global state management

---

## 2. Phase Determination Logic

### 2.1 Overview

Phase determination uses a **hybrid approach** combining:
1. **RapidAPI cycle_phases endpoint** (primary source)
2. **Adaptive local calculations** (fallback/adjustment)
3. **Probabilistic fertility modeling** (ovulation window selection)

### 2.1.1 Medical Accuracy: Ovulation vs Fertile Window

**⚠️ IMPORTANT MEDICAL CLARIFICATION:**

**Ovulation (Biological Reality):**
- Ovulation is a **single event** lasting approximately **12-24 hours**
- Only **one ovulation event** occurs per cycle
- The egg is released from the ovary during this brief window

**Fertile Window (Biological Reality):**
- The **fertile window** is approximately **5-6 days** per cycle
- This includes:
  - **5 days before ovulation**: Sperm can survive in the reproductive tract
  - **Ovulation day** (12-24 hours): Egg is released and viable
  - **1 day after ovulation**: Egg remains viable

**"Ovulation Phase" (System Abstraction):**
- The system's **"Ovulation Phase"** is a **UX abstraction** representing the **prediction uncertainty band** around the estimated ovulation date
- It does **NOT** represent multiple ovulation events
- It represents: "We predict ovulation occurred somewhere within these 1-3 days (uncertainty band)"
- **Naming Convention**: "Ovulation Phase" = "Probable Ovulation Window (Uncertainty Band)"

**Why This Matters:**
- The system correctly models a single ovulation event with uncertainty
- The documentation must clearly distinguish between:
  - **Biological ovulation** (single 12-24 hour event)
  - **Fertile window** (5-6 days including sperm survival)
  - **"Ovulation Phase"** (1-3 day uncertainty band for prediction purposes)

### 2.2 RapidAPI Data Trust Rules (Field-Level)

**TRUSTED FROM RAPIDAPI:**
- ✓ **Dates** (`entry.get("date")`) - Use as-is, these are accurate
- ✓ **Cycle boundaries** - Use `first_cycle_start` from API (p1 days)
- ✓ **Timeline structure** - Process entries in order
- ✓ **predicted_starts** - Use API's cycle start dates for fallback mode

**OVERRIDDEN / CALCULATED LOCALLY:**
- ✗ **Phase names** (`entry.get("phase")`) - We recalculate to ensure 1-3 day uncertainty band
- ✗ **Ovulation dates** - We calculate our own using `predict_ovulation()` (not API's)
- ✗ **Phase-day IDs** (`day_in_phase`) - We recalculate with our phase counters
- ✗ **Fertility probabilities** - We calculate using `fertility_probability()` (not in API)

**HYBRID APPROACH:**
- Use API cycle boundaries (`first_cycle_start`) for structure
- Use API dates for timeline
- Override phases with our logic (ensures 1-3 day uncertainty band for ovulation prediction)
- Calculate our own ovulation dates (more accurate with adaptive `cycle_start_sd`)
- Add fertility probabilities (not provided by API)

**Note:** The "Ovulation Phase" represents prediction uncertainty around a single ovulation event, not multiple ovulation events.

### 2.3 Phase Assignment Algorithm

The system determines phases in the following order:

#### Step 1: Period Phase
```python
if days_since_cycle_start <= period_days:
    phase = "Period"
```

**⚠️ CRITICAL: 1-Indexed Day Calculation**
- **`days_since_cycle_start` is 1-INDEXED** (cycle start = day 1, not day 0)
- **Formula**: `(date_obj - cycle_start).days + 1`
- **Example**: If `period_days = 5`, then days **1, 2, 3, 4, 5** are Period phase (5 days inclusive)
- **DO NOT** change to `< period_days` or `period_days + 1` - this will break silently
- **Why This Matters**: Prevents off-by-one errors during refactoring

**Period Phase Details:**
- Uses adaptive `period_days` from `estimate_period_length(user_id)`
- Range: 3-8 days (clamped)
- Default prior: 5.0 days
- **Boundary Check**: `days_since_cycle_start <= period_days` (inclusive of period_days)

#### Step 2: Ovulation Phase (Uncertainty Band Selection)
```python
ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
if offset_from_ov in ovulation_days:
    phase = "Ovulation"
```

**⚠️ Medical Accuracy Note:**
- **Biological Reality**: Ovulation is a single event (12-24 hours)
- **System Abstraction**: "Ovulation Phase" represents the **prediction uncertainty band**
- **Meaning**: "We predict ovulation occurred somewhere within these 1-3 days"
- **NOT**: Multiple ovulation events

**Uncertainty Band Selection Strategy:**
1. Calculate fertility probabilities for days around predicted ovulation (±5 days)
2. Sort by probability (descending), then by distance from 0 (ascending)
3. Always include day 0 (predicted ovulation day)
4. Build contiguous window: add adjacent days maintaining contiguity
5. Maximum 3 days (1-3 days based on cycle regularity and prediction uncertainty)

**Key Function:** `select_ovulation_days(ovulation_sd, max_days=3)`
- Uses `fertility_probability()` (biologically meaningful for fertile window)
- Ensures contiguous block centered on predicted ovulation day
- Regular cycles (low SD): 1-2 day uncertainty band
- Irregular cycles (high SD): 2-3 day uncertainty band
- **Represents**: Prediction uncertainty, not multiple ovulation events

#### Step 3: Follicular vs Luteal
```python
if date_obj < ovulation_date:
    phase = "Follicular"
else:
    phase = "Luteal"
```

**⚠️ Source of Truth: Ovulation Date Defines Phase Boundaries**

The system uses **ovulation_date as the single source of truth** for phase boundaries. Follicular phase length is **NOT separately calculated** - it is determined implicitly by the ovulation date.

**Follicular Phase:**
- **Source of Truth**: `date_obj < ovulation_date` (ovulation date defines the end)
- **Starts**: After period ends
- **Ends**: When ovulation uncertainty band begins (determined by ovulation_date)
- **Length**: Implicitly determined by `ovulation_date - period_end` (NOT calculated separately)
- **Note**: Includes the fertile window days before ovulation (sperm survival)
- **Why This Matters**: Prevents drift between explicit calculation and implicit definition

**Luteal Phase:**
- **Source of Truth**: `date_obj >= ovulation_date` (ovulation date defines the start)
- **Starts**: After ovulation uncertainty band ends (determined by ovulation_date)
- **Ends**: Next cycle start (period day 1)
- **Length**: Implicitly determined by `next_cycle_start - ovulation_end` (NOT calculated separately)
- Uses adaptive `luteal_mean` from `estimate_luteal(user_id)` for ovulation prediction
- Range: 10-18 days (clamped)
- Default prior: 14.0 ± 2.0 days
- **Note**: Begins after the predicted ovulation uncertainty band

### 2.4 Day Indexing System (1-Indexed)

**⚠️ CRITICAL: All Day Calculations Are 1-INDEXED**

**Key Principle:**
- **Cycle start = Day 1** (NOT Day 0)
- **Formula**: `days_since_cycle_start = (date_obj - cycle_start).days + 1`
- **Why**: Prevents off-by-one errors and matches human intuition (first day = day 1)

**Period Phase Boundary:**
```python
# ⚠️ CRITICAL: days_since_cycle_start is 1-INDEXED
if days_since_cycle_start <= period_days:
    phase = "Period"
```

**Example:**
- If `period_days = 5`:
  - Day 1 = Period (p1)
  - Day 2 = Period (p2)
  - Day 3 = Period (p3)
  - Day 4 = Period (p4)
  - Day 5 = Period (p5) ← **Inclusive boundary**
  - Day 6 = Follicular (f1)
- **Total Period Days**: 5 days (days 1-5 inclusive)

**⚠️ Refactoring Warning:**
- **DO NOT** change to `< period_days` (would exclude day 5)
- **DO NOT** change to `period_days + 1` (would include day 6)
- **MUST** use `<= period_days` (includes all period days)

**All Day Variables Are 1-Indexed:**
- `days_since_cycle_start`: 1-indexed
- `days_since_start`: 1-indexed
- `day_in_cycle`: 1-indexed
- `day_in_phase`: 1-indexed (from phase counters)

### 2.5 Phase Counter System

Each cycle maintains independent phase counters that reset at cycle boundaries:

```python
phase_counters = {
    "Period": 0,
    "Follicular": 0,
    "Ovulation": 0,
    "Luteal": 0
}
```

**Reset Rules:**
- Counters reset to 0 at cycle start (`days_since_cycle_start == 1`)
- Counters reset when crossing cycle boundary (date decreases)
- Each phase increments independently
- `day_in_phase = phase_counters[phase] + 1` (1-indexed)

### 2.6 Cycle Boundary Detection

**Method 1: RapidAPI Timeline**
- Uses `first_cycle_start` from API (first p1 date in timeline)
- Trusts API's cycle structure

**Method 2: Predicted Cycle Starts**
- Uses `get_predicted_cycle_starts_from_db()` (p1 days from database)
- More accurate than modulo math (accounts for cycle variations)

**Method 3: Rolling Calculation**
- Uses `calculate_rolling_cycle_starts()` (fallback)
- Generates cycle starts forward/backward from `last_period_date`

---

## 3. Core Calculations & Formulas

### 3.1 Adaptive Luteal Phase Estimation

**Function:** `estimate_luteal(user_id, user_observations=None)`

**Formula:**
```python
# Population prior
prior_mean = 14.0
prior_sd = 2.0

# User observations (from period logs)
n = len(user_observations)
obs_mean = sum(user_observations) / n

# Bayesian smoothing with sample-size weighting
k = 5  # Prior strength constant
weight = n / (n + k)  # More observations → trust data more

# Weighted combination
luteal_mean = (1 - weight) * prior_mean + weight * obs_mean
luteal_sd = (1 - weight) * prior_sd + weight * obs_sd

# Clamp to allowed range
luteal_mean = max(10.0, min(18.0, luteal_mean))
```

**Update When Period Logged:**
```python
predicted_ov_date_str, ovulation_sd = predict_ovulation(...)
observed_luteal = period_start - predicted_ovulation

# Confidence gating: Only update if ovulation prediction was high confidence
# This prevents training on incorrect predictions from:
# - Stress cycles
# - PCOS-like patterns
# - Anovulatory cycles
# - Early app usage (limited data)
# - Missed ovulation
confidence_threshold = 1.5  # High confidence threshold (days)

if 10 <= observed_luteal <= 18:  # Valid range
    if ovulation_sd <= confidence_threshold:
        # High confidence - safe to learn from
        update_luteal_estimate(user_id, observed_luteal, has_markers=False)
    else:
        # Low confidence - skip update to avoid bad training
        # Log warning but don't update
```

**⚠️ Critical Safety Feature:**
- **Confidence Gating**: Only updates luteal estimate when `ovulation_sd <= 1.5`
- **Prevents Bad Training**: Avoids learning from incorrect ovulation predictions
- **Protects Against**: Stress cycles, PCOS patterns, anovulatory cycles, early app usage
- **Rationale**: Low-confidence ovulation predictions may be wrong, so observed luteal would be incorrect

**Storage:**
- `users.luteal_observations`: JSON array (last 12 observations)
- `users.luteal_mean`: Current estimated mean
- `users.luteal_sd`: Current estimated standard deviation

### 3.2 Adaptive Period Length Estimation

**Function:** `estimate_period_length(user_id, user_observations=None)`

**Formula:**
```python
# Population prior
prior_mean = 5.0

# Get user observations from period_logs
# Group consecutive dates into periods
periods = group_consecutive_dates(period_logs)
user_observations = [period_length for period in periods[-12:]]

# Bayesian smoothing
n = len(user_observations)
k = 5  # Prior strength constant
weight = n / (n + k)

obs_mean = sum(user_observations) / n
period_days = (1 - weight) * prior_mean + weight * obs_mean

# Clamp to allowed range
period_days = max(3.0, min(8.0, period_days))
```

**Storage:**
- Calculated on-demand from `period_logs` table
- No separate storage (recalculated each time)

### 3.3 Ovulation Prediction

**Function:** `predict_ovulation(cycle_start_date, cycle_length_estimate, luteal_mean, luteal_sd, cycle_start_sd, user_id)`

**⚠️ Medical Accuracy:**
- **Biological Reality**: Ovulation is a single event (12-24 hours)
- **System Purpose**: Predicts the most likely day of ovulation
- **Uncertainty**: The `ovulation_sd` represents prediction uncertainty, not multiple ovulation events
- **"Ovulation Phase"**: Represents the uncertainty band around this single predicted event

**Formula:**
```python
# Ovulation date calculation (single predicted event)
ovulation_offset = cycle_length_estimate - luteal_mean
ovulation_date = cycle_start + timedelta(days=int(ovulation_offset))

# Combined uncertainty (prediction confidence)
ovulation_sd = sqrt(cycle_start_sd² + luteal_sd²)
```

**Cycle Start Uncertainty:**
- **Function:** `estimate_cycle_start_sd(user_id, cycle_length_estimate)`
- **Factors:**
  - Cycle length variance (irregular cycles → higher SD)
  - Logging consistency (missed periods → higher SD)
  - Sample size (fewer observations → higher SD)

**Formula:**
```python
base_sd = 0.5  # Very regular, consistent logging
cycle_variance_component = min(1.5, cycle_sd / 5.0)
missed_periods_component = missed_periods_penalty * 1.0
sample_size_component = max(0.0, (5 - n) / 5.0) * 0.5

adaptive_sd = base_sd + cycle_variance_component + missed_periods_component + sample_size_component
adaptive_sd = max(0.5, min(3.0, adaptive_sd))  # Clamp to 0.5-3.0 days
```

### 3.4 Fertility Probability Calculation

**Function:** `fertility_probability(offset_from_ovulation, ovulation_sd)`

**⚠️ Biological Accuracy:**
- **Peak Conception Probability**: Typically day -1 or -2 (before ovulation), not day 0
- **Sperm Survival**: Decays over time (not binary on/off)
- **Medical Data**: Real conception studies show peak fertility 1-2 days before ovulation

**Formula:**
```python
# Early return for dates far from ovulation
if abs(offset_from_ovulation) > 10:
    return 0.0

# Normal distribution component (ovulation probability)
p_ov = normal_pdf(offset_from_ovulation, 0.0, ovulation_sd)

# Sperm survival kernel with decay curve (biologically accurate)
if -5.0 <= offset_from_ovulation <= 0.0:
    # Decay curve: exp(offset / 2.0)
    # Creates smooth decay: day -5 (low) → day -1 (high) → day 0 (moderate)
    p_sperm_raw = exp(offset_from_ovulation / 2.0)
    # Scale to make day -1 peak (reflects medical data)
    p_sperm = min(1.0, p_sperm_raw * 1.65)
else:
    p_sperm = 0.0

# Weighted combination (50/50 split for balanced representation)
raw_prob = 0.5 * p_ov + 0.5 * p_sperm

# Normalization factor (peak fertility at day -1, not day 0)
peak_day = -1.0
peak_p_ov = normal_pdf(peak_day, 0.0, ovulation_sd)
peak_p_sperm = min(1.0, exp(peak_day / 2.0) * 1.65)
norm_factor = 0.5 * peak_p_ov + 0.5 * peak_p_sperm
normalized_prob = raw_prob / norm_factor

# Clamp to [0, 1]
return max(0.0, min(1.0, normalized_prob))
```

**Components:**
- **50% Normal Distribution**: Models ovulation probability (peak at predicted ovulation day)
- **50% Sperm Survival Decay**: Models decaying sperm viability over 5 days before ovulation
- **Decay Curve**: `exp(offset / 2.0)` creates smooth decay (not binary)
- **Peak Shift**: Normalized so day -1 has peak fertility (reflects medical data)

**Sperm Survival Values (After Scaling):**
- **Day -5**: ~0.14 (low)
- **Day -4**: ~0.23 (low-moderate)
- **Day -3**: ~0.37 (moderate)
- **Day -2**: ~0.61 (high)
- **Day -1**: ~1.0 (peak) ⭐
- **Day 0**: ~0.82 (high, but below day -1)

**⚠️ Medical Accuracy:**
- **Fertile Window**: 5-6 days total (5 days before + ovulation day + 1 day after)
- **Ovulation Event**: Single 12-24 hour event within the fertile window
- **Peak Fertility**: Day -1 or -2 (before ovulation), not day 0
- **Fertility Probability**: Represents the probability of conception, not multiple ovulation events
- **Sperm Survival**: Decays over time (not binary), reflecting biological reality

### 3.5 Ovulation Probability (Phase Determination)

**Function:** `ovulation_probability(offset_from_ovulation, ovulation_sd)`

**Purpose:** Used for phase determination (NOT fertility tracking)

**⚠️ Medical Accuracy:**
- Models the probability that ovulation occurred on a given day
- Represents prediction uncertainty around a **single ovulation event**
- Does NOT represent multiple ovulation events

**Formula:**
```python
# Early return for dates far from predicted ovulation
if abs(offset_from_ovulation) > 10:
    return 0.0

# Normal distribution component only (no sperm survival)
# Models: "Probability that ovulation occurred on this day"
p_ov = normal_pdf(offset_from_ovulation, 0.0, ovulation_sd)

# Normalize to peak at 1.0 on predicted ovulation day
peak_prob = normal_pdf(0.0, 0.0, ovulation_sd)
normalized_prob = p_ov / peak_prob

return max(0.0, min(1.0, normalized_prob))
```

**Difference from Fertility Probability:**
- **Fertility Probability**: Includes sperm survival (5-day fertile window)
- **Ovulation Probability**: Only ovulation event probability (narrower window, prediction uncertainty)
- **Usage**: Phase determination uses `select_ovulation_days()` which uses fertility probability
- **Key Point**: Both model a **single ovulation event** with uncertainty, not multiple events

### 3.6 Normal Distribution PDF

**Function:** `normal_pdf(x, mean, sd)`

**Formula:**
```python
if sd <= 0:
    return 0.0

variance = sd * sd
coefficient = 1.0 / (sd * sqrt(2 * π))
exponent = -0.5 * ((x - mean) / sd) ** 2

return coefficient * exp(exponent)
```

### 3.7 Cycle Length Update (Bayesian)

**Function:** `update_cycle_length_bayesian(user_id, new_cycle_length)`

**Formula:**
```python
k = 5  # Prior strength constant
n = 1  # This is 1 new observation
weight = n / (n + k)

updated_cycle_length = (1 - weight) * old_cycle_length + weight * new_cycle_length
```

**When Used:**
- After RapidAPI calculates average cycle length
- When user logs a period (calculates from previous period)
- Smooths cycle length over time (prevents sudden jumps)

---

## 4. Data Flow & API Integration

### 4.1 Cycle Prediction Flow

```
1. User Request
   ↓
   GET /cycles/phase-map?start_date=X&end_date=Y
   
2. Check Database
   ↓
   Query user_cycle_days table for date range
   
3. If No Data or Partial Data
   ↓
   Get User Data: last_period_date, cycle_length
   ↓
   Prepare past_cycle_data (last 12 cycles)
   
4. Try RapidAPI (Primary)
   ↓
   POST /process_cycle_data
   ├─ Get request_id
   ├─ GET /predicted_cycle_starts
   ├─ GET /average_cycle_length
   ├─ GET /average_period_length
   └─ GET /cycle_phases ⭐ (PRIMARY SOURCE)
   
5. Process RapidAPI Timeline
   ↓
   ├─ Trust: Dates, cycle boundaries
   ├─ Override: Phase names, ovulation dates
   ├─ Calculate: Fertility probabilities
   └─ Generate: Phase-day IDs
   
6. If RapidAPI Fails
   ↓
   Fallback: calculate_phase_for_date_range()
   ├─ Use predicted cycle starts from DB
   ├─ Calculate ovulation dates adaptively
   ├─ Select ovulation days (top-N)
   └─ Generate phase mappings
   
7. Store in Database
   ↓
   ├─ Full update: Delete all, insert all
   └─ Partial update: Delete future only, insert new
   
8. Return Phase Map
   ↓
   Format: {date, phase, phase_day_id, fertility_prob, ...}
```

### 4.2 RapidAPI Integration

**Base URL:** `https://womens-health-menstrual-cycle-phase-predictions-insights.p.rapidapi.com`

**Authentication:**
```python
headers = {
    "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
    "X-RapidAPI-Host": "womens-health-menstrual-cycle-phase-predictions-insights.p.rapidapi.com",
    "Content-Type": "application/json"
}
```

**Endpoints Used:**

1. **POST /process_cycle_data**
   - **Purpose**: Submit past cycle data, get request_id
   - **Payload:**
     ```json
     {
       "current_date": "2025-11-16",
       "past_cycle_data": [
         {"cycle_start_date": "2025-10-01", "period_length": 5},
         ...
       ],
       "max_cycle_predictions": 6
     }
     ```
   - **Returns:** `{"request_id": "..."}`

2. **GET /get_data/{request_id}/predicted_cycle_starts**
   - **Returns:** `{"predicted_cycle_starts": ["2025-11-01", ...]}`

3. **GET /get_data/{request_id}/average_cycle_length**
   - **Returns:** `{"average_cycle_length": 28.5}`

4. **GET /get_data/{request_id}/average_period_length**
   - **Returns:** `{"average_period_length": 5.2}`

5. **GET /get_data/{request_id}/cycle_phases** ⭐ (PRIMARY)
   - **Returns:**
     ```json
     {
       "cycle_phases": [
         {
           "date": "2025-11-01",
           "phase": "Period",
           "day_in_phase": 1
         },
         ...
       ]
     }
     ```
   - **Usage**: Primary source for phase timeline
   - **Trust**: Dates, cycle boundaries
   - **Override**: Phase names, ovulation dates

**Error Handling:**
- **Timeout**: 10s connect, 30s read
- **HTTP Errors**: Detailed error messages
- **Fallback**: Local calculation if API fails

### 4.3 Period Logging Flow

```
1. User Logs Period
   ↓
   POST /periods/log
   {
     "start_date": "2025-11-16",
     "end_date": "2025-11-20"
   }
   
2. Calculate Observed Luteal
   ↓
   predicted_ov_date_str, ovulation_sd = predict_ovulation(...)
   observed_luteal = period_start - predicted_ovulation
   
3. Confidence Gating & Validation
   ↓
   ├─ Check ovulation_sd <= 1.5 (high confidence threshold)
   └─ Check 10 <= observed_luteal <= 18 (valid range)
   ↓
   if both conditions met:
       proceed to update
   else:
       skip update (low confidence or invalid observation)
   
4. Update Estimates (only if high confidence)
   ↓
   ├─ Cycle length: update_cycle_length_bayesian()
   └─ Luteal mean: update_luteal_estimate() (only if ovulation_sd <= 1.5)
   
5. Detect Early/Late Period
   ↓
   detect_early_late_period(user_id, logged_period_date)
   ├─ Compare: actual_start vs predicted_start
   └─ If difference >= 2 days: should_adjust = True
   
6. Regenerate Predictions
   ↓
   if should_adjust:
       generate_cycle_phase_map(update_future_only=True)
   else:
       generate_cycle_phase_map(update_future_only=False)
   
7. Store Period Log
   ↓
   Insert into period_logs table
```

### 4.4 Partial Update Logic

**Purpose:** Preserve historical data when recalculating predictions

**Implementation:**
```python
if update_future_only:
    # Delete only future dates
    supabase.table("user_cycle_days").delete()\
        .eq("user_id", user_id)\
        .gte("date", current_date).execute()
    
    # Insert new predictions
    supabase.table("user_cycle_days").insert(insert_data).execute()
else:
    # Delete all existing
    supabase.table("user_cycle_days").delete()\
        .eq("user_id", user_id).execute()
    
    # Insert all new
    supabase.table("user_cycle_days").insert(insert_data).execute()
```

**When Used:**
- Early/late period detection triggers partial update
- User logs period → only future dates recalculated
- Preserves historical predictions

### 4.5 Data Source Priority

| Source | Confidence | When Used |
|--------|-----------|-----------|
| **RapidAPI cycle_phases** | 0.9 | API succeeds, use timeline + override phases |
| **Adjusted** (RapidAPI + manual phases) | 0.7 | API predictions available, manual phase calculation |
| **Fallback** (local calculation) | 0.4 | RapidAPI unavailable, use last_period_date + cycle_length |

---

## 5. Calendar Display System

### 5.1 Calendar Data Retrieval

**Frontend Request:**
```javascript
// Dashboard.jsx or Calendar.jsx
const response = await getPhaseMap(startDate, endDate)
// startDate = 1 month before active month
// endDate = 1 month after active month
```

**Backend Endpoint:**
```
GET /cycles/phase-map?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Response Format:**
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
    },
    ...
  ]
}
```

**⚠️ Medical Accuracy Note:**
- `"phase": "Ovulation"` represents the **prediction uncertainty band** around a single ovulation event
- `"predicted_ovulation_date"` is the most likely day of the single ovulation event
- `"ovulation_sd"` represents prediction uncertainty (not multiple events)
- The 1-3 day "Ovulation Phase" indicates: "We predict ovulation occurred somewhere within these days"

### 5.2 Phase Color Coding

**Color Scheme:**
- **Period**: Soft pink (#F8BBD9)
- **Follicular**: Light green/teal (#B2DFDB)
- **Ovulation**: Soft yellow (#FFF8E1)
- **Luteal**: Light purple (#E1BEE7)

**Implementation:**
```javascript
const phaseColors = {
  "Period": "#F8BBD9",
  "Follicular": "#B2DFDB",
  "Ovulation": "#FFF8E1",
  "Luteal": "#E1BEE7"
};
```

### 5.3 Calendar Features

**Interactive Elements:**
- Click date → View daily details (phase, fertility probability, hormones)
- Period logging directly from calendar
- Fertility probability indicators (visual cues)
- Phase transitions highlighted

**Data Display:**
- Current phase badge
- Fertility window indicators
- Predicted ovulation date
- Cycle day number

### 5.4 Date Range Calculation

**Default Range:**
- **Start Date**: 1 month before active month
- **End Date**: 1 month after active month
- **Total**: ~90 days of predictions

**Dynamic Adjustment:**
- Expands if user navigates to future months
- Caches predictions in database
- Only regenerates when needed

---

## 6. Assumptions & Defaults

### 6.1 Population Priors

**Luteal Phase:**
- **Prior Mean**: 14.0 days
- **Prior SD**: 2.0 days
- **Range**: 10-18 days (clamped)
- **Rationale**: Medical literature standard

**Period Length:**
- **Prior Mean**: 5.0 days
- **Range**: 3-8 days (clamped)
- **Rationale**: Typical menstrual period duration

**Cycle Length:**
- **Default**: 28 days
- **Range**: 21-45 days (valid cycle range)
- **Rationale**: Average menstrual cycle length

### 6.2 Bayesian Smoothing Parameters

**Prior Strength Constant (k):**
- **Default**: k = 5
- **Meaning**: Equivalent to having 5 prior observations
- **Weight Formula**: `weight = n / (n + k)`
- **Effect**: More observations → trust data more

**Weight Examples:**
- 1 observation: weight = 1/6 = 16.7% (trust data)
- 5 observations: weight = 5/10 = 50% (balanced)
- 10 observations: weight = 10/15 = 66.7% (trust data more)
- 20 observations: weight = 20/25 = 80% (mostly trust data)

**Marker Adjustment:**
- **With LH/BBT markers**: k = 3 (trust data more)
- **Without markers**: k = 5 (standard)

### 6.3 Ovulation Uncertainty Band Constraints

**⚠️ Medical Accuracy:**
- **Biological Reality**: Ovulation is a single event (12-24 hours)
- **System Abstraction**: "Ovulation Phase" represents prediction uncertainty, not multiple ovulation events
- **Fertile Window**: 5-6 days total (sperm survival + ovulation + egg viability)
- **"Ovulation Phase"**: 1-3 day uncertainty band around predicted ovulation date

**Maximum Uncertainty Band Days:**
- **Default**: max_days = 3
- **Range**: 1-3 days
- **Rationale**: Prediction uncertainty band (not biological ovulation duration)
- **Meaning**: "We predict ovulation occurred somewhere within these 1-3 days"

**Selection Strategy:**
- Always include day 0 (predicted ovulation day)
- Build contiguous window centered on predicted ovulation day
- Regular cycles (low SD): 1-2 day uncertainty band
- Irregular cycles (high SD): 2-3 day uncertainty band
- **Represents**: Prediction confidence, not multiple ovulation events

### 6.4 Cycle Start Uncertainty

**Base Uncertainty:**
- **Base SD**: 0.5 days (very regular, consistent logging)
- **Maximum SD**: 3.0 days (irregular cycles, missed periods)
- **Range**: 0.5-3.0 days

**Factors:**
- **Cycle Variance**: Higher variance → higher SD
- **Missed Periods**: Large gaps → higher SD
- **Sample Size**: Fewer observations → higher SD

### 6.5 Fertility Probability Thresholds

**⚠️ Medical Accuracy:**
- **Biological Fertile Window**: 5-6 days (sperm survival + ovulation + egg viability)
- **"Ovulation Phase"**: 1-3 day uncertainty band around predicted ovulation date
- **Fertility Probability**: Models conception probability, not multiple ovulation events

**Ovulation Uncertainty Band:**
- **Selection Method**: Top-N days by fertility probability
- **Not Threshold-Based**: Uses `select_ovulation_days()` (top-N selection)
- **Range**: 1-3 days (contiguous block)
- **Represents**: Prediction uncertainty band, not biological ovulation duration

**Fertile Window (Informational):**
- **Peak Fertility**: Typically day -1 or -2 (before ovulation) - reflects medical data
- **High Fertility**: fertility_prob >= 0.6 (includes days before ovulation due to sperm survival)
- **Moderate Fertility**: fertility_prob >= 0.2
- **Low Fertility**: fertility_prob < 0.2
- **Total Fertile Window**: ~5-6 days (spans beyond "Ovulation Phase" due to sperm survival)
- **Sperm Survival**: Decays over time (not binary), with peak viability at day -1

### 6.6 Data Validation Rules

**Observed Luteal Length:**
- **Valid Range**: 10-18 days
- **Rationale**: Medical literature (normal luteal phase)
- **Confidence Gating**: Requires `ovulation_sd <= 1.5` (high confidence ovulation prediction)
- **Rationale for Confidence Gating**: Prevents training on incorrect ovulation predictions from:
  - Stress cycles
  - PCOS-like patterns
  - Anovulatory cycles
  - Early app usage (limited data)
  - Missed ovulation
- **Action**: Only update if both conditions met (valid range AND high confidence), otherwise skip

**Cycle Length:**
- **Valid Range**: 21-45 days
- **Rationale**: Normal menstrual cycle range
- **Action**: Filter out invalid cycles

**Period Length:**
- **Valid Range**: 3-8 days
- **Rationale**: Normal menstrual period range
- **Action**: Clamp to range in estimation

### 6.7 Early/Late Period Detection

**Threshold:**
- **Difference**: >= 2 days
- **Action**: Trigger partial update (`update_future_only=True`)
- **Rationale**: Significant deviation from prediction

**Calculation:**
```python
difference = actual_start - predicted_start
if abs(difference) >= 2:
    should_adjust = True
```

### 6.8 Sample Size Limits

**Luteal Observations:**
- **Storage**: Last 12 observations
- **Rationale**: Recent data more relevant
- **Action**: Trim to 12 when adding new observation

**Period Observations:**
- **Storage**: Last 12 periods
- **Rationale**: Recent patterns more relevant
- **Action**: Use last 12 periods for estimation

**Cycle Predictions:**
- **RapidAPI**: 6-12 cycles (default: 6, max: 12)
- **Rationale**: API requirements and accuracy

---

## 7. Phase-Day ID System

### 7.1 ID Format

**Pattern:** `{prefix}{day_number}`

**Prefixes:**
- **Period**: `p` (e.g., p1, p2, p3, ...)
- **Follicular**: `f` (e.g., f1, f2, f3, ...)
- **Ovulation**: `o` (e.g., o1, o2, o3, ...)
- **Luteal**: `l` (e.g., l1, l2, l3, ...)

**Examples:**
- `p3` = Day 3 of Period phase
- `f10` = Day 10 of Follicular phase
- `o2` = Day 2 of Ovulation phase (if 2-3 day window)
- `l15` = Day 15 of Luteal phase

### 7.2 ID Generation

**Function:** `generate_phase_day_id(phase, day_in_phase)`

**Implementation:**
```python
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

### 7.3 Phase Counter System

**Per-Cycle Counters:**
```python
phase_counters = {
    "Period": 0,
    "Follicular": 0,
    "Ovulation": 0,
    "Luteal": 0
}
```

**Increment Rules:**
- Each phase increments independently
- Counters reset at cycle boundary
- `day_in_phase = phase_counters[phase] + 1` (1-indexed)

**Reset Rules:**
- Reset to 0 at cycle start (`days_since_cycle_start == 1`)
- Reset when crossing cycle boundary (date decreases)
- Explicit reset prevents counter drift

### 7.4 ID Ranges

**Theoretical Maximums:**
- **Period**: p1-p12 (max 12 days, clamped to 3-8)
- **Follicular**: f1-f30 (dynamic, typically 7-14 days)
- **Ovulation**: o1-o8 (max 8 days, typically 1-3 days) ⚠️ *Uncertainty band, not biological duration*
- **Luteal**: l1-l25 (max 25 days, clamped to 10-18)

**Actual Ranges (Adaptive):**
- **Period**: p1-p8 (based on `estimate_period_length()`)
- **Follicular**: f1-f20 (dynamic, determined by ovulation_date - NOT separately calculated)
- **Ovulation**: o1-o3 (based on `select_ovulation_days()`) ⚠️ *Represents prediction uncertainty band*
- **Luteal**: l1-l18 (based on `estimate_luteal()`, but length determined by ovulation_date)

**⚠️ Important:**
- Follicular and Luteal phase lengths are **NOT explicitly calculated**
- They are **implicitly determined** by the ovulation_date (source of truth)
- Follicular: `ovulation_date - period_end`
- Luteal: `next_cycle_start - ovulation_end`
- This prevents drift between explicit calculations and implicit definitions

**⚠️ Medical Accuracy Note:**
- The "Ovulation Phase" (o1-o3) represents the **prediction uncertainty band** around a single ovulation event
- Biological ovulation is a single 12-24 hour event
- The 1-3 day range represents prediction confidence, not multiple ovulation events

### 7.5 Usage in System

**Calendar Display:**
- Phase-day ID determines color coding
- Used for phase-specific styling
- Enables phase transitions visualization

**Wellness Data Retrieval:**
- Hormone data: `hormones_data.id = phase_day_id`
- Nutrition data: `nutrition_*.hormone_id = phase_day_id`
- Exercise data: `exercises_*.hormone_id = phase_day_id`

**API Responses:**
- Every date includes `phase_day_id`
- Frontend uses ID for data lookup
- Enables phase-specific recommendations

### 7.6 ID Consistency

**Guarantees:**
- Unique per cycle (resets at cycle boundary)
- Sequential within phase (1, 2, 3, ...)
- Contiguous (no gaps in numbering)
- Cycle-independent (each cycle starts from 1)

**Edge Cases Handled:**
- Cycle boundary crossing (explicit reset)
- Missing phases (counters independent)
- Phase transitions (smooth increment)

---

## 8. Medical Safety & Liability Protections

### 8.1 Overview

PeriodCycle.AI implements comprehensive medical safety and liability protections to ensure:
- Users understand limitations of predictions
- Low-confidence data is suppressed
- Appropriate medical language is used
- Legal disclaimers are clearly displayed

**See `MEDICAL_SAFETY_REQUIREMENTS.md` for complete documentation.**

### 8.2 UI Disclaimers

**Required Disclaimers:**
1. **Contraception Warning**: "NOT FOR CONTRACEPTION - Do NOT rely on fertility predictions for birth control"
2. **Diagnosis Warning**: "NOT FOR DIAGNOSIS - Cycle predictions are estimates, not medical diagnoses"
3. **General Medical Disclaimer**: "Educational purposes only - Consult healthcare professionals"

**Implementation:**
- Component: `frontend/src/components/SafetyDisclaimer.jsx`
- Display: All pages showing cycle/fertility data
- Multilingual: English, Hindi, Gujarati

### 8.3 Confidence-Based Data Suppression

**Fertility Probability Suppression:**
- **Threshold**: `MIN_CONFIDENCE_FOR_FERTILITY = 0.5`
- **Rule**: Only return `fertility_prob` if `confidence >= 0.5`
- **Rationale**: Low-confidence predictions (fallback mode, confidence = 0.4) are suppressed

**Implementation:**
```python
# backend/routes/cycles.py
MIN_CONFIDENCE_FOR_FERTILITY = 0.5
confidence = item.get("confidence", 0.0)
if "fertility_prob" in item and confidence >= MIN_CONFIDENCE_FOR_FERTILITY:
    formatted_entry["fertility_prob"] = item["fertility_prob"]
# If confidence is low, do NOT include fertility_prob (suppressed for safety)
```

**Confidence Levels:**
- **RapidAPI** (confidence: 0.9): ✅ Fertility data shown
- **Adjusted** (confidence: 0.7): ✅ Fertility data shown
- **Fallback** (confidence: 0.4): ❌ Fertility data suppressed

### 8.4 Medical Language Requirements

**Required Wording:**
- ✅ "Estimated ovulation date" (not "Ovulation date")
- ✅ "Predicted cycle start" (not "Cycle start")
- ✅ "Likely fertile window" (not "Fertile window")
- ✅ "Probable phase" (not "Phase")

**Implementation:**
- Backend: `predicted_ovulation_date_label = "Estimated ovulation date"`
- Frontend: Use translation keys `safety.estimated`, `safety.predicted`, `safety.likely`
- All API responses use appropriate medical language

### 8.5 Legal & Ethical Considerations

**Liability Protection:**
- Clear disclaimers prevent user reliance on predictions for contraception/diagnosis
- Confidence-based suppression prevents display of inaccurate data
- Medical language sets appropriate expectations

**Ethical Requirements:**
- Users understand limitations of predictions
- Users know when to consult healthcare professionals
- System does not overstate prediction accuracy

---

## Appendix A: Key Functions Reference

### Core Functions

**`estimate_luteal(user_id, user_observations=None)`**
- Returns: `(mean, sd)` tuple
- Purpose: Adaptive luteal phase estimation with Bayesian smoothing

**`estimate_period_length(user_id, user_observations=None)`**
- Returns: `float` (period length in days)
- Purpose: Adaptive period length estimation with Bayesian smoothing

**`predict_ovulation(cycle_start_date, cycle_length_estimate, luteal_mean, luteal_sd, cycle_start_sd, user_id)`**
- Returns: `(ovulation_date_str, ovulation_sd)` tuple
- Purpose: Predict ovulation date with uncertainty quantification

**`fertility_probability(offset_from_ovulation, ovulation_sd)`**
- Returns: `float` (0.0-1.0)
- Purpose: Calculate fertility probability for a day

**`ovulation_probability(offset_from_ovulation, ovulation_sd)`**
- Returns: `float` (0.0-1.0)
- Purpose: Calculate ovulation probability for phase determination

**`select_ovulation_days(ovulation_sd, max_days=3)`**
- Returns: `set` of day offsets (e.g., {-1, 0, 1})
- Purpose: Select top-N days for ovulation uncertainty band (1-3 days)
- **Medical Note**: Represents prediction uncertainty around a single ovulation event, not multiple events

**`estimate_cycle_start_sd(user_id, cycle_length_estimate)`**
- Returns: `float` (standard deviation in days)
- Purpose: Estimate cycle start uncertainty based on cycle variance

**`generate_cycle_phase_map(user_id, past_cycle_data, current_date, update_future_only=False)`**
- Returns: `List[Dict]` (phase mappings)
- Purpose: Generate complete phase-day mappings using RapidAPI or fallback

**`generate_phase_day_id(phase, day_in_phase)`**
- Returns: `str` (e.g., "p1", "f10", "o2", "l15")
- Purpose: Generate phase-day ID from phase name and day number

---

## Appendix B: Database Schema

### Core Tables

**`users`**
- `id`: UUID (primary key)
- `email`: VARCHAR
- `password_hash`: VARCHAR
- `last_period_date`: DATE
- `cycle_length`: INTEGER (default: 28)
- `luteal_observations`: TEXT (JSON array)
- `luteal_mean`: FLOAT (default: 14.0)
- `luteal_sd`: FLOAT (default: 2.0)

**`period_logs`**
- `id`: UUID (primary key)
- `user_id`: UUID (foreign key)
- `date`: DATE (one row per day of period)
- `created_at`: TIMESTAMP

**`user_cycle_days`**
- `id`: UUID (primary key)
- `user_id`: UUID (foreign key)
- `date`: DATE
- `phase`: VARCHAR
- `phase_day_id`: VARCHAR
- `source`: VARCHAR (optional: "api", "adjusted", "fallback")
- `confidence`: FLOAT (optional: 0.4-0.9)
- `fertility_prob`: FLOAT (optional)
- `predicted_ovulation_date`: DATE (optional)
- `luteal_estimate`: FLOAT (optional)
- `luteal_sd`: FLOAT (optional)
- `ovulation_sd`: FLOAT (optional)

---

## Appendix C: Error Handling

### API Error Handling

**RapidAPI Errors:**
- **Timeout**: 10s connect, 30s read → Fallback to local calculation
- **HTTP Errors**: Detailed error messages → Fallback to local calculation
- **Empty Response**: Fallback to local calculation

**Database Errors:**
- **Connection Errors**: Retry with exponential backoff
- **Missing Columns**: Graceful degradation (optional fields)
- **RLS Violations**: Return 403 Forbidden

### Validation Errors

**Invalid Data:**
- Observed luteal outside 10-18 days → Skip update
- Low confidence ovulation prediction (ovulation_sd > 1.5) → Skip luteal update (confidence gating)
- Cycle length outside 21-45 days → Filter out
- Period length outside 3-8 days → Clamp to range

**Missing Data:**
- No `last_period_date` → Return error
- No past cycles → Use defaults (prior values)
- No RapidAPI key → Use fallback calculation

---

## Document Version

**Version:** 1.1  
**Last Updated:** 2025-11-16  
**Based on:** `cycle_utils.py` (1726 lines)  
**Status:** Complete and up-to-date with current implementation

**Medical Accuracy Updates:**
- Clarified that "Ovulation Phase" represents prediction uncertainty band, not multiple ovulation events
- Added medical accuracy disclaimers throughout document
- Distinguished between biological ovulation (single 12-24 hour event) and system abstraction (1-3 day uncertainty band)
- Clarified fertile window (5-6 days) vs ovulation uncertainty band (1-3 days)
- **Updated fertility probability formula** to reflect biological reality:
  - Peak fertility at day -1 or -2 (before ovulation), not day 0
  - Sperm survival uses decay curve (not binary)
  - 50/50 weight split (reduced ovulation-day dominance)
  - Reflects real conception data from medical studies
- **Added confidence gating for luteal estimate updates**:
  - Only updates when `ovulation_sd <= 1.5` (high confidence)
  - Prevents training on incorrect ovulation predictions
  - Protects against stress cycles, PCOS patterns, anovulatory cycles, early app usage
- **Fixed follicular phase calculation inconsistency**:
  - Removed incorrect explicit formula from documentation
  - Clarified that ovulation_date is the single source of truth
  - Follicular and Luteal lengths are implicitly determined by ovulation_date (NOT separately calculated)
  - Prevents drift between explicit calculations and implicit definitions
- **Documented 1-indexed day calculation to prevent off-by-one errors**:
  - All day calculations are 1-indexed (cycle start = day 1, not day 0)
  - Added explicit warnings in code comments
  - Documented period phase boundary logic: `days_since_cycle_start <= period_days`
  - Example: If period_days = 5, then days 1-5 inclusive = Period phase (5 days total)
  - Prevents silent breakage during refactoring
- **Implemented medical safety and liability protections**:
  - UI disclaimers for NOT contraception / NOT diagnosis
  - Confidence-based fertility data suppression (threshold: 0.5)
  - Medical language requirements ("Estimated", "Predicted", "Likely")
  - See `MEDICAL_SAFETY_REQUIREMENTS.md` for complete details
- **Fixed race condition in cycle phase map updates**:
  - Replaced delete-then-insert with upsert pattern (try insert, catch conflict, then update)
  - Prevents data loss when calendar fetch + background regen collide
  - Handles concurrent period logs and multiple API calls safely
  - See `RACE_CONDITION_PROTECTION.md` for complete details

---

## Summary: Key Medical Accuracy Points

**For Developers and Medical Reviewers:**

1. **Ovulation is a Single Event:**
   - Biological reality: 12-24 hours
   - Only one ovulation event per cycle
   - System models this correctly

2. **"Ovulation Phase" is a System Abstraction:**
   - Represents prediction uncertainty band (1-3 days)
   - Meaning: "We predict ovulation occurred somewhere within these days"
   - Does NOT represent multiple ovulation events
   - Alternative naming: "Probable Ovulation Window (Uncertainty Band)"

3. **Fertile Window vs Ovulation Phase:**
   - **Fertile Window**: 5-6 days (sperm survival + ovulation + egg viability)
   - **"Ovulation Phase"**: 1-3 days (prediction uncertainty band)
   - The fertile window is larger than the "Ovulation Phase" due to sperm survival

4. **System Correctness:**
   - The system correctly models a single ovulation event with uncertainty
   - The 1-3 day range represents prediction confidence, not biological duration
   - All calculations assume a single ovulation event per cycle
   - Fertility probability reflects biological reality:
     - Peak fertility at day -1 or -2 (before ovulation)
     - Sperm survival decays over time (not binary)
     - Formula matches real conception data from medical studies

---

*This document reflects the complete system architecture, algorithms, and data flows as implemented in the PeriodCycle.AI application. Medical accuracy disclaimers have been added to prevent misinterpretation of system abstractions as biological reality.*
