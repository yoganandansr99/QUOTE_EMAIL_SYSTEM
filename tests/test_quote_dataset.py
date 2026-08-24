import pytest
import os
import yaml
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from services.quote_service import QuoteService
from services.scheduler_service import DailyJobService


class TestQuoteDatasetAndLogic:
    """Unit tests for dataset loading, deduplication, categorization, and 365-day exclusion."""

    @pytest.mark.asyncio
    async def test_dataset_import_and_deduplication(self, db: AsyncIOMotorDatabase):
        """Test importing from data/quotes.json and ensuring duplicate prevention."""
        quote_service = QuoteService(db)

        # Import once
        res1 = await quote_service.import_quotes_from_dataset()
        assert "total_in_dataset" in res1
        assert res1["total_in_dataset"] > 0
        assert res1["total_in_db"] > 0

        # Import a second time: duplicate prevention must ensure 0 new quotes are added
        res2 = await quote_service.import_quotes_from_dataset()
        assert res2["imported"] == 0
        assert res2["duplicates_skipped"] == res1["total_in_dataset"]

    def test_quote_categorization_rules(self, db: AsyncIOMotorDatabase):
        """Test keyword-based and alias categorization logic."""
        quote_service = QuoteService(db)

        # Direct alias
        assert quote_service.categorize_quote("Any quote", raw_category="work") == "career"
        assert quote_service.categorize_quote("Any quote", raw_category="knowledge") == "study"
        assert quote_service.categorize_quote("Any quote", raw_category="mindfulness") == "happiness"

        # Keyword based matching
        cat1 = quote_service.categorize_quote("Great leadership requires humble service and inspiring teamwork.")
        assert cat1 == "leadership"

        cat2 = quote_service.categorize_quote("Daily discipline and consistent routine eliminate procrastination.")
        assert cat2 == "discipline"

        cat3 = quote_service.categorize_quote("Starting a venture involves calculated risk and constant innovation.")
        assert cat3 == "entrepreneurship"

        cat4 = quote_service.categorize_quote("Overcoming failure and adversity builds inner courage.")
        assert cat4 == "failure_resilience"

    @pytest.mark.asyncio
    async def test_365_day_quote_exclusion(self, db: AsyncIOMotorDatabase, test_email: str):
        """Test that a quote delivered to a user is excluded from selection for 365 days."""
        quote_service = QuoteService(db)

        user_id = "test_user_exclusion_123"

        # Insert a test quote
        q1_id = await quote_service.store_quote({
            "quote": "Test Quote Alpha One For Exclusion Rule",
            "author": "Exclusion Author A",
            "category": "discipline",
            "tags": ["discipline"]
        })
        assert q1_id is not None

        # Simulate that Quote 1 was sent to user yesterday
        await db.delivery_history.insert_one({
            "user_id": user_id,
            "quote_id": q1_id,
            "sent_at": datetime.utcnow() - timedelta(days=1),
            "status": "sent"
        })

        # Selection for this user must exclude Quote 1
        eligible = await quote_service.get_eligible_quote_for_user(
            user_id=user_id,
            interests=["discipline"],
            days=365
        )

        assert eligible is not None
        assert eligible["id"] != q1_id

    @pytest.mark.asyncio
    async def test_delivery_history_only_recorded_on_success(
        self,
        db: AsyncIOMotorDatabase,
        test_email: str
    ):
        """Verify delivery_history is saved only on successful email sending, while errors log to email_logs."""
        job_service = DailyJobService(db)

        # Create verified user
        user_res = await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["happiness"],
            "created_at": datetime.utcnow()
        })
        user_id = str(user_res.inserted_id)

        # Insert test quote
        await job_service.quote_service.store_quote({
            "quote": "Test Quote Happiness Delivery 99",
            "author": "Joy Author",
            "category": "happiness",
            "image_url": "https://example.com/test.jpg"
        })

        # Test Case A: Email fails
        with patch("services.email_service.email_service.send_daily_inspiration_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False

            result = await job_service.execute_daily_inspiration_job()
            assert result["failed"] >= 1

            # delivery_history must NOT have record
            delivery = await db.delivery_history.find_one({"user_id": user_id})
            assert delivery is None

            # email_logs MUST have failure record
            log_entry = await db.email_logs.find_one({"user_id": user_id, "status": "failed"})
            assert log_entry is not None

        # Test Case B: Email succeeds
        with patch("services.email_service.email_service.send_daily_inspiration_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await job_service.execute_daily_inspiration_job()
            assert result["sent"] >= 1

            # delivery_history MUST now have successful record
            delivery = await db.delivery_history.find_one({"user_id": user_id, "status": "sent"})
            assert delivery is not None

    def test_github_actions_workflow_syntax(self):
        """Validate .github/workflows/daily-inspiration.yml is valid YAML and has required schedule/secrets."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        workflow_path = os.path.join(base_dir, ".github", "workflows", "daily-inspiration.yml")

        assert os.path.exists(workflow_path), "Workflow YAML file must exist"

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_content = yaml.safe_load(f)

        assert "name" in workflow_content
        # In YAML, 'on' key parses to True in boolean or 'on' in dict
        on_key = True if True in workflow_content else "on"
        triggers = workflow_content[on_key]
        assert "schedule" in triggers
        assert "workflow_dispatch" in triggers
