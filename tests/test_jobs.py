import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from unittest.mock import patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings


@pytest.mark.asyncio
class TestJobsEndpoint:
    """Tests for protected daily inspiration job endpoints."""

    async def test_job_missing_cron_secret(self, client: AsyncClient):
        """Test calling daily job endpoint without X-Cron-Secret header fails with 401."""
        response = await client.post("/api/jobs/send-daily-inspiration")
        assert response.status_code == 401
        assert "Missing required authentication header" in response.json()["detail"]

    async def test_job_invalid_cron_secret(self, client: AsyncClient):
        """Test calling daily job endpoint with wrong X-Cron-Secret fails with 401."""
        response = await client.post(
            "/api/jobs/send-daily-inspiration",
            headers={"X-Cron-Secret": "wrong-secret-token"}
        )
        assert response.status_code == 401
        assert "Invalid X-Cron-Secret" in response.json()["detail"]

    async def test_job_valid_cron_secret_execution(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email: str
    ):
        """Test calling daily job endpoint with valid secret successfully runs the process."""
        # 1. Create a verified test user
        user_res = await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["success"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        user_id = str(user_res.inserted_id)

        # 2. Create a test quote in quotes collection
        quote_res = await db.quotes.insert_one({
            "quote": "Test Quote For Daily Job Execution",
            "author": "Job Tester",
            "category": "success",
            "quote_hash": "job_test_hash_unique_1",
            "tags": ["success", "test"],
            "created_at": datetime.utcnow()
        })
        quote_id = str(quote_res.inserted_id)

        # Mock email sending to simulate successful delivery
        with patch("services.email_service.email_service.send_daily_inspiration_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = await client.post(
                "/api/jobs/send-daily-inspiration",
                headers={"X-Cron-Secret": settings.cron_secret}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["job"] == "send-daily-inspiration"
            assert data["sent"] >= 1

            # Verify delivery_history was created
            delivery = await db.delivery_history.find_one({"user_id": user_id})
            assert delivery is not None
            assert delivery["status"] == "sent"

    async def test_import_quotes_endpoint(self, client: AsyncClient, db: AsyncIOMotorDatabase):
        """Test the protected quote import endpoint."""
        response = await client.post(
            "/api/jobs/import-quotes",
            headers={"X-Cron-Secret": settings.cron_secret}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "result" in data
