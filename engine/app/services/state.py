"""Project folder layout, the state.json contract, and the timeline spine."""

import json
from pathlib import Path
from typing import Any

STATE_FILE = "state.json"
SCRIPT_FILE = "script.json"
VISUAL_FILE = "visual.json"
QA_FILE = "qa.json"
VIDEO_FILE = "output/video.mp4"


class StageError(RuntimeError):
    """Raised by a pipeline stage when it cannot complete."""


def project_dir(data_dir: Path, job_id: str) -> Path:
    return data_dir / "projects" / job_id


def read_state(directory: Path) -> dict:
    path = directory / STATE_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(directory: Path, state: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / STATE_FILE).write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def write_json(directory: Path, name: str, data: Any) -> None:
    (directory / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def initial_state(job_id: str, title: str, aspect: str, mode: str, inputs: dict) -> dict:
    return {
        "job_id": job_id,
        "title": title,
        "aspect": aspect,
        "mode": mode,
        "inputs": inputs,
        "stages": {
            "script": {"status": "pending"},
            "visual": {"status": "pending"},
            "compose": {"status": "pending"},
            "qa": {"status": "pending"},
        },
        "timeline": {"spine": "duration", "total": 0.0, "lines": []},
        "outputs": {
            "script": SCRIPT_FILE,
            "visual": VISUAL_FILE,
            "qa": QA_FILE,
            "video": VIDEO_FILE,
        },
    }


def compute_spine(
    lines: list[dict],
    words_per_second: float,
    min_card_seconds: float,
    line_pause_seconds: float,
) -> dict:
    """Duration-spine timeline: contiguous per-line windows from reading-speed estimates.

    Every line gets absolute start/end seconds; cards are contiguous (the inter-line pause is
    part of each card window), so the timeline has no gaps.
    """
    cursor = 0.0
    timed: list[dict] = []
    for index, line in enumerate(lines):
        words = len(line["say"].split())
        speech = words / max(words_per_second, 0.5)
        pause = line_pause_seconds if index < len(lines) - 1 else 0.0
        duration = max(min_card_seconds, speech) + pause
        timed.append(
            {
                "id": f"L{index + 1}",
                "section": line["section"],
                "text": line["say"],
                "overlay": line.get("overlay"),
                "start": round(cursor, 3),
                "end": round(cursor + duration, 3),
            }
        )
        cursor += duration
    return {"spine": "duration", "total": round(cursor, 3), "lines": timed}
