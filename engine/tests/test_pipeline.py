import asyncio
import json
from pathlib import Path

import app.services.llm as llm_module
import app.services.stages.compose as compose_module
from app.services.pipeline import run_stages
from app.services.state import initial_state, read_state, write_state

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


def _make_project(tmp_path: Path):
    directory = tmp_path / "proj"
    (directory / "assets").mkdir(parents=True)
    (directory / "assets" / "photo.jpg").write_bytes(b"fake-jpg")
    (directory / "assets" / "music.mp3").write_bytes(b"fake-mp3")
    state = initial_state(
        "testjob",
        "Test watch",
        "9:16",
        "voiceless",
        {
            "photo": "assets/photo.jpg",
            "music": "assets/music.mp3",
            "product": {"name": "Watch X", "points": "light, accurate, Rp 299.000"},
        },
    )
    write_state(directory, state)
    return directory, state


def _make_ctx(directory: Path, state: dict, job_id: str) -> dict:
    return {
        "job_id": job_id,
        "dir": directory,
        "state": state,
        "aspect": "9:16",
        "mode": "voiceless",
        "title": "Test watch",
    }


def test_stages_produce_artifacts(tmp_path, monkeypatch):
    async def fake_llm(system, user):
        return FAKE_SCRIPT

    def fake_render(compose_dir, out_path, quality, runner):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"fake-video-bytes")

    monkeypatch.setattr(llm_module, "complete", fake_llm)
    monkeypatch.setattr(compose_module, "render_video", fake_render)
    monkeypatch.setattr(compose_module, "_ensure_gsap", lambda *a, **k: None)

    directory, state = _make_project(tmp_path)
    asyncio.run(run_stages(_make_ctx(directory, state, "testjob")))

    state = read_state(directory)
    for stage in ("script", "visual", "compose", "qa"):
        assert state["stages"][stage]["status"] == "done"
    assert (directory / "script.json").exists()
    assert (directory / "visual.json").exists()
    assert (directory / "qa.json").exists()
    assert (directory / "output" / "video.mp4").exists()

    qa = json.loads((directory / "qa.json").read_text(encoding="utf-8"))
    assert qa["passed"] is True

    timeline = state["timeline"]
    assert timeline["spine"] == "duration"
    assert timeline["lines"][0]["start"] == 0
    assert timeline["total"] > 0
    assert len(timeline["lines"]) == 3
    composition = (directory / "compose" / "index.html").read_text(encoding="utf-8")
    assert 'data-composition-id="main"' in composition
    assert "card-L1" in composition


def test_script_stage_rejects_invalid_llm_output(tmp_path, monkeypatch):
    import app.services.stages.script as script_stage
    from app.services.state import StageError

    async def fake_llm(system, user):
        return "sorry, here is a marketing essay instead"

    monkeypatch.setattr(llm_module, "complete", fake_llm)
    directory, state = _make_project(tmp_path)
    try:
        asyncio.run(script_stage.run(_make_ctx(directory, state, "testjob2")))
        raised = False
    except StageError:
        raised = True
    assert raised is True
