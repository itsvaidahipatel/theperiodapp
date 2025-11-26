-- Migration: Add luteal phase tracking fields to users table
-- These fields support adaptive luteal phase estimation

-- Add luteal_observations column (JSON array of observed luteal lengths)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_observations TEXT DEFAULT NULL;

-- Add luteal_mean column (current estimated mean)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_mean FLOAT DEFAULT 14.0;

-- Add luteal_sd column (current estimated standard deviation)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS luteal_sd FLOAT DEFAULT 2.0;

-- Add comments
COMMENT ON COLUMN users.luteal_observations IS 'JSON array of observed luteal phase lengths (last 12 cycles)';
COMMENT ON COLUMN users.luteal_mean IS 'Current estimated mean luteal phase length (Bayesian smoothed)';
COMMENT ON COLUMN users.luteal_sd IS 'Current estimated standard deviation of luteal phase length';

-- Note: Existing records will have default values (mean=14.0, sd=2.0)
-- The system will update these as users log periods





