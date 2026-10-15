"""Settings endpoints: read merged settings, persist overrides in the data directory."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import Settings, get_settings, save_overrides

router = APIRouter()


class SettingsUpdate(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    compose_quality: str | None = None
    render_runner: str | None = None


def _public(settings: Settings) -> dict[str, Any]:
    return {
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "llm_api_key_set": bool(settings.llm_api_key),
        "compose_quality": settings.compose_quality,
        "render_runner": settings.render_runner,
    }


@router.get("")
def read_settings() -> dict[str, Any]:
    return _public(get_settings())


@router.put("")
def update_settings(payload: SettingsUpdate) -> dict[str, Any]:
    values = payload.model_dump(exclude_none=True)
    if values:
        save_overrides(values)
    return _public(get_settings())
