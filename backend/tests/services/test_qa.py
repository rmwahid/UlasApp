import asyncio
import json
from pathlib import Path

from app.services.stages import qa as qa_stage
from app.services.state import compute_spine, initial_state, write_state

SETTINGS = {
    "words_per_second": 2.7,
    "min_card_seconds": 1.8,
    "line_pause_seconds": 0.35,
    "hook_min_card_seconds": 2.6,
}


def _line(index: int, text: str, start: float, end: float, section: str = "solution") -> dict:
    return {
        "id": f"L{index}",
        "section": section,
        "text": text,
        "hint": "",
        "overlay": None,
        "start": start,
        "end": end,
    }


def _project(tmp_path: Path, lines: list[dict], video: bool = True) -> tuple[Path, dict]:
    directory = tmp_path / "proj"
    (directory / "output").mkdir(parents=True)
    if video:
        (directory / "output" / "video.mp4").write_bytes(b"fake-video")
    state = initial_state(
        "testjob",
        "Test",
        "9:16",
        "voiceless",
        {
            "assets": [
                {
                    "id": "a01",
                    "kind": "photo",
                    "path": "assets/a01.jpg",
                    "name": "a01.jpg",
                    "hero": True,
                    "duration": None,
                    "scenes": [],
                }
            ]
        },
    )
    (directory / "assets").mkdir(exist_ok=True)
    (directory / "assets" / "a01.jpg").write_bytes(b"fake-media")
    state["timeline"] = {
        "spine": "duration",
        "total": lines[-1]["end"],
        "lines": lines,
    }
    state["shotlist"] = {
        "shots": [
            {
                "id": f"S{index + 1}",
                "line": line["id"],
                "asset": "a01",
                "mode": "photo",
                "source_start": None,
                "start": line["start"],
                "end": line["end"],
                "overlay": None,
                "locked": False,
            }
            for index, line in enumerate(lines)
        ],
        "matched_by": "rotation",
        "notes": "",
    }
    write_state(directory, state)
    return directory, state


def _run(directory: Path, state: dict) -> dict:
    """Run QA and return the artifact, whether the stage passed or raised."""
    try:
        asyncio.run(qa_stage.run({"job_id": "testjob", "dir": directory, "state": state}))
    except qa_stage.StageError:
        pass
    return json.loads((directory / "qa.json").read_text(encoding="utf-8"))


def _check(qa: dict, name: str) -> dict:
    return next(check for check in qa["checks"] if check["name"] == name)


def test_spine_output_passes_the_reading_time_check(tmp_path):
    lines = compute_spine(
        [
            {
                "section": "hook",
                "say": "Jam ini bikin aku telat tidur seminggu penuh.",
                "hint": "a",
            },
            {"section": "proof", "say": "Akurasinya cuma meleset dua detik per hari.", "hint": "b"},
            {"section": "cta", "say": "Cek link di bio sebelum kehabisan.", "hint": "c"},
        ],
        SETTINGS["words_per_second"],
        SETTINGS["min_card_seconds"],
        SETTINGS["line_pause_seconds"],
        SETTINGS["hook_min_card_seconds"],
    )["lines"]
    directory, state = _project(tmp_path, lines)
    qa = _run(directory, state)
    check = _check(qa, "card_reading_time")
    assert check["passed"] is True, check["detail"]
    assert _check(qa, "hook_card_time")["passed"] is True
    assert qa["passed"] is True


def test_the_spine_holds_a_short_hook_longer_than_its_words_need():
    """The opening card is the one a viewer has not committed to yet, so it holds above the floor."""
    lines = compute_spine(
        [
            {"section": "hook", "say": "Tiga kata saja.", "hint": "a"},
            {"section": "cta", "say": "Cek bio.", "hint": "b"},
        ],
        SETTINGS["words_per_second"],
        SETTINGS["min_card_seconds"],
        SETTINGS["line_pause_seconds"],
        SETTINGS["hook_min_card_seconds"],
    )["lines"]
    hook_window = lines[0]["end"] - lines[0]["start"]
    filler_window = lines[1]["end"] - lines[1]["start"]
    assert hook_window >= SETTINGS["hook_min_card_seconds"]
    assert filler_window < SETTINGS["hook_min_card_seconds"]
    assert lines[1]["start"] == lines[0]["end"]


def test_a_hook_card_under_the_floor_fails_the_hook_check(tmp_path):
    lines = [
        _line(1, "Hook pendek.", 0.0, 1.9, section="hook"),
        _line(2, "Cek link di bio sekarang juga ya.", 1.9, 4.2, section="cta"),
    ]
    directory, state = _project(tmp_path, lines)
    qa = _run(directory, state)
    check = _check(qa, "hook_card_time")
    assert check["passed"] is False
    assert "L1" in check["detail"]
    assert qa["passed"] is False


def test_a_card_too_short_for_its_text_fails_the_reading_time_check(tmp_path):
    lines = [
        _line(1, "Baris pembuka yang cukup panjang untuk dibaca.", 0.0, 3.0, section="hook"),
        _line(2, "Ini baris kedua yang juga panjang sekali isinya.", 3.0, 3.4),
    ]
    directory, state = _project(tmp_path, lines)
    check = _check(_run(directory, state), "card_reading_time")
    assert check["passed"] is False
    assert "L2" in check["detail"]


def test_a_short_label_in_a_short_card_is_fine(tmp_path):
    lines = [
        _line(1, "Harga murah", 0.0, 2.6, section="hook"),
        _line(2, "Cek bio", 2.6, 4.4),
    ]
    directory, state = _project(tmp_path, lines)
    qa = _run(directory, state)
    assert _check(qa, "card_reading_time")["passed"] is True
    assert _check(qa, "hook_card_time")["passed"] is True


def test_reading_time_check_is_part_of_the_artifact(tmp_path):
    lines = [_line(1, "Harga murah", 0.0, 2.6, section="hook")]
    directory, state = _project(tmp_path, lines)
    qa = _run(directory, state)
    names = [check["name"] for check in qa["checks"]]
    assert names == [
        "timeline_coverage",
        "min_card_time",
        "hook_card_time",
        "shot_coverage",
        "shot_material",
        "card_reading_time",
        "video_rendered",
    ]
    assert qa["passed"] is True
