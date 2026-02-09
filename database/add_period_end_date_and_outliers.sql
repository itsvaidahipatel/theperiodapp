-- Migration: Add period end date support and outlier detection
-- This enables users to log both period start and end dates

-- Add end_date and is_manual_end columns to period_logs
ALTER TABLE period_logs
ADD COLUMN IF NOT EXISTS end_date DATE DEFAULT NULL;

ALTER TABLE period_logs
ADD COLUMN IF NOT EXISTS is_manual_end BOOLEAN DEFAULT FALSE;

-- Add is_outlier column to period_start_logs for outlier detection
ALTER TABLE period_start_logs
ADD COLUMN IF NOT EXISTS is_outlier BOOLEAN DEFAULT FALSE;

-- Add index for faster queries on end_date
CREATE INDEX IF NOT EXISTS idx_period_logs_end_date ON period_logs(user_id, end_date);

-- Add index for outlier queries
CREATE INDEX IF NOT EXISTS idx_period_start_logs_outlier ON period_start_logs(user_id, is_outlier);

-- Update existing period_logs: set end_date to NULL (will use estimated period length)
-- This is safe because the code already handles NULL end_date

COMMENT ON COLUMN period_logs.end_date IS 'Manual end date logged by user. If NULL, system uses estimated_period_length.';
COMMENT ON COLUMN period_logs.is_manual_end IS 'True if user manually clicked "Period Ended", false if using AI estimate.';
COMMENT ON COLUMN period_start_logs.is_outlier IS 'True if cycle length is outside Mean ± 2×SD (outlier detection).';
