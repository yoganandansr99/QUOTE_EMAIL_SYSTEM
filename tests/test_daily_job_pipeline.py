import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from unittest.mock import patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scheduler_service import DailyJobService
from core.config import settings


@pytest.mark.asyncio
class TestDailyJobPipeline:
    """End-to-end tests for multi-user daily dispatch, Groq content integration, and error isolation."""

    async def test_multi_user_batch_with_one_failure_isolation(self, db: AsyncIOMotorDatabase):
        """When 1 user out of 3 fails (e.g. invalid email / SMTP refusal), other 2 users succeed."""
        # 1. User A (valid, multi-category)
        await db.users.insert_one({
            "email": "user_a@test.com",
            "status": "verified",
            "interests": ["success", "career"],
            "category_cycle_index": 0,
            "created_at": datetime.utcnow()
        })

        # 2. User B (will fail)
        await db.users.insert_one({
            "email": "user_fail@test.com",
            "status": "verified",
            "interests": ["study"],
            "category_cycle_index": 0,
            "created_at": datetime.utcnow()
        })

        # 3. User C (valid, single-category)
        await db.users.insert_one({
            "email": "user_c@test.com",
            "status": "verified",
            "interests": ["happiness"],
            "category_cycle_index": 0,
            "created_at": datetime.utcnow()
        })

        # Ensure quotes exist
        await db.quotes.insert_one({
            "quote": "Quote for A",
            "author": "Author A",
            "category": "success",
            "quote_hash": "pipeline_quote_a",
            "created_at": datetime.utcnow()
        })
        await db.quotes.insert_one({
            "quote": "Quote for B",
            "author": "Author B",
            "category": "study",
            "quote_hash": "pipeline_quote_b",
            "created_at": datetime.utcnow()
        })
        await db.quotes.insert_one({
            "quote": "Quote for C",
            "author": "Author C",
            "category": "happiness",
            "quote_hash": "pipeline_quote_c",
            "created_at": datetime.utcnow()
        })

        job_service = DailyJobService(db)

        # Mock send email such that user_fail@test.com returns False, others return True
        async def mock_send(to_email, **kwargs):
            if "fail" in to_email:
                return False
            return True

        with patch("services.email_service.email_service.send_daily_inspiration_email", side_effect=mock_send):
            result = await job_service.execute_daily_inspiration_job()

            assert result["success"] is True
            assert result["sent"] == 2
            assert result["failed"] == 1

            # Verify delivery_history only has records for user_a and user_c
            deliveries = await db.delivery_history.find({}).to_list(length=10)
            user_a = await db.users.find_one({"email": "user_a@test.com"})
            user_b = await db.users.find_one({"email": "user_fail@test.com"})
            user_c = await db.users.find_one({"email": "user_c@test.com"})

            delivery_user_ids = [d["user_id"] for d in deliveries]
            assert str(user_a["_id"]) in delivery_user_ids
            assert str(user_c["_id"]) in delivery_user_ids
            assert str(user_b["_id"]) not in delivery_user_ids

            # Verify user_a advanced cycle index, user_b did NOT
            user_a_updated = await db.users.find_one({"email": "user_a@test.com"})
            user_b_updated = await db.users.find_one({"email": "user_fail@test.com"})
            assert user_a_updated["category_cycle_index"] == 1
            assert user_b_updated["category_cycle_index"] == 0
