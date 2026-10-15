import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

_OVERRIDE_FILE = "settings.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ULASAPP_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "UlasApp Engine"
    data_dir: Path = Path.home() / ".ulasapp"
    frontend_origin: str = "http://localhost:5173"
    frontend_origin_alt: str = "http://127.0.0.1:5173"

    # Timeline spine (voiceless mode): reading-speed based durations
    reading_words_per_second: float = 2.7
    min_card_seconds: float = 1.8
    line_pause_seconds: float = 0.35
    # The hook is the one card a viewer has not committed to yet, so it holds longer than the rest
    # even when its line is short.
    hook_min_card_seconds: float = 2.6

    # Card readability: a card must stay up long enough to be READ, not just long enough to feel
    # calm. QA checks every card against a settled beat plus a per-word reading time.
    read_settle_seconds: float = 0.55
    read_seconds_per_word: float = 0.26

    # Material indexing: scene-change sensitivity of the clip scan (higher = fewer scenes)
    scene_threshold: float = 10.0

    # LLM (OpenAI-compatible chat completions endpoint)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""

    # HyperFrames composition render
    compose_quality: str = "looks"
    render_runner: str = "npx"  # "npx" (Node 22+) or "bunx" (Bun 1.4+)
    ffmpeg_dir: str = ""  # optional explicit FFmpeg bin dir; auto-detected when empty


def _overrides_path(data_dir: Path) -> Path:
    return data_dir / _OVERRIDE_FILE


def get_settings() -> Settings:
    """Settings from environment, merged with JSON overrides stored in the data directory."""
    base = Settings()
    base.data_dir.mkdir(parents=True, exist_ok=True)
    overrides_path = _overrides_path(base.data_dir)
    if overrides_path.exists():
        try:
            overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            overrides = {}
        allowed = set(Settings.model_fields.keys())
        clean = {k: v for k, v in overrides.items() if k in allowed}
        if clean:
            return Settings(**clean)
    return base


def save_overrides(values: dict[str, Any]) -> None:
    """Persist a subset of settings as JSON overrides in the data directory."""
    base = Settings()
    base.data_dir.mkdir(parents=True, exist_ok=True)
    allowed = set(Settings.model_fields.keys())
    clean = {k: v for k, v in values.items() if k in allowed}
    _overrides_path(base.data_dir).write_text(json.dumps(clean, indent=2), encoding="utf-8")
