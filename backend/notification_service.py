"""
Notification Service for Smart Notification Agent
Handles scheduling and sending notifications for phase transitions and period reminders
Uses APScheduler (free) for task scheduling
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import supabase
from email_service import email_service
from cycle_utils import get_user_phase_day, calculate_today_phase_day_id
from config import settings

# Create global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")

class NotificationService:
    """Service for managing smart notifications."""
    
    def __init__(self):
        self.scheduler = scheduler
        self.running = False
        
    def start(self):
        """Start the notification scheduler."""
        if not self.running:
            # Schedule daily check at 6 AM UTC (adjusts to user's preferred time)
            # This will run every day and check all users
            self.scheduler.add_job(
                self.check_all_notifications,
                trigger=CronTrigger(hour=6, minute=0),  # 6 AM UTC daily
                id="daily_notification_check",
                replace_existing=True
            )
            self.scheduler.start()
            self.running = True
            print("✅ Notification scheduler started")
    
    def stop(self):
        """Stop the notification scheduler."""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            print("🛑 Notification scheduler stopped")
    
    async def check_all_notifications(self):
        """Check and send notifications for all users who have them enabled."""
        try:
            print(f"🔔 Running daily notification check at {datetime.now()}")
            
            # Get all users with email notifications enabled
            response = supabase.table("users").select(
                "id, name, email, email_notifications_enabled, notification_preferences, "
                "last_period_date, cycle_length, last_phase_notification, last_phase_notification_date, language"
            ).eq("email_notifications_enabled", True).execute()
            
            if not response.data:
                print("No users with notifications enabled")
                return
            
            users = response.data
            print(f"Found {len(users)} users with notifications enabled")
            
            for user in users:
                try:
                    await self.check_user_notifications(user)
                except Exception as e:
                    print(f"❌ Error checking notifications for user {user.get('id')}: {str(e)}")
                    continue
            
            print(f"✅ Notification check completed for {len(users)} users")
            
        except Exception as e:
            print(f"❌ Error in daily notification check: {str(e)}")
    
    async def check_user_notifications(self, user: Dict):
        """Check and send notifications for a specific user."""
        user_id = user.get("id")
        email = user.get("email")
        name = user.get("name", "User")
        language = user.get("language", "en")
        
        if not email:
            return
        
        preferences = user.get("notification_preferences", {})
        if isinstance(preferences, str):
            import json
            preferences = json.loads(preferences) if preferences else {}
        
        # Check phase transition
        if preferences.get("phase_transitions", True):
            await self.check_phase_transition(user)
        
        # Check period reminder
        if preferences.get("period_reminders", True):
            await self.check_period_reminder(user)
    
    async def check_phase_transition(self, user: Dict):
        """Check if user has entered a new phase and send notification if needed."""
        try:
            user_id = user.get("id")
            email = user.get("email")
            name = user.get("name", "User")
            language = user.get("language", "en")
            last_notified_phase = user.get("last_phase_notification")
            last_notified_date = user.get("last_phase_notification_date")
            
            # Get current phase
            today = datetime.now().strftime("%Y-%m-%d")
            phase_info = get_user_phase_day(user_id, today)
            
            if not phase_info or not phase_info.get("phase"):
                # Try calculating
                phase_day_id = calculate_today_phase_day_id(user_id)
                if phase_day_id:
                    phase_map = {
                        "p": "Period",
                        "f": "Follicular",
                        "o": "Ovulation",
                        "l": "Luteal"
                    }
                    current_phase = phase_map.get(phase_day_id[0].lower(), "Period")
                else:
                    return
            else:
                current_phase = phase_info.get("phase")
            
            # Check if phase changed (and we haven't notified for this phase yet today)
            today_date = datetime.now().date()
            if last_notified_date:
                last_notified_date_obj = datetime.strptime(last_notified_date, "%Y-%m-%d").date() if isinstance(last_notified_date, str) else last_notified_date
            else:
                last_notified_date_obj = None
            
            # Only send if:
            # 1. Phase changed from last notified phase, OR
            # 2. We haven't sent a notification for this phase today
            should_notify = False
            if current_phase != last_notified_phase:
                should_notify = True  # Phase changed
            elif last_notified_date_obj != today_date:
                should_notify = True  # Haven't notified for this phase today
            
            if not should_notify:
                return
            
            # Get phase-specific tips
            phase_tips = self._get_phase_tips(current_phase, language)
            
            # Send email
            old_phase = last_notified_phase or "Unknown"
            success = email_service.send_phase_transition_email(
                to_email=email,
                user_name=name,
                old_phase=old_phase,
                new_phase=current_phase,
                phase_tips={current_phase: phase_tips},
                language=language
            )
            
            if success:
                # Update last notified phase and date
                supabase.table("users").update({
                    "last_phase_notification": current_phase,
                    "last_phase_notification_date": today
                }).eq("id", user_id).execute()
                print(f"✅ Phase transition notification sent to {email} (Phase: {current_phase})")
            
        except Exception as e:
            print(f"❌ Error checking phase transition for user {user.get('id')}: {str(e)}")
    
    async def check_period_reminder(self, user: Dict):
        """Check if user needs a period reminder and send if needed."""
        try:
            user_id = user.get("id")
            email = user.get("email")
            name = user.get("name", "User")
            language = user.get("language", "en")
            last_period_date = user.get("last_period_date")
            cycle_length = user.get("cycle_length", 28)
            
            if not last_period_date:
                return  # Can't predict without last period date
            
            preferences = user.get("notification_preferences", {})
            if isinstance(preferences, str):
                import json
                preferences = json.loads(preferences) if preferences else {}
            
            reminder_days_before = preferences.get("reminder_days_before", 2)
            
            # Calculate next period date
            if isinstance(last_period_date, str):
                last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
            else:
                last_period = last_period_date
            
            next_period = last_period + timedelta(days=cycle_length)
            
            # Advance to next period if it's in the past
            today = datetime.now().date()
            while next_period.date() < today:
                next_period = next_period + timedelta(days=cycle_length)
            
            days_until = (next_period.date() - today).days
            
            # Send reminder if we're within the reminder window
            if days_until <= reminder_days_before and days_until >= 0:
                # Check if we already sent a reminder for this period
                # (Simple check: only send once per predicted period)
                predicted_date_str = next_period.strftime("%Y-%m-%d")
                
                # For simplicity, we'll send if days_until matches reminder_days_before
                # This ensures we send exactly on the reminder day
                if days_until == reminder_days_before:
                    success = email_service.send_period_reminder_email(
                        to_email=email,
                        user_name=name,
                        predicted_date=predicted_date_str,
                        days_until=days_until,
                        language=language
                    )
                    
                    if success:
                        print(f"✅ Period reminder sent to {email} (Period in {days_until} days)")
            
        except Exception as e:
            print(f"❌ Error checking period reminder for user {user.get('id')}: {str(e)}")
    
    def _get_phase_tips(self, phase: str, language: str = "en") -> str:
        """Get phase-specific tips for email."""
        tips = {
            "en": {
                "Period": "Rest well, stay hydrated, and use heating pads for cramps. Consider gentle yoga or light stretching.",
                "Follicular": "Your energy is rising! Great time for high-intensity workouts and trying new activities. Eat protein-rich foods.",
                "Ovulation": "Peak fertility window. Your energy and confidence are at their highest. Enjoy social activities and creative projects.",
                "Luteal": "Focus on self-care and stress management. Moderate exercise and magnesium-rich foods can help with PMS symptoms."
            },
            "hi": {
                "Period": "अच्छी तरह आराम करें, हाइड्रेटेड रहें, और ऐंठन के लिए हीटिंग पैड का उपयोग करें। हल्की योग या स्ट्रेचिंग करें।",
                "Follicular": "आपकी ऊर्जा बढ़ रही है! उच्च-तीव्रता वाले वर्कआउट और नई गतिविधियों को आज़माने का शानदार समय। प्रोटीन युक्त खाद्य पदार्थ खाएं।",
                "Ovulation": "शीर्ष प्रजनन क्षमता की खिड़की। आपकी ऊर्जा और आत्मविश्वास अपने उच्चतम स्तर पर हैं। सामाजिक गतिविधियों और रचनात्मक परियोजनाओं का आनंद लें।",
                "Luteal": "स्व-देखभाल और तनाव प्रबंधन पर ध्यान दें। मध्यम व्यायाम और मैग्नीशियम युक्त खाद्य पदार्थ PMS लक्षणों में मदद कर सकते हैं।"
            },
            "gu": {
                "Period": "સારી રીતે આરામ કરો, હાઇડ્રેટેડ રહો, અને ઐંચણ માટે હીટિંગ પેડનો ઉપયોગ કરો. હળવા યોગા અથવા સ્ટ્રેચિંગ કરો.",
                "Follicular": "તમારી ઊર્જા વધી રહી છે! ઊંચી-તીવ્રતા વાળા વર્કઆઉટ્સ અને નવી પ્રવૃત્તિઓ અજમાવવાનો સમય. પ્રોટીન યુક્ત ખોરાક ખાઓ.",
                "Ovulation": "ટોચની ફર્ટિલિટી વિન્ડો. તમારી ઊર્જા અને આત્મવિશ્વાસ તેમના ઉચ્ચતમ સ્તરે છે. સામાજિક પ્રવૃત્તિઓ અને રચનાત્મક પ્રોજેક્ટ્સનો આનંદ માણો.",
                "Luteal": "સelf-care અને તણાવ વ્યવસ્થાપન પર ધ્યાન કેન્દ્રિત કરો. મધ્યમ કસરત અને મેગ્નેશિયમ યુક્ત ખોરાક PMS લક્ષણોમાં મદદ કરી શકે છે."
            }
        }
        
        return tips.get(language, tips["en"]).get(phase, "")

# Create singleton instance
notification_service = NotificationService()
