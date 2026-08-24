import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
class TestSubscription:
    """Tests for subscription endpoints."""

    async def test_request_otp_success(self, client: AsyncClient, test_email):
        """Test successful OTP request."""
        with patch("services.email_service.email_service.send_otp_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = await client.post(
                "/api/subscription/request-otp",
                json={"email": test_email}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "OTP sent successfully" in data["message"]
            assert data["expires_in_minutes"] == 5

    async def test_request_otp_invalid_email(self, client: AsyncClient):
        """Test OTP request with invalid email."""
        response = await client.post(
            "/api/subscription/request-otp",
            json={"email": "invalid-email"}
        )

        assert response.status_code in [400, 422]

    async def test_request_otp_already_subscribed(self, client: AsyncClient, db, test_email):
        """Test that an already verified/subscribed user cannot subscribe again."""
        # Insert a verified user into the database
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["success", "happiness"]
        })

        # Attempt to request OTP for new subscription
        response = await client.post(
            "/api/subscription/request-otp",
            json={"email": test_email}
        )

        assert response.status_code == 400
        assert "already subscribed" in response.json()["detail"].lower()

    async def test_request_otp_rate_limit(self, client: AsyncClient, test_email):
        """Test OTP rate limiting."""
        with patch("services.email_service.email_service.send_otp_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # First request
            response1 = await client.post(
                "/api/subscription/request-otp",
                json={"email": test_email}
            )
            assert response1.status_code == 200

            # Second immediate request (should be rate limited)
            response2 = await client.post(
                "/api/subscription/request-otp",
                json={"email": test_email}
            )
            assert response2.status_code == 429

    async def test_verify_otp_invalid_format(self, client: AsyncClient, test_email):
        """Test OTP verification with invalid format."""
        response = await client.post(
            "/api/subscription/verify-otp",
            json={"email": test_email, "otp": "123"}
        )

        assert response.status_code == 400

    async def test_verify_otp_wrong_code(self, client: AsyncClient, test_email):
        """Test OTP verification with wrong code."""
        response = await client.post(
            "/api/subscription/verify-otp",
            json={"email": test_email, "otp": "123456"}
        )

        assert response.status_code == 400
        assert "No valid OTP found" in response.json()["detail"]

    async def test_get_subscription_status_new_user(self, client: AsyncClient):
        """Test subscription status for new user."""
        response = await client.get(
            "/api/subscription/status",
            params={"email": "new_user@test.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_subscribed"] is False
        assert data["is_verified"] is False

    async def test_unsubscribe_user_not_found(self, client: AsyncClient):
        """Test unsubscribe for non-existent user."""
        response = await client.post(
            "/api/subscription/unsubscribe",
            params={"email": "nonexistent@test.com"}
        )

        assert response.status_code == 404
