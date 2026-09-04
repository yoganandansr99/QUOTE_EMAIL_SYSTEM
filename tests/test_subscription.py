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

    async def test_get_google_client_id(self, client: AsyncClient):
        """Test Google Client ID retrieval endpoint."""
        response = await client.get("/api/subscription/google-client-id")
        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data
        assert "is_configured" in data

    async def test_google_auth_new_user_with_token(self, client: AsyncClient, db, test_email):
        """Test Google Auth creating a new verified user."""
        mock_payload = {
            "email": test_email,
            "email_verified": True,
            "name": "Google User",
            "picture": "https://example.com/photo.jpg"
        }

        with patch("routers.subscription.verify_google_token", new_callable=AsyncMock) as mock_verify, \
             patch("routers.subscription.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
            mock_verify.return_value = mock_payload

            response = await client.post(
                "/api/subscription/google-auth",
                json={"credential": "mock-google-jwt-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["is_new"] is True
            assert data["email"] == test_email
            assert data["name"] == "Google User"

            # Check database user record
            user = await db.users.find_one({"email": test_email})
            assert user is not None
            assert user["status"] == "verified"
            assert user["auth_provider"] == "google"
            assert user["name"] == "Google User"
            mock_welcome.assert_called_once()

    async def test_google_auth_existing_user(self, client: AsyncClient, db, test_email):
        """Test Google Auth signing in an existing user."""
        await db.users.insert_one({
            "email": test_email,
            "status": "pending",
            "interests": ["career"]
        })

        mock_payload = {
            "email": test_email,
            "email_verified": True,
            "name": "Existing User"
        }

        with patch("routers.subscription.verify_google_token", new_callable=AsyncMock) as mock_verify, \
             patch("routers.subscription.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
            mock_verify.return_value = mock_payload

            response = await client.post(
                "/api/subscription/google-auth",
                json={"credential": "mock-google-jwt-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["is_new"] is False
            assert data["email"] == test_email

            user = await db.users.find_one({"email": test_email})
            assert user["status"] == "verified"
            assert user["auth_provider"] == "google"

    async def test_google_auth_invalid_token(self, client: AsyncClient):
        """Test Google Auth with invalid token."""
        from fastapi import HTTPException
        with patch("routers.subscription.verify_google_token", side_effect=HTTPException(status_code=400, detail="Invalid Google authentication token.")):
            response = await client.post(
                "/api/subscription/google-auth",
                json={"credential": "invalid-token"}
            )

            assert response.status_code == 400
            assert "Invalid Google authentication token" in response.json()["detail"]

    async def test_google_auth_missing_credential(self, client: AsyncClient):
        """Test Google Auth rejects requests missing genuine credential token."""
        response = await client.post(
            "/api/subscription/google-auth",
            json={"email": "random_fake@gmail.com", "name": "Fake User"}
        )

        assert response.status_code == 400
        assert "credential" in response.json()["detail"].lower()

    async def test_verify_google_token_id_token_pathway(self):
        """Test verify_google_token succeeds with standard ID token."""
        from routers.subscription import verify_google_token
        import httpx

        mock_resp = httpx.Response(
            status_code=200,
            json={"email": "verified_user@gmail.com", "email_verified": True, "name": "Verified User"},
            request=httpx.Request("GET", "https://oauth2.googleapis.com/tokeninfo")
        )

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            payload = await verify_google_token("valid_id_token_jwt")
            assert payload["email"] == "verified_user@gmail.com"
            assert payload["name"] == "Verified User"

    async def test_verify_google_token_access_token_pathway(self):
        """Test verify_google_token succeeds with OAuth2 access token fallback."""
        from routers.subscription import verify_google_token
        import httpx

        mock_id_fail = httpx.Response(
            status_code=400,
            json={"error": "invalid_token"},
            request=httpx.Request("GET", "https://oauth2.googleapis.com/tokeninfo")
        )
        mock_access_ok = httpx.Response(
            status_code=200,
            json={"scope": "email profile openid"},
            request=httpx.Request("GET", "https://oauth2.googleapis.com/tokeninfo")
        )
        mock_userinfo = httpx.Response(
            status_code=200,
            json={"email": "oauth_user@gmail.com", "email_verified": True, "name": "OAuth User"},
            request=httpx.Request("GET", "https://www.googleapis.com/oauth2/v3/userinfo")
        )

        with patch("httpx.AsyncClient.get", side_effect=[mock_id_fail, mock_access_ok, mock_userinfo]):
            payload = await verify_google_token("ya29.valid_access_token")
            assert payload["email"] == "oauth_user@gmail.com"
            assert payload["name"] == "OAuth User"

