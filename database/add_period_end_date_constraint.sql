-- Migration: Add CHECK constraint for period_logs.end_date
-- Ensures end_date >= start_date when end_date is not NULL
-- This is a safety constraint to prevent invalid date ranges
--
-- PREREQUISITE: Run add_period_end_date_and_outliers.sql first to add the end_date column

-- First, ensure the end_date column exists (in case prerequisite migration wasn't run)
DO $$
BEGIN
    -- Check if end_date column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'period_logs' 
        AND column_name = 'end_date'
    ) THEN
        -- Add end_date column if it doesn't exist
        ALTER TABLE period_logs
        ADD COLUMN end_date DATE DEFAULT NULL;
        
        ALTER TABLE period_logs
        ADD COLUMN is_manual_end BOOLEAN DEFAULT FALSE;
        
        RAISE NOTICE 'Added end_date and is_manual_end columns to period_logs';
    ELSE
        RAISE NOTICE 'end_date column already exists, skipping column creation';
    END IF;
END $$;

-- Now add the CHECK constraint
DO $$
BEGIN
    -- Check if constraint already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'period_logs_end_date_check'
        AND conrelid = 'period_logs'::regclass
    ) THEN
        -- Add CHECK constraint: end_date IS NULL OR end_date >= date (start_date)
        ALTER TABLE period_logs
        ADD CONSTRAINT period_logs_end_date_check 
        CHECK (end_date IS NULL OR end_date >= date);
        
        RAISE NOTICE 'Added CHECK constraint period_logs_end_date_check';
    ELSE
        RAISE NOTICE 'Constraint period_logs_end_date_check already exists, skipping';
    END IF;
END $$;

-- Add comment explaining the constraint (if it exists)
COMMENT ON CONSTRAINT period_logs_end_date_check ON period_logs IS 
'Ensures end_date is either NULL (optional) or >= start_date (date column)';
