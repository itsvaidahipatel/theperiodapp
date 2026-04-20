-- Migration: Add push notification preference tracking columns
-- Supports 3 push types: Upcoming reminders, Logging reminders, Health alerts

-- Update notification_preferences JSONB structure
-- New structure:
-- {
--   "upcoming_reminders": true,
--   "logging_reminders": true,
--   "health_alerts": true,
--   "pause_emails_until": null,  -- DATE string or null
--   "snooze_this_cycle": false
-- }

-- Add columns to track push sending
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS last_notification_sent_date DATE DEFAULT NULL;

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS last_anomaly_notification_cycle_start DATE DEFAULT NULL;

-- Add comments
COMMENT ON COLUMN users.last_notification_sent_date IS 'Date when last push notification was sent (to enforce max 1 push/day)';
COMMENT ON COLUMN users.last_anomaly_notification_cycle_start IS 'Start date of cycle when last anomaly push was sent (to enforce max 1 per cycle)';

-- Update existing notification_preferences to new structure
-- This migration preserves existing preferences but adds new fields
UPDATE users
SET notification_preferences = COALESCE(
  notification_preferences::jsonb,
  '{}'::jsonb
) || jsonb_build_object(
  'upcoming_reminders', COALESCE((notification_preferences->>'period_reminders')::boolean, true),
  'logging_reminders', COALESCE((notification_preferences->>'period_reminders')::boolean, true),
  'health_alerts', true,
  'pause_emails_until', NULL,
  'snooze_this_cycle', false
)
WHERE notification_preferences IS NULL 
   OR NOT (notification_preferences ? 'upcoming_reminders');

-- Note: Existing users will have all notification types enabled by default
-- Users can customize in Profile → Notifications
