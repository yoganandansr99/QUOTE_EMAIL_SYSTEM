import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from unittest.mock import patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scheduler_service import DailyJobService
from services.quote_service import QuoteService


@pytest.mark.asyncio
class TestCategoryPreferenceCycling:
    """Tests verifying multiple category preference cycling behavior in exact order."""

    async def test_single_category_user_cycle(self, db: AsyncIOMotorDatabase):
        """User with 1 category always receives that category on every execution."""
        # 1. Create user with single category
        user_res = await db.users.insert_one({
            "email": "single_cat_test@test.com",
            "status": "verified",
            "interests": ["study"],
            "category_cycle_index": 0,
            "created_at": datetime.utcnow()
        })
        user_id = str(user_res.inserted_id)

        # 2. Add quotes in study category
        await db.quotes.insert_one({
            "quote": "Learning is a treasure that will follow its owner everywhere.",
            "author": "Chinese Proverb",
            "category": "study",
            "quote_hash": "single_cat_study_1",
            "created_at": datetime.utcnow()
        })

        job_service = DailyJobService(db)

        with patch("services.email_service.email_service.send_daily_inspiration_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Run job 3 times
            for _ in range(3):
                result = await job_service.execute_daily_inspiration_job()
                assert result["sent"] >= 1

            # Verify deliveries are in 'study' category
            deliveries = await db.delivery_history.find({"user_id": user_id}).to_list(length=10)
            assert len(deliveries) >= 1
            for deliv in deliveries:
                assert deliv.get("category") == "study"

    async def test_multi_category_cycling_order(self, db: AsyncIOMotorDatabase):
        """User with ['success', 'study', 'discipline'] cycles through them in exact order."""
        email = "multi_cat_cycle_test@test.com"
        categories = ["success", "study", "discipline"]

        user_res = await db.users.insert_one({
            "email": email,
            "status": "verified",
            "interests": categories,
            "category_cycle_index": 0,
            "created_at": datetime.utcnow()
        })
        user_id = str(user_res.inserted_id)

        # Seed 1 quote per category
        for cat in categories:
            await db.quotes.insert_one({
                "quote": f"Unique quote for {cat}",
                "author": f"Author for {cat}",
                "category": cat,
                "quote_hash": f"multi_cat_hash_{cat}",
                "created_at": datetime.utcnow()
            })

        job_service = DailyJobService(db)

        with patch("services.email_service.email_service.send_daily_inspiration_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Day 1: Expected category = success (index 0 -> advances to 1)
            await job_service.execute_daily_inspiration_job()
            u1 = await db.users.find_one({"_id": user_res.inserted_id})
            assert u1["category_cycle_index"] == 1

            # Day 2: Expected category = study (index 1 -> advances to 2)
            await job_service.execute_daily_inspiration_job()
            u2 = await db.users.find_one({"_id": user_res.inserted_id})
            assert u2["category_cycle_index"] == 2

            # Day 3: Expected category = discipline (index 2 -> advances to 0)
            await job_service.execute_daily_inspiration_job()
            u3 = await db.users.find_one({"_id": user_res.inserted_id})
            assert u3["category_cycle_index"] == 0

            # Day 4: Cycles back to success (index 0 -> advances to 1)
            await job_service.execute_daily_inspiration_job()
            u4 = await db.users.find_one({"_id": user_res.inserted_id})
            assert u4["category_cycle_index"] == 1

    async def test_preference_change_safe_bounds(self, db: AsyncIOMotorDatabase):
        """When user changes preferences from 3 categories to 2, index remains safely in bounds."""
        email = "pref_change_test@test.com"
        user_res = await db.users.insert_one({
            "email": email,
            "status": "verified",
            "interests": ["success", "career", "study"],
            "category_cycle_index": 2,  # Was pointing at 'study'
            "created_at": datetime.utcnow()
        })
        user_id = str(user_res.inserted_id)

        # User updates interests to only 2 categories: ['leadership', 'happiness']
        await db.users.update_one(
            {"_id": user_res.inserted_id},
            {"$set": {"interests": ["leadership", "happiness"]}}
        )

        # Seed quotes
        await db.quotes.insert_one({
            "quote": "Leadership quote for test",
            "author": "Leader",
            "category": "leadership",
            "quote_hash": "pref_change_leader_1",
            "created_at": datetime.utcnow()
        })
        await db.quotes.insert_one({
            "quote": "Happiness quote for test",
            "author": "Happy",
            "category": "happiness",
            "quote_hash": "pref_change_happy_1",
            "created_at": datetime.utcnow()
        })

        job_service = DailyJobService(db)

        with patch("services.email_service.email_service.send_daily_inspiration_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            # Index 2 % 2 = 0 -> selects leadership, advances to (0+1)%2 = 1
            await job_service.execute_daily_inspiration_job()

            updated = await db.users.find_one({"_id": user_res.inserted_id})
            assert updated["category_cycle_index"] == 1
