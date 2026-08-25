import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from models.user import UserStatus
from .email_service import email_service
from .quote_service import QuoteService
from .image_service import ImageService


class DailyJobService:
    """
    Executes the daily inspiration email delivery job across verified subscribers.
    Does not use background cron/APScheduler; triggered on-demand or via GitHub Actions.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.quote_service = QuoteService(db)
        self.image_service = ImageService()

    async def execute_daily_inspiration_job(self) -> Dict[str, Any]:
        """
        Execute the daily inspiration email process:
        1. Ensure quotes dataset is seeded.
        2. Query all active verified subscribers.
        3. For each user, select an eligible quote (365-day uniqueness enforced).
        4. Fetch & cache related imagery.
        5. Send personalized email.
        6. Save delivery_history ONLY after successful delivery.
        7. Log failures to email_logs.
        8. Continue processing other users if one fails.
        """
        start_time = datetime.utcnow()
        print(f"[{start_time.isoformat()}] Starting Daily Inspiration Job...")

        # 1. Ensure quotes are populated from dataset
        await self.quote_service.ensure_minimum_quotes(minimum=50)

        # 2. Get all verified subscribers
        subscribers = list(await self.db.users.find({
            "status": UserStatus.VERIFIED.value
        }).to_list(length=None))

        total_subscribers = len(subscribers)
        print(f"Found {total_subscribers} verified subscribers to process.")

        sent_count = 0
        failed_count = 0
        skipped_count = 0
        errors: List[Dict[str, str]] = []

        for subscriber in subscribers:
            user_id = str(subscriber.get("_id"))
            user_email = subscriber.get("email")
            user_interests = subscriber.get("interests", [])

            try:
                # 3. Select 365-day eligible quote
                quote = await self.quote_service.get_eligible_quote_for_user(
                    user_id=user_id,
                    interests=user_interests,
                    days=365
                )

                if not quote:
                    print(f"No eligible quote found for user {user_email}. Skipping.")
                    skipped_count += 1
                    continue

                quote_id = quote.get("id")

                # 4. Fetch image if not cached
                if not quote.get("image_url"):
                    image_data = await self.image_service.get_image_for_quote(
                        quote=quote.get("quote"),
                        category=quote.get("category"),
                        tags=quote.get("tags")
                    )
                    quote["image_url"] = image_data.get("url")
                    quote["image_source"] = image_data.get("source")
                    quote["image_photographer"] = image_data.get("photographer")

                    await self.quote_service.update_quote_image(quote_id, image_data)

                # Prepare content
                person_story = quote.get("person_story") or self._get_default_person_story(quote.get("author"))
                daily_action = quote.get("daily_action") or self._get_default_daily_action(quote.get("category"))

                # 5. Send Email
                email_sent = await email_service.send_daily_inspiration_email(
                    to_email=user_email,
                    quote=quote.get("quote"),
                    author=quote.get("author"),
                    image_url=quote.get("image_url"),
                    person_story=person_story,
                    daily_action=daily_action,
                    user_id=user_id
                )

                if email_sent:
                    # 6. Save delivery_history ONLY on successful delivery
                    await self._record_successful_delivery(user_id=user_id, quote_id=quote_id)
                    await self._log_email(
                        user_id=user_id,
                        email=user_email,
                        subject=f"Your Daily Inspiration - {datetime.utcnow().strftime('%B %d, %Y')}",
                        status="sent"
                    )
                    sent_count += 1
                else:
                    # Log failure in email_logs only (not delivery_history)
                    error_msg = getattr(email_service, "last_error", None) or "Resend API delivery rejected or failed to dispatch email."
                    await self._log_email(
                        user_id=user_id,
                        email=user_email,
                        subject=f"Your Daily Inspiration - {datetime.utcnow().strftime('%B %d, %Y')}",
                        status="failed",
                        error=error_msg
                    )
                    failed_count += 1
                    errors.append({"email": user_email, "error": error_msg})

                # Slight delay to prevent mail server throttling
                await asyncio.sleep(0.3)

            except Exception as e:
                error_msg = str(e)
                print(f"Error processing subscriber {user_email}: {error_msg}")
                await self._log_email(
                    user_id=user_id,
                    email=user_email,
                    subject=f"Your Daily Inspiration - {datetime.utcnow().strftime('%B %d, %Y')}",
                    status="failed",
                    error=error_msg
                )
                failed_count += 1
                errors.append({"email": user_email, "error": error_msg})

        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()
        print(f"Daily Inspiration Job finished in {duration_seconds:.2f}s. Sent: {sent_count}, Failed: {failed_count}, Skipped: {skipped_count}.")

        return {
            "success": True,
            "job": "send-daily-inspiration",
            "executed_at": start_time.isoformat(),
            "duration_seconds": duration_seconds,
            "total_subscribers": total_subscribers,
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "errors": errors[:10]  # Return sample of errors if any
        }

    async def send_daily_emails(self) -> Dict[str, Any]:
        """Backward-compatible alias for execute_daily_inspiration_job."""
        return await self.execute_daily_inspiration_job()

    async def _record_successful_delivery(self, user_id: str, quote_id: str):
        """Record successful delivery in delivery_history."""
        delivery_record = {
            "user_id": user_id,
            "quote_id": quote_id,
            "sent_at": datetime.utcnow(),
            "status": "sent"
        }
        await self.db.delivery_history.insert_one(delivery_record)

    async def _log_email(self, user_id: str, email: str, subject: str, status: str, error: Optional[str] = None):
        """Log email sending attempt in email_logs."""
        email_log = {
            "user_id": user_id,
            "email": email,
            "subject": subject,
            "status": status,
            "error_message": error,
            "sent_at": datetime.utcnow()
        }
        await self.db.email_logs.insert_one(email_log)

    def _get_default_person_story(self, author: str) -> str:
        """Get a default inspirational background story."""
        return f"{author} has inspired countless individuals through their wisdom and achievements. Their journey reminds us that every great accomplishment begins with a single step and the courage to pursue our dreams."

    def _get_default_daily_action(self, category: str) -> str:
        """Get a default actionable challenge based on category."""
        actions = {
            "success": "Take one small step today toward a goal you've been postponing.",
            "career": "Spend 15 minutes learning a new skill that will advance your career.",
            "study": "Read an article or chapter about a topic you've been curious about.",
            "personal_growth": "Write down three things you're grateful for and one area you'd like to improve.",
            "leadership": "Offer help or guidance to someone who could benefit from your experience.",
            "discipline": "Complete a task you've been avoiding before the day ends.",
            "entrepreneurship": "Spend 20 minutes working on a business idea or project you're passionate about.",
            "failure_resilience": "Identify one setback from your past and reflect on what it taught you.",
            "happiness": "Do something kind for yourself or someone else today."
        }
        return actions.get(category, "Take one positive action today that aligns with your goals and values.")


# Backward-compatible class alias
SchedulerService = DailyJobService
