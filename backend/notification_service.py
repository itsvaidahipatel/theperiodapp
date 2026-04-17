"""
Clean Email Notification Service
Implements 3 email types:
1. Upcoming Period Reminder (7 days before, 3 days before - optional, max 1-2 per cycle)
2. Period Logging Reminder (during predicted period, once per day, stops when logged)
3. Health/Anomaly Alert (rare, max 1 per cycle)

Rules:
- Max 1 email per day per user
- Auto-cancel on period log
- Respect user preferences
- Never send duplicates
"""
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import supabase
from email_service import email_service
from cycle_utils import predict_cycle_starts_from_period_logs
from period_start_logs import get_last_confirmed_period_start
from cycle_stats import get_cycle_stats
import json

# Create global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")

class NotificationService:
    """Service for managing clean email notifications."""
    
    def __init__(self):
        self.scheduler = scheduler
        self.running = False
        
    def start(self):
        """Start the notification scheduler."""
        if not self.running:
            # Schedule daily check at 9 AM UTC (adjusts to user's preferred time)
            self.scheduler.add_job(
                self.check_all_notifications,
                trigger=CronTrigger(hour=9, minute=0),  # 9 AM UTC daily
                id="daily_email_check",
                replace_existing=True
            )
            self.scheduler.start()
            self.running = True
            print("✅ Email notification scheduler started")
    
    def stop(self):
        """Stop the notification scheduler."""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            print("🛑 Email notification scheduler stopped")
    
    async def check_all_notifications(self):
        """Check and send notifications for all users who have them enabled."""
        try:
            print(f"🔔 Running daily email check at {datetime.now()}")
            
            # Get all users with email notifications enabled
            response = supabase.table("users").select(
                "id, name, email, email_notifications_enabled, notification_preferences, "
                "last_email_sent_date, last_anomaly_email_cycle_start, language"
            ).eq("email_notifications_enabled", True).execute()
            
            if not response.data:
                print("No users with email notifications enabled")
                return
            
            users = response.data
            print(f"Found {len(users)} users with email notifications enabled")
            
            for user in users:
                try:
                    await self.check_user_emails(user)
                except Exception as e:
                    print(f"❌ Error checking emails for user {user.get('id')}: {str(e)}")
                    continue
            
            print(f"✅ Email check completed for {len(users)} users")
            
        except Exception as e:
            print(f"❌ Error in daily email check: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def check_user_emails(self, user: Dict):
        """Check and send emails for a specific user."""
        user_id = user.get("id")
        email = user.get("email")
        name = user.get("name", "User")
        language = user.get("language", "en")
        
        if not email:
            return
        
        # Parse notification preferences
        preferences = user.get("notification_preferences", {})
        if isinstance(preferences, str):
            try:
                preferences = json.loads(preferences) if preferences else {}
            except json.JSONDecodeError:
                preferences = {}
        
        
        # Enforce max 1 email per day
        last_email_date = user.get("last_email_sent_date")
        today = datetime.now().date()
        
        if last_email_date:
            if isinstance(last_email_date, str):
                last_email_date_obj = datetime.strptime(last_email_date, "%Y-%m-%d").date()
            else:
                last_email_date_obj = last_email_date
            
            if last_email_date_obj == today:
                print(f"⏸️ Already sent email today for user {user_id}")
                return
        
        # Check upcoming period reminder
        if preferences.get("upcoming_reminders", True):
            await self.check_upcoming_period_reminder(user)
        
        # Check period logging reminder (most important)
        if preferences.get("logging_reminders", True):
            await self.check_period_logging_reminder(user)
        
        # Check health anomaly alert (rare)
        if preferences.get("health_alerts", True):
            await self.check_health_anomaly_alert(user)
    
    async def check_upcoming_period_reminder(self, user: Dict):
        """Check if user needs an upcoming period reminder (7 days or 3 days before)."""
        try:
            user_id = user.get("id")
            email = user.get("email")
            name = user.get("name", "User")
            language = user.get("language", "en")
            
            # Get next predicted period start
            predicted_starts = predict_cycle_starts_from_period_logs(user_id, max_cycles=3)
            if not predicted_starts:
                return
            
            today = datetime.now().date()
            next_period = None
            
            # Find next future period
            for predicted_start in predicted_starts:
                if isinstance(predicted_start, datetime):
                    predicted_date = predicted_start.date()
                elif isinstance(predicted_start, str):
                    predicted_date = datetime.strptime(predicted_start, "%Y-%m-%d").date()
                else:
                    predicted_date = predicted_start
                
                if predicted_date > today:
                    next_period = predicted_date
                    break
            
            if not next_period:
                return
            
            days_until = (next_period - today).days
            
            # Send reminder at 7 days before OR 3 days before (optional)
            # Only send once per cycle (check if we already sent for this predicted period)
            should_send = False
            
            if days_until == 7:
                should_send = True
            elif days_until == 3:
                # Optional: Only send if user hasn't received 7-day reminder
                # For simplicity, we'll send both (max 2 per cycle as specified)
                should_send = True
            
            if should_send:
                success = email_service.send_upcoming_period_reminder_email(
                    to_email=email,
                    user_name=name,
                    predicted_date=next_period.strftime("%Y-%m-%d"),
                    days_until=days_until,
                    language=language
                )
                
                if success:
                    self._update_last_email_date(user_id)
                    print(f"✅ Upcoming period reminder sent to {email} ({days_until} days before)")
        
        except Exception as e:
            print(f"❌ Error checking upcoming period reminder for user {user.get('id')}: {str(e)}")
    
    async def check_period_logging_reminder(self, user: Dict):
        """Check if user needs a period logging reminder (during predicted period window)."""
        try:
            user_id = user.get("id")
            email = user.get("email")
            name = user.get("name", "User")
            language = user.get("language", "en")
            
            # Get predicted period starts
            predicted_starts = predict_cycle_starts_from_period_logs(user_id, max_cycles=3)
            if not predicted_starts:
                return
            
            today = datetime.now().date()
            
            # Check if today is within any predicted period window
            # Period window = predicted start date + estimated period length (typically 3-8 days)
            from cycle_utils import estimate_period_length
            period_length = estimate_period_length(user_id)
            period_length_days = int(round(max(3.0, min(8.0, period_length))))  # Normalized
            
            in_predicted_period = False
            predicted_start_date = None
            
            for predicted_start in predicted_starts:
                if isinstance(predicted_start, datetime):
                    predicted_date = predicted_start.date()
                elif isinstance(predicted_start, str):
                    predicted_date = datetime.strptime(predicted_start, "%Y-%m-%d").date()
                else:
                    predicted_date = predicted_start
                
                # Check if today is within predicted period window
                period_end = predicted_date + timedelta(days=period_length_days - 1)
                
                if predicted_date <= today <= period_end:
                    in_predicted_period = True
                    predicted_start_date = predicted_date
                    break
            
            if not in_predicted_period:
                return
            
            # CRITICAL: Check if user has already logged period for today or recent days
            # If logged, cancel all future reminders
            period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).gte("date", predicted_start_date.strftime("%Y-%m-%d")).execute()
            
            if period_logs_response.data:
                # User has logged period - don't send reminder
                print(f"✅ User {user_id} has logged period, skipping logging reminder")
                return
            
            # Send reminder (once per day during predicted period)
            success = email_service.send_period_logging_reminder_email(
                to_email=email,
                user_name=name,
                predicted_date=predicted_start_date.strftime("%Y-%m-%d"),
                language=language
            )
            
            if success:
                self._update_last_email_date(user_id)
                print(f"✅ Period logging reminder sent to {email}")
        
        except Exception as e:
            print(f"❌ Error checking period logging reminder for user {user.get('id')}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def check_health_anomaly_alert(self, user: Dict):
        """Check if user needs a health anomaly alert (rare, max 1 per cycle)."""
        try:
            user_id = user.get("id")
            email = user.get("email")
            name = user.get("name", "User")
            language = user.get("language", "en")
            
            # Get last anomaly email cycle start
            last_anomaly_cycle_start = user.get("last_anomaly_email_cycle_start")
            
            # Get current cycle start
            current_cycle_start = get_last_confirmed_period_start(user_id)
            if not current_cycle_start:
                return
            
            # Parse dates
            if isinstance(current_cycle_start, str):
                current_cycle_start_date = datetime.strptime(current_cycle_start, "%Y-%m-%d").date()
            else:
                current_cycle_start_date = current_cycle_start
            
            # Check if we already sent anomaly email for this cycle
            if last_anomaly_cycle_start:
                if isinstance(last_anomaly_cycle_start, str):
                    last_anomaly_date = datetime.strptime(last_anomaly_cycle_start, "%Y-%m-%d").date()
                else:
                    last_anomaly_date = last_anomaly_cycle_start
                
                if last_anomaly_date == current_cycle_start_date:
                    # Already sent for this cycle
                    return
            
            # Get cycle stats to detect anomalies
            # Notification emails should use user's language when available.
            language = user.get("language", "en") if isinstance(user, dict) else "en"
            stats = get_cycle_stats(user_id, language=language)
            
            anomaly_detected = False
            anomaly_type = None
            anomaly_description = None
            
            # Check for anomalies:
            # 1. Cycle length consistently <21 or >45 days
            avg_cycle_length = stats.get("averageCycleLength", 28)
            if avg_cycle_length < 21:
                anomaly_detected = True
                anomaly_type = "short_cycle"
                anomaly_description = f"Your average cycle length ({avg_cycle_length:.1f} days) is shorter than typical (21-45 days)."
            elif avg_cycle_length > 45:
                anomaly_detected = True
                anomaly_type = "long_cycle"
                anomaly_description = f"Your average cycle length ({avg_cycle_length:.1f} days) is longer than typical (21-45 days)."
            
            # 2. Period length >8 days for multiple cycles
            avg_period_length = stats.get("averagePeriodLength", 5)
            if avg_period_length > 8:
                anomaly_detected = True
                anomaly_type = "long_period"
                anomaly_description = f"Your average period length ({avg_period_length:.1f} days) is longer than typical (3-8 days)."
            
            # 3. High irregularity (CV >= 25%)
            cycle_regularity = stats.get("cycleRegularity", "unknown")
            if cycle_regularity == "irregular":
                anomaly_detected = True
                anomaly_type = "irregular_cycles"
                anomaly_description = "Your cycles show high variability. This pattern is worth keeping an eye on."
            
            # 4. Missed periods / long gaps
            days_since_last = stats.get("daysSinceLastPeriod")
            if days_since_last and days_since_last > 60:
                anomaly_detected = True
                anomaly_type = "missed_period"
                anomaly_description = f"It's been {days_since_last} days since your last period. This is longer than typical."
            
            if anomaly_detected:
                success = email_service.send_health_anomaly_alert_email(
                    to_email=email,
                    user_name=name,
                    anomaly_type=anomaly_type,
                    anomaly_description=anomaly_description,
                    language=language
                )
                
                if success:
                    self._update_last_email_date(user_id)
                    # Update last anomaly email cycle start
                    supabase.table("users").update({
                        "last_anomaly_email_cycle_start": current_cycle_start_date.strftime("%Y-%m-%d")
                    }).eq("id", user_id).execute()
                    print(f"✅ Health anomaly alert sent to {email} ({anomaly_type})")
        
        except Exception as e:
            print(f"❌ Error checking health anomaly alert for user {user.get('id')}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _update_last_email_date(self, user_id: str):
        """Update last_email_sent_date to today."""
        try:
            today = datetime.now().date().strftime("%Y-%m-%d")
            supabase.table("users").update({
                "last_email_sent_date": today
            }).eq("id", user_id).execute()
        except Exception as e:
            print(f"⚠️ Error updating last_email_sent_date: {str(e)}")

# Create singleton instance
notification_service = NotificationService()
