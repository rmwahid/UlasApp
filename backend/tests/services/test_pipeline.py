import asyncio
import json
from pathlib import Path

import pytest

import app.core.media as media_module
import app.services.llm as llm_module
import app.services.stages.compose as compose_module
from app.services.pipeline import run_stages
from app.services.state import StageError, initial_state, read_state, write_state

FAKE_SCRIPT = json.dumps(
    {
        "lines": [
            {
                "section": "hook",
                "say": "Jam ini bikin aku telat tidur seminggu penuh.",
                "hint": "close up of the watch",
                "overlay": None,
            },
            {
                "section": "proof",
                "say": "Akurasinya cuma meleset dua detik per hari.",
                "hint": "dial detail",
                "overlay": "2s / hari",
            },
            {
                "section": "cta",
                "say": "Cek link di bio sebelum kehabisan.",
                "hint": "watch on wrist",
                "overlay": "Cek bio",
            },
        ]
    }
)

PHOTO = {
    "id": "a01",
    "kind": "photo",
    "path": "assets/a01.jpg",
    "name": "foto produk.jpg",
    "hero": False,
    "duration": None,
    "scenes": [],
}
SHORT_CLIP = {
    "id": "a02",
    "kind": "clip",
    "path": "assets/a02.mp4",
    "name": "rekaman pendek.mp4",
    "hero": False,
    "duration": 0.5,
    "scenes": [],
}
SCENE_CLIP = {
    "id": "a03",
    "kind": "clip",
    "path": "assets/a03.mp4",
    "name": "rekaman potong.mp4",
    "hero": True,
    "duration": 8.0,
    "scenes": [],
}

ASSIGNMENT_JSON = json.dumps(
    {
        "assignment": [
            {"line": "L1", "asset": "a03"},
            {"line": "L2", "asset": "a02"},
            {"line": "L3", "asset": "a01"},
        ],
        "notes": "the cut clip opens, the still closes",
    }
)


def _make_project(tmp_path: Path, assets: list[dict]) -> tuple[Path, dict]:
    directory = tmp_path / "proj"
    (directory / "assets").mkdir(parents=True)
    for asset in assets:
        (directory / asset["path"]).write_bytes(b"fake-media")
    (directory / "assets" / "music.mp3").write_bytes(b"fake-mp3")
    state = initial_state(
        "testjob",
        "Test watch",
        "9:16",
        "voiceless",
        {
            "assets": [dict(asset) for asset in assets],
            "music": "assets/music.mp3",
            "product": {"name": "Watch X", "points": "light, accurate, Rp 299.000"},
        },
    )
    write_state(directory, state)
    return directory, state


def _make_ctx(directory: Path, state: dict, job_id: str = "testjob") -> dict:
    return {
        "job_id": job_id,
        "dir": directory,
        "state": state,
        "aspect": "9:16",
        "mode": "voiceless",
        "title": "Test watch",
    }


def _patch_stage_io(
    monkeypatch, script: str = FAKE_SCRIPT, assignment: str = ASSIGNMENT_JSON
) -> None:
    """Stand in for the LLM, the renderer, and the media tools the stages shell out to."""

    async def fake_llm(system, user):
        if "Material (id, kind, orientation" in user:
            return assignment
        return script

    async def fake_vision(system, user, images, max_tokens=400):
        return f"Material visible in {len(images)} frame(s)."

    def fake_render(compose_dir, out_path, quality, runner):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"fake-video-bytes")

    def fake_scenes(path, threshold):
        return {"a02.mp4": [], "a03.mp4": [1.0]}[Path(path).name]

    def fake_freeze(source, target, start, duration):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fake-freeze")

    def fake_thumbnail(source, target, at, width):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fake-frame")

    monkeypatch.setenv("ULASAPP_LLM_API_KEY", "test-key")
    monkeypatch.setenv("ULASAPP_LLM_MODEL", "test-model")
    monkeypatch.setattr(llm_module, "complete", fake_llm)
    monkeypatch.setattr(llm_module, "complete_with_images", fake_vision)
    monkeypatch.setattr(compose_module, "render_video", fake_render)
    monkeypatch.setattr(compose_module, "_ensure_gsap", lambda *a, **k: None)
    monkeypatch.setattr(media_module, "detect_scenes", fake_scenes)
    monkeypatch.setattr(media_module, "freeze_segment", fake_freeze)
    monkeypatch.setattr(media_module, "make_thumbnail", fake_thumbnail)


def test_stages_turn_material_into_a_shotlist_and_a_rendered_video(tmp_path, monkeypatch):
    _patch_stage_io(monkeypatch)
    directory, state = _make_project(tmp_path, [PHOTO, SHORT_CLIP, SCENE_CLIP])
    asyncio.run(run_stages(_make_ctx(directory, state)))

    state = read_state(directory)
    for stage in ("describe", "script", "visual", "compose", "qa"):
        assert state["stages"][stage]["status"] == "done"
    assert (directory / "script.json").exists()
    assert (directory / "shotlist.json").exists()
    assert not (directory / "visual.json").exists()
    assert (directory / "qa.json").exists()
    assert json.loads((directory / "qa.json").read_text(encoding="utf-8"))["passed"] is True

    timeline = state["timeline"]
    assert timeline["spine"] == "duration"
    assert [line["id"] for line in timeline["lines"]] == ["L1", "L2", "L3"]
    assert timeline["lines"][0]["start"] == 0
    assert timeline["lines"][0]["hint"] == "close up of the watch"
    assert timeline["total"] > 0

    stored = json.loads((directory / "shotlist.json").read_text(encoding="utf-8"))
    assert stored == state["shotlist"]
    assert stored["matched_by"] == "model"
    assert stored["notes"] == "the cut clip opens, the still closes"
    shots = stored["shots"]
    assert [shot["asset"] for shot in shots] == ["a03", "a02", "a01"]
    assert shots[0]["mode"] == "trim"
    assert shots[0]["source_start"] == 1.0
    assert shots[1]["mode"] == "freeze"
    assert shots[2]["mode"] == "photo"
    assert state["inputs"]["assets"][2]["scenes"] == [
        {"start": 0.0, "end": 1.0},
        {"start": 1.0, "end": 8.0},
    ]
    assert all(asset["description"] for asset in state["inputs"]["assets"])
    assert state["describe"] == {"described": 3, "total": 3}
    assert len(state["versions"]) == 1
    version = state["versions"][0]
    assert version["number"] == 1
    assert version["resolution"] == "1080x1920"
    assert version["file"].startswith("output/test-watch_")
    assert version["file"].endswith("_1080x1920_v1.mp4")
    assert state["outputs"]["video"] == version["file"]
    assert (directory / version["file"]).exists()

    composition = (directory / "compose" / "index.html").read_text(encoding="utf-8")
    assert 'data-composition-id="main"' in composition
    assert "card-L1" in composition
    assert '<img class="media" src="assets/a01.jpg"' in composition
    assert '<video id="shot-S1" class="clip media media-layer"' in composition
    assert '<video id="shot-S2" class="clip media media-layer"' in composition
    assert 'data-media-start="1.0"' in composition
    assert 'src="media/a02__0.000__' in composition
    assert "muted playsinline" in composition
    assert "crossorigin" not in composition


def test_one_photo_covers_every_line_with_a_single_zoom(tmp_path, monkeypatch):
    _patch_stage_io(monkeypatch)
    directory, state = _make_project(tmp_path, [PHOTO])
    asyncio.run(run_stages(_make_ctx(directory, state)))

    state = read_state(directory)
    shots = state["shotlist"]["shots"]
    assert [shot["asset"] for shot in shots] == ["a01", "a01", "a01"]
    assert [shot["line"] for shot in shots] == ["L1", "L2", "L3"]

    composition = (directory / "compose" / "index.html").read_text(encoding="utf-8")
    assert composition.count('<img class="media"') == 1
    assert composition.count('tl.fromTo("#shot-S1 .media"') == 1


def test_script_stage_rejects_invalid_llm_output(tmp_path, monkeypatch):
    import app.services.stages.script as script_stage

    _patch_stage_io(monkeypatch, script="sorry, here is a marketing essay instead")
    directory, state = _make_project(tmp_path, [PHOTO])
    with pytest.raises(StageError):
        asyncio.run(script_stage.run(_make_ctx(directory, state, "testjob2")))
