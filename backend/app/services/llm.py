"""LLM access through an OpenAI-compatible chat completions endpoint."""

import base64
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

REQUEST_TIMEOUT_SECONDS = 120
VISION_TIMEOUT_SECONDS = 300
# This model reasons before it writes. Measured reasoning runs: about 1800 tokens for one image,
# 2700 to 5800 for a matching call over nine described assets, and the provider default can run out
# first, which comes back as an empty answer. Ask for room explicitly.
TEXT_MAX_TOKENS = 16000
VISION_MAX_TOKENS = 4000


class LLMError(RuntimeError):
    """Raised when the LLM is not configured or the request fails."""


def read_message(body: dict[str, Any]) -> str:
    """The visible answer of a chat completion, with a useful error when it is empty.

    A reasoning model spends tokens in its own channel before writing anything visible, so a tight
    output cap can return a successful, empty answer. That is an error rather than an empty string,
    or the caller would silently store nothing.
    """
    choices = body.get("choices") or []
    message = (choices[0].get("message") if choices else None) or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    reason = choices[0].get("finish_reason") if choices else None
    hint = " (the whole budget went to reasoning)" if reason == "length" else ""
    raise LLMError(f"the model returned no visible answer{hint} [finish_reason={reason}]")


def _endpoint() -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise LLMError("LLM is not configured. Set the API key and model in Settings first.")
    return (
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        settings.llm_model,
        (settings.llm_api_key),
    )


async def _post(payload: dict[str, Any], api_key: str, timeout: int) -> str:
    url, _, _ = _endpoint()
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
    return read_message(body)


async def complete(system: str, user: str) -> str:
    _, model, api_key = _endpoint()
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.8,
        "max_tokens": TEXT_MAX_TOKENS,
    }
    return await _post(payload, api_key, REQUEST_TIMEOUT_SECONDS)


async def complete_with_images(
    system: str, user: str, images: list[Path], max_tokens: int | None = VISION_MAX_TOKENS
) -> str:
    """Ask the model about one or more local images, sent inline as data URLs.

    The output budget is deliberately generous: a small cap is consumed by the model's reasoning
    channel before it writes anything, and the caller then stores nothing at all.
    """
    _, model, api_key = _endpoint()
    parts: list[dict[str, Any]] = [{"type": "text", "text": user}]
    for image in images:
        encoded = base64.b64encode(image.read_bytes()).decode()
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
            }
        )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": parts},
        ],
        "temperature": 0.2,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return await _post(payload, api_key, VISION_TIMEOUT_SECONDS)
