# Clean Email Notification System

## Overview

This document describes the clean email notification system that implements exactly 3 email types with respectful, non-spam behavior.

## Email Types

### 1️⃣ Upcoming Period Reminder
**Purpose:** Heads-up, planning, mental prep

**Trigger:**
- Predicted period start is approaching

**When:**
- 7 days before (optional)
- 3 days before (optional)

**Rules:**
- Max 1–2 emails per cycle
- Sent only if email notifications are enabled
- Respects user preferences

**Example tone:**
"Your next period is expected around Jan 14. Just a gentle reminder 💙"

### 2️⃣ Period Logging Reminder (Most Important)
**Purpose:** Remind user to log period during predicted window

**Trigger:**
- User is in predicted period window
- Period has not been logged yet

**When:**
- Once per day during predicted period

**Stop Conditions (CRITICAL):**
- User logs period → all future reminders canceled
- Period window ends → reminders stop

**Anti-spam rules:**
- Max 1 per day
- Only during predicted period days
- Auto-stop immediately on log

**Example:**
"Don't forget to log your period if it has started today 🌸"

### 3️⃣ Health / Anomaly Alert (Rare, Respectful)
**Purpose:** Awareness, not alarm

**Triggers (examples):**
- Cycle length consistently <21 or >45 days
- Period length >8 days for multiple cycles
- High irregularity (CV ≥ 25%)
- Missed periods / long gaps (>60 days)

**Rules:**
- Max 1 per cycle
- Never sent repeatedly
- Never diagnostic

**Tone:**
"We noticed a pattern in your recent cycles that's worth keeping an eye on. This doesn't necessarily mean something is wrong."

**Always includes:**
"This is not medical advice."

## Profile Settings

In Profile → Notifications:

**Email Notifications**
- ☑ Receive emails (master switch)

**What would you like to receive?**
- ☑ Upcoming period reminders
- ☑ Period logging reminders
- ☑ Health insights / anomaly alerts

**Optional:**
- "Pause emails for X days" (date picker)
- "Snooze reminders this cycle" (checkbox)

**Unsubscribe:**
- Turn off "Receive emails" to unsubscribe from all emails
- Unsubscribe link in every email

## Email Logic

### Daily Background Job

Every day at 9 AM UTC:

1. Check users with email enabled
2. For each user:
   - Check if emails are paused or snoozed
   - Enforce max 1 email/day
   - Check upcoming period → maybe send reminder
   - Check if in predicted period & not logged → send log reminder
   - Check anomaly detected & not sent this cycle → send alert

**Enforce:**
- 1 email/day max
- No duplicates
- Auto-cancel on log
- Respect pause/snooze settings

## Database Schema

### New Columns in `users` table:

```sql
-- Email tracking
last_email_sent_date DATE DEFAULT NULL
last_anomaly_email_cycle_start DATE DEFAULT NULL

-- Updated notification_preferences JSONB structure:
{
  "upcoming_reminders": true,
  "logging_reminders": true,
  "health_alerts": true,
  "pause_emails_until": null,  -- DATE string or null
  "snooze_this_cycle": false
}
```

## Implementation Files

### Backend:
- `backend/email_service.py` - Email templates and sending
- `backend/notification_service.py` - Daily job and email logic
- `backend/routes/user.py` - API endpoints for notification preferences
- `database/add_email_notification_preferences.sql` - Database migration

### Frontend:
- `frontend/src/pages/Profile.jsx` - Notification settings UI

## Safety & Trust Rules (Non-Negotiable)

✅ Clear unsubscribe in every email
✅ Never send multiple emails same day
✅ Never shame or scare
✅ Never diagnose
✅ Always explain why user got the email
✅ Auto-stop reminders when period is logged
✅ Respect user preferences
✅ Max 1 anomaly email per cycle

## Email Service Configuration

The system uses Gmail SMTP (free tier) by default. Configure via environment variables:

```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Gmail App Password, not regular password
FROM_EMAIL=your-email@gmail.com
APP_NAME=PeriodCycle.AI
```

**Recommended alternatives:**
- SendGrid (transactional emails)
- Resend (modern, developer-friendly)

## Testing

To test the email system:

1. Enable email notifications in Profile
2. Set up SMTP credentials
3. Wait for daily job (or trigger manually)
4. Verify emails are sent correctly
5. Test unsubscribe functionality
6. Test pause/snooze features
7. Verify auto-stop on period log

## Migration

Run the database migration:

```sql
-- Run database/add_email_notification_preferences.sql
```

This will:
- Add new columns for email tracking
- Update notification_preferences structure
- Preserve existing user preferences (backward compatible)

## Summary

✅ Only 3 email types
✅ Respectful, non-spam behavior
✅ User control (unsubscribe, pause, snooze)
✅ Auto-stop on period log
✅ Max 1 email/day enforcement
✅ Health alerts are rare and respectful
✅ Clear unsubscribe in every email

This is exactly how a respectful health app should behave.
