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
                "greeting": f"Hi {user_name}! 👋",
                "transition": f"You've entered the {phase_names['en'].get(new_phase, new_phase)}.",
                "tips_title": "Tips for this phase:",
                "unsubscribe": "Don't want these emails? You can turn off notifications in your Profile Settings."
            },
            "hi": {
                "subject": f"आपका चक्र {phase_names['hi'].get(new_phase, new_phase)} में प्रवेश कर गया है",
                "greeting": f"नमस्ते {user_name}! 👋",
                "transition": f"आप {phase_names['hi'].get(new_phase, new_phase)} में प्रवेश कर चुके हैं।",
                "tips_title": "इस चरण के लिए सुझाव:",
                "unsubscribe": "इन ईमेल नहीं चाहते? आप अपनी प्रोफ़ाइल सेटिंग्स में अधिसूचनाएं बंद कर सकते हैं।"
            },
            "gu": {
                "subject": f"તમારો ચક્ર {phase_names['gu'].get(new_phase, new_phase)} માં પ્રવેશ કર્યો છે",
                "greeting": f"હેલો {user_name}! 👋",
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
                "greeting": f"Hi {user_name}! 📅",
                "message": f"Your next period is predicted to start on <strong>{predicted_date}</strong> ({days_until} day{'s' if days_until != 1 else ''} away).",
                "prepare": "Time to prepare! Make sure you have everything you need.",
                "unsubscribe": "Don't want these reminders? You can adjust notification settings in your Profile."
            },
            "hi": {
                "subject": f"आपका मासिक धर्म {days_until} दिन{'ों' if days_until != 1 else ''} में आने की उम्मीद है",
                "greeting": f"नमस्ते {user_name}! 📅",
                "message": f"आपके अगले मासिक धर्म की शुरुआत <strong>{predicted_date}</strong> ({days_until} दिन{'ों' if days_until != 1 else ''} बाद) होने की भविष्यवाणी की गई है।",
                "prepare": "तैयारी करने का समय! सुनिश्चित करें कि आपके पास सब कुछ है।",
                "unsubscribe": "इन अनुस्मारक नहीं चाहते? आप अपनी प्रोफ़ाइल में अधिसूचना सेटिंग्स समायोजित कर सकते हैं।"
            },
            "gu": {
                "subject": f"તમારો માસિક ધર્મ {days_until} દિવસ{'ો' if days_until != 1 else ''} માં આવવાની અપેક્ષા છે",
                "greeting": f"હેલો {user_name}! 📅",
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

# Create singleton instance
email_service = EmailService()
