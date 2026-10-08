"""Project folder layout, the state.json contract, the brief, and the timeline spine."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_FILE = "state.json"
SCRIPT_FILE = "script.json"
SHOTLIST_FILE = "shotlist.json"
QA_FILE = "qa.json"
VIDEO_FILE = "output/video.mp4"
VERSION_DIR = "output"
SLUG_MAX_CHARS = 40

# The stages a project runs, in order. `describe` only writes material descriptions, so the user can
# check and correct what the vision model saw before anything is rendered.
STAGE_NAMES = ("describe", "script", "visual", "compose", "qa")


class StageError(RuntimeError):
    """Raised by a pipeline stage when it cannot complete."""


def project_dir(data_dir: Path, job_id: str) -> Path:
    return data_dir / "projects" / job_id


def slug(text: str) -> str:
    """A file-safe version of a project name, for output file names."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return (cleaned or "project")[:SLUG_MAX_CHARS].strip("-")


def script_fingerprint(state: dict) -> str:
    """What the script was written from: when this changes, the script has to be written again.

    Editing a description or the storyboard keeps the same fingerprint, so generating another
    version reuses the approved script instead of quietly rewriting the user's lines.
    """
    source = {
        "product": (state.get("inputs") or {}).get("product") or {},
        "brief": state.get("brief") or {},
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def version_path(name: str, width: int, height: int, number: int, moment: datetime) -> str:
    """`name_timestamp_resolution_vN.mp4`, the file name a finished render gets."""
    stamp = moment.astimezone(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{VERSION_DIR}/{slug(name)}_{stamp}_{width}x{height}_v{number}.mp4"


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
    (directory / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def initial_state(job_id: str, title: str, aspect: str, mode: str, inputs: dict) -> dict:
    return {
        "job_id": job_id,
        "title": title,
        "aspect": aspect,
        "mode": mode,
        "inputs": inputs,
        "brief": {"direction": "", "overlay_style": ""},
        "stages": {name: {"status": "pending"} for name in STAGE_NAMES},
        "timeline": {"spine": "duration", "total": 0.0, "lines": []},
        "shotlist": {"shots": []},
        "versions": [],
        "outputs": {
            "script": SCRIPT_FILE,
            "shotlist": SHOTLIST_FILE,
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
                "hint": line.get("hint") or "",
                "overlay": line.get("overlay"),
                "start": round(cursor, 3),
                "end": round(cursor + duration, 3),
            }
        )
        cursor += duration
    return {"spine": "duration", "total": round(cursor, 3), "lines": timed}
