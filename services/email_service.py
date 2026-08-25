from typing import Optional, List
from datetime import datetime
import httpx
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings


class EmailService:
    def __init__(self):
        self.api_key = settings.resend_api_key
        self.email_from = settings.email_from
        self.email_from_name = settings.email_from_name
        self.api_url = "https://api.resend.com/emails"
        self.last_error: str = ""
    
    async def send_otp_email(self, to_email: str, otp: str) -> bool:
        """Send OTP verification email."""
        subject = "Your Daily Inspiration Verification Code"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">Daily Inspiration</h1>
            </div>
            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <h2 style="color: #333;">Verify Your Email</h2>
                <p style="color: #666;">Thank you for subscribing to Daily Inspiration!</p>
                <p style="color: #666;">Your verification code is:</p>
                <div style="background: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                    <span style="font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px;">{otp}</span>
                </div>
                <p style="color: #999; font-size: 14px;">This code will expire in {settings.otp_expiry_minutes} minutes.</p>
                <p style="color: #999; font-size: 14px;">If you didn't request this code, please ignore this email.</p>
            </div>
        </body>
        </html>
        """
        
        return await self._send_email(to_email, subject, body)
    
    async def send_daily_inspiration_email(
        self,
        to_email: str,
        quote: str,
        author: str,
        image_url: str,
        person_story: str,
        daily_action: str,
        user_id: str
    ) -> bool:
        """Send daily inspiration email."""
        subject = f"🌟 Your Daily Inspiration - {datetime.now().strftime('%B %d, %Y')}"
        base_url = getattr(settings, 'base_url', 'http://localhost:8000')
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0;">Good Morning!</h1>
                <p style="color: rgba(255,255,255,0.9); margin-top: 10px;">Your daily dose of inspiration is here ✨</p>
            </div>
            
            <div style="background: white; padding: 40px 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <p style="font-size: 24px; font-style: italic; color: #333; line-height: 1.6;">
                        "{quote}"
                    </p>
                    <p style="font-size: 18px; color: #667eea; margin-top: 15px;">— {author}</p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <img src="{image_url}" alt="Inspirational Image" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                </div>
                
                <div style="background: #f8f9fa; padding: 25px; border-radius: 10px; margin: 25px 0; border-left: 4px solid #667eea;">
                    <h3 style="color: #333; margin-top: 0;">👤 Person of the Day</h3>
                    <p style="color: #555; line-height: 1.6;">{person_story}</p>
                </div>
                
                <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 25px; border-radius: 10px; margin: 25px 0;">
                    <h3 style="color: #333; margin-top: 0;">💭 Today's Thought</h3>
                    <p style="color: #555; line-height: 1.6;">Let this quote inspire you to take action and make today count. Remember, every great journey begins with a single step.</p>
                </div>
                
                <div style="background: #fff3cd; padding: 25px; border-radius: 10px; margin: 25px 0; border-left: 4px solid #ffc107;">
                    <h3 style="color: #856404; margin-top: 0;">🎯 Today's Challenge</h3>
                    <p style="color: #856404; line-height: 1.6;">{daily_action}</p>
                </div>
                
                <div style="text-align: center; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                    <p style="color: #666; margin-bottom: 15px;">How did this inspire you today?</p>
                    <a href="{base_url}/api/feedback?user_id={user_id}&type=loved" style="display: inline-block; padding: 10px 20px; margin: 5px; background: #28a745; color: white; text-decoration: none; border-radius: 5px;">❤️ Loved it</a>
                    <a href="{base_url}/api/feedback?user_id={user_id}&type=useful" style="display: inline-block; padding: 10px 20px; margin: 5px; background: #17a2b8; color: white; text-decoration: none; border-radius: 5px;">👍 Useful</a>
                    <a href="{base_url}/api/feedback?user_id={user_id}&type=not_for_me" style="display: inline-block; padding: 10px 20px; margin: 5px; background: #6c757d; color: white; text-decoration: none; border-radius: 5px;">👎 Not for me</a>
                </div>
            </div>
            
            <div style="background: #333; padding: 20px; border-radius: 0 0 10px 10px; text-align: center;">
                <p style="color: #999; font-size: 14px; margin: 0;">
                    You're receiving this email because you subscribed to Daily Inspiration.
                    <br><br>
                    <a href="{base_url}/unsubscribe?email={to_email}" style="color: #667eea; text-decoration: none;">Unsubscribe</a> | 
                    <a href="{base_url}/feedback?email={to_email}" style="color: #667eea; text-decoration: none;">Give Feedback & Thoughts</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        return await self._send_email(to_email, subject, body)

    async def send_admin_feedback_notification(
        self,
        user_email: str,
        feedback_type: str,
        comment: Optional[str] = None,
        rating: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Send notification of user feedback to administrator email."""
        admin_email = getattr(settings, 'admin_feedback_email', 'promotionp270@gmail.com')
        subject = f"📬 New User Feedback: {feedback_type.upper()} from {user_email}"
        
        rating_stars = "⭐" * rating if rating else "Not specified"
        comment_display = comment if comment and comment.strip() else "No additional comment provided."
        timestamp_str = datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc; color: #1e293b;">
            <div style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 25px; border-radius: 12px 12px 0 0; text-align: center;">
                <h2 style="color: white; margin: 0; font-size: 22px;">📬 New Daily Inspiration Feedback</h2>
                <p style="color: rgba(255,255,255,0.9); margin-top: 6px; font-size: 14px;">Feedback submitted by a subscriber</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e2e8f0; border-top: none;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 10px 0; font-weight: bold; color: #64748b; width: 140px;">User Email:</td>
                        <td style="padding: 10px 0; font-weight: bold; color: #0f172a;">{user_email}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 10px 0; font-weight: bold; color: #64748b;">Feedback Type:</td>
                        <td style="padding: 10px 0;"><span style="background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 13px;">{feedback_type}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 10px 0; font-weight: bold; color: #64748b;">Rating:</td>
                        <td style="padding: 10px 0; font-size: 15px;">{rating_stars}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 10px 0; font-weight: bold; color: #64748b;">Submitted At:</td>
                        <td style="padding: 10px 0; color: #475569;">{timestamp_str}</td>
                    </tr>
                </table>

                <div style="background: #f8fafc; border-left: 4px solid #4f46e5; padding: 18px; border-radius: 6px; margin-top: 15px;">
                    <h4 style="margin: 0 0 8px 0; color: #334155; font-size: 14px;">User's Message / Feedback:</h4>
                    <p style="margin: 0; color: #1e293b; font-size: 15px; line-height: 1.6; white-space: pre-wrap;">{comment_display}</p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px; color: #94a3b8; font-size: 12px;">
                <p>Daily Inspiration System Notification · Destination: {admin_email}</p>
            </div>
        </body>
        </html>
        """

        return await self._send_email(admin_email, subject, body)
    
    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send an email via the Resend HTTPS API.
        Does not use SMTP/smtplib so it works reliably on Render Free tiers and cloud platforms.
        """
        self.last_error = ""
        api_key = self.api_key or settings.resend_api_key
        if not api_key:
            self.last_error = "RESEND_API_KEY is not configured in environment."
            print(f"Resend Error: {self.last_error}")
            return False

        from_addr = self.email_from or settings.email_from or "onboarding@resend.dev"
        from_name = self.email_from_name or settings.email_from_name or "Daily Inspiration"
        from_header = f"{from_name} <{from_addr}>" if from_name and "@" not in from_name else from_addr

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": from_header,
            "to": [to_email],
            "subject": subject,
            "html": body
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)

                if response.status_code in [200, 201]:
                    data = response.json()
                    if data and "id" in data:
                        return True
                    return True
                else:
                    error_msg = response.text
                    try:
                        err_json = response.json()
                        error_msg = err_json.get("message") or err_json.get("name") or error_msg
                    except Exception:
                        pass
                    self.last_error = f"Resend API Error (HTTP {response.status_code}): {error_msg}"
                    print(self.last_error)
                    return False
        except Exception as e:
            self.last_error = f"Resend HTTP dispatch failed: {str(e)}"
            print(self.last_error)
            return False


email_service = EmailService()
