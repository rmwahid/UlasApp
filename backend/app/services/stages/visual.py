"""Stage: index the material and plan which asset covers which script line."""

import asyncio
from pathlib import Path

from app.core import media
from app.core.config import get_settings
from app.services import matching, shotlist
from app.services.state import SHOTLIST_FILE, StageError, write_json


async def _index_asset(directory: Path, asset: dict, threshold: float) -> None:
    """Fill an asset's scene list from a real pass over the stored file."""
    if asset.get("kind") != "clip":
        asset["scenes"] = []
        return
    path = directory / asset["path"]
    if not path.exists():
        raise StageError(f"Material file is missing: {asset['name']}")
    duration = float(asset.get("duration") or 0.0)
    times = await asyncio.to_thread(media.detect_scenes, path, threshold)
    asset["scenes"] = shotlist.scene_segments(times, duration)
    if not asset["scenes"]:
        raise StageError(f"Could not read a usable length out of {asset['name']}.")


async def run(ctx: dict) -> None:
    settings = get_settings()
    state = ctx["state"]
    directory = Path(ctx["dir"])
    lines = (state.get("timeline") or {}).get("lines") or []
    assets = state["inputs"].get("assets") or []
    if not lines:
        raise StageError("Timeline has no lines; run the script stage first.")
    if not assets:
        raise StageError("No material was uploaded for this project.")
    for asset in assets:
        await _index_asset(directory, asset, settings.scene_threshold)
    assignment, notes, match_reason = await matching.assign(lines, assets)
    result = shotlist.build_shotlist(
        lines,
        assets,
        state.get("shotlist"),
        assignment=assignment,
        matched_by="model" if assignment else "rotation",
        notes="; ".join(part for part in (notes, match_reason) if part),
    )
    state["shotlist"] = result
    write_json(directory, SHOTLIST_FILE, result)
