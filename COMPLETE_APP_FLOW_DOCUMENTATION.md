# Complete App Flow Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Data Models](#data-models)
4. [Backend Services](#backend-services)
5. [API Endpoints](#api-endpoints)
6. [Frontend Components](#frontend-components)
7. [Complete User Flows](#complete-user-flows)
8. [Medical Accuracy & Calculations](#medical-accuracy--calculations)
9. [Data Flow Diagrams](#data-flow-diagrams)
10. [Edge Cases & Validation](#edge-cases--validation)
11. [Error Handling](#error-handling)

---

## Overview

This application is a comprehensive menstrual cycle tracking system that:
- Tracks period start dates (cycle starts)
- Predicts future cycles based on historical data
- Calculates cycle phases (Period, Follicular, Ovulation, Luteal)
- Displays cycle statistics and insights
- Provides medically accurate predictions following ACOG guidelines

### Core Design Principles

1. **One Log = One Cycle Start**: Each period log represents a cycle start date (LMP - Last Menstrual Period)
2. **Derived Data**: Cycle length, period length, ovulation dates are all derived from cycle starts
3. **Medical Accuracy**: All calculations follow ACOG (American College of Obstetricians and Gynecologists) guidelines
4. **Adaptive Learning**: System learns from user data to improve predictions

---

## System Architecture

### Tech Stack

**Backend:**
- Python FastAPI
- Supabase (PostgreSQL)
- Date handling: Python `datetime`

**Frontend:**
- React + TypeScript
- Vite
- `react-calendar` for calendar component
- `date-fns` for date manipulation
- `lucide-react` for icons

### Database Schema

#### `users` Table
```sql
- id: UUID (Primary Key)
- last_period_date: DATE
- cycle_length: INTEGER (default: 28)
- period_length: INTEGER (default: 5)
```

#### `period_logs` Table
```sql
- id: UUID (Primary Key)
- user_id: UUID (Foreign Key → users.id)
- date: DATE (Cycle start date)
- flow: TEXT (optional)
- notes: TEXT (optional)
```

**Design Note**: `period_logs` stores cycle start dates only. One log = one cycle start.

**⚠️ CRITICAL RULE**: `period_logs` is the **audit/UX layer** for user input. It is NOT used for cycle calculations.

#### `period_start_logs` Table
```sql
- id: UUID (Primary Key)
- user_id: UUID (Foreign Key → users.id)
- start_date: DATE (Cycle start date)
- is_confirmed: BOOLEAN (true for past dates, false for predictions)
```

**Design Note**: This is a derived table synced from `period_logs`. 

**⚠️ CRITICAL RULE**: `period_start_logs` is the **source of truth** for all cycle calculations.

**All cycle calculations MUST use `period_start_logs`, never `period_logs`.**

This separation ensures:
- `period_logs` = User input (can have duplicates, errors, future dates)
- `period_start_logs` = Validated, deduplicated cycle starts (used for calculations)

**Why this matters:**
- Prevents computing stats from raw user input
- Ensures anomaly logic is always applied
- Maintains data consistency across the system

#### `user_cycle_days` Table
```sql
- id: UUID (Primary Key)
- user_id: UUID (Foreign Key → users.id)
- date: DATE
- phase: TEXT (Period, Follicular, Ovulation, Luteal)
- phase_day_id: TEXT (e.g., p1, f5, o2, l10)
- fertility_prob: FLOAT (0.0 - 1.0)
- source: TEXT (api, adjusted, fallback)
- confidence: FLOAT (0.0 - 1.0)
```

**Design Note**: Cache table for phase mappings. Can be regenerated at any time.

---

## Data Models

### Period Log
```python
{
    "id": "uuid",
    "userId": "uuid",
    "date": "YYYY-MM-DD",
    "flow": "light|medium|heavy" (optional),
    "notes": "string" (optional),
    "isAnomaly": boolean
}
```

### Cycle
```python
{
    "cycle_number": int,  # Most recent = 1
    "start_date": "YYYY-MM-DD",
    "length": int,  # Days between consecutive period starts
    "is_outlier": boolean,  # < 21 days
    "is_irregular": boolean  # > 45 days
}
```

### Prediction
```python
{
    "predictedStart": "YYYY-MM-DD",
    "predictedEnd": "YYYY-MM-DD",
    "ovulation": "YYYY-MM-DD",
    "fertileWindow": {
        "start": "YYYY-MM-DD",
        "end": "YYYY-MM-DD"
    },
    "confidence": {
        "level": "High|Medium|Low",
        "percentage": int,  # 0-100
        "reason": "string"
    }
}
```

### Cycle Statistics
```python
{
    "totalCycles": int,
    "averageCycleLength": float,
    "averagePeriodLength": float,
    "cycleRegularity": "very_regular|regular|somewhat_irregular|irregular|unknown",
    "longestCycle": int,
    "shortestCycle": int,
    "longestPeriod": int,
    "shortestPeriod": int,
    "lastPeriodDate": "YYYY-MM-DD",
    "daysSinceLastPeriod": int,
    "anomalies": int,
    "confidence": {...},
    "insights": ["string"],
    "cycleLengths": [int]  # Last 6 cycles for chart
}
```

### Phase Day Mapping
```python
{
    "date": "YYYY-MM-DD",
    "phase": "Period|Follicular|Ovulation|Luteal",
    "phase_day_id": "p1|f5|o2|l10",
    "fertility_prob": float,  # 0.0 - 1.0
    "source": "api|adjusted|fallback",
    "confidence": float  # 0.0 - 1.0
}
```

---

## Backend Services

### 1. Period Service (`backend/period_service.py`)

Core period tracking and prediction logic.

#### Constants (ACOG Guidelines)
```python
MIN_CYCLE_DAYS = 21  # Normal range: 21-35 days, Extended tracking: up to 45 days
MAX_CYCLE_DAYS = 45
MIN_DAYS_BETWEEN_PERIODS = 10
DEFAULT_CYCLE_DAYS = 28
DEFAULT_PERIOD_DAYS = 5
MIN_PERIOD_DAYS = 2
MAX_PERIOD_DAYS = 8
```

**Cycle Length Handling:**
- **Normal Range**: 21-35 days (ACOG standard)
- **Extended Tracking**: Up to 45 days (for irregular cycles)
- **Cycles < 21 days**: Allowed but auto-marked as anomalies, excluded from averages
- **Cycles > 45 days**: Allowed but auto-marked as anomalies, excluded from averages

#### Key Functions

**`calculate_rolling_average(user_id: str) -> float`**
- Calculates rolling average of cycle length from last 3 non-anomaly cycles
- Excludes cycles outside 21-45 day range
- Falls back to profile default if insufficient data

**`calculate_rolling_period_length(user_id: str) -> float`**
- Gets period length from user profile
- Falls back to default (5 days)
- Note: Cannot calculate from consecutive dates (design: one log = one cycle start)

**`calculate_ovulation_day(cycle_length: int) -> int`**
- Medically accurate ovulation calculation
- Uses luteal phase consistency (12-16 days, usually 14)
- Adjusts for cycle length:
  - Short cycles (< MIN_CYCLE_DAYS): 12-day luteal phase (auto-marked as anomaly)
  - Normal cycles (21-35 days): 14-day luteal phase
  - Long cycles (>35 days): 16-day luteal phase
- Ensures ovulation doesn't occur during period (minimum day 8)
- **Note**: Cycles < 21 days are allowed but auto-marked as anomalies and excluded from averages

**`calculate_prediction_confidence(user_id: str) -> Dict`**
- Calculates confidence level (High/Medium/Low) based on:
  - Number of logged cycles (more = higher confidence)
  - Cycle regularity (variance/standard deviation)
  - Recency of data
- Returns: `{level, percentage, reason}`

**`get_predictions(user_id: str, count: int = 6) -> List[Dict]`**
- Generates predictions for next N cycles
- Each prediction includes:
  - `predictedStart`: Predicted period start date
  - `predictedEnd`: Predicted period end date
  - `ovulation`: Ovulation date
  - `fertileWindow`: 5 days before ovulation to ovulation day (6 days total)
  - `confidence`: Confidence level object

**`can_log_period(user_id: str, date_to_check: date) -> Dict`**
- Validates if a period can be logged
- Prevents overlapping periods
- Ensures minimum 10 days between period starts
- Returns: `{canLog: bool, reason?: string}`

**`check_anomaly(user_id: str, date_to_check: date) -> bool`**
- Checks if cycle length is outside normal range (21-45 days)
- Compares with previous period start date

### 2. Cycle Stats Service (`backend/cycle_stats.py`)

Comprehensive cycle statistics computation.

#### Key Functions

**`get_cycle_stats(user_id: str) -> Dict`**
- Calculates comprehensive cycle statistics:
  - `totalCycles`: Number of complete cycles
  - `averageCycleLength`: Rolling average (empirically derived from cycles)
  - `averagePeriodLength`: Rolling average (from user profile, not empirically derived)
  - `cycleRegularity`: Classification based on coefficient of variation
  - `longestCycle` / `shortestCycle`: Range of cycle lengths (empirically derived from cycles)
  - `longestPeriod` / `shortestPeriod`: Range of period lengths (**profile-based, not empirically derived**)
  - `lastPeriodDate`: Most recent period start
  - `daysSinceLastPeriod`: Days since last period
  - `anomalies`: Count of anomaly cycles
  - `confidence`: Prediction confidence object
  - `insights`: Array of personalized insights
  - `cycleLengths`: Array of last 6 cycle lengths (for chart)
  
**⚠️ Note on Period Length Stats:**
- `longestPeriod` and `shortestPeriod` are currently profile-based (from user's `period_length` field)
- They are **not empirically derived** from actual logged period data
- This is because the system design uses "one log = one cycle start" (no period end dates tracked)
- Future enhancement: Could track period end dates separately to calculate empirical period lengths

**Regularity Classification:**
- **Very Regular**: Coefficient of variation < 8%
- **Regular**: CV < 15%
- **Somewhat Irregular**: CV < 25%
- **Irregular**: CV >= 25%

### 3. Period Start Logs (`backend/period_start_logs.py`)

Manages the derived `period_start_logs` table.

#### Key Functions

**`sync_period_start_logs_from_period_logs(user_id: str) -> None`**
- Syncs PeriodStartLogs from period_logs
- Extracts unique dates (one per cycle start)
- Marks future dates as `is_confirmed=false`
- Marks past dates as `is_confirmed=true`

**`get_period_start_logs(user_id: str, confirmed_only: bool = False) -> List[Dict]`**
- Gets PeriodStartLogs from database
- Can filter to confirmed only (past dates)

**`get_cycles_from_period_starts(user_id: str) -> List[Dict]`**
- Derives cycles from PeriodStartLogs
- Cycle length = gap between consecutive period starts
- Only includes valid cycle lengths (21-45 days per ACOG)

**`validate_cycle_length(cycle_length: int) -> Dict`**
- Validates and classifies cycle length
- Returns: `{is_valid, is_outlier, is_irregular, should_exclude_from_average, reason}`

### 4. Prediction Cache (`backend/prediction_cache.py`)

Manages phase prediction cache.

#### Key Functions

**`invalidate_predictions_after_period(user_id: str, period_start_date: Optional[str]) -> None`**
- Invalidates (deletes) all predicted days after a period start
- Used when a new period is logged

**`regenerate_predictions_from_last_confirmed_period(user_id: str, days_ahead: int = 90) -> None`**
- Regenerates predictions from last confirmed period
- Generates phase mappings for future dates

### 5. Cycle Utils (`backend/cycle_utils.py`)

Core phase calculation utilities.

#### Key Functions

**`calculate_phase_for_date_range(user_id: str, last_period_date: str, cycle_length: int, start_date: Optional[str], end_date: Optional[str]) -> List[Dict]`**
- Primary function for calculating phases
- Generates phase mappings for a date range
- Returns list of phase day mappings

**`generate_phase_day_id(phase: str, day_in_phase: int) -> str`**
- Generates phase day ID (e.g., p1, f5, o2, l10)
- Format: `{prefix}{day_number}`

**Phase Prefixes:**
- Period: `p` (p1-p12)
- Follicular: `f` (f1-f40)
- Ovulation: `o` (o1-o4)
- Luteal: `l` (l1-l25)

---

## API Endpoints

### Period Routes (`/api/periods/`)

#### `POST /log`
Log a period entry.

**Request:**
```json
{
  "date": "YYYY-MM-DD",
  "flow": "light|medium|heavy" (optional),
  "notes": "string" (optional)
}
```

**Response:**
```json
{
  "log": {
    "id": "uuid",
    "userId": "uuid",
    "date": "YYYY-MM-DD",
    "flow": "string",
    "notes": "string",
    "isAnomaly": boolean
  },
  "logs": [...],
  "predictions": [...],
  "rollingAverage": float,
  "rollingPeriodAverage": float
}
```

**Flow:**
1. Validate date (no overlaps, minimum spacing)
2. Check for anomaly
3. Save daily bleeding log
4. Rebuild PeriodStartLogs
5. Recompute cycle stats
6. Invalidate predictions
7. Regenerate predictions
8. Update user profile

#### `GET /logs`
Get all period logs for the current user.

**Response:**
```json
[
  {
    "id": "uuid",
    "userId": "uuid",
    "startDate": "YYYY-MM-DD",
    "endDate": null,
    "isAnomaly": boolean
  }
]
```

#### `GET /predictions?count=6`
Get predictions with confidence levels.

**Response:**
```json
{
  "predictions": [...],
  "rollingAverage": float,
  "rollingPeriodAverage": float,
  "confidence": {
    "level": "High|Medium|Low",
    "percentage": int,
    "reason": "string"
  }
}
```

#### `GET /stats`
Get comprehensive cycle statistics.

**Response:**
```json
{
  "totalCycles": int,
  "averageCycleLength": float,
  "averagePeriodLength": float,
  "cycleRegularity": "string",
  "longestCycle": int,
  "shortestCycle": int,
  "lastPeriodDate": "YYYY-MM-DD",
  "daysSinceLastPeriod": int,
  "anomalies": int,
  "confidence": {...},
  "insights": ["string"],
  "cycleLengths": [int]
}
```

#### `DELETE /log/{log_id}`
Delete a period log entry. Recalculates predictions.

#### `PATCH /log/{log_id}/anomaly`
Toggle anomaly flag for a period log.

### Cycle Routes (`/api/cycles/`)

#### `GET /phase-map?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
Get phase mappings for a date range.

**Response:**
```json
{
  "phase_map": [
    {
      "date": "YYYY-MM-DD",
      "phase": "Period|Follicular|Ovulation|Luteal",
      "phase_day_id": "p1|f5|o2|l10",
      "fertility_prob": float,
      "source": "string",
      "confidence": float
    }
  ]
}
```

---

## Frontend Components

### 1. PeriodCalendar Component (`frontend/src/components/PeriodCalendar.jsx`)

Interactive calendar with phase-based color coding.

**Features:**
- Date range: 1 year past to 2 years future
- Phase-based color coding:
  - Period: `#fb7185` (red/pink)
  - Follicular: `#fef3c7` (yellow/amber)
  - Ovulation: `#7dd3fc` (light blue)
  - Luteal: `#ddd6fe` (purple/lavender)
- Click date to select (doesn't log automatically)
- Log button appears below calendar when date is selected
- Shows selected date information
- Prevents accidental logging
- Legend showing all 4 phases
- Medical note explaining calculations

**State Management:**
- `selectedDate`: Currently selected date
- `phaseMap`: Phase data for visible months
- `periodLogs`: All period logs
- `loading`: Loading state
- `error`: Error message

**Key Functions:**
- `handleDateClick(date)`: Selects a date
- `handleLogPeriod()`: Logs the selected period
- `fetchPhaseMap()`: Fetches phase data for visible months
- `fetchLogs()`: Fetches all period logs

**Event Listeners:**
- Listens for `periodLogged` event to refresh data

### Frontend Event Contract

**⚠️ IMPORTANT**: The frontend uses an event-driven pattern for data synchronization.

#### `periodLogged` Event

**Purpose**: Single source of truth for post-log refreshes across all components.

**When Emitted:**
- After successful period logging in `PeriodCalendar` component
- After successful period logging in `PeriodLogModal` component

**Who Listens:**
- `PeriodCalendar`: Refreshes phase map and period logs
- `CycleStats`: Refreshes cycle statistics
- `Dashboard`: Refreshes all data

**Event Contract:**
```javascript
// Emit event
window.dispatchEvent(new CustomEvent('periodLogged'))

// Listen for event
window.addEventListener('periodLogged', handlePeriodLogged)
```

**Rules:**
1. **Always emit** after successful period log (don't forget!)
2. **Don't double-fetch** - components should debounce if needed
3. **Don't create competing events** - use `periodLogged` as the single source
4. **Clean up listeners** - remove event listeners in component cleanup

**Why This Pattern:**
- Decouples components (calendar doesn't need to know about stats)
- Ensures all components stay in sync
- Prevents race conditions
- Makes the app feel responsive (optimistic updates)

### 2. CycleStats Component (`frontend/src/components/CycleStats.jsx`)

Displays comprehensive cycle statistics.

**Features:**
- Confidence badge with percentage and level
- Key metrics grid:
  - Average cycle length with range
  - Average period length with range
  - Cycle regularity classification
  - Last period date
- Recent cycle lengths bar chart (last 6 cycles)
- Personalized insights list
- Anomaly indicators

**State Management:**
- `stats`: Cycle statistics data
- `loading`: Loading state
- `error`: Error message

**Event Listeners:**
- Listens for `periodLogged` event to refresh data

### 3. Dashboard (`frontend/src/pages/Dashboard.jsx`)

Main dashboard page integrating calendar and statistics.

**Layout:**
- Calendar section (left)
- Cycle statistics section (right)
- AI Assistant card
- Other feature cards

---

## Complete User Flows

### Flow 1: Logging a Period

```
1. User opens Dashboard
   ↓
2. User clicks date on calendar
   ↓
3. Date is selected (highlighted)
   ↓
4. Log button appears below calendar
   ↓
5. User clicks "Log Period Start"
   ↓
6. Frontend validates: canLogPeriod(date)
   ↓
7. If invalid → Show error message
   ↓
8. If valid → POST /api/periods/log
   ↓
9. Backend Processing:
   a. Validate date (no overlaps, minimum spacing)
   b. Check for anomaly (21-45 day range)
   c. Save period log
   d. Rebuild PeriodStartLogs
   e. Recompute cycle stats
   f. Invalidate predictions
   g. Regenerate predictions
   h. Update user profile
   ↓
10. Frontend Updates:
    a. Optimistically update UI
    b. Receive updated logs and predictions
    c. Dispatch 'periodLogged' event
    d. Refresh calendar phase map
    e. Refresh cycle statistics
    f. Clear selected date
```

### Flow 2: Viewing Calendar

```
1. User opens Dashboard
   ↓
2. Frontend fetches phase map for visible months
   ↓
3. GET /api/cycles/phase-map?start_date=...&end_date=...
   ↓
4. Backend calculates phases:
   a. Get last confirmed period start
   b. Calculate cycle length (rolling average)
   c. Calculate phases for date range
   d. Generate phase day IDs
   e. Calculate fertility probabilities
   ↓
5. Frontend renders calendar:
   a. Each date shows phase color
   b. Phase day ID displayed (p1, f5, etc.)
   c. Fertile window indicator (orange dot)
   d. Ovulation indicator (blue dot)
```

### Flow 3: Viewing Cycle Statistics

```
1. User opens Dashboard
   ↓
2. Frontend fetches cycle statistics
   ↓
3. GET /api/periods/stats
   ↓
4. Backend calculates statistics:
   a. Get cycles from PeriodStartLogs
   b. Calculate rolling averages
   c. Calculate regularity (coefficient of variation)
   d. Get cycle length ranges
   e. Calculate confidence
   f. Generate insights
   ↓
5. Frontend displays:
   a. Confidence badge
   b. Key metrics grid
   c. Cycle length chart
   d. Insights list
```

### Flow 4: Getting Predictions

```
1. User requests predictions (or auto-fetched)
   ↓
2. GET /api/periods/predictions?count=6
   ↓
3. Backend generates predictions:
   a. Get last confirmed period start
   b. Calculate rolling average cycle length
   c. Calculate rolling average period length
   d. For each prediction:
      - Calculate next cycle start
      - Calculate ovulation day
      - Calculate fertile window (5 days before ovulation)
      - Calculate predicted period end
   e. Calculate confidence
   ↓
4. Frontend displays predictions:
   a. Future period start dates
   b. Ovulation dates
   c. Fertile windows
   d. Confidence levels
```

---

## Medical Accuracy & Calculations

### ACOG Guidelines

**Normal Cycle Range:** 21-35 days (extended to 45 for tracking)
**Extended Tracking Range:** Up to 45 days (for irregular cycles)
**Cycle Length Handling:**
- Cycles < 21 days: Allowed but auto-marked as anomalies, excluded from averages
- Cycles 21-35 days: Normal range (ACOG standard)
- Cycles 35-45 days: Extended tracking (irregular but tracked)
- Cycles > 45 days: Allowed but auto-marked as anomalies, excluded from averages

**Normal Period Range:** 3-7 days (extended to 2-8 for tracking)
**Luteal Phase:** 12-16 days (usually 14)
**Ovulation:** Typically 14 days before next period
**Fertile Window:** 5-6 days (5 days before ovulation + ovulation day)

### Ovulation Calculation

```python
# Determine luteal phase length based on cycle length
if cycle_length < 21:
    luteal_phase = 12
elif cycle_length > 35:
    luteal_phase = 16
else:
    luteal_phase = 14

# Ovulation day = cycle_length - luteal_phase
ovulation_day = cycle_length - luteal_phase

# Ensure ovulation doesn't occur during period (minimum day 8)
ovulation_day = max(8, ovulation_day)
```

### Fertile Window Calculation

```python
# Fertile window: 5 days before ovulation to ovulation day
fertile_start = ovulation_date - timedelta(days=5)
fertile_end = ovulation_date

# Ensure fertile window doesn't start before period start
if fertile_start < period_start:
    fertile_start = period_start
```

### Phase Calculation

**Period Phase (p1-p12):**
- Days 1 to period_length
- Typically 3-7 days, up to 12 days

**Follicular Phase (f1-f40):**
- After period, before fertile window
- Variable length (extended to 40 days max)
- Starts on day 1 (overlaps with period)

### Phase Overlap Rules

**⚠️ CRITICAL**: When multiple phases apply to a date, priority order is:

1. **Period** (highest priority)
2. **Ovulation** 
3. **Luteal**
4. **Follicular** (lowest priority)

This priority order ensures:
- **Deterministic phase assignment** (no ambiguity)
- **Consistent calendar coloring** (one color per day)
- **Correct phase day IDs** (one ID per day)
- **Accurate fertility probability** (one value per day)

**Example:**
- Day 1 of cycle: Period phase (p1) takes priority over Follicular
- Day 14 (ovulation day): Ovulation phase (o1) takes priority over Follicular/Luteal
- Day 15: Luteal phase (l1) takes priority over Follicular

**Ovulation Phase (o1-o4):**
- **Modeling Note**: This is an "ovulation window" for tracking purposes
- **Medical Reality**: Ovulation itself is ~24 hours, fertility drops fast after
- **Implementation**: 3-4 days total (2-3 days before ovulation + ovulation day)
- **No day after ovulation** (fertility drops immediately)
- **UI Label**: Displayed as "Ovulation" to users
- **Internal Logic**: Treated as `ovulation_window` in calculations

**Luteal Phase (l1-l25):**
- After ovulation until next period
- Typically 12-16 days (usually 14)

### Cycle Regularity Classification

Based on coefficient of variation (CV = std_dev / mean * 100):

- **Very Regular**: CV < 8%
- **Regular**: CV < 15%
- **Somewhat Irregular**: CV < 25%
- **Irregular**: CV >= 25%

### Confidence Calculation

Factors:
1. **Number of cycles** (more = higher): 15 points per cycle, max 100
2. **Regularity** (lower CV = higher): 5-30 points
3. **Recency** (recent = higher): 5-20 points

Score ranges:
- **High**: >= 70%
- **Medium**: 50-69%
- **Low**: < 50%

---

## Data Flow Diagrams

### Period Logging Flow

```
User Action
    ↓
Frontend Validation (canLogPeriod)
    ↓
POST /api/periods/log
    ↓
Backend Validation (can_log_period)
    ↓
Save to period_logs
    ↓
sync_period_start_logs_from_period_logs()
    ↓
update_user_cycle_stats()
    ↓
invalidate_predictions_after_period()
    ↓
regenerate_predictions_from_last_confirmed_period()
    ↓
Update user profile (last_period_date, period_length)
    ↓
Return response with logs, predictions, averages
    ↓
Frontend updates UI
    ↓
Dispatch 'periodLogged' event
    ↓
All components refresh
```

### Phase Calculation Flow

```
GET /api/cycles/phase-map
    ↓
Get last confirmed period start
    ↓
Calculate rolling average cycle length
    ↓
For each date in range:
    ↓
    Calculate day in cycle
    ↓
    Determine phase (Period/Follicular/Ovulation/Luteal)
    ↓
    Calculate ovulation day
    ↓
    Calculate fertile window
    ↓
    Generate phase_day_id
    ↓
    Calculate fertility_probability
    ↓
Store in user_cycle_days (cache)
    ↓
Return phase_map
```

### Cycle Statistics Flow

```
GET /api/periods/stats
    ↓
get_cycles_from_period_starts()
    ↓
Filter valid cycles (21-45 days)
    ↓
Calculate statistics:
    - Rolling averages
    - Regularity (CV)
    - Ranges (longest/shortest)
    - Confidence
    - Insights
    ↓
Return comprehensive stats
```

---

## Edge Cases & Validation

### Period Logging Validation

1. **Duplicate Dates:**
   - Check if date already exists in period_logs
   - Return error: "Period already logged for this date."

2. **Minimum Spacing:**
   - Ensure minimum 10 days between period starts
   - Return error: "Periods must be at least 10 days apart."

3. **Anomaly Detection:**
   - Check if cycle length is outside 21-45 day range
   - Mark as anomaly but still allow logging

4. **Future Dates:**
   - Allowed (for planning/pre-logging)
   - Marked as `is_confirmed=false` in PeriodStartLogs

5. **Past Dates:**
   - Allowed (retroactive logging)
   - Marked as `is_confirmed=true` in PeriodStartLogs

### Cycle Calculation Edge Cases

1. **No Data:**
   - Use defaults (28-day cycle, 5-day period)
   - Confidence: Low (0%)

2. **Insufficient Data (< 3 cycles):**
   - Use available data
   - Lower confidence
   - Show message: "Log at least 3 cycles for better predictions."

3. **Irregular Cycles:**
   - Calculate variance
   - Classify regularity
   - Adjust confidence accordingly

4. **Anomaly Cycles:**
   - Counted separately
   - Excluded from averages
   - Shown in insights

### Phase Calculation Edge Cases

1. **Dates Outside Logged Periods:**
   - Use predictions
   - Calculate phases based on predicted cycle length

2. **Future Dates:**
   - Use estimated cycles
   - Based on last logged period + average cycle length

3. **Past Dates:**
   - Use historical data
   - Calculate phases based on actual cycle length

4. **No Data:**
   - Falls back to defaults (28-day cycle, 5-day period)
   - Still shows phases for visualization

### Prediction Edge Cases

1. **No Logged Periods:**
   - Return empty predictions
   - Show message: "Log at least one period to see predictions."

2. **Single Period:**
   - Use default cycle length
   - Low confidence

3. **Anomaly Cycles:**
   - Excluded from rolling average
   - Still used for individual predictions

---

## Error Handling

### Backend Error Responses

**400 Bad Request:**
```json
{
  "detail": "Period already logged for this date."
}
```

**404 Not Found:**
```json
{
  "detail": "Period log not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Failed to log period: {error message}"
}
```

### Frontend Error Handling

1. **API Errors:**
   - Displayed to user in error message
   - Logged to console for debugging

2. **Validation Errors:**
   - Shown before API call
   - Prevent invalid submissions

3. **Network Errors:**
   - Graceful fallback
   - Show retry option

4. **Date Parsing Errors:**
   - Fixed timezone handling
   - Use `new Date(year, month-1, day)` instead of parsing ISO strings

### Error Recovery

1. **Failed Period Log:**
   - Show error message
   - Allow retry
   - Don't update UI optimistically

2. **Failed Phase Map Fetch:**
   - Show loading state
   - Retry automatically
   - Fallback to cached data if available

3. **Failed Statistics Fetch:**
   - Show error message
   - Allow manual refresh
   - Show cached data if available

---

## Testing Considerations

### Test Cases

1. **Period Logging:**
   - Log first period
   - Log overlapping period (should fail)
   - Log period too close (should fail)
   - Log period with valid spacing (should succeed)
   - Log duplicate period (should fail)

2. **Predictions:**
   - No logged periods (uses defaults)
   - 1 logged period (uses defaults)
   - 2+ logged periods (calculates average)
   - Anomaly cycles (excluded from average)

3. **Phase Calculation:**
   - 28-day cycle (standard)
   - 21-day cycle (short)
   - 35-day cycle (long)
   - Irregular cycles

4. **Statistics:**
   - No data
   - Insufficient data
   - Regular cycles
   - Irregular cycles
   - Anomaly cycles

5. **Calendar:**
   - Past dates
   - Future dates
   - Current date
   - Date selection
   - Phase display

---

## Key Features Summary

✅ Period logging with validation
✅ Overlap prevention (10-day minimum)
✅ Anomaly detection (21-45 day range)
✅ Rolling average calculation (last 3 cycles)
✅ Period length tracking (from profile)
✅ Cycle-length based ovulation
✅ Prediction confidence levels
✅ Comprehensive cycle statistics
✅ Phase-based calendar (4 phases)
✅ Unique phase IDs (p1-p12, f1-f40, o1-o4, l1-l25)
✅ Visual cycle history
✅ Cycle length chart
✅ Mobile-first responsive design
✅ Medical accuracy (ACOG guidelines)
✅ Timezone-safe date handling
✅ Extended date range (1 year past, 2 years future)
✅ Fertile window calculation (5-6 days)
✅ Automatic data refresh after logging

---

## Important Notes

1. **User ID**: Uses TEXT/UUID type
2. **Date Handling**: Always use `new Date(year, month-1, day)` to avoid timezone issues
3. **Response Format**: All responses use camelCase (transform from snake_case)
4. **Error Format**: `{error: "message"}` or `{detail: "message"}` for consistency
5. **Phase IDs**: Unique identifiers for each day in cycle
6. **Ovulation Phase**: Modeled as 3-4 day window (medically, ovulation is ~24 hours)
7. **Follicular Phase**: Extended (up to 40 days)
8. **All Cycles**: History view shows all cycles (no limit)
9. **Period Length**: Stored in user profile, not calculated from consecutive dates
10. **Cycle Length Validation**: Standardized to 21-45 days (ACOG) across all modules
11. **Data Source Rule**: All cycle calculations MUST use `period_start_logs`, never `period_logs`
12. **Phase Priority**: Period → Ovulation → Luteal → Follicular (when overlaps occur)
13. **Event Pattern**: Use `periodLogged` event as single source of truth for post-log refreshes

---

## Future Enhancements

1. **Period Length Tracking:**
   - Allow users to log period end dates
   - Calculate actual period length from start/end dates
   - Update user profile with calculated period length

2. **Advanced Predictions:**
   - Machine learning models for cycle prediction
   - Personalized ovulation windows
   - Symptom tracking integration

3. **Data Export:**
   - Export cycle data to CSV/PDF
   - Share with healthcare providers

4. **Notifications:**
   - Period reminders
   - Fertile window alerts
   - Cycle insights

---

## Conclusion

This documentation provides a comprehensive overview of the complete app flow, from user interactions to backend processing to data storage. The system is designed with medical accuracy, data consistency, and user experience in mind.

For questions or clarifications, refer to the individual module documentation or the code comments.
