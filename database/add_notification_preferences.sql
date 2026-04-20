-- Migration: Add notification preferences to users table
-- Supports Smart Notification Agent feature

-- Add push_notifications_enabled column (master switch)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS push_notifications_enabled BOOLEAN DEFAULT true;

-- Add fcm_token for mobile push delivery
ALTER TABLE users
ADD COLUMN IF NOT EXISTS fcm_token TEXT;

-- Add notification_preferences column (JSONB for flexible settings)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS notification_preferences JSONB DEFAULT '{
  "phase_transitions": true,
  "period_reminders": true,
  "reminder_days_before": 2,
  "preferred_notification_time": "09:00",
  "timezone": "Asia/Kolkata"
}'::jsonb;

-- Add last_phase_notification column (to track last notified phase)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS last_phase_notification VARCHAR(50) DEFAULT NULL;

-- Add last_phase_notification_date column (to track when last phase notification was sent)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS last_phase_notification_date DATE DEFAULT NULL;

-- Add comments
COMMENT ON COLUMN users.push_notifications_enabled IS 'Master switch for all push notifications';
COMMENT ON COLUMN users.fcm_token IS 'FCM device token for Firebase push notifications';
COMMENT ON COLUMN users.notification_preferences IS 'JSONB object with notification preferences (phase_transitions, period_reminders, reminder_days_before, preferred_notification_time, timezone)';
COMMENT ON COLUMN users.last_phase_notification IS 'Last phase for which a notification was sent (to avoid duplicate phase transition alerts)';
COMMENT ON COLUMN users.last_phase_notification_date IS 'Date when the last phase notification was sent';

-- Note: Existing users will have push_notifications_enabled = true by default
-- Users can disable notifications in their profile settings
