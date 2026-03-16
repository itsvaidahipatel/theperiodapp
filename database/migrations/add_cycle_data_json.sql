-- Migration: Add cycle_data_json to period_start_logs for Immutable Past
-- Stores phase mappings for completed cycles (one cycle per period start)
-- When a new period is logged, the completed cycle's phases are saved here

ALTER TABLE period_start_logs
ADD COLUMN IF NOT EXISTS cycle_data_json JSONB DEFAULT NULL;

COMMENT ON COLUMN period_start_logs.cycle_data_json IS 'Immutable phase mappings for the completed cycle ending at the next period start. Array of {date, phase, phase_day_id, ...}. Never overwritten once set.';
