import asyncio
import logging
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
from .groq_service import groq_service

logger = logging.getLogger("scheduler_service")


class DailyJobService:
    """
    Executes the daily inspiration email delivery job across verified subscribers.
    Integrates:
    - Multi-category cycling in exact preference order.
    - 365-day quote uniqueness enforcement.
    - Category image retrieval from MongoDB with rotation.
    - Groq AI generated Person of the Day, Today's Thought, and Today's Challenge with anti-hallucination guardrails.
    - Resilient error handling and batch processing isolation.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.quote_service = QuoteService(db)
        self.image_service = ImageService(db)

    async def execute_daily_inspiration_job(self) -> Dict[str, Any]:
        """
        Execute the complete daily inspiration email dispatch pipeline:
        1. Ensure quotes dataset and category images are seeded in MongoDB.
        2. Query all active verified subscribers.
        3. For each user:
           a. Calculate next category based on user's preference cycle index.
           b. Select 365-day unread quote for that category.
           c. Fetch category image from MongoDB.
           d. Call Groq AI for structured content (Person of the Day, Today's Thought, Today's Challenge).
           e. Send email via SMTP.
           f. Record delivery_history and advance category_cycle_index on success.
           g. Log failure and isolate errors so other users continue.
        """
        start_time = datetime.utcnow()
        print(f"[{start_time.isoformat()}] Starting Daily Inspiration Job...")

        # 1. Ensure quotes and images are populated in MongoDB
        await self.quote_service.ensure_minimum_quotes(minimum=50)
        await self.image_service.ensure_minimum_images(minimum_per_category=50)

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
            user_interests = subscriber.get("interests", []) or []

            try:
                # 3. Determine active category for today using preference cycling
                target_category = None
                next_cycle_index = 0

                if user_interests:
                    current_cycle_index = subscriber.get("category_cycle_index", 0)
                    if not isinstance(current_cycle_index, int) or current_cycle_index < 0:
                        current_cycle_index = 0
                    
                    effective_index = current_cycle_index % len(user_interests)
                    target_category = str(user_interests[effective_index]).lower().strip()
                    next_cycle_index = (effective_index + 1) % len(user_interests)

                # 4. Select 365-day eligible quote
                quote = await self.quote_service.get_eligible_quote_for_user(
                    user_id=user_id,
                    interests=user_interests if not target_category else None,
                    target_category=target_category,
                    days=365
                )

                if not quote:
                    print(f"No eligible quote found for user {user_email}. Skipping.")
                    skipped_count += 1
                    continue

                quote_id = quote.get("id")
                quote_category = quote.get("category") or target_category or "personal_growth"

                # 5. Fetch Category Image from MongoDB (with rotation and fallbacks)
                image_data = await self.image_service.get_image_for_category(
                    category=quote_category,
                    user_id=user_id
                )
                image_url = image_data.get("url")
                image_ref = image_data.get("image_reference")

                # 6. Groq AI Generation for Person of the Day, Today's Thought, and Today's Challenge
                verified_story = quote.get("person_story") or self._get_default_person_story(quote.get("author", "Inspirational Leader"))
                verified_action = quote.get("daily_action") or self._get_default_daily_action(quote_category)

                ai_content = await groq_service.generate_email_content(
                    quote=quote.get("quote", ""),
                    author=quote.get("author", "Unknown"),
                    category=quote_category,
                    verified_person_story=verified_story,
                    verified_daily_action=verified_action
                )

                # 7. Dispatch Email
                email_sent = await email_service.send_daily_inspiration_email(
                    to_email=user_email,
                    quote=quote.get("quote"),
                    author=quote.get("author"),
                    image_url=image_url,
                    person_story=ai_content.get("person_of_day", verified_story),
                    daily_action=ai_content.get("todays_challenge", verified_action),
                    user_id=user_id,
                    todays_thought=ai_content.get("todays_thought"),
                    category_name=quote_category
                )

                if email_sent:
                    # 8. Record successful delivery ONLY on success
                    await self._record_successful_delivery(
                        user_id=user_id,
                        quote_id=quote_id,
                        category=quote_category,
                        image_reference=image_ref
                    )

                    # Advance user category cycle index in MongoDB
                    if user_interests:
                        await self.db.users.update_one(
                            {"_id": subscriber["_id"]},
                            {
                                "$set": {
                                    "category_cycle_index": next_cycle_index,
                                    "updated_at": datetime.utcnow()
                                }
                            }
                        )

                    await self._log_email(
                        user_id=user_id,
                        email=user_email,
                        subject=f"Your Daily Inspiration - {datetime.utcnow().strftime('%B %d, %Y')}",
                        status="sent"
                    )
                    sent_count += 1
                else:
                    # Log failure in email_logs only (not delivery_history, do not advance cycle)
                    error_msg = getattr(email_service, "last_error", None) or "SMTP delivery rejected or failed to dispatch email."
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
            "errors": errors[:10]
        }

    async def send_daily_emails(self) -> Dict[str, Any]:
        """Backward-compatible alias for execute_daily_inspiration_job."""
        return await self.execute_daily_inspiration_job()

    async def _record_successful_delivery(
        self,
        user_id: str,
        quote_id: str,
        category: Optional[str] = None,
        image_reference: Optional[str] = None
    ):
        """Record successful delivery in delivery_history."""
        delivery_record = {
            "user_id": user_id,
            "quote_id": quote_id,
            "category": category,
            "image_reference": image_reference,
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
        return (
            f"{author} has inspired countless individuals through their wisdom and achievements. "
            "Their journey reminds us that every great accomplishment begins with a single step and the courage to pursue our dreams."
        )

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
