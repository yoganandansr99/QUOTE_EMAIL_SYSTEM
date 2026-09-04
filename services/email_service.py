from typing import Optional, List
from datetime import datetime
import asyncio
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings


class EmailService:
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.smtp_use_ssl = settings.smtp_use_ssl
        self.email_from = settings.email_from
        self.email_from_name = settings.email_from_name
        self.last_error: str = ""

    @property
    def base_url(self) -> str:
        """Resolve centralized application base URL for email hyperlinks."""
        raw_url = (
            getattr(settings, "app_base_url", None)
            or getattr(settings, "base_url", None)
            or os.getenv("APP_BASE_URL")
            or os.getenv("BASE_URL")
            or "http://localhost:8000"
        )
        return str(raw_url).strip().rstrip("/")
    
    async def send_otp_email(self, to_email: str, otp: str) -> bool:
        """Send OTP verification email."""
        subject = "Your Daily Inspiration Verification Code"
        base_url = self.base_url
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
                <div style="text-align: center; margin: 25px 0;">
                    <a href="{base_url}/verify?email={to_email}" style="display: inline-block; padding: 12px 28px; background: #667eea; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px;">Enter Code on Website →</a>
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
        base_url = self.base_url
        
        # Ensure image_url is always a valid HTTP/HTTPS image URL with fallback
        safe_image_url = str(image_url).strip() if image_url and str(image_url).strip() not in ("None", "null", "") else ""
        if not safe_image_url or not safe_image_url.startswith("http"):
            safe_image_url = "https://images.pexels.com/photos/1114690/pexels-photo-1114690.jpeg?auto=compress&cs=tinysrgb&w=800"
        
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
                    <img src="{safe_image_url}" alt="Inspirational Image" width="540" style="width: 100%; max-width: 540px; height: auto; display: block; margin: 0 auto; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 0;" />
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
                    <a href="{base_url}/preferences?email={to_email}" style="color: #667eea; text-decoration: none;">Manage Preferences</a> | 
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
    
    def _send_smtp_sync(self, to_email: str, subject: str, body: str) -> bool:
        """
        Synchronous helper to dispatch an email via standard SMTP protocol.
        Runs in an async worker thread to preserve non-blocking performance.
        """
        self.last_error = ""
        host = self.smtp_host or settings.smtp_host
        port = self.smtp_port or settings.smtp_port
        user = self.smtp_user or settings.smtp_user
        password = self.smtp_password or settings.smtp_password
        use_tls = self.smtp_use_tls if self.smtp_use_tls is not None else settings.smtp_use_tls
        use_ssl = self.smtp_use_ssl if self.smtp_use_ssl is not None else settings.smtp_use_ssl
        # Resolve from_addr and from_name intelligently
        raw_from = (self.email_from or settings.email_from or os.getenv("EMAIL_FROM", "")).strip()
        raw_name = (self.email_from_name or settings.email_from_name or os.getenv("EMAIL_FROM_NAME", "")).strip()

        if raw_from and "@" in raw_from:
            from_addr = raw_from
            from_name = raw_name or "Daily Inspiration"
        elif raw_from and "@" not in raw_from:
            # If a display name was passed into EMAIL_FROM instead of an email address
            from_name = raw_from
            from_addr = user or "noreply@dailyinspiration.com"
        else:
            from_addr = user or "noreply@dailyinspiration.com"
            from_name = raw_name or "Daily Inspiration"

        if not host:
            self.last_error = "SMTP_HOST is not configured in environment."
            print(f"SMTP Error: {self.last_error}")
            return False

        if not to_email:
            self.last_error = "Recipient email address (to_email) is missing or empty."
            print(f"SMTP Error: {self.last_error}")
            return False

        # Construct MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email.utils.formataddr((from_name, from_addr)) if from_name else from_addr
        msg["To"] = to_email
        msg["Date"] = email.utils.formatdate(localtime=True)
        domain = host if ("." in host and not host.replace(".", "").isdigit()) else "localhost"
        msg["Message-ID"] = email.utils.make_msgid(domain=domain)

        # Attach HTML payload
        html_part = MIMEText(body, "html", "utf-8")
        msg.attach(html_part)

        server = None
        try:
            if use_ssl or port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15.0)
            else:
                server = smtplib.SMTP(host, port, timeout=15.0)
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()

            if user and password:
                server.login(user, password)

            server.sendmail(from_addr, [to_email], msg.as_string())
            return True

        except smtplib.SMTPAuthenticationError as e:
            error_detail = e.smtp_error.decode("utf-8", errors="ignore") if isinstance(e.smtp_error, bytes) else str(e)
            self.last_error = f"SMTP Authentication failed: {error_detail}"
            print(f"SMTP Error: {self.last_error}")
            return False
        except smtplib.SMTPConnectError as e:
            self.last_error = f"SMTP Connection failed to {host}:{port}: {str(e)}"
            print(f"SMTP Error: {self.last_error}")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            self.last_error = f"SMTP Recipient refused for {to_email}: {str(e)}"
            print(f"SMTP Error: {self.last_error}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            self.last_error = f"SMTP Server unexpectedly disconnected from {host}:{port}: {str(e)}"
            print(f"SMTP Error: {self.last_error}")
            return False
        except smtplib.SMTPException as e:
            self.last_error = f"SMTP Protocol Error: {str(e)}"
            print(f"SMTP Error: {self.last_error}")
            return False
        except Exception as e:
            self.last_error = f"SMTP dispatch failed: {str(e)}"
            print(f"SMTP Error: {self.last_error}")
            return False
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send an email via SMTP protocol asynchronously without blocking the event loop.
        """
        return await asyncio.to_thread(self._send_smtp_sync, to_email, subject, body)


email_service = EmailService()
