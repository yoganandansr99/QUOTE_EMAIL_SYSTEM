import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.email_service import EmailService


@pytest.mark.asyncio
class TestEmailServiceResend:
    """Unit tests for EmailService with Resend HTTPS API."""

    async def test_send_email_success(self):
        """Test successful email dispatch via Resend API."""
        service = EmailService()
        service.api_key = "re_test_api_key"
        service.email_from = "onboarding@resend.dev"
        service.email_from_name = "Daily Inspiration"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            success = await service._send_email(
                to_email="subscriber@example.com",
                subject="Test Subject",
                body="<p>Hello World</p>"
            )

            assert success is True
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["headers"]["Authorization"] == "Bearer re_test_api_key"
            assert call_kwargs["json"]["to"] == ["subscriber@example.com"]
            assert call_kwargs["json"]["subject"] == "Test Subject"
            assert "Daily Inspiration <onboarding@resend.dev>" in call_kwargs["json"]["from"]

    async def test_send_email_api_error_response(self):
        """Test error handling when Resend API returns HTTP 422/400."""
        service = EmailService()
        service.api_key = "re_test_api_key"

        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = '{"message": "Invalid to address", "name": "validation_error"}'
        mock_response.json.return_value = {"message": "Invalid to address", "name": "validation_error"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            success = await service._send_email(
                to_email="invalid_email",
                subject="Test Subject",
                body="<p>Hello World</p>"
            )

            assert success is False

    async def test_send_email_missing_api_key(self):
        """Test safety fallback when RESEND_API_KEY is not set."""
        service = EmailService()
        service.api_key = ""

        with patch("core.config.settings.resend_api_key", ""):
            success = await service._send_email(
                to_email="user@example.com",
                subject="Test",
                body="<p>Test</p>"
            )

            assert success is False

    async def test_send_otp_email_invokes_send_email(self):
        """Test send_otp_email formats template and calls _send_email."""
        service = EmailService()
        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_internal_send:
            mock_internal_send.return_value = True

            result = await service.send_otp_email("user@example.com", "123456")

            assert result is True
            mock_internal_send.assert_called_once()
            args = mock_internal_send.call_args[0]
            assert args[0] == "user@example.com"
            assert "Verification Code" in args[1]
            assert "123456" in args[2]

    async def test_send_daily_inspiration_email_invokes_send_email(self):
        """Test send_daily_inspiration_email formats template and calls _send_email."""
        service = EmailService()
        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_internal_send:
            mock_internal_send.return_value = True

            result = await service.send_daily_inspiration_email(
                to_email="user@example.com",
                quote="Stay hungry, stay foolish.",
                author="Steve Jobs",
                image_url="https://images.pexels.com/sample.jpg",
                person_story="Steve Jobs co-founded Apple.",
                daily_action="Take one bold step today.",
                user_id="user_123"
            )

            assert result is True
            mock_internal_send.assert_called_once()
            args = mock_internal_send.call_args[0]
            assert args[0] == "user@example.com"
            assert "Your Daily Inspiration" in args[1]
            assert "Stay hungry, stay foolish." in args[2]
            assert "Steve Jobs" in args[2]
