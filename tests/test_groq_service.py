from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.groq_service import GroqService


@pytest.mark.asyncio
class TestGroqService:
    """Unit and integration tests for GroqService structured generation and anti-hallucination fallbacks."""

    async def test_fallback_when_api_key_missing(self):
        """When GROQ_API_KEY is empty, returns safe verified fallback content."""
        service = GroqService(api_key="")
        result = await service.generate_email_content(
            quote="Action is the foundational key to all success.",
            author="Pablo Picasso",
            category="success",
            verified_person_story="Pablo Picasso was an influential Spanish painter and sculptor.",
            verified_daily_action="Identify one key goal today."
        )

        assert isinstance(result, dict)
        assert "person_of_day" in result
        assert "todays_thought" in result
        assert "todays_challenge" in result
        assert "Picasso" in result["person_of_day"]
        assert len(result["person_of_day"]) > 10
        assert len(result["todays_thought"]) > 10
        assert len(result["todays_challenge"]) > 10

    async def test_successful_groq_structured_generation(self):
        """When Groq returns valid JSON, parses and returns structured output."""
        service = GroqService(api_key="gsk_test_mock_key_valid")

        mock_groq_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"person_of_day": "Pablo Picasso revolutionized modern art through relentless creative experimentation.", "todays_thought": "True mastery is not a passive state but an active pursuit forged by deliberate action.", "todays_challenge": "Spend 20 minutes creating something without judging the initial outcome."}'
                    }
                }
            ]
        }

        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = mock_groq_response

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await service.generate_email_content(
                quote="Action is the foundational key to all success.",
                author="Pablo Picasso",
                category="success",
                verified_person_story="Pablo Picasso was an influential Spanish painter."
            )

            assert "Pablo Picasso revolutionized modern art" in result["person_of_day"]
            assert "True mastery is not a passive state" in result["todays_thought"]
            assert "Spend 20 minutes creating" in result["todays_challenge"]

    async def test_groq_malformed_json_fallback(self):
        """When Groq returns malformed non-JSON, gracefully falls back without crashing."""
        service = GroqService(api_key="gsk_test_mock_key_valid")

        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Not a valid JSON payload"}}]
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await service.generate_email_content(
                quote="Opportunities don't happen. You create them.",
                author="Chris Grosser",
                category="success",
                verified_person_story="Chris Grosser has inspired many through entrepreneurship."
            )

            assert isinstance(result, dict)
            assert "person_of_day" in result
            assert "todays_thought" in result
            assert "todays_challenge" in result

    async def test_groq_http_error_fallback(self):
        """When Groq returns 429 rate limit or 500 error, returns verified fallback."""
        service = GroqService(api_key="gsk_test_mock_key_valid")

        mock_response = MagicMock(status_code=429, text="Rate limit exceeded")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await service.generate_email_content(
                quote="Opportunities don't happen. You create them.",
                author="Chris Grosser",
                category="success"
            )

            assert isinstance(result, dict)
            assert len(result["person_of_day"]) > 0
            assert len(result["todays_thought"]) > 0
            assert len(result["todays_challenge"]) > 0

    async def test_groq_timeout_fallback(self):
        """When Groq times out, returns verified fallback seamlessly."""
        service = GroqService(api_key="gsk_test_mock_key_valid")

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
            result = await service.generate_email_content(
                quote="Opportunities don't happen. You create them.",
                author="Chris Grosser",
                category="success"
            )

            assert isinstance(result, dict)
            assert "Chris Grosser" in result["person_of_day"] or "wisdom" in result["person_of_day"]
