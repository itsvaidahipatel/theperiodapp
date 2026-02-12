-- Add avg_bleeding_days to users table (typical bleeding length in days, 2-8+)
-- Run in Supabase SQL editor

ALTER TABLE users
ADD COLUMN IF NOT EXISTS avg_bleeding_days INTEGER DEFAULT 5;

COMMENT ON COLUMN users.avg_bleeding_days IS 'User-reported typical bleeding length in days (2-8). Used to auto-set period end_date when logging start.';

-- Backfill existing users without the column (handled by DEFAULT 5)
