"""
Email Service for Smart Notification Agent
Uses Gmail SMTP (free, no cost for basic usage)
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
import os
from datetime import datetime
from config import settings

class EmailService:
    """Email service using Gmail SMTP (free tier)."""
    
    def __init__(self):
        # Gmail SMTP Configuration (free, no cost)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")  # Your Gmail address
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")  # Gmail App Password (not regular password)
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username)
        self.app_name = os.getenv("APP_NAME", "PeriodCycle.AI")
        
    def _create_message(
        self, 
        to_email: str, 
        subject: str, 
        html_body: str, 
        text_body: Optional[str] = None
    ) -> MIMEMultipart:
        """Create email message."""
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.app_name} <{self.from_email}>"
        message["To"] = to_email
        
        # Create text version if provided, otherwise strip HTML
        if not text_body:
            # Simple HTML stripping (for basic emails)
            import re
            text_body = re.sub(r'<[^>]+>', '', html_body)
        
        # Add both text and HTML parts
        text_part = MIMEText(text_body, "plain")
        html_part = MIMEText(html_body, "html")
        
        message.attach(text_part)
        message.attach(html_part)
        
        return message
    
    def send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_body: str, 
        text_body: Optional[str] = None
    ) -> bool:
        """
        Send email via Gmail SMTP.
        Returns True if successful, False otherwise.
        """
        try:
            # Check if email is configured
            if not self.smtp_username or not self.smtp_password:
                print("⚠️ Email not configured. Set SMTP_USERNAME and SMTP_PASSWORD environment variables.")
                return False
            
            # Create message
            message = self._create_message(to_email, subject, html_body, text_body)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            print(f"✅ Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_phase_transition_email(
        self, 
        to_email: str, 
        user_name: str, 
        old_phase: str, 
        new_phase: str, 
        phase_tips: Dict[str, str],
        language: str = "en"
    ) -> bool:
        """Send phase transition notification email."""
        phase_names = {
            "en": {
                "Period": "Period",
                "Follicular": "Follicular Phase",
                "Ovulation": "Ovulation Phase",
                "Luteal": "Luteal Phase"
            },
            "hi": {
                "Period": "मासिक धर्म",
                "Follicular": "फॉलिक्युलर चरण",
                "Ovulation": "ओव्यूलेशन चरण",
                "Luteal": "ल्यूटियल चरण"
            },
            "gu": {
                "Period": "માસિક ધર્મ",
                "Follicular": "ફોલિક્યુલર તબક્કો",
                "Ovulation": "ઓવ્યુલેશન તબક્કો",
                "Luteal": "લ્યુટિયલ તબક્કો"
            }
        }
        
        translations = {
            "en": {
                "subject": f"Your cycle has entered {phase_names['en'].get(new_phase, new_phase)}",
                "greeting": f"Hi {user_name}!",
                "transition": f"You've entered the {phase_names['en'].get(new_phase, new_phase)}.",
                "tips_title": "Tips for this phase:",
                "unsubscribe": "Don't want these emails? You can turn off notifications in your Profile Settings."
            },
            "hi": {
                "subject": f"आपका चक्र {phase_names['hi'].get(new_phase, new_phase)} में प्रवेश कर गया है",
                "greeting": f"नमस्ते {user_name}!",
                "transition": f"आप {phase_names['hi'].get(new_phase, new_phase)} में प्रवेश कर चुके हैं।",
                "tips_title": "इस चरण के लिए सुझाव:",
                "unsubscribe": "इन ईमेल नहीं चाहते? आप अपनी प्रोफ़ाइल सेटिंग्स में अधिसूचनाएं बंद कर सकते हैं।"
            },
            "gu": {
                "subject": f"તમારો ચક્ર {phase_names['gu'].get(new_phase, new_phase)} માં પ્રવેશ કર્યો છે",
                "greeting": f"હેલો {user_name}!",
                "transition": f"તમે {phase_names['gu'].get(new_phase, new_phase)} માં પ્રવેશ કર્યો છે.",
                "tips_title": "આ તબક્કા માટે ટીપ્સ:",
                "unsubscribe": "આ ઇમેઇલ્સ નથી જોઈએ? તમે તમારી પ્રોફાઇલ સેટિંગ્સમાં સૂચનાઓ બંધ કરી શકો છો."
            }
        }
        
        t = translations.get(language, translations["en"])
        tips = phase_tips.get(new_phase, "")
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .phase-box {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #667eea; }}
        .tips-box {{ background: #fff9e6; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #ffc107; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        .button {{ display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>{t['greeting']}</h2>
            <div class="phase-box">
                <h3>{t['transition']}</h3>
            </div>
            {f'<div class="tips-box"><h4>{t["tips_title"]}</h4><p>{tips}</p></div>' if tips else ''}
            <div class="footer">
                <p>{t['unsubscribe']}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        subject = t["subject"]
        return self.send_email(to_email, subject, html_body)
    
    def send_period_reminder_email(
        self, 
        to_email: str, 
        user_name: str, 
        predicted_date: str, 
        days_until: int,
        language: str = "en"
    ) -> bool:
        """Send period prediction reminder email."""
        translations = {
            "en": {
                "subject": f"Your period is expected in {days_until} day{'s' if days_until != 1 else ''}",
                "greeting": f"Hi {user_name}!",
                "message": f"Your next period is predicted to start on <strong>{predicted_date}</strong> ({days_until} day{'s' if days_until != 1 else ''} away).",
                "prepare": "Time to prepare! Make sure you have everything you need.",
                "unsubscribe": "Don't want these reminders? You can adjust notification settings in your Profile."
            },
            "hi": {
                "subject": f"आपका मासिक धर्म {days_until} दिन{'ों' if days_until != 1 else ''} में आने की उम्मीद है",
                "greeting": f"नमस्ते {user_name}!",
                "message": f"आपके अगले मासिक धर्म की शुरुआत <strong>{predicted_date}</strong> ({days_until} दिन{'ों' if days_until != 1 else ''} बाद) होने की भविष्यवाणी की गई है।",
                "prepare": "तैयारी करने का समय! सुनिश्चित करें कि आपके पास सब कुछ है।",
                "unsubscribe": "इन अनुस्मारक नहीं चाहते? आप अपनी प्रोफ़ाइल में अधिसूचना सेटिंग્સ समायोजित कर सकते हैं।"
            },
            "gu": {
                "subject": f"તમારો માસિક ધર્મ {days_until} દિવસ{'ો' if days_until != 1 else ''} માં આવવાની અપેક્ષા છે",
                "greeting": f"હેલો {user_name}!",
                "message": f"તમારા આગામી માસિક ધર્મની શરૂઆત <strong>{predicted_date}</strong> ({days_until} દિવસ{'ો' if days_until != 1 else ''} પછી) થવાની આગાહી કરવામાં આવી છે.",
                "prepare": "તૈયારી કરવાનો સમય! ખાતરી કરો કે તમારી પાસે બધું છે.",
                "unsubscribe": "આ રીમાઇન્ડર્સ જોઈએ નહીં? તમે તમારી પ્રોફાઇલમાં સૂચના સેટિંગ્સ સમાયોજિત કરી શકો છો."
            }
        }
        
        t = translations.get(language, translations["en"])
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .reminder-box {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #e91e63; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>{t['greeting']}</h2>
            <div class="reminder-box">
                <p>{t['message']}</p>
                <p><em>{t['prepare']}</em></p>
            </div>
            <div class="footer">
                <p>{t['unsubscribe']}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        subject = t["subject"]
        return self.send_email(to_email, subject, html_body)
    
    def send_upcoming_period_reminder_email(
        self,
        to_email: str,
        user_name: str,
        predicted_date: str,
        days_until: int,
        language: str = "en"
    ) -> bool:
        """Send upcoming period reminder email (7 days before or 3 days before)."""
        translations = {
            "en": {
                "subject": f"Your next period is expected around {predicted_date}",
                "greeting": f"Hi {user_name}!",
                "message": f"Your next period is expected around <strong>{predicted_date}</strong> ({days_until} day{'s' if days_until != 1 else ''} away).",
                "prepare": "Just a gentle reminder to help you prepare.",
                "unsubscribe": "Don't want these emails? You can turn off notifications in your Profile Settings."
            },
            "hi": {
                "subject": f"आपका अगला मासिक धर्म {predicted_date} के आसपास आने की उम्मीद है",
                "greeting": f"नमस्ते {user_name}!",
                "message": f"आपके अगले मासिक धर्म की शुरुआत <strong>{predicted_date}</strong> ({days_until} दिन{'ों' if days_until != 1 else ''} बाद) होने की उम्मीद है।",
                "prepare": "बस एक कोमल अनुस्मारक आपको तैयार करने में मदद करने के लिए।",
                "unsubscribe": "इन ईमेल नहीं चाहते? आप अपनी प्रोफ़ाइल सेटिंग्स में अधिसूचनाएं बंद कर सकते हैं।"
            },
            "gu": {
                "subject": f"તમારો આગામી માસિક ધર્મ {predicted_date} ની આસપાસ આવવાની અપેક્ષા છે",
                "greeting": f"હેલો {user_name}!",
                "message": f"તમારા આગામી માસિક ધર્મની શરૂઆત <strong>{predicted_date}</strong> ({days_until} દિવસ{'ો' if days_until != 1 else ''} પછી) થવાની અપેક્ષા છે.",
                "prepare": "ફક્ત એક નરમ રીમાઇન્ડર તમને તૈયાર કરવામાં મદદ કરવા માટે.",
                "unsubscribe": "આ ઇમેઇલ્સ નથી જોઈએ? તમે તમારી પ્રોફાઇલ સેટિંગ્સમાં સૂચનાઓ બંધ કરી શકો છો."
            }
        }
        
        t = translations.get(language, translations["en"])
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #e91e63 0%, #f06292 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .reminder-box {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #e91e63; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        .unsubscribe-link {{ color: #666; text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>{t['greeting']}</h2>
            <div class="reminder-box">
                <p>{t['message']}</p>
                <p><em>{t['prepare']}</em></p>
            </div>
            <div class="footer">
                <p>{t['unsubscribe']}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        subject = t["subject"]
        return self.send_email(to_email, subject, html_body)
    
    def send_period_logging_reminder_email(
        self,
        to_email: str,
        user_name: str,
        predicted_date: str,
        language: str = "en"
    ) -> bool:
        """Send period logging reminder email (during predicted period window)."""
        translations = {
            "en": {
                "subject": "Don't forget to log your period",
                "greeting": f"Hi {user_name}!",
                "message": "Don't forget to log your period if it has started today.",
                "predicted": f"Your period was predicted to start around <strong>{predicted_date}</strong>.",
                "unsubscribe": "Don't want these reminders? You can turn off notifications in your Profile Settings."
            },
            "hi": {
                "subject": "अपना मासिक धर्म लॉग करना न भूलें",
                "greeting": f"नमस्ते {user_name}!",
                "message": "अगर आज आपका मासिक धर्म शुरू हुआ है तो इसे लॉग करना न भूलें।",
                "predicted": f"आपके मासिक धर्म की शुरुआत <strong>{predicted_date}</strong> के आसपास होने की भविष्यवाणी की गई थी।",
                "unsubscribe": "इन अनुस्मारक नहीं चाहते? आप अपनी प्रोफ़ाइल सेटिंग्स में अधिसूचनाएं बंद कर सकते हैं।"
            },
            "gu": {
                "subject": "તમારો માસિક ધર્મ લોગ કરવાનું ભૂલશો નહીં",
                "greeting": f"હેલો {user_name}!",
                "message": "જો આજે તમારો માસિક ધર્મ શરૂ થયો છે તો તેને લોગ કરવાનું ભૂલશો નહીં.",
                "predicted": f"તમારા માસિક ધર્મની શરૂઆત <strong>{predicted_date}</strong> ની આસપાસ થવાની આગાહી કરવામાં આવી હતી.",
                "unsubscribe": "આ રીમાઇન્ડર્સ જોઈએ નહીં? તમે તમારી પ્રોફાઇલ સેટિંગ્સમાં સૂચનાઓ બંધ કરી શકો છો."
            }
        }
        
        t = translations.get(language, translations["en"])
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #e91e63 0%, #f06292 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .reminder-box {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #e91e63; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>{t['greeting']}</h2>
            <div class="reminder-box">
                <p>{t['message']}</p>
                <p>{t['predicted']}</p>
            </div>
            <div class="footer">
                <p>{t['unsubscribe']}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        subject = t["subject"]
        return self.send_email(to_email, subject, html_body)
    
    def send_health_anomaly_alert_email(
        self,
        to_email: str,
        user_name: str,
        anomaly_type: str,
        anomaly_description: str,
        language: str = "en"
    ) -> bool:
        """Send health anomaly alert email (rare, respectful, non-diagnostic)."""
        translations = {
            "en": {
                "subject": "A pattern worth keeping an eye on",
                "greeting": f"Hi {user_name},",
                "intro": "We noticed a pattern in your recent cycles that's worth keeping an eye on.",
                "disclaimer": "This doesn't necessarily mean something is wrong.",
                "anomaly_label": "What we noticed:",
                "medical_disclaimer": "<strong>This is not medical advice.</strong> If you have concerns, please consult with a healthcare provider.",
                "unsubscribe": "Don't want these alerts? You can turn off health insights in your Profile Settings."
            },
            "hi": {
                "subject": "ध्यान देने योग्य एक पैटर्न",
                "greeting": f"नमस्ते {user_name},",
                "intro": "हमने आपके हाल के चक्रों में एक पैटर्न देखा है जिस पर ध्यान देना उचित है।",
                "disclaimer": "इसका मतलब यह नहीं है कि कुछ गलत है।",
                "anomaly_label": "हमने क्या देखा:",
                "medical_disclaimer": "<strong>यह चिकित्सा सलाह नहीं है।</strong> यदि आपको चिंता है, तो कृपया एक स्वास्थ्य सेवा प्रदाता से परामर्श करें।",
                "unsubscribe": "इन अलर्ट नहीं चाहते? आप अपनी प्रोफ़ाइल सेटिंग्स में स्वास्थ्य अंतर्दृष्टि बंद कर सकते हैं।"
            },
            "gu": {
                "subject": "ધ્યાન આપવા યોગ્ય એક પેટર્ન",
                "greeting": f"હેલો {user_name},",
                "intro": "અમે તમારા તાજેતરના ચક્રોમાં એક પેટર્ન જોયો છે જેની નજર રાખવી યોગ્ય છે.",
                "disclaimer": "આનો અર્થ એ નથી કે કંઈક ખોટું છે.",
                "anomaly_label": "અમે શું જોયું:",
                "medical_disclaimer": "<strong>આ તબીબી સલાહ નથી.</strong> જો તમને ચિંતા છે, તો કૃપા કરીને હેલ્થકેર પ્રદાતા સાથે સલાહ લો.",
                "unsubscribe": "આ એલર્ટ જોઈએ નહીં? તમે તમારી પ્રોફાઇલ સેટિંગ્સમાં હેલ્થ ઇનસાઇટ્સ બંધ કરી શકો છો."
            }
        }
        
        t = translations.get(language, translations["en"])
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #ff9800 0%, #ffb74d 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .alert-box {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #ff9800; }}
        .disclaimer-box {{ background: #fff3e0; padding: 15px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #ff9800; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>{t['greeting']}</h2>
            <p>{t['intro']}</p>
            <p><em>{t['disclaimer']}</em></p>
            <div class="alert-box">
                <p><strong>{t['anomaly_label']}</strong></p>
                <p>{anomaly_description}</p>
            </div>
            <div class="disclaimer-box">
                <p>{t['medical_disclaimer']}</p>
            </div>
            <div class="footer">
                <p>{t['unsubscribe']}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        subject = t["subject"]
        return self.send_email(to_email, subject, html_body)
    
    def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        language: str = "en"
    ) -> bool:
        """Send welcome email to new users explaining PeriodCycle.AI and how to use it."""
        translations = {
            "en": {
                "subject": "Welcome to PeriodCycle.AI",
                "greeting": f"Hi {user_name}!",
                "welcome": "Welcome to PeriodCycle.AI! We're so excited to have you join us.",
                "what_is_title": "What is PeriodCycle.AI?",
                "what_is_text": "PeriodCycle.AI is your personal period tracking companion that helps you understand your cycle, predict your periods, and get personalized insights about your health and wellness.",
                "features_title": "Key Features:",
                "feature1": "<strong>Smart Period Tracking:</strong> Log your periods and get accurate predictions",
                "feature2": "<strong>Cycle Insights:</strong> Understand your cycle patterns and regularity",
                "feature3": "<strong>Personalized Wellness:</strong> Get nutrition, exercise, and wellness tips tailored to your cycle phase",
                "feature4": "<strong>AI Chat Assistant:</strong> Ask questions about your cycle and get helpful answers",
                "how_to_title": "How to Get Started:",
                "step1": "1. <strong>Log Your Period:</strong> Start by logging your last period date in the calendar",
                "step2": "2. <strong>Track Daily:</strong> Log your period each day it occurs for accurate predictions",
                "step3": "3. <strong>Explore Your Calendar:</strong> View your cycle phases, predictions, and insights",
                "step4": "4. <strong>Check Statistics:</strong> See your cycle patterns and regularity in the Stats section",
                "step5": "5. <strong>Get Personalized Tips:</strong> Discover nutrition and exercise recommendations for each phase",
                "tips_title": "Pro Tips:",
                "tip1": "Log your period consistently for the most accurate predictions",
                "tip2": "The more data you log, the better insights you'll get",
                "tip3": "Check your calendar regularly to see upcoming predictions",
                "tip4": "Use the AI chat to ask questions about your cycle anytime",
                "closing": "We're here to support you on your journey. If you have any questions, feel free to explore the app or reach out.",
                "unsubscribe": "Don't want these emails? You can turn off notifications in your Profile Settings."
            },
            "hi": {
                "subject": "PeriodCycle.AI में आपका स्वागत है",
                "greeting": f"नमस्ते {user_name}!",
                "welcome": "PeriodCycle.AI में आपका स्वागत है! हमें आपके साथ होने की खुशी है।",
                "what_is_title": "PeriodCycle.AI क्या है?",
                "what_is_text": "PeriodCycle.AI आपका व्यक्तिगत मासिक धर्म ट्रैकिंग साथी है जो आपको अपने चक्र को समझने, अपने मासिक धर्म की भविष्यवाणी करने और अपने स्वास्थ्य और कल्याण के बारे में व्यक्तिगत अंतर्दृष्टि प्राप्त करने में मदद करता है।",
                "features_title": "मुख्य विशेषताएं:",
                "feature1": "<strong>स्मार्ट पीरियड ट्रैकिंग:</strong> अपने मासिक धर्म को लॉग करें और सटीक भविष्यवाणियां प्राप्त करें",
                "feature2": "<strong>चक्र अंतर्दृष्टि:</strong> अपने चक्र पैटर्न और नियमितता को समझें",
                "feature3": "<strong>व्यक्तिगत कल्याण:</strong> अपने चक्र चरण के अनुसार पोषण, व्यायाम और कल्याण युक्तियां प्राप्त करें",
                "feature4": "<strong>AI चैट असिस्टेंट:</strong> अपने चक्र के बारे में प्रश्न पूछें और सहायक उत्तर प्राप्त करें",
                "how_to_title": "कैसे शुरू करें:",
                "step1": "1. <strong>अपना मासिक धर्म लॉग करें:</strong> कैलेंडर में अपनी अंतिम मासिक धर्म की तारीख लॉग करके शुरू करें",
                "step2": "2. <strong>दैनिक ट्रैक करें:</strong> सटीक भविष्यवाणियों के लिए प्रत्येक दिन अपना मासिक धर्म लॉग करें",
                "step3": "3. <strong>अपने कैलेंडर का अन्वेषण करें:</strong> अपने चक्र चरण, भविष्यवाणियां और अंतर्दृष्टि देखें",
                "step4": "4. <strong>आंकड़े देखें:</strong> आंकड़े अनुभाग में अपने चक्र पैटर्न और नियमितता देखें",
                "step5": "5. <strong>व्यक्तिगत युक्तियां प्राप्त करें:</strong> प्रत्येक चरण के लिए पोषण और व्यायाम सिफारिशें खोजें",
                "tips_title": "प्रो टिप्स:",
                "tip1": "सबसे सटीक भविष्यवाणियों के लिए लगातार अपना मासिक धर्म लॉग करें",
                "tip2": "जितना अधिक डेटा आप लॉग करेंगे, उतनी बेहतर अंतर्दृष्टि मिलेगी",
                "tip3": "आगामी भविष्यवाणियां देखने के लिए नियमित रूप से अपना कैलेंडर देखें",
                "tip4": "किसी भी समय अपने चक्र के बारे में प्रश्न पूछने के लिए AI चैट का उपयोग करें",
                "closing": "हम आपकी यात्रा में आपका समर्थन करने के लिए यहां हैं। यदि आपके कोई प्रश्न हैं, तो कृपया ऐप का अन्वेषण करें या संपर्क करें।",
                "unsubscribe": "इन ईमेल नहीं चाहते? आप अपनी प्रोफ़ाइल सेटिंग्स में अधिसूचनाएं बंद कर सकते हैं।"
            },
            "gu": {
                "subject": "PeriodCycle.AI માં આપનું સ્વાગત છે",
                "greeting": f"હેલો {user_name}!",
                "welcome": "PeriodCycle.AI માં આપનું સ્વાગત છે! અમને તમારી સાથે હોવાની ખુશી છે.",
                "what_is_title": "PeriodCycle.AI શું છે?",
                "what_is_text": "PeriodCycle.AI તમારો વ્યક્તિગત માસિક ધર્મ ટ્રેકિંગ સાથી છે જે તમને તમારા ચક્રને સમજવામાં, તમારા માસિક ધર્મની આગાહી કરવામાં અને તમારા આરોગ્ય અને સુખાકારી વિશે વ્યક્તિગત અંતર્દૃષ્ટિ મેળવવામાં મદદ કરે છે.",
                "features_title": "મુખ્ય લક્ષણો:",
                "feature1": "<strong>સ્માર્ટ પીરિયડ ટ્રેકિંગ:</strong> તમારા માસિક ધર્મને લોગ કરો અને સચોટ આગાહીઓ મેળવો",
                "feature2": "<strong>ચક્ર અંતર્દૃષ્ટિ:</strong> તમારા ચક્ર પેટર્ન અને નિયમિતતાને સમજો",
                "feature3": "<strong>વ્યક્તિગત સુખાકારી:</strong> તમારા ચક્ર તબક્કા માટે પોષણ, વ્યાયામ અને સુખાકારી ટિપ્સ મેળવો",
                "feature4": "<strong>AI ચેટ એસિસ્ટન્ટ:</strong> તમારા ચક્ર વિશે પ્રશ્નો પૂછો અને મદદરૂપ જવાબો મેળવો",
                "how_to_title": "કેવી રીતે શરૂ કરવું:",
                "step1": "1. <strong>તમારો માસિક ધર્મ લોગ કરો:</strong> કેલેન્ડરમાં તમારી છેલ્લી માસિક ધર્મની તારીખ લોગ કરીને શરૂ કરો",
                "step2": "2. <strong>દૈનિક ટ્રેક કરો:</strong> સચોટ આગાહીઓ માટે દરેક દિવસ તમારો માસિક ધર્મ લોગ કરો",
                "step3": "3. <strong>તમારા કેલેન્ડરનું અન્વેષણ કરો:</strong> તમારા ચક્ર તબક્કા, આગાહીઓ અને અંતર્દૃષ્ટિ જુઓ",
                "step4": "4. <strong>આંકડાઓ તપાસો:</strong> આંકડા વિભાગમાં તમારા ચક્ર પેટર્ન અને નિયમિતતા જુઓ",
                "step5": "5. <strong>વ્યક્તિગત ટિપ્સ મેળવો:</strong> દરેક તબક્કા માટે પોષણ અને વ્યાયામ ભલામણો શોધો",
                "tips_title": "પ્રો ટિપ્સ:",
                "tip1": "સૌથી સચોટ આગાહીઓ માટે સતત તમારો માસિક ધર્મ લોગ કરો",
                "tip2": "તમે જેટલો વધુ ડેટા લોગ કરશો, તેટલી સારી અંતર્દૃષ્ટિ મળશે",
                "tip3": "આગામી આગાહીઓ જોવા માટે નિયમિત રીતે તમારા કેલેન્ડરને તપાસો",
                "tip4": "કોઈપણ સમયે તમારા ચક્ર વિશે પ્રશ્નો પૂછવા માટે AI ચેટનો ઉપયોગ કરો",
                "closing": "અમે તમારી યાત્રામાં તમારું સમર્થન કરવા માટે અહીં છીએ. જો તમારા કોઈ પ્રશ્નો હોય, તો કૃપા કરીને એપ્લિકેશનનું અન્વેષણ કરો અથવા સંપર્ક કરો.",
                "unsubscribe": "આ ઇમેઇલ્સ જોઈએ નહીં? તમે તમારી પ્રોફાઇલ સેટિંગ્સમાં સૂચનાઓ બંધ કરી શકો છો."
            }
        }
        
        t = translations.get(language, translations["en"])
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #e91e63 0%, #f06292 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #e91e63; }}
        .feature-list {{ list-style: none; padding: 0; }}
        .feature-list li {{ padding: 10px 0 10px 35px; border-bottom: 1px solid #eee; position: relative; }}
        .feature-list li:last-child {{ border-bottom: none; }}
        .feature-list li:before {{ content: ''; position: absolute; left: 0; top: 12px; width: 20px; height: 20px; background: #e91e63; border-radius: 3px; }}
        .feature-list li:nth-child(1):before {{ background: linear-gradient(135deg, #e91e63, #f06292); }}
        .feature-list li:nth-child(2):before {{ background: linear-gradient(135deg, #667eea, #764ba2); }}
        .feature-list li:nth-child(3):before {{ background: linear-gradient(135deg, #f093fb, #f5576c); }}
        .feature-list li:nth-child(4):before {{ background: linear-gradient(135deg, #4facfe, #00f2fe); }}
        .step-list {{ list-style: none; padding: 0; }}
        .step-list li {{ padding: 10px 0 10px 30px; position: relative; }}
        .step-list li:before {{ content: counter(step-counter); counter-increment: step-counter; position: absolute; left: 0; top: 8px; width: 24px; height: 24px; background: #e91e63; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; }}
        .step-list {{ counter-reset: step-counter; }}
        .tip-box {{ background: #fff9e6; padding: 15px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #ffc107; }}
        .tip-box .step-list li {{ padding-left: 25px; }}
        .tip-box .step-list li:before {{ content: '•'; background: transparent; color: #ffc107; font-size: 20px; width: auto; height: auto; position: absolute; left: 0; top: 5px; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>{t['greeting']}</h2>
            <p>{t['welcome']}</p>
            
            <div class="section">
                <h3>{t['what_is_title']}</h3>
                <p>{t['what_is_text']}</p>
            </div>
            
            <div class="section">
                <h3>{t['features_title']}</h3>
                <ul class="feature-list">
                    <li>{t['feature1']}</li>
                    <li>{t['feature2']}</li>
                    <li>{t['feature3']}</li>
                    <li>{t['feature4']}</li>
                </ul>
            </div>
            
            <div class="section">
                <h3>{t['how_to_title']}</h3>
                <ul class="step-list">
                    <li>{t['step1']}</li>
                    <li>{t['step2']}</li>
                    <li>{t['step3']}</li>
                    <li>{t['step4']}</li>
                    <li>{t['step5']}</li>
                </ul>
            </div>
            
            <div class="tip-box">
                <h4>{t['tips_title']}</h4>
                <ul class="step-list">
                    <li>{t['tip1']}</li>
                    <li>{t['tip2']}</li>
                    <li>{t['tip3']}</li>
                    <li>{t['tip4']}</li>
                </ul>
            </div>
            
            <p>{t['closing']}</p>
            
            <div class="footer">
                <p>{t['unsubscribe']}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        subject = t["subject"]
        return self.send_email(to_email, subject, html_body)

# Create singleton instance
email_service = EmailService()
