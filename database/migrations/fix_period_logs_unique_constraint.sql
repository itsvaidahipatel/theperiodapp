-- Migration: Fix period_logs unique constraint
-- The database has a unique constraint on user_id only, but it should be on (user_id, date)
-- This allows multiple period logs per user (one per date)

-- Step 1: Drop the old unique constraint on user_id if it exists
DO $$
BEGIN
    -- Check if the constraint exists and drop it
    IF EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'period_logs_user_id_key'
    ) THEN
        ALTER TABLE period_logs DROP CONSTRAINT period_logs_user_id_key;
        RAISE NOTICE 'Dropped old unique constraint on user_id';
    END IF;
END $$;

-- Step 2: Ensure the correct unique constraint on (user_id, date) exists
-- This allows multiple period logs per user, but only one per date
DO $$
BEGIN
    -- Check if the constraint already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'period_logs_user_id_date_key'
    ) THEN
        ALTER TABLE period_logs ADD CONSTRAINT period_logs_user_id_date_key UNIQUE (user_id, date);
        RAISE NOTICE 'Added unique constraint on (user_id, date)';
    ELSE
        RAISE NOTICE 'Unique constraint on (user_id, date) already exists';
    END IF;
END $$;

-- Verify the constraint
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conrelid = 'period_logs'::regclass
AND contype = 'u';
