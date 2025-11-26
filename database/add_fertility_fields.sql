-- Migration: Add optional fertility tracking fields to user_cycle_days table
-- These fields are OPTIONAL - fertility probabilities are calculated on-the-fly if not stored
-- Storing them improves performance but is not required

-- Add fertility_prob column (optional, can be NULL)
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS fertility_prob FLOAT DEFAULT NULL;

-- Add predicted_ovulation_date column (optional, can be NULL)
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS predicted_ovulation_date DATE DEFAULT NULL;

-- Add luteal_estimate column (optional, can be NULL)
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS luteal_estimate FLOAT DEFAULT NULL;

-- Add ovulation_sd column (optional, can be NULL)
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS ovulation_sd FLOAT DEFAULT NULL;

-- Add comments
COMMENT ON COLUMN user_cycle_days.fertility_prob IS 'Fertility probability (0.0-1.0) for this day';
COMMENT ON COLUMN user_cycle_days.predicted_ovulation_date IS 'Predicted ovulation date for this cycle';
COMMENT ON COLUMN user_cycle_days.luteal_estimate IS 'Luteal phase estimate used for this prediction';
COMMENT ON COLUMN user_cycle_days.ovulation_sd IS 'Standard deviation of ovulation prediction';

-- Note: Existing records will have NULL for these columns
-- The application calculates these values on-the-fly if not stored
-- Storing them improves performance but is optional





