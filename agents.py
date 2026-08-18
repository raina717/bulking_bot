import base64
import json
import os
import logging
from typing import Optional

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

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
    "food. Always return your best total estimate, even if uncertain. Reply in JSON format strictly matching the requested schema."
)

async def _ask_groq(system_prompt: str, user_message: str, response_format: str = "text") -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set")
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3
    }
    
    if response_format == "json_object":
        payload["response_format"] = {"type": "json_object"}
        
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


async def estimate_food_from_text(description: str) -> Optional[dict]:
    """Call Groq for text-based food calorie/protein estimation using JSON mode."""
    if not GROQ_API_KEY:
        logger.warning("Food estimate text skipped: GROQ_API_KEY is not set")
        return None
        
    try:
        # We append a reminder to output strict JSON matching the fields so Groq's json_object mode parses properly.
        prompt = FOOD_ESTIMATE_SYSTEM_PROMPT + '\n\nYou must reply ONLY with a JSON object containing keys: "food_name", "kcal", "protein_g", "confidence". Do not wrap in markdown code blocks.'
        
        response_text = await _ask_groq(prompt, description, response_format="json_object")
        data = json.loads(response_text)
        
        # Ensure correct types
        return {
            "food_name": str(data.get("food_name", "Unknown")),
            "kcal": float(data.get("kcal", 0)),
            "protein_g": float(data.get("protein_g", 0)),
            "confidence": str(data.get("confidence", "low"))
        }
    except Exception as e:
        logger.warning("Food estimate from text failed: %s", e)
        return None


async def estimate_food_from_image(image_bytes: bytes, media_type: str, caption: str = "") -> Optional[dict]:
    """Call Gemini Vision for image-based food calorie/protein estimation."""
    if _gemini_client is None:
        logger.warning("Food estimate image skipped: GEMINI_API_KEY is not set")
        return None
    try:
        part = types.Part.from_bytes(data=image_bytes, mime_type=media_type)
        content = [part]
        if caption:
            content.append(caption)
        else:
            content.append("Estimate the calories & protein of this meal photo.")
            
        resp = await _gemini_client.aio.models.generate_content(
            model='gemini-2.0-flash',
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
        logger.warning("Food estimate from image failed: %s", e)
        return None


async def ask_agent(system_prompt: str, user_message: str) -> tuple[str, str]:
    """Standard conversational agent (now routed to Groq)."""
    try:
        answer = await _ask_groq(system_prompt, user_message)
        return answer, "groq"
    except Exception as e:
        logger.error("Groq chat failed: %s", e)
        return (
            "Maaf, API Groq sedang bermasalah atau key-nya belum disetup. "
            "Coba cek GROQ_API_KEY di file .env kamu ya.",
            "none",
        )
