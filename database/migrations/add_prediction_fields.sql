-- Migration: Add prediction fields and cache RapidAPI request_id
-- Run this in your Supabase SQL editor

-- Add new columns to user_cycle_days table
ALTER TABLE user_cycle_days 
ADD COLUMN IF NOT EXISTS prediction_confidence FLOAT,
ADD COLUMN IF NOT EXISTS ovulation_offset INTEGER,
ADD COLUMN IF NOT EXISTS is_predicted BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS rapidapi_request_id VARCHAR(255);

-- Rename old confidence column to prediction_confidence (if it exists)
-- Note: If confidence column doesn't exist, this will fail gracefully
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_cycle_days' AND column_name = 'confidence'
    ) THEN
        ALTER TABLE user_cycle_days RENAME COLUMN confidence TO prediction_confidence;
    END IF;
END $$;

-- Add index on rapidapi_request_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_request_id 
ON user_cycle_days(rapidapi_request_id) 
WHERE rapidapi_request_id IS NOT NULL;

-- Add index on is_predicted for filtering
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_is_predicted 
ON user_cycle_days(is_predicted);

-- Add rapidapi_request_id to users table for caching
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS rapidapi_request_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS rapidapi_request_id_expires_at TIMESTAMP WITH TIME ZONE;

-- Add index on users.rapidapi_request_id
CREATE INDEX IF NOT EXISTS idx_users_request_id 
ON users(rapidapi_request_id) 
WHERE rapidapi_request_id IS NOT NULL;

-- Add comment explaining the fields
COMMENT ON COLUMN user_cycle_days.prediction_confidence IS 'Confidence level of the prediction (0.0-1.0). Higher values indicate more reliable predictions.';
COMMENT ON COLUMN user_cycle_days.ovulation_offset IS 'Days from cycle start to predicted ovulation (integer). Calculated as cycle_length - luteal_mean.';
COMMENT ON COLUMN user_cycle_days.is_predicted IS 'TRUE if this is a predicted phase, FALSE if based on logged period data.';
COMMENT ON COLUMN user_cycle_days.rapidapi_request_id IS 'RapidAPI request_id used to generate this prediction. Used for caching and reducing API calls.';
COMMENT ON COLUMN users.rapidapi_request_id IS 'Cached RapidAPI request_id for this user. Reduces API calls by reusing request_id across multiple predictions.';
COMMENT ON COLUMN users.rapidapi_request_id_expires_at IS 'Expiration timestamp for cached request_id. Request_id expires after 24 hours or when cycle data changes.';
