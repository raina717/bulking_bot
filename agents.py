"""
Router 2 agent: Claude (utama) dan Hermes (fallback, self-hosted via Ollama).

Alur:
1. Coba jawab pakai Claude dulu (akurasi lebih bisa diandalkan buat kalkulasi
   & saran nutrisi).
2. Kalau Claude gagal (API error, timeout, rate limit, atau ANTHROPIC_API_KEY
   belum diisi), otomatis fallback ke Hermes yang jalan lokal di VPS lewat
   Ollama, biar bot tetap bisa jawab.
"""
import os
import logging
import httpx
from anthropic import AsyncAnthropic, APIError, APIConnectionError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes3")

_claude_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


async def _ask_claude(system_prompt: str, user_message: str) -> str:
    if _claude_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY belum diisi")
    resp = await _claude_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        timeout=30.0,
    )
    return resp.content[0].text


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


async def ask_agent(system_prompt: str, user_message: str) -> tuple[str, str]:
    """
    Return (jawaban, nama_agent_yang_jawab).
    Coba Claude dulu, fallback ke Hermes kalau gagal.
    """
    try:
        answer = await _ask_claude(system_prompt, user_message)
        return answer, "claude"
    except (APIError, APIConnectionError, APITimeoutError, RateLimitError, RuntimeError) as e:
        logger.warning("Claude gagal (%s), fallback ke Hermes...", e)
    except Exception as e:
        logger.warning("Claude error tak terduga (%s), fallback ke Hermes...", e)

    try:
        answer = await _ask_hermes(system_prompt, user_message)
        return answer, "hermes"
    except Exception as e:
        logger.error("Hermes juga gagal: %s", e)
        return (
            "Waduh, dua-duanya (Claude & Hermes) lagi gak bisa dihubungi. "
            "Cek koneksi API key / Ollama service di VPS ya.",
            "none",
        )
