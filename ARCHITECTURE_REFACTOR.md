# Architecture Refactor: PeriodEvent-Based System

## Overview

This document describes the major architectural refactoring that transforms the system from storing cycles and predictions as semi-persistent state to a Flo-inspired architecture where:

- **Period logs = facts** (user input, immutable)
- **PeriodEvents = interpretation** (derived, stable layer)
- **Cycles = derived** (computed from PeriodEvents, never stored)
- **Predictions = cache** (user_cycle_days is a cache that can be fully regenerated)

## Core Problems Solved

### Problem 1: Editing Past Period Logs Invalidates Stored Days

**Before:** Storing `user_cycle_days` as truth meant that when a user logged a period late, historical rows became logically inconsistent even if preserved.

**After:** PeriodEvents are rebuilt whenever period_logs change. Cycles are derived from PeriodEvents. Predictions are regenerated from the last confirmed period.

### Problem 2: "Partial Update" Logic Was Brittle

**Before:** Complex logic tried to surgically preserve predictions with `update_future_only=True`, but this was fundamentally unsafe for biological systems.

**After:** Simple rule: If a period is logged → delete all predicted days after the previous confirmed period start. Regenerate everything. Predictions are cheap. Inconsistency is expensive.

### Problem 3: Cycles Didn't Exist as First-Class Entities

**Before:** Cycles were inferred in many places with no single authority defining "This is cycle #12" or "This cycle starts here".

**After:** PeriodEvents provide the anchor. Cycles are derived from PeriodEvents with a clear definition:
- Cycle.start = PeriodEvent[n].start_date
- Cycle.length = PeriodEvent[n+1].start_date - PeriodEvent[n].start_date

## New Architecture Components

### 1. PeriodEvent Layer (`backend/period_events.py`)

**Purpose:** Stable, derived layer that groups consecutive period days into period events.

**Key Functions:**
- `build_period_events(user_id)` - Groups consecutive bleeding days into periods
- `sync_period_events_to_db(user_id)` - Rebuilds PeriodEvents from period_logs and stores them
- `get_period_events(user_id, confirmed_only=False)` - Retrieves PeriodEvents from database
- `get_cycles_from_period_events(user_id)` - Derives cycles from PeriodEvents
- `get_last_confirmed_period_start(user_id)` - Gets anchor point for predictions

**PeriodEvent Schema:**
```sql
CREATE TABLE period_events (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    length INTEGER NOT NULL,
    is_confirmed BOOLEAN DEFAULT FALSE,  -- true if gap >= 1 non-bleeding day after
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 2. Cycle Statistics (`backend/cycle_stats.py`)

**Purpose:** Computes cycle statistics from PeriodEvents.

**Key Functions:**
- `compute_cycle_stats_from_period_events(user_id)` - Computes mean, SD, variance from PeriodEvents
- `update_user_cycle_stats(user_id)` - Updates user's cycle_length in users table

### 3. Prediction Cache (`backend/prediction_cache.py`)

**Purpose:** Manages user_cycle_days as a cache that can be fully regenerated.

**Key Functions:**
- `invalidate_predictions_after_period(user_id, period_start_date)` - Deletes all predicted days after a period start
- `regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=90)` - Regenerates predictions from last confirmed period

**New Rule:** If a period is logged → delete all predicted days after the previous confirmed period start. Regenerate everything.

### 4. Luteal Learning (`backend/luteal_learning.py`)

**Purpose:** Learns luteal phase length from confirmed PeriodEvents only.

**Key Functions:**
- `compute_observed_luteal_from_confirmed_cycles(user_id, new_period_start)` - Computes observed luteal only from confirmed cycles
- `learn_luteal_from_new_period(user_id, new_period_start)` - Updates luteal estimate if conditions are met

**Critical Rules:**
1. Only compute if we have at least 2 confirmed PeriodEvents
2. Only use ovulation that was predicted BEFORE the new period log
3. Only use high-confidence ovulation predictions (ovulation_sd <= 1.5)

This prevents training on:
- Shifted predictions from partial updates
- Low-confidence ovulation predictions
- Stress cycles, PCOS patterns, anovulatory cycles

## Simplified Period Logging Flow

### Before (Complex):
1. Save period log
2. Detect early/late period
3. Calculate cycle length
4. Predict ovulation for previous cycle
5. Calculate observed luteal
6. Confidence gate luteal update
7. Partial regeneration with `update_future_only`
8. Complex logic to preserve past data

### After (Simple):
1. **Save daily bleeding log**
2. **Rebuild PeriodEvents** (`sync_period_events_to_db`)
3. **Recompute cycle stats** (`update_user_cycle_stats`)
4. **Mark future predictions as dirty** (`invalidate_predictions_after_period`)
5. **Regenerate predictions from last confirmed period** (`regenerate_predictions_from_last_confirmed_period`)
6. **Asynchronous luteal learning** (non-blocking, `learn_luteal_from_new_period`)

Luteal updates happen asynchronously and don't block the UX.

## Database Migration

Run the migration to create the `period_events` table:

```sql
-- See: database/migrations/add_period_events.sql
```

## Updated Endpoints

### POST `/periods/log`

**New Flow:**
1. Saves period log
2. Rebuilds PeriodEvents
3. Recomputes cycle stats
4. Invalidates predictions after last confirmed period
5. Regenerates predictions
6. Asynchronously learns luteal (non-blocking)

### GET `/cycles/health-check`

**Updated:** Now uses PeriodEvents and derived cycles instead of directly processing period_logs.

## Key Principles

1. **Period logs = facts** - User input, immutable
2. **PeriodEvents = interpretation** - Derived, stable layer that groups consecutive days
3. **Cycles = derived** - Computed from PeriodEvents, never stored permanently
4. **Predictions = cache** - user_cycle_days is a cache that can be fully regenerated
5. **Predictions are cheap. Inconsistency is expensive.** - Full regeneration is preferred over partial updates

## Benefits

1. **Consistency:** No more logically inconsistent historical rows
2. **Simplicity:** Removed complex partial update logic
3. **Reliability:** Single source of truth (PeriodEvents) for cycle boundaries
4. **Maintainability:** Clear separation of concerns
5. **Medical Credibility:** Luteal learning only from confirmed cycles with high-confidence predictions

## Migration Notes

- Existing `user_cycle_days` data will be regenerated on next period log
- PeriodEvents will be built automatically when period logs are synced
- No data loss - all period_logs are preserved
- Cycle statistics will be recomputed from PeriodEvents

## Future Enhancements

1. Add analytics logging for skipped luteal updates
2. Consider versioning for PeriodEvents (track changes over time)
3. Add background job to periodically rebuild PeriodEvents for all users
4. Enhance luteal learning with LH/BBT markers when available
