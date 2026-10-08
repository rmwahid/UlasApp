import asyncio
from pathlib import Path

import pytest

from app.core import media
from app.services import describe, llm


def _photo(asset_id="a01"):
    return {
        "id": asset_id,
        "kind": "photo",
        "path": f"assets/{asset_id}.jpg",
        "name": f"{asset_id}.jpg",
        "duration": None,
        "scenes": [],
    }


def _clip(asset_id="a02", duration=9.0, scenes=None):
    return {
        "id": asset_id,
        "kind": "clip",
        "path": f"assets/{asset_id}.mp4",
        "name": f"{asset_id}.mp4",
        "duration": duration,
        "scenes": scenes if scenes is not None else [{"start": 0.0, "end": duration}],
    }


def _project(tmp_path: Path, asset: dict) -> Path:
    directory = tmp_path / "proj"
    (directory / asset["path"]).parent.mkdir(parents=True, exist_ok=True)
    (directory / asset["path"]).write_bytes(b"fake-media")
    return directory


def test_clean_description_collapses_whitespace_and_quotes():
    assert describe.clean_description('  "A watch on a   wrist.\nClose up. "  ') == (
        "A watch on a wrist. Close up."
    )


def test_clean_description_refuses_an_empty_answer():
    with pytest.raises(llm.LLMError):
        describe.clean_description("   \n  ")


def test_clean_description_caps_the_length():
    cleaned = describe.clean_description("word " * 200)
    assert len(cleaned) <= describe.MAX_DESCRIPTION_CHARS + 3
    assert cleaned.endswith("...")


def test_frame_moments_uses_every_scene_when_there_are_few():
    clip = _clip(
        scenes=[
            {"start": 0.0, "end": 2.0},
            {"start": 2.0, "end": 5.0},
            {"start": 5.0, "end": 9.0},
        ]
    )
    assert describe.frame_moments(clip) == [1.0, 3.5, 7.0]


def test_frame_moments_spreads_over_the_scenes_when_there_are_many():
    clip = _clip(
        scenes=[{"start": index, "end": index + 1} for index in range(8)],
        duration=8.0,
    )
    moments = describe.frame_moments(clip)
    assert len(moments) == describe.MAX_FRAMES
    assert moments == sorted(moments)
    assert moments[0] == 0.5
    assert moments[-1] == 7.5


def test_frame_moments_falls_back_to_the_middle_of_a_clip_without_scenes():
    assert describe.frame_moments(_clip(duration=6.0, scenes=[])) == [3.0]


def test_describe_photo_sends_a_downscaled_copy(tmp_path, monkeypatch):
    asset = _photo()
    directory = _project(tmp_path, asset)
    sampled: list[float] = []
    sent: dict = {}

    def fake_thumbnail(source, target, at, width):
        sampled.append(at)
        assert width == describe.FRAME_WIDTH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"frame")

    async def fake_vision(system, user, images, max_tokens=400):
        sent["count"] = len(images)
        sent["image"] = images[0]
        return "A blue product photo on a plain background."

    monkeypatch.setattr(media, "make_thumbnail", fake_thumbnail)
    monkeypatch.setattr(llm, "complete_with_images", fake_vision)
    description = asyncio.run(describe.describe_asset(directory, asset))
    assert description == "A blue product photo on a plain background."
    assert sampled == [0.0]
    assert sent["count"] == 1
    assert sent["image"] == directory / describe.FRAME_DIR / "a01-0.jpg"


def test_describe_clip_samples_scene_frames_and_keeps_them(tmp_path, monkeypatch):
    asset = _clip(
        scenes=[
            {"start": 0.0, "end": 3.0},
            {"start": 3.0, "end": 6.0},
            {"start": 6.0, "end": 9.0},
        ]
    )
    directory = _project(tmp_path, asset)
    moments: list[float] = []

    def fake_thumbnail(source, target, at, width):
        moments.append(at)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"frame")

    async def fake_vision(system, user, images, max_tokens=400):
        assert len(images) == 3
        return "The seller turns a watch over in their hands."

    monkeypatch.setattr(media, "make_thumbnail", fake_thumbnail)
    monkeypatch.setattr(llm, "complete_with_images", fake_vision)
    description = asyncio.run(describe.describe_asset(directory, asset))
    assert description == "The seller turns a watch over in their hands."
    assert moments == [1.5, 4.5, 7.5]
    assert sorted(path.name for path in (directory / describe.FRAME_DIR).iterdir()) == [
        "a02-0.jpg",
        "a02-1.jpg",
        "a02-2.jpg",
    ]


def test_describe_asset_reports_missing_material(tmp_path):
    asset = _photo()
    with pytest.raises(media.MediaError):
        asyncio.run(describe.describe_asset(tmp_path / "proj", asset))
