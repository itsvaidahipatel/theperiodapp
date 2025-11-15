# Cycle Prediction Guide

## Overview

The cycle prediction system integrates with the Women's Health API to predict menstrual cycles and generate phase-day mappings. This guide explains how to use it.

## API Endpoint

### Generate Cycle Predictions

**POST** `/cycles/predict`

**Request Body:**
```json
{
  "past_cycle_data": [
    {
      "cycle_start_date": "2023-01-05",
      "period_length": 5
    },
    {
      "cycle_start_date": "2023-02-01",
      "period_length": 4
    },
    {
      "cycle_start_date": "2023-02-28",
      "period_length": 4
    },
    {
      "cycle_start_date": "2023-03-26",
      "period_length": 5
    },
    {
      "cycle_start_date": "2023-04-20",
      "period_length": 5
    }
  ],
  "current_date": "2023-05-15"
}
```

**Response:**
```json
{
  "message": "Cycle predictions generated successfully",
  "phase_mappings": [
    {
      "date": "2023-05-15",
      "phase": "Period",
      "phase_day_id": "p1"
    },
    {
      "date": "2023-05-16",
      "phase": "Period",
      "phase_day_id": "p2"
    },
    ...
  ],
  "current_phase": {
    "date": "2023-05-15",
    "phase": "Period",
    "phase_day_id": "p1"
  }
}
```

## Phase-Day ID System

### Period Phase (Menstrual)
- **IDs**: p1, p2, p3, ..., p12
- **Duration**: Typically 3-7 days (based on average_period_length)
- **Color**: Red/Pink

### Follicular Phase
- **IDs**: f1, f2, f3, ..., f30
- **Duration**: Variable (cycle length - period - ovulation - luteal)
- **Color**: Teal/Green

### Ovulation Phase
- **IDs**: o1, o2, o3, ..., o8
- **Duration**: Typically 5-8 days
- **Color**: Yellow

### Luteal Phase
- **IDs**: l1, l2, l3, ..., l25
- **Duration**: Typically 12-16 days
- **Color**: Purple

## How It Works

1. **User provides past cycle data** - At least 3-5 cycles recommended
2. **Backend calls Women's Health API** - Processes data and gets predictions
3. **Phase mapping generation** - Creates daily phase-day IDs
4. **Storage** - Mappings stored in `user_cycle_days` table
5. **Display** - Calendar shows phases with colors

## Usage in Frontend

### Example: Triggering Cycle Prediction

```javascript
import { predictCycles } from './utils/api'

const handlePredictCycles = async () => {
  const pastCycleData = [
    { cycle_start_date: "2023-01-05", period_length: 5 },
    { cycle_start_date: "2023-02-01", period_length: 4 },
    // ... more cycles
  ]
  
  const currentDate = new Date().toISOString().split('T')[0]
  
  try {
    const response = await predictCycles(pastCycleData, currentDate)
    console.log('Predictions generated:', response)
    // Refresh calendar and phase data
  } catch (error) {
    console.error('Prediction failed:', error)
  }
}
```

### Getting Current Phase

```javascript
import { getCurrentPhase } from './utils/api'

const fetchCurrentPhase = async () => {
  try {
    const phase = await getCurrentPhase()
    console.log('Current phase:', phase.phase, phase.phase_day_id)
  } catch (error) {
    console.error('Failed to get phase:', error)
  }
}
```

### Getting Phase Map for Calendar

```javascript
import { getPhaseMap } from './utils/api'

const fetchPhaseMap = async () => {
  const today = new Date()
  const startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1)
  const endDate = new Date(today.getFullYear(), today.getMonth() + 2, 0)
  
  try {
    const response = await getPhaseMap(
      startDate.toISOString().split('T')[0],
      endDate.toISOString().split('T')[0]
    )
    console.log('Phase map:', response.phase_map)
  } catch (error) {
    console.error('Failed to get phase map:', error)
  }
}
```

## Data Requirements

### Minimum Data
- At least 3 past cycles for basic predictions
- Cycle start dates (YYYY-MM-DD format)
- Period lengths (number of days)

### Recommended Data
- 5-6 cycles for better accuracy
- Consistent tracking over time
- Regular updates when new periods occur

## Integration with Wellness Data

Once phase-day IDs are generated, they're used to fetch:

1. **Hormone Data** - `/wellness/hormones?phase_day_id=p5`
2. **Nutrition Data** - `/wellness/nutrition?phase_day_id=f10&language=en&cuisine=south_indian`
3. **Exercise Data** - `/wellness/exercises?phase_day_id=o2&language=en&category=Yoga`

## Regenerating Predictions

Predictions should be regenerated when:
- User logs a new period start date
- User updates cycle length
- Significant time has passed (monthly recommended)
- User reports irregular cycles

## Error Handling

Common errors:
- **Insufficient data**: Need at least 3 cycles
- **Invalid dates**: Dates must be in YYYY-MM-DD format
- **API errors**: Check RapidAPI key and quota
- **Database errors**: Check Supabase connection

## Best Practices

1. **Store past cycle data** - Keep history in period_logs table
2. **Auto-regenerate** - Trigger predictions when new period logged
3. **Cache results** - Store phase mappings to reduce API calls
4. **Handle edge cases** - Irregular cycles, missing data
5. **User feedback** - Allow users to correct predictions

## Example Workflow

1. User registers and provides last_period_date
2. User logs 3-5 past periods through period logging
3. System automatically generates predictions
4. Calendar displays phases with colors
5. Wellness data shows phase-specific recommendations
6. User logs new period → predictions regenerate

