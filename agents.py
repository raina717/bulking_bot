import base64
import json
import os
import logging
from typing import Optional

import httpx
from anthropic import AsyncAnthropic, APIError, APIConnectionError, APITimeoutError, RateLimitError
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes3")

_claude_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


async def _ask_gemini(system_prompt: str, user_message: str) -> str:
    if _gemini_client is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    resp = await _gemini_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=[user_message],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
        )
    )
    return resp.text


async def _ask_hermes(system_prompt: str, user_message: str) -> str:
    payload = {
        "model": HERMES_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]


class FoodEstimate(BaseModel):
    food_name: str = Field(description="Short name of the food/meal identified")
    kcal: float = Field(description="Estimated total calories (kcal) for the whole portion")
    protein_g: float = Field(description="Estimated total protein (g) for the whole portion")
    confidence: str = Field(description="low, medium, or high")

FOOD_ESTIMATE_SYSTEM_PROMPT = (
    "You are a nutrition assistant estimating calories & protein from a food description or "
    "photo, for someone bulking in Indonesia. Assume a normal single-serving portion if not "
    "stated. If the user provides multiple meals (e.g., morning, afternoon, night), calculate "
    "the sum of all meals and combine their names. Use general knowledge of Indonesian home/street "
    "food. Always return your best total estimate, even if uncertain."
)


async def _estimate_food(content: list) -> Optional[dict]:
    """Call Gemini for food calorie/protein estimation."""
    if _gemini_client is None:
        logger.warning("Food estimate skipped: GEMINI_API_KEY is not set")
        return None
    try:
        resp = await _gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=FOOD_ESTIMATE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=FoodEstimate,
                temperature=0.1,
            )
        )
        return json.loads(resp.text)
    except Exception as e:
        logger.warning("Food estimate failed: %s", e)
        return None


async def estimate_food_from_text(description: str) -> Optional[dict]:
    return await _estimate_food([description])


async def estimate_food_from_image(image_bytes: bytes, media_type: str, caption: str = "") -> Optional[dict]:
    part = types.Part.from_bytes(data=image_bytes, mime_type=media_type)
    content = [part]
    if caption:
        content.append(caption)
    else:
        content.append("Estimate the calories & protein of this meal photo.")
    return await _estimate_food(content)


async def ask_agent(system_prompt: str, user_message: str) -> tuple[str, str]:
    try:
        answer = await _ask_gemini(system_prompt, user_message)
        return answer, "gemini"
    except Exception as e:
        logger.warning("Gemini failed (%s), falling back to Hermes...", e)

    try:
        answer = await _ask_hermes(system_prompt, user_message)
        return answer, "hermes"
    except Exception as e:
        logger.error("Hermes also failed: %s", e)
        return (
            "Maaf, API Gemini sedang bermasalah atau key-nya belum disetup. "
            "Coba cek GEMINI_API_KEY di file .env ya.",
            "none",
        )
