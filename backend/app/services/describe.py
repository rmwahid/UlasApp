"""Short visual descriptions of uploaded material, so shots can be matched by content.

An asset is described once: for a still, by sending the file itself; for a clip, by sending frames
taken from up to three of its scenes. The description is stored on the asset record, so a re-render
never pays for it again, and the frames stay on disk where they can be inspected.
"""

import asyncio
from pathlib import Path

from app.core import media
from app.services import llm
from app.services.llm import LLMError

FRAME_WIDTH = 512
MAX_FRAMES = 3
MAX_DESCRIPTION_CHARS = 240
FRAME_DIR = "descriptions"

SYSTEM_PROMPT = (
    "You describe product material for a short vertical review video. Answer with one plain "
    "sentence, at most 25 words, naming what is visible: the product, the setting, the action, the "
    "camera angle. No lists, no markdown, no quotes, no speculation about things you cannot see."
)

USER_PROMPT = (
    "Describe the material shown in this image so it can be matched to a script line later. "
    "Say what is visible and how it is framed."
)

CLIP_PROMPT = (
    "These images are frames taken from different moments of one short video clip, in order. "
    "Describe what the clip shows overall in one sentence."
)


def clean_description(answer: str) -> str:
    """Reduce a model answer to one short line, refusing empty or obviously broken output."""
    text = " ".join(str(answer).split())
    text = text.strip("\"'` ")
    if not text:
        raise LLMError("the model returned an empty description")
    if len(text) > MAX_DESCRIPTION_CHARS:
        text = text[:MAX_DESCRIPTION_CHARS].rstrip() + "..."
    return text


def frame_moments(asset: dict) -> list[float]:
    """Where to sample a clip: the middle of up to three scenes, spread over its length."""
    duration = float(asset.get("duration") or 0.0)
    scenes = asset.get("scenes") or [{"start": 0.0, "end": duration}]
    if len(scenes) <= MAX_FRAMES:
        chosen = scenes
    else:
        step = (len(scenes) - 1) / (MAX_FRAMES - 1)
        chosen = [scenes[round(index * step)] for index in range(MAX_FRAMES)]
    moments = [
        round((float(scene["start"]) + float(scene["end"])) / 2, 3)
        for scene in chosen
        if float(scene["end"]) > float(scene["start"])
    ]
    return moments or [round(duration / 2, 3)]


async def describe_asset(directory: Path, asset: dict) -> str:
    """One short description of one stored asset, written with the configured vision model.

    Stills are downscaled to the same width as clip frames before they are sent: a full-size photo
    costs more image tokens, and this model reasons longer the more it has to look at.
    """
    source = directory / asset["path"]
    if not source.exists():
        raise media.MediaError(f"material file is missing: {asset['name']}")
    if asset.get("kind") == "clip":
        images = await _clip_frames(directory, asset, source)
        prompt = CLIP_PROMPT
    else:
        images = [await _frame(directory, source, asset["id"], 0, 0.0)]
        prompt = USER_PROMPT
    answer = await llm.complete_with_images(SYSTEM_PROMPT, prompt, images)
    return clean_description(answer)


async def _frame(directory: Path, source: Path, asset_id: str, index: int, at: float) -> Path:
    target = directory / FRAME_DIR / f"{asset_id}-{index}.jpg"
    await asyncio.to_thread(media.make_thumbnail, source, target, at, FRAME_WIDTH)
    return target


async def _clip_frames(directory: Path, asset: dict, source: Path) -> list[Path]:
    frames = [
        await _frame(directory, source, asset["id"], index, moment)
        for index, moment in enumerate(frame_moments(asset))
    ]
    if not frames:
        raise media.MediaError(f"could not sample any frame from {asset['name']}")
    return frames
