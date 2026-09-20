import json
import logging
import sys
import os
from typing import Dict, Any, Optional
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

logger = logging.getLogger("groq_service")


class GroqService:
    """
    Service for generating structured daily inspiration email content using Groq AI.
    Enforces strict anti-hallucination guardrails and reliable fallbacks.
    """

    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model if model is not None else (settings.groq_model or "llama-3.3-70b-versatile")

    def get_fallback_content(
        self,
        quote: str,
        author: str,
        category: str,
        verified_person_story: Optional[str] = None,
        verified_daily_action: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Produce verified fallback content when Groq is unavailable or returns an error.
        Guarantees zero downtime and safe content.
        """
        # Person of the day fallback
        if verified_person_story and verified_person_story.strip():
            person_of_day = verified_person_story.strip()
        else:
            person_of_day = (
                f"{author} has inspired generations through their wisdom, dedication, and enduring principles. "
                "Their journey demonstrates that true success is built through perseverance and purposeful action."
            )

        # Today's thought fallback
        todays_thought = (
            f"Let this wisdom from {author} remind you that every meaningful achievement begins with a conscious choice. "
            "Focus on the present moment and take steady, intentional action toward your highest potential."
        )

        # Today's challenge fallback
        category_actions = {
            "success": "Identify one key priority today and complete a focused 25-minute sprint toward it.",
            "career": "Take 15 minutes today to organize your workflow or refine a professional deliverable.",
            "study": "Read or study for 20 minutes on a subject that expands your current knowledge.",
            "personal_growth": "Write down three things you are grateful for and one habit you choose to practice today.",
            "leadership": "Offer genuine encouragement or constructive assistance to a peer or teammate today.",
            "discipline": "Finish your most important task before checking non-essential notifications.",
            "entrepreneurship": "Brainstorm one creative solution to a daily problem and outline two action steps.",
            "failure_resilience": "Reflect on a recent obstacle and identify one valuable insight it provided.",
            "happiness": "Perform one small act of kindness or share a warm word of appreciation with someone today."
        }

        if verified_daily_action and verified_daily_action.strip():
            todays_challenge = verified_daily_action.strip()
        else:
            todays_challenge = category_actions.get(
                category.lower().strip(),
                "Take one positive, intentional step today that moves you closer to your goals."
            )

        return {
            "person_of_day": person_of_day,
            "todays_thought": todays_thought,
            "todays_challenge": todays_challenge
        }

    async def generate_email_content(
        self,
        quote: str,
        author: str,
        category: str,
        verified_person_story: Optional[str] = None,
        verified_daily_action: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate structured Person of the Day, Today's Thought, and Today's Challenge using Groq.
        Returns a dictionary with keys: person_of_day, todays_thought, todays_challenge.
        Falls back safely without throwing exceptions if Groq fails or API key is missing.
        """
        fallback = self.get_fallback_content(
            quote=quote,
            author=author,
            category=category,
            verified_person_story=verified_person_story,
            verified_daily_action=verified_daily_action
        )

        api_key = (self.api_key or settings.groq_api_key or os.getenv("GROQ_API_KEY", "")).strip()
        if not api_key:
            return fallback

        model = (self.model or settings.groq_model or "llama-3.3-70b-versatile").strip()

        # Build prompt with strict anti-hallucination instructions
        verified_info = verified_person_story.strip() if verified_person_story else f"{author} is a renowned figure noted for their inspirational words and contributions."

        system_prompt = (
            "You are an inspiring, factually rigorous editorial AI for the 'Daily Inspiration' email publication.\n"
            "Your job is to generate exactly three sections in valid JSON format:\n"
            "1. 'person_of_day': 2-4 lines summarizing the verified background of the person. "
            "CRITICAL ANTI-HALLUCINATION RULE: Do NOT invent awards, dates, institutions, quotes, degrees, positions, or personal facts. "
            "Summarize or rewrite ONLY the verified facts supplied in the user prompt.\n"
            "2. 'todays_thought': 2-4 lines explaining the inner philosophical meaning, mindset lesson, and practical relevance of the provided quote. "
            "Base this ONLY on the provided quote text. Do not invent external facts.\n"
            "3. 'todays_challenge': 1 concise, practical, realistic, and safe daily action challenge that the user can complete today based directly on the quote. "
            "Do NOT provide medical, financial, or hazardous advice.\n\n"
            "STRICT OUTPUT REQUIREMENT: Output MUST be a valid JSON object with exactly these three keys:\n"
            "{\n"
            '  "person_of_day": "...",\n'
            '  "todays_thought": "...",\n'
            '  "todays_challenge": "..."\n'
            "}"
        )

        user_prompt = (
            f"Category: {category}\n"
            f"Quote: \"{quote}\"\n"
            f"Quote Author: {author}\n"
            f"Verified Person Information: {verified_info}\n\n"
            "Generate the JSON object containing person_of_day, todays_thought, and todays_challenge according to the strict instructions."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.6,
            "max_tokens": 500
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    self.GROQ_API_URL,
                    json=payload,
                    headers=headers
                )

                if response.status_code != 200:
                    logger.warning(
                        "Groq API returned HTTP %s: %s",
                        response.status_code,
                        response.text[:200]
                    )
                    return fallback

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return fallback

                content_raw = choices[0].get("message", {}).get("content", "")
                if not content_raw:
                    return fallback

                parsed = json.loads(content_raw)
                person_of_day = str(parsed.get("person_of_day", "")).strip()
                todays_thought = str(parsed.get("todays_thought", "")).strip()
                todays_challenge = str(parsed.get("todays_challenge", "")).strip()

                return {
                    "person_of_day": person_of_day if person_of_day else fallback["person_of_day"],
                    "todays_thought": todays_thought if todays_thought else fallback["todays_thought"],
                    "todays_challenge": todays_challenge if todays_challenge else fallback["todays_challenge"]
                }

        except json.JSONDecodeError as jde:
            logger.warning("Failed to decode Groq JSON response: %s", str(jde))
            return fallback
        except httpx.TimeoutException:
            logger.warning("Groq API request timed out after 12s. Using fallback.")
            return fallback
        except Exception as e:
            logger.warning("Groq API call encountered an unexpected error: %s", str(e))
            return fallback


groq_service = GroqService()
