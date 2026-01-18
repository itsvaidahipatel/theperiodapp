# Smart Notification Agent Setup Guide

## Overview
The Smart Notification Agent sends email notifications for:
1. **Phase Transition Alerts**: Notifies users when they enter a new menstrual cycle phase
2. **Period Prediction Reminders**: Sends reminders before predicted period start dates

All notifications are sent via **Gmail SMTP (free, no cost)**.

---

## 🗄️ Database Setup

### Step 1: Run Migration
Run the SQL migration to add notification preference columns to the `users` table:

```sql
-- File: database/add_notification_preferences.sql
-- Run this in your Supabase SQL Editor
```

This adds:
- `email_notifications_enabled` (BOOLEAN, default: true)
- `notification_preferences` (JSONB)
- `last_phase_notification` (VARCHAR, for tracking)
- `last_phase_notification_date` (DATE, for tracking)

---

## 📧 Email Configuration (Free Gmail SMTP)

### Step 1: Create Gmail App Password

1. Go to your Google Account: https://myaccount.google.com
2. Navigate to **Security** → **2-Step Verification** (enable if not already)
3. Scroll down to **App passwords**
4. Create a new app password:
   - Select app: **Mail**
   - Select device: **Other (Custom name)** → Enter "PeriodCycle.AI"
   - Click **Generate**
   - **Copy the 16-character password** (you won't see it again!)

### Step 2: Set Environment Variables

Add these to your **Railway backend environment variables** (or `.env` for local):

```env
# Gmail SMTP Configuration (FREE)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com          # Your Gmail address
SMTP_PASSWORD=your-16-char-app-password     # Gmail App Password (NOT your regular password!)
FROM_EMAIL=your-email@gmail.com             # Usually same as SMTP_USERNAME
APP_NAME=PeriodCycle.AI                     # Display name in emails
```

**Important Notes:**
- ⚠️ **Never use your regular Gmail password** - use the App Password
- ✅ Gmail free tier allows **500 emails/day** (plenty for notifications)
- ✅ No cost - completely free
- ✅ Scalable - upgrade to Google Workspace if needed (higher limits)

---

## 🔧 Backend Setup

### Step 1: Install Dependencies

The notification system uses **APScheduler** (free) for scheduling:

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- `apscheduler==3.10.4` (free Python scheduler)

### Step 2: Start Backend

The notification scheduler **automatically starts** when the FastAPI app starts:

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000
```

You should see:
```
✅ Notification scheduler started
✅ Smart Notification Agent started
```

---

## 📋 How It Works

### Notification Schedule

- **Daily Check**: Runs at 6:00 AM UTC (adjusts to user's preferred time)
- **Phase Transitions**: Checks if user entered a new phase → sends email
- **Period Reminders**: Checks if user's period is coming → sends email X days before

### Notification Logic

#### Phase Transition Alerts
- Triggered when user enters a new cycle phase (Period → Follicular → Ovulation → Luteal)
- Only sends once per phase transition
- Includes phase-specific tips and recommendations
- Respects user's language preference (English/Hindi/Gujarati)

#### Period Reminders
- Sends X days before predicted period start (default: 2 days)
- Only sends if `period_reminders` is enabled in preferences
- Uses cycle prediction data to calculate next period date

---

## 🎨 Frontend Setup

### Notification Settings UI

Users can manage notifications in **Profile → Notifications** tab:

1. **Enable/Disable All Notifications**: Master toggle
2. **Phase Transition Alerts**: Toggle on/off
3. **Period Reminders**: Toggle on/off
4. **Reminder Days Before**: Choose 1-5 days before period

All settings are saved immediately and applied to future notifications.

---

## 🧪 Testing

### Test Phase Transition Notification

1. Set user's `last_phase_notification` to a different phase in database
2. Wait for daily check (or manually trigger)
3. Should receive email when phase changes

### Test Period Reminder

1. Set user's `last_period_date` in database
2. Ensure period is predicted in 1-5 days
3. Should receive reminder email

### Manual Testing (Optional)

You can manually trigger the notification check:

```python
from notification_service import notification_service

# Check all users
await notification_service.check_all_notifications()

# Check specific user
await notification_service.check_user_notifications(user_dict)
```

---

## 📊 Monitoring

### Check Notification Status

The scheduler logs to console:
- `🔔 Running daily notification check at {datetime}`
- `✅ Phase transition notification sent to {email}`
- `✅ Period reminder sent to {email}`
- `❌ Error checking notifications for user {id}`

### Database Queries

```sql
-- Check users with notifications enabled
SELECT id, email, email_notifications_enabled, notification_preferences 
FROM users 
WHERE email_notifications_enabled = true;

-- Check last notified phase
SELECT id, email, last_phase_notification, last_phase_notification_date 
FROM users;
```

---

## 🚀 Scalability

### Current Setup (Free)
- ✅ **Gmail SMTP**: 500 emails/day (free tier)
- ✅ **APScheduler**: Handles 1000+ users easily
- ✅ **Async processing**: Non-blocking, efficient

### Scaling Up (If Needed)

If you exceed Gmail's free limit (500/day):
1. **Option 1**: Upgrade to Google Workspace (higher limits)
2. **Option 2**: Use multiple Gmail accounts (distribute load)
3. **Option 3**: Switch to paid service (SendGrid, Mailgun) - but NOT needed initially

### Performance Optimizations

- Scheduler runs **once daily** (not per-user cron)
- Batched processing (all users in one run)
- Error handling prevents one user from blocking others
- Database queries are optimized with indexes

---

## 🛠️ Troubleshooting

### Emails Not Sending

1. **Check SMTP credentials**:
   ```bash
   # Verify environment variables are set
   echo $SMTP_USERNAME
   echo $SMTP_PASSWORD
   ```

2. **Check Gmail App Password**: Must be 16 characters, no spaces

3. **Check logs**: Look for error messages in backend console

4. **Test email connection**:
   ```python
   from email_service import email_service
   email_service.send_email(
       to_email="test@example.com",
       subject="Test",
       html_body="<p>Test email</p>"
   )
   ```

### Scheduler Not Running

1. Check if scheduler started: Look for `✅ Notification scheduler started` in logs
2. Check timezone: Default is UTC, adjust if needed
3. Check APScheduler installation: `pip list | grep apscheduler`

### Users Not Receiving Notifications

1. Check `email_notifications_enabled` in database (must be `true`)
2. Check `notification_preferences` JSONB (phase_transitions/period_reminders must be `true`)
3. Verify user has `last_period_date` set (required for predictions)
4. Check spam folder (Gmail sometimes filters automated emails)

---

## 📝 Environment Variables Summary

### Required (for email to work):
```env
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Optional (defaults provided):
```env
SMTP_SERVER=smtp.gmail.com          # Default
SMTP_PORT=587                        # Default
FROM_EMAIL=your-email@gmail.com      # Defaults to SMTP_USERNAME
APP_NAME=PeriodCycle.AI              # Default
```

---

## ✅ Checklist

- [ ] Database migration run (`add_notification_preferences.sql`)
- [ ] Gmail App Password created
- [ ] Environment variables set in Railway (or `.env`)
- [ ] Backend dependencies installed (`apscheduler`)
- [ ] Backend started (scheduler should auto-start)
- [ ] Test email sent successfully
- [ ] Frontend Profile page has "Notifications" tab
- [ ] Users can toggle notification preferences
- [ ] Daily notification check runs (check logs)

---

## 🎉 Success!

Once setup is complete:
- ✅ Users will receive phase transition emails automatically
- ✅ Users will receive period reminder emails before their period
- ✅ Users can manage all preferences in Profile → Notifications
- ✅ System is scalable and free (Gmail SMTP)
- ✅ All emails support multilingual content (English/Hindi/Gujarati)

**No additional costs - everything uses free services!**
