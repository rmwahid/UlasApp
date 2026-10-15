"""Stage: describe the uploaded material with the vision model, before anything is rendered.

This runs on its own so the user can read what the model saw, correct it, and only then ask for the
video. A wrong description is worse than none, because it silently drives the shot placement.
"""

from pathlib import Path

from app.core import media
from app.core.config import get_settings
from app.services import describe
from app.services.llm import LLMError
from app.services.state import AssetRecord, StageContext, StageError

DESCRIBE_ATTEMPTS = 3


async def _describe_one(directory: Path, asset: AssetRecord) -> str:
    """Describe one asset, retrying empty answers; this model reasons and can answer nothing."""
    reason = "no attempt ran"
    for _ in range(DESCRIBE_ATTEMPTS):
        try:
            return await describe.describe_asset(directory, asset)
        except (LLMError, media.MediaError) as exc:
            reason = str(exc)[:160]
    raise StageError(f"{asset['name']}: {reason}")


async def run(ctx: StageContext) -> None:
    settings = get_settings()
    state = ctx["state"]
    directory = Path(ctx["dir"])
    inputs = state["inputs"]
    assets: list[AssetRecord] = inputs.get("assets") or []
    if not assets:
        raise StageError("No material was uploaded for this project.")
    if not settings.llm_api_key or not settings.llm_model:
        raise StageError("No LLM is configured. Add the API key and model in Settings first.")
    failures: list[str] = []
    for asset in assets:
        if asset.get("description"):
            continue
        try:
            asset["description"] = await _describe_one(directory, asset)
        except StageError as exc:
            failures.append(str(exc))
        state["describe"] = {
            "described": sum(1 for item in assets if item.get("description")),
            "total": len(assets),
        }
    if failures:
        state["describe"]["failed"] = failures
        raise StageError("Some material could not be described: " + "; ".join(failures)[:400])
