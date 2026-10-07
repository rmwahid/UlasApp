"""Stage 2 (Phase 1): assign the single uploaded photo to every script line."""

from pathlib import Path

from app.services.state import VISUAL_FILE, StageError, write_json


async def run(ctx: dict) -> None:
    state = ctx["state"]
    directory = Path(ctx["dir"])
    photo_rel = state["inputs"].get("photo")
    if not photo_rel:
        raise StageError("No photo input recorded for this project.")
    photo_path = directory / photo_rel
    if not photo_path.exists():
        raise StageError(f"Photo file is missing: {photo_rel}")
    lines = state["timeline"].get("lines", [])
    if not lines:
        raise StageError("Timeline has no lines; run the script stage first.")
    shots = [
        {
            "id": f"S{index + 1}",
            "line": line["id"],
            "asset": photo_rel,
            "start": line["start"],
            "end": line["end"],
        }
        for index, line in enumerate(lines)
    ]
    write_json(directory, VISUAL_FILE, {"shots": shots})
