-- Migration: Add optional source and confidence columns to user_cycle_days table
-- These columns are optional and will be NULL for existing records
-- The application will work without these columns (graceful degradation)

-- Add source column (optional, can be NULL)
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT NULL;

-- Add confidence column (optional, can be NULL)
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT NULL;

-- Add comment to explain the columns
COMMENT ON COLUMN user_cycle_days.source IS 'Data source: api, adjusted, or fallback';
COMMENT ON COLUMN user_cycle_days.confidence IS 'Confidence score: 1.0 (API), 0.7 (adjusted), 0.5 (fallback)';

-- Note: Existing records will have NULL for these columns, which is fine
-- The application handles NULL gracefully





