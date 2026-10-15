"""Project folder layout, the state.json contract, the brief, the style block, and the timeline spine."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from app.services.beats import DEFAULT_SHAPE, resolve_beats
from app.services.tones import DEFAULT_BADGE, DEFAULT_ENERGY, DEFAULT_TONE

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

# The one section every script opens with, whatever else its shape contains.
HOOK_SECTION = "hook"


class Scene(TypedDict):
    """One continuous shot inside a clip, in source seconds."""

    start: float
    end: float


class AssetRecord(TypedDict):
    """One uploaded material file, as stored under `inputs.assets`.

    Only the identity is guaranteed: projects created before the vision step or before a field
    existed simply do not carry the optional keys.
    """

    id: str
    kind: str
    path: str
    name: NotRequired[str]
    hero: NotRequired[bool]
    size: NotRequired[int]
    width: NotRequired[int]
    height: NotRequired[int]
    codec: NotRequired[str]
    duration: NotRequired[float | None]
    scenes: NotRequired[list[Scene]]
    description: NotRequired[str | None]
    description_source: NotRequired[str | None]


class ProductDetails(TypedDict, total=False):
    """What the user typed about the product: the facts, both free text."""

    name: str
    points: str


class Inputs(TypedDict, total=False):
    """Project inputs: the material list (or a legacy single photo), the facts, the music track."""

    assets: list[AssetRecord]
    product: ProductDetails
    music: str | None
    photo: str


class Brief(TypedDict):
    """The user's intent for this video, separate from the material and the product facts."""

    direction: str
    overlay_style: str


class Style(TypedDict):
    """Shape (the beat order) plus the tone and its three deliberate overrides."""

    shape: str
    beats: list[str]
    tone: str
    accent: str | None
    energy: str
    badge: str


class ScriptLine(TypedDict):
    """One line as the script stage wrote it, before the spine gives it absolute times."""

    section: str
    say: str
    hint: str
    overlay: str | None


class TimelineLine(TypedDict):
    """One line on the timeline: the words plus their absolute window in the video."""

    id: str
    section: str
    text: str
    hint: str
    overlay: str | None
    start: float
    end: float


class Timeline(TypedDict):
    """The duration spine: contiguous per-line windows covering the whole video."""

    spine: str
    total: float
    lines: list[TimelineLine]


class Shot(TypedDict):
    """One line's material: which asset, which part of it, over which window."""

    id: str
    line: str
    asset: str
    mode: str
    source_start: float | None
    start: float
    end: float
    overlay: str | None
    locked: bool


class Shotlist(TypedDict):
    """The shot plan and how it was decided (model, rotation or manual)."""

    shots: list[Shot]
    matched_by: NotRequired[str]
    notes: NotRequired[str]


class VersionRecord(TypedDict):
    """One rendered file, listed newest first in the result section."""

    number: int
    file: str
    resolution: str
    created_at: str
    summary: str


class Outputs(TypedDict):
    """Where the stage artifacts live inside the project folder."""

    script: str
    shotlist: str
    qa: str
    video: str


class StageStatus(TypedDict, total=False):
    """One stage's progress: its status, plus the error when it failed."""

    status: str
    error: str


class DescribeStatus(TypedDict, total=False):
    """How the material description pass went, for the UI to show."""

    described: int
    total: int
    failed: list[str]


class ProjectState(TypedDict, total=False):
    """The whole on-disk state.json.

    Every key is optional on purpose: projects written by earlier versions keep exactly the keys
    they were written with, and readers fall back to sensible defaults for anything missing.
    """

    job_id: str
    title: str
    aspect: str
    mode: str
    inputs: Inputs
    brief: Brief
    style: Style
    stages: dict[str, StageStatus]
    timeline: Timeline
    shotlist: Shotlist
    versions: list[VersionRecord]
    outputs: Outputs
    run_stages: list[str]
    script_fingerprint: str
    describe: DescribeStatus


class StageContext(TypedDict):
    """What one stage run gets: the project identity, its folder, and the state it reads/writes."""

    job_id: str
    dir: Path
    state: ProjectState
    aspect: str
    mode: str
    title: str


def default_style() -> Style:
    """The style block a project starts with: the default shape, tone and overrides."""
    return {
        "shape": DEFAULT_SHAPE,
        "beats": [],
        "tone": DEFAULT_TONE,
        "accent": None,
        "energy": DEFAULT_ENERGY,
        "badge": DEFAULT_BADGE,
    }


class StageError(RuntimeError):
    """Raised by a pipeline stage when it cannot complete."""


def project_dir(data_dir: Path, job_id: str) -> Path:
    return data_dir / "projects" / job_id


def slug(text: str) -> str:
    """A file-safe version of a project name, for output file names."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return (cleaned or "project")[:SLUG_MAX_CHARS].strip("-")


def script_fingerprint(state: ProjectState) -> str:
    """What the script was written from: when this changes, the script has to be written again.

    Editing a description or the storyboard keeps the same fingerprint, so generating another
    version reuses the approved script instead of quietly rewriting the user's lines. The beat order
    of the chosen shape IS part of it, because a different order means different lines; the tone and
    its overrides are not, because they only change how the same lines look.
    """
    style = state.get("style")
    inputs = state.get("inputs")
    source: dict[str, Any] = {
        "product": (inputs.get("product") if inputs else None) or {},
        "brief": state.get("brief") or {},
        "beats": resolve_beats(
            (style.get("shape") if style else None) or DEFAULT_SHAPE,
            style.get("beats") if style else None,
        ),
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def version_path(name: str, width: int, height: int, number: int, moment: datetime) -> str:
    """`name_timestamp_resolution_vN.mp4`, the file name a finished render gets."""
    stamp = moment.astimezone(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{VERSION_DIR}/{slug(name)}_{stamp}_{width}x{height}_v{number}.mp4"


def read_state(directory: Path) -> ProjectState:
    path = directory / STATE_FILE
    if not path.exists():
        return {}
    # The file is written by this engine only; the read is the trust boundary for its shape.
    return cast(ProjectState, json.loads(path.read_text(encoding="utf-8")))


def write_state(directory: Path, state: ProjectState) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / STATE_FILE).write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def write_json(directory: Path, name: str, data: Any) -> None:
    (directory / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def initial_state(job_id: str, title: str, aspect: str, mode: str, inputs: Inputs) -> ProjectState:
    stages: dict[str, StageStatus] = {name: {"status": "pending"} for name in STAGE_NAMES}
    return {
        "job_id": job_id,
        "title": title,
        "aspect": aspect,
        "mode": mode,
        "inputs": inputs,
        "brief": {"direction": "", "overlay_style": ""},
        "style": default_style(),
        "stages": stages,
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
    lines: list[ScriptLine],
    words_per_second: float,
    min_card_seconds: float,
    line_pause_seconds: float,
    hook_min_card_seconds: float = 0.0,
) -> Timeline:
    """Duration-spine timeline: contiguous per-line windows from reading-speed estimates.

    Every line gets absolute start/end seconds; cards are contiguous (the inter-line pause is
    part of each card window), so the timeline has no gaps. A hook line holds for at least
    hook_min_card_seconds, because a viewer who has not committed yet needs longer on screen.
    """
    cursor = 0.0
    timed: list[TimelineLine] = []
    for index, line in enumerate(lines):
        words = len(line["say"].split())
        speech = words / max(words_per_second, 0.5)
        pause = line_pause_seconds if index < len(lines) - 1 else 0.0
        floor = hook_min_card_seconds if line["section"] == HOOK_SECTION else min_card_seconds
        duration = max(floor, min_card_seconds, speech) + pause
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
