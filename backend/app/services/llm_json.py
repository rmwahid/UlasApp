"""Reading a JSON object out of a model answer, with the fences models like to add."""

import json
from typing import Any


class LLMOutputError(ValueError):
    """Raised when a model answer does not contain a usable JSON object."""


def extract_json_object(text: str) -> dict[str, Any]:
    """Return the first JSON object in `text`, ignoring code fences and surrounding prose."""
    cleaned = text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMOutputError("the answer did not contain a JSON object")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"the answer was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMOutputError("the answer was not a JSON object")
    return parsed
