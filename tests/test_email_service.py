import pytest
import smtplib
from unittest.mock import patch, AsyncMock, MagicMock
from services.email_service import EmailService


@pytest.mark.asyncio
class TestEmailServiceSMTP:
    """Unit tests for EmailService with standard SMTP protocol."""

    async def test_send_email_smtp_starttls_success(self):
        """Test successful email dispatch via SMTP with STARTTLS (Port 587)."""
        service = EmailService()
        service.smtp_host = "smtp.example.com"
        service.smtp_port = 587
        service.smtp_user = "sender@example.com"
        service.smtp_password = "secret_password"
        service.smtp_use_tls = True
        service.smtp_use_ssl = False
        service.email_from = "sender@example.com"
        service.email_from_name = "Daily Inspiration"

        mock_server = MagicMock()

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value = mock_server

            success = await service._send_email(
                to_email="subscriber@example.com",
                subject="Test Subject",
                body="<p>Hello World</p>"
            )

            assert success is True
            mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=15.0)
            mock_server.ehlo.assert_called()
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("sender@example.com", "secret_password")
            mock_server.sendmail.assert_called_once()
            
            args, kwargs = mock_server.sendmail.call_args
            assert args[0] == "sender@example.com"
            assert args[1] == ["subscriber@example.com"]
            assert "Daily Inspiration <sender@example.com>" in args[2]
            assert "Subject: Test Subject" in args[2]
            mock_server.quit.assert_called_once()

    async def test_send_email_smtp_ssl_success(self):
        """Test successful email dispatch via SMTP with SSL (Port 465)."""
        service = EmailService()
        service.smtp_host = "smtp.example.com"
        service.smtp_port = 465
        service.smtp_user = "sender@example.com"
        service.smtp_password = "secret_password"
        service.smtp_use_tls = False
        service.smtp_use_ssl = True
        service.email_from = "sender@example.com"

        mock_server = MagicMock()

        with patch("smtplib.SMTP_SSL") as mock_smtp_ssl_cls:
            mock_smtp_ssl_cls.return_value = mock_server

            success = await service._send_email(
                to_email="subscriber@example.com",
                subject="SSL Subject",
                body="<p>SSL Test</p>"
            )

            assert success is True
            mock_smtp_ssl_cls.assert_called_once_with("smtp.example.com", 465, timeout=15.0)
            mock_server.login.assert_called_once_with("sender@example.com", "secret_password")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    async def test_send_email_authentication_error(self):
        """Test error handling when SMTP authentication fails."""
        service = EmailService()
        service.smtp_host = "smtp.example.com"
        service.smtp_port = 587
        service.smtp_user = "sender@example.com"
        service.smtp_password = "wrong_password"

        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

        with patch("smtplib.SMTP", return_value=mock_server):
            success = await service._send_email(
                to_email="subscriber@example.com",
                subject="Test Auth Failure",
                body="<p>Hello</p>"
            )

            assert success is False
            assert "Authentication failed" in service.last_error

    async def test_send_email_connection_error(self):
        """Test error handling when SMTP server cannot be connected."""
        service = EmailService()
        service.smtp_host = "invalid.smtp.host"
        service.smtp_port = 587

        with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "Connection refused")):
            success = await service._send_email(
                to_email="subscriber@example.com",
                subject="Test Connection Error",
                body="<p>Hello</p>"
            )

            assert success is False
            assert "Connection failed" in service.last_error

    async def test_send_email_recipient_refused(self):
        """Test error handling when SMTP recipient is refused."""
        service = EmailService()
        service.smtp_host = "smtp.example.com"

        mock_server = MagicMock()
        mock_server.sendmail.side_effect = smtplib.SMTPRecipientsRefused({"bad@example.com": (550, b"User unknown")})

        with patch("smtplib.SMTP", return_value=mock_server):
            success = await service._send_email(
                to_email="bad@example.com",
                subject="Test Recipient Refused",
                body="<p>Hello</p>"
            )

            assert success is False
            assert "Recipient refused" in service.last_error

    async def test_send_email_missing_host(self):
        """Test safety fallback when SMTP_HOST is not configured."""
        service = EmailService()
        service.smtp_host = ""

        with patch("core.config.settings.smtp_host", ""):
            success = await service._send_email(
                to_email="user@example.com",
                subject="Test",
                body="<p>Test</p>"
            )

            assert success is False
            assert "SMTP_HOST is not configured" in service.last_error

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

    async def test_send_admin_feedback_notification_invokes_send_email(self):
        """Test send_admin_feedback_notification formats template and calls _send_email."""
        service = EmailService()
        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_internal_send:
            mock_internal_send.return_value = True

            result = await service.send_admin_feedback_notification(
                user_email="subscriber@example.com",
                feedback_type="loved",
                comment="Great inspiration!",
                rating=5,
                user_id="user_123"
            )

            assert result is True
            mock_internal_send.assert_called_once()
            args = mock_internal_send.call_args[0]
            assert "promotionp270@gmail.com" in args[0]
            assert "New User Feedback: LOVED" in args[1]
            assert "subscriber@example.com" in args[2]
            assert "Great inspiration!" in args[2]
