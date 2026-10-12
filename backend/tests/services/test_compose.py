import asyncio
from pathlib import Path

from app.services.stages import compose


def _photo(asset_id: str) -> dict:
    return {
        "id": asset_id,
        "kind": "photo",
        "path": f"assets/{asset_id}.jpg",
        "name": f"{asset_id}.jpg",
        "hero": False,
        "duration": None,
        "scenes": [],
        "description": "a watch on a table",
    }


def _clip(asset_id: str) -> dict:
    return {
        "id": asset_id,
        "kind": "clip",
        "path": f"assets/{asset_id}.mp4",
        "name": f"{asset_id}.mp4",
        "hero": True,
        "duration": 12.0,
        "scenes": [{"start": 0.0, "end": 12.0}],
        "description": "someone holding the watch",
    }


def _project(tmp_path: Path, style: dict | None = None) -> tuple[Path, dict]:
    directory = tmp_path / "proj"
    (directory / "assets").mkdir(parents=True)
    (directory / "assets" / "a01.jpg").write_bytes(b"still")
    (directory / "assets" / "a02.mp4").write_bytes(b"clip")
    lines = [
        {
            "id": "L1",
            "section": "hook",
            "text": "Jam ini langsung aku pakai.",
            "hint": "a",
            "overlay": "HARGA 99RIBU",
            "start": 0.0,
            "end": 3.0,
        },
        {
            "id": "L2",
            "section": "proof",
            "text": "Disiram air tetap jalan.",
            "hint": "b",
            "overlay": None,
            "start": 3.0,
            "end": 6.0,
        },
        {
            "id": "L3",
            "section": "cta",
            "text": "Cek keranjang kuning.",
            "hint": "c",
            "overlay": "CEK 99K",
            "start": 6.0,
            "end": 9.0,
        },
    ]
    shots = [
        {
            "id": "S1",
            "line": "L1",
            "asset": "a02",
            "mode": "trim",
            "source_start": 1.0,
            "start": 0.0,
            "end": 3.0,
            "overlay": None,
            "locked": False,
        },
        {
            "id": "S2",
            "line": "L2",
            "asset": "a01",
            "mode": "photo",
            "source_start": None,
            "start": 3.0,
            "end": 6.0,
            "overlay": None,
            "locked": False,
        },
        {
            "id": "S3",
            "line": "L3",
            "asset": "a01",
            "mode": "photo",
            "source_start": None,
            "start": 6.0,
            "end": 9.0,
            "overlay": "CEK 99K",
            "locked": False,
        },
    ]
    state = {
        "job_id": "testjob",
        "title": "Test",
        "aspect": "9:16",
        "mode": "voiceless",
        "inputs": {"assets": [_clip("a02"), _photo("a01")], "music": None},
        "brief": {"direction": "", "overlay_style": ""},
        "style": style
        or {
            "shape": "ulasan",
            "tone": "bersih",
            "accent": None,
            "energy": "normal",
            "badge": "pill",
        },
        "stages": {},
        "timeline": {"spine": "duration", "total": 9.0, "lines": lines},
        "shotlist": {"shots": shots},
        "versions": [],
        "outputs": {"video": "output/video.mp4"},
    }
    return directory, state


def _run(directory: Path, state: dict, monkeypatch) -> str:
    def fake_render(compose_dir, out_path, quality, runner):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"fake-video")

    monkeypatch.setattr(compose, "render_video", fake_render)
    monkeypatch.setattr(compose, "_ensure_gsap", lambda *args, **kwargs: None)
    asyncio.run(
        compose.run({"job_id": "testjob", "dir": directory, "state": state, "title": "Test"})
    )
    return (directory / "compose" / "index.html").read_text(encoding="utf-8")


def test_the_composition_carries_the_tone_tokens(tmp_path, monkeypatch):
    directory, state = _project(tmp_path)
    page = _run(directory, state, monkeypatch)
    assert "background: #0b0f14" in page
    assert "#f5b52e" in page
    assert "system-ui" in page
    assert "@@TOK" not in page, "a token was left unreplaced"


def test_section_tags_are_never_shown_on_the_video(tmp_path, monkeypatch):
    directory, state = _project(tmp_path)
    page = _run(directory, state, monkeypatch)
    assert "section-tag" not in page
    for tag in ("HOOK", "PROBLEM", "SOLUTION", "PROOF", "CTA"):
        assert f">{tag}<" not in page


def test_the_opening_and_closing_cards_are_treated_differently(tmp_path, monkeypatch):
    directory, state = _project(tmp_path)
    page = _run(directory, state, monkeypatch)
    assert '<section id="card-L1" class="clip card-clip hero"' in page
    assert '<div class="card hero">' in page
    assert '<div class="card card">' in page
    assert '<div class="card plate">' in page


def test_freezes_stay_out_of_the_media_contract(tmp_path, monkeypatch):
    directory, state = _project(tmp_path)
    page = _run(directory, state, monkeypatch)
    assert 'data-media-start="1.0"' in page
    assert "muted playsinline" in page
    assert "crossorigin" not in page
    assert 'data-composition-id="main"' in page


def test_overrides_change_what_the_page_says(tmp_path, monkeypatch):
    directory, state = _project(
        tmp_path,
        {
            "shape": "ulasan",
            "tone": "tegas",
            "accent": "#123456",
            "energy": "energik",
            "badge": "plain",
        },
    )
    page = _run(directory, state, monkeypatch)
    assert "#123456" in page
    assert "background: transparent" in page
    assert "scale: 1.224" in page, "energik should push the camera further than the normal tone"


def test_two_tones_do_not_render_the_same_page(tmp_path, monkeypatch):
    first_dir, first_state = _project(tmp_path / "a")
    second_dir, second_state = _project(
        tmp_path / "b",
        {"shape": "ulasan", "tone": "hangat", "accent": None, "energy": "normal", "badge": "pill"},
    )
    first = _run(first_dir, first_state, monkeypatch)
    second = _run(second_dir, second_state, monkeypatch)
    assert first != second


def test_a_version_is_recorded_for_every_render(tmp_path, monkeypatch):
    directory, state = _project(tmp_path)
    _run(directory, state, monkeypatch)
    assert state["versions"][0]["resolution"] == "1080x1920"
    assert state["versions"][0]["summary"].startswith("3 shots, 2 material")
    assert state["outputs"]["video"].endswith("_v1.mp4")
    assert (directory / state["outputs"]["video"]).exists()
    _run(directory, state, monkeypatch)
    assert [version["number"] for version in state["versions"]] == [1, 2]
    assert state["versions"][1]["file"] != state["versions"][0]["file"]
