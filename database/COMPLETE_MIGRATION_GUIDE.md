# Complete Database Migration Guide

## Overview
This guide lists all database changes needed for the adaptive cycle prediction system.

---

## 📋 Required Database Changes

### 1. **Users Table** - Add Luteal Phase Tracking Fields

**Migration Script**: `database/add_luteal_fields.sql`

**New Columns**:
```sql
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_observations TEXT DEFAULT NULL;

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_mean FLOAT DEFAULT 14.0;

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_sd FLOAT DEFAULT 2.0;
```

**Purpose**:
- `luteal_observations`: JSON array storing last 12 observed luteal phase lengths
- `luteal_mean`: Current estimated mean luteal phase length (Bayesian smoothed)
- `luteal_sd`: Current estimated standard deviation of luteal phase length

**Default Values**:
- `luteal_mean = 14.0` (population prior)
- `luteal_sd = 2.0` (population prior)
- `luteal_observations = NULL` (empty for new users)

---

### 2. **user_cycle_days Table** - Add Source and Confidence Tracking

**Migration Script**: `database/add_confidence_source_columns.sql`

**New Columns**:
```sql
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT NULL;

ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT NULL;
```

**Purpose**:
- `source`: Tracks data source - "api" | "adjusted" | "fallback"
- `confidence`: Confidence score - 0.4 (fallback) | 0.7 (adjusted) | 0.9 (API)

**Note**: These columns are **optional**. The application works without them (graceful degradation).

---

### 3. **user_cycle_days Table** - Optional: Add Fertility Fields

**Status**: ⚠️ **OPTIONAL** - These fields are calculated on-the-fly and returned in API responses, but can be stored for faster retrieval.

**New Columns** (if you want to store them):
```sql
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS fertility_prob FLOAT DEFAULT NULL;

ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS predicted_ovulation_date DATE DEFAULT NULL;

ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS luteal_estimate FLOAT DEFAULT NULL;

ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS ovulation_sd FLOAT DEFAULT NULL;
```

**Purpose**:
- `fertility_prob`: Fertility probability (0.0-1.0) for this day
- `predicted_ovulation_date`: Predicted ovulation date for this cycle
- `luteal_estimate`: Luteal phase estimate used for this prediction
- `ovulation_sd`: Standard deviation of ovulation prediction

**Note**: These are **NOT required**. The system calculates them on-the-fly when needed. Storing them is optional but can improve performance.

---

## 🚀 Migration Execution Order

### Step 1: Run Luteal Fields Migration (REQUIRED)
```sql
-- Execute: database/add_luteal_fields.sql
```
This is **required** for adaptive luteal phase estimation to work.

### Step 2: Run Source/Confidence Migration (RECOMMENDED)
```sql
-- Execute: database/add_confidence_source_columns.sql
```
This is **recommended** for tracking data quality and source.

### Step 3: Run Fertility Fields Migration (OPTIONAL)
```sql
-- Execute: database/add_fertility_fields.sql (create this if you want to store fertility data)
```
This is **optional** - only needed if you want to store fertility probabilities in the database.

---

## 📊 Complete Migration Script

Here's a combined migration script you can run:

```sql
-- ============================================
-- COMPLETE DATABASE MIGRATION
-- Adaptive Cycle Prediction System
-- ============================================

-- ============================================
-- 1. USERS TABLE - Luteal Phase Tracking
-- ============================================
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_observations TEXT DEFAULT NULL;

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_mean FLOAT DEFAULT 14.0;

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_sd FLOAT DEFAULT 2.0;

COMMENT ON COLUMN users.luteal_observations IS 'JSON array of observed luteal phase lengths (last 12 cycles)';
COMMENT ON COLUMN users.luteal_mean IS 'Current estimated mean luteal phase length (Bayesian smoothed)';
COMMENT ON COLUMN users.luteal_sd IS 'Current estimated standard deviation of luteal phase length';

-- ============================================
-- 2. USER_CYCLE_DAYS TABLE - Source & Confidence
-- ============================================
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT NULL;

ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT NULL;

COMMENT ON COLUMN user_cycle_days.source IS 'Data source: api, adjusted, or fallback';
COMMENT ON COLUMN user_cycle_days.confidence IS 'Confidence score: 1.0 (API), 0.7 (adjusted), 0.5 (fallback)';

-- ============================================
-- 3. USER_CYCLE_DAYS TABLE - Fertility Fields (OPTIONAL)
-- ============================================
-- Uncomment these if you want to store fertility data in the database
-- Otherwise, they are calculated on-the-fly

-- ALTER TABLE user_cycle_days 
-- ADD COLUMN IF NOT EXISTS fertility_prob FLOAT DEFAULT NULL;

-- ALTER TABLE user_cycle_days 
-- ADD COLUMN IF NOT EXISTS predicted_ovulation_date DATE DEFAULT NULL;

-- ALTER TABLE user_cycle_days 
-- ADD COLUMN IF NOT EXISTS luteal_estimate FLOAT DEFAULT NULL;

-- ALTER TABLE user_cycle_days 
-- ADD COLUMN IF NOT EXISTS ovulation_sd FLOAT DEFAULT NULL;

-- COMMENT ON COLUMN user_cycle_days.fertility_prob IS 'Fertility probability (0.0-1.0) for this day';
-- COMMENT ON COLUMN user_cycle_days.predicted_ovulation_date IS 'Predicted ovulation date for this cycle';
-- COMMENT ON COLUMN user_cycle_days.luteal_estimate IS 'Luteal phase estimate used for this prediction';
-- COMMENT ON COLUMN user_cycle_days.ovulation_sd IS 'Standard deviation of ovulation prediction';

-- ============================================
-- VERIFICATION
-- ============================================
-- Run these queries to verify the migration:

-- Check users table columns
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('luteal_observations', 'luteal_mean', 'luteal_sd');

-- Check user_cycle_days table columns
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'user_cycle_days' 
AND column_name IN ('source', 'confidence', 'fertility_prob', 'predicted_ovulation_date', 'luteal_estimate', 'ovulation_sd');
```

---

## ✅ Summary

### Required Changes:
1. ✅ **Users table**: Add `luteal_observations`, `luteal_mean`, `luteal_sd`
   - **File**: `database/add_luteal_fields.sql`
   - **Status**: REQUIRED

2. ✅ **user_cycle_days table**: Add `source`, `confidence`
   - **File**: `database/add_confidence_source_columns.sql`
   - **Status**: RECOMMENDED (optional but useful)

### Optional Changes:
3. ⚠️ **user_cycle_days table**: Add fertility fields
   - **File**: Create `database/add_fertility_fields.sql` if needed
   - **Status**: OPTIONAL (calculated on-the-fly)

---

## 🔍 Current Database Schema

### Users Table (Existing + New)
- `id` (UUID, PRIMARY KEY)
- `name` (TEXT)
- `email` (TEXT, UNIQUE)
- `password_hash` (TEXT)
- `last_period_date` (DATE)
- `cycle_length` (INTEGER)
- `language` (TEXT)
- `favorite_cuisine` (TEXT)
- `favorite_exercise` (TEXT)
- `interests` (ARRAY)
- `created_at` (TIMESTAMP)
- **NEW**: `luteal_observations` (TEXT, JSON array)
- **NEW**: `luteal_mean` (FLOAT, default 14.0)
- **NEW**: `luteal_sd` (FLOAT, default 2.0)

### user_cycle_days Table (Existing + New)
- `user_id` (UUID, FOREIGN KEY)
- `date` (DATE)
- `phase` (VARCHAR(50))
- `phase_day_id` (VARCHAR(10))
- `PRIMARY KEY (user_id, date)`
- **NEW**: `source` (VARCHAR(20), optional)
- **NEW**: `confidence` (FLOAT, optional)
- **OPTIONAL**: `fertility_prob` (FLOAT, optional)
- **OPTIONAL**: `predicted_ovulation_date` (DATE, optional)
- **OPTIONAL**: `luteal_estimate` (FLOAT, optional)
- **OPTIONAL**: `ovulation_sd` (FLOAT, optional)

---

## 🎯 What Happens Without Migrations

### Without Luteal Fields (Users Table):
- ❌ Adaptive luteal estimation won't work
- ❌ System will use default 14 days (no learning)
- ⚠️ **This migration is REQUIRED**

### Without Source/Confidence (user_cycle_days):
- ✅ System still works
- ⚠️ Can't track data quality
- ⚠️ Can't distinguish API vs fallback data
- ✅ **This migration is OPTIONAL but recommended**

### Without Fertility Fields (user_cycle_days):
- ✅ System still works
- ✅ Fertility probabilities calculated on-the-fly
- ⚠️ Slightly slower (recalculation each time)
- ✅ **This migration is OPTIONAL**

---

## 📝 Migration Execution

### For Supabase:

1. **Open Supabase Dashboard**
2. **Go to SQL Editor**
3. **Run the migration scripts in order**:
   - First: `database/add_luteal_fields.sql` (REQUIRED)
   - Second: `database/add_confidence_source_columns.sql` (RECOMMENDED)
   - Third: `database/add_fertility_fields.sql` (OPTIONAL - create if needed)

### For PostgreSQL (Direct):

```bash
psql -U your_user -d your_database -f database/add_luteal_fields.sql
psql -U your_user -d your_database -f database/add_confidence_source_columns.sql
```

---

## ✅ Verification Checklist

After running migrations, verify:

- [ ] `users.luteal_observations` column exists
- [ ] `users.luteal_mean` column exists (default 14.0)
- [ ] `users.luteal_sd` column exists (default 2.0)
- [ ] `user_cycle_days.source` column exists
- [ ] `user_cycle_days.confidence` column exists
- [ ] Existing records have NULL for new columns (expected)
- [ ] New predictions populate the new columns correctly

---

## 🚨 Important Notes

1. **Backward Compatibility**: All new columns are optional (NULL allowed)
2. **Default Values**: Existing users get defaults (luteal_mean=14.0, luteal_sd=2.0)
3. **No Data Loss**: Migrations use `ADD COLUMN IF NOT EXISTS` (safe)
4. **Graceful Degradation**: System works without optional columns
5. **Performance**: Storing fertility fields improves performance but is optional

---

## 📞 Need Help?

If migrations fail:
1. Check Supabase logs for errors
2. Verify column names don't conflict
3. Ensure you have ALTER TABLE permissions
4. Check if columns already exist (use `IF NOT EXISTS`)





