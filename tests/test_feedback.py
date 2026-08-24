import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
class TestFeedback:
    """Tests for feedback endpoints."""

    async def test_submit_user_feedback_portal(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test submitting feedback from web portal and sending to admin."""
        with patch("services.email_service.email_service.send_admin_feedback_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            response = await client.post(
                "/api/feedback/submit",
                json={
                    "email": test_email,
                    "feedback_type": "suggestion",
                    "comment": "Please add more quotes from Marcus Aurelius!",
                    "rating": 5
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "received" in data["message"].lower()

            # Verify saved to MongoDB
            saved = await db.feedback.find_one({"user_email": test_email})
            assert saved is not None
            assert saved["feedback_type"] == "suggestion"
            assert saved["rating"] == 5
            assert "Marcus Aurelius" in saved["comment"]

            # Verify admin notification was triggered
            mock_notify.assert_called_once()
            args, kwargs = mock_notify.call_args
            assert kwargs.get("user_email") == test_email or args[0] == test_email

    async def test_submit_user_feedback_invalid_email(self, client: AsyncClient):
        """Test feedback submission with invalid email format."""
        response = await client.post(
            "/api/feedback/submit",
            json={
                "email": "invalid-email-address",
                "feedback_type": "general",
                "comment": "Nice website"
            }
        )
        assert response.status_code in [400, 422]

    async def test_submit_user_feedback_empty_comment(self, client: AsyncClient, test_email):
        """Test feedback submission with empty comment."""
        response = await client.post(
            "/api/feedback/submit",
            json={
                "email": test_email,
                "feedback_type": "general",
                "comment": "   "
            }
        )
        assert response.status_code == 400
        assert "feedback comment" in response.json()["detail"]

    async def test_submit_feedback_success(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test submitting feedback for specific quote."""
        with patch("services.email_service.email_service.send_admin_feedback_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            # Create test user
            user_result = await db.users.insert_one({
                "email": test_email,
                "status": "verified",
                "interests": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            user_id = str(user_result.inserted_id)

            # Create test quote
            quote_result = await db.quotes.insert_one({
                "quote": "Test Quote",
                "author": "Test Author",
                "category": "success",
                "quote_hash": "test_hash_123",
                "created_at": datetime.utcnow()
            })
            quote_id = str(quote_result.inserted_id)

            response = await client.post(
                "/api/feedback",
                params={
                    "user_id": user_id,
                    "quote_id": quote_id,
                    "feedback_type": "loved"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["feedback_type"] == "loved"

    async def test_submit_feedback_invalid_user(self, client: AsyncClient):
        """Test submitting feedback with invalid user ID."""
        response = await client.post(
            "/api/feedback",
            params={
                "user_id": "invalid_id",
                "quote_id": "invalid_id",
                "feedback_type": "loved"
            }
        )

        assert response.status_code in [400, 404]

    async def test_get_feedback_history(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test getting feedback history."""
        # Create test user & feedback
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        await db.feedback.insert_one({
            "user_email": test_email,
            "feedback_type": "loved",
            "comment": "Great quote!",
            "rating": 5,
            "created_at": datetime.utcnow()
        })

        response = await client.get(
            "/api/feedback/history",
            params={"email": test_email}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_email
        assert data["feedback_count"] >= 1
        assert len(data["feedback"]) >= 1

    async def test_feedback_via_email_link(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test feedback submission via email link."""
        with patch("services.email_service.email_service.send_admin_feedback_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            # Create test user
            user_result = await db.users.insert_one({
                "email": test_email,
                "status": "verified",
                "interests": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            user_id = str(user_result.inserted_id)

            # Create test quote
            quote_result = await db.quotes.insert_one({
                "quote": "Test Quote",
                "author": "Test Author",
                "category": "success",
                "quote_hash": "test_hash_456",
                "created_at": datetime.utcnow()
            })
            quote_id = str(quote_result.inserted_id)

            # Create delivery history
            await db.delivery_history.insert_one({
                "user_id": user_id,
                "quote_id": quote_id,
                "sent_at": datetime.utcnow(),
                "status": "sent"
            })

            response = await client.get(
                "/api/feedback/email",
                params={
                    "user_id": user_id,
                    "type": "useful"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
