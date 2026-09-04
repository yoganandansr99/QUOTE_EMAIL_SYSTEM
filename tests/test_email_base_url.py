import pytest
import os
from unittest.mock import patch
from core.config import settings
from services.email_service import email_service


def test_clean_base_url_property():
    """Verify clean_base_url trims trailing slashes."""
    with patch.object(settings, 'app_base_url', 'https://my-azure-app.azurewebsites.net/'):
        assert settings.clean_base_url == "https://my-azure-app.azurewebsites.net"
        assert settings.base_url == "https://my-azure-app.azurewebsites.net"
        assert email_service.base_url == "https://my-azure-app.azurewebsites.net"


def test_app_url_env_priority():
    """Verify APP_URL takes priority and normalizes https."""
    with patch.object(settings, 'app_url', 'https://custom-domain.com/'):
        with patch.object(settings, 'app_base_url', ''):
            assert settings.clean_base_url == "https://custom-domain.com"
            assert email_service.base_url == "https://custom-domain.com"


def test_website_hostname_azure_autodetect():
    """Verify Azure WEBSITE_HOSTNAME auto-detection prepends https://."""
    with patch.dict(os.environ, {"WEBSITE_HOSTNAME": "inspire-app.azurewebsites.net"}, clear=False):
        with patch.object(settings, 'app_url', ''):
            with patch.object(settings, 'app_base_url', ''):
                with patch.dict(os.environ, {"APP_URL": "", "APP_BASE_URL": "", "BASE_URL": ""}):
                    assert settings.clean_base_url == "https://inspire-app.azurewebsites.net"
                    assert email_service.base_url == "https://inspire-app.azurewebsites.net"


@pytest.mark.asyncio
async def test_otp_email_contains_azure_base_url():
    """Verify that OTP email contains the production APP_BASE_URL."""
    azure_url = "https://daily-inspiration-prod.azurewebsites.net"
    with patch.object(settings, 'app_base_url', azure_url):
        with patch.object(email_service, '_send_email') as mock_send:
            mock_send.return_value = True
            
            await email_service.send_otp_email(
                to_email="subscriber@example.com",
                otp="849201"
            )
            
            assert mock_send.called
            args, kwargs = mock_send.call_args
            to_email, subject, body = args
            
            assert to_email == "subscriber@example.com"
            assert "849201" in body
            assert f"{azure_url}/verify?email=subscriber@example.com" in body
            assert "localhost" not in body


@pytest.mark.asyncio
async def test_daily_inspiration_email_contains_all_azure_links():
    """Verify that all feedback, preferences, and unsubscribe links in daily emails use APP_BASE_URL."""
    azure_url = "https://daily-inspiration-prod.azurewebsites.net"
    with patch.object(settings, 'app_base_url', azure_url):
        with patch.object(email_service, '_send_email') as mock_send:
            mock_send.return_value = True
            
            await email_service.send_daily_inspiration_email(
                to_email="subscriber@example.com",
                quote="The future belongs to those who believe in the beauty of their dreams.",
                author="Eleanor Roosevelt",
                image_url="https://images.pexels.com/sample.jpg",
                person_story="Eleanor Roosevelt championed universal human rights.",
                daily_action="Write down 3 things you are grateful for today.",
                user_id="user_123456789"
            )
            
            assert mock_send.called
            args, kwargs = mock_send.call_args
            to_email, subject, body = args
            
            # Feedback links
            assert f"{azure_url}/api/feedback?user_id=user_123456789&type=loved" in body
            assert f"{azure_url}/api/feedback?user_id=user_123456789&type=useful" in body
            assert f"{azure_url}/api/feedback?user_id=user_123456789&type=not_for_me" in body
            
            # Management links
            assert f"{azure_url}/unsubscribe?email=subscriber@example.com" in body
            assert f"{azure_url}/preferences?email=subscriber@example.com" in body
            assert f"{azure_url}/feedback?email=subscriber@example.com" in body
            
            # No localhost URLs
            assert "localhost" not in body
            assert "127.0.0.1" not in body
