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
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
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
    try:
        answer = await _ask_claude(system_prompt, user_message)
        return answer, "claude"
    except (APIError, APIConnectionError, APITimeoutError, RateLimitError, RuntimeError) as e:
        logger.warning("Claude failed (%s), falling back to Hermes...", e)
    except Exception as e:
        logger.warning("Unexpected Claude error (%s), falling back to Hermes...", e)

    try:
        answer = await _ask_hermes(system_prompt, user_message)
        return answer, "hermes"
    except Exception as e:
        logger.error("Hermes also failed: %s", e)
        return (
            "Both Claude and Hermes are unreachable. "
            "Please check your API key or Ollama service connection.",
            "none",
        )
