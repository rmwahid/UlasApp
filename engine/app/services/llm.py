"""LLM access through an OpenAI-compatible chat completions endpoint."""

import httpx

from app.core.config import get_settings


class LLMError(RuntimeError):
    """Raised when the LLM is not configured or the request fails."""


async def complete(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise LLMError(
            "LLM is not configured. Set the API key and model in Settings first."
        )
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.8,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response did not contain a message.") from exc
