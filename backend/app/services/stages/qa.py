"""Stage 5: automated checks - timeline coverage, card readability, shot plan, output."""

from itertools import pairwise
from pathlib import Path

from app.core.config import get_settings
from app.services.shotlist import FREEZE_EPSILON, MODE_FREEZE, MODE_PHOTO
from app.services.state import HOOK_SECTION, QA_FILE, StageError, write_json


def _shot_plan_check(shots: list[dict], lines: list[dict], total: float) -> dict:
    """Every script line has exactly one shot and the shots cover the timeline end to end."""
    assigned = [shot["line"] for shot in shots]
    expected = [line["id"] for line in lines]
    if assigned != expected:
        return {
            "name": "shot_assignment",
            "passed": False,
            "detail": f"{len(assigned)} shots for {len(expected)} lines; one shot per line is required",
        }
    covered = bool(shots) and abs(float(shots[0]["start"])) < 0.011
    for shot, line in zip(shots, lines, strict=True):
        if abs(float(shot["start"]) - float(line["start"])) > 0.011:
            covered = False
            break
        if abs(float(shot["end"]) - float(line["end"])) > 0.011:
            covered = False
            break
    if covered and shots:
        covered = abs(float(shots[-1]["end"]) - total) <= 0.011
    for current, following in pairwise(shots):
        if abs(float(following["start"]) - float(current["end"])) > 0.011:
            covered = False
            break
    used = sorted({shot["asset"] for shot in shots})
    return {
        "name": "shot_coverage",
        "passed": covered,
        "detail": f"{len(shots)} shots, no gaps, material used: {', '.join(used)}",
    }


def _shot_material_check(shots: list[dict], assets: dict[str, dict], directory: Path) -> dict:
    """Every shot points at a known asset whose window fits the stored source file."""
    problems: list[str] = []
    for shot in shots:
        asset = assets.get(shot["asset"])
        if asset is None:
            problems.append(f"{shot['id']} uses unknown material {shot['asset']}")
            continue
        if not (directory / asset["path"]).exists():
            problems.append(f"{shot['id']} material file is missing ({asset['name']})")
            continue
        if shot.get("mode") == MODE_PHOTO and asset.get("kind") != "photo":
            problems.append(f"{shot['id']} shows a still from a clip")
        if shot.get("mode") == MODE_FREEZE and asset.get("kind") != "clip":
            problems.append(f"{shot['id']} holds a frame of a still")
        if shot.get("mode") == MODE_FREEZE:
            continue
        span = float(shot["end"]) - float(shot["start"])
        offset = float(shot.get("source_start") or 0.0)
        if asset.get("kind") == "clip":
            duration = float(asset.get("duration") or 0.0)
            if offset + span > duration + FREEZE_EPSILON:
                problems.append(f"{shot['id']} reads past the end of {asset['id']}")
    return {
        "name": "shot_material",
        "passed": not problems,
        "detail": "; ".join(problems) if problems else f"{len(shots)} shots resolve to real files",
    }


def _reading_time_check(lines: list[dict], settle: float, per_word: float) -> dict:
    """Every card stays up long enough to be read, judged by how much text it carries.

    A floor on card time (checked separately) says nothing about a card carrying a long sentence:
    the honest rule is a settled beat plus a per-word reading time. With the shipped spine settings
    every line clears this with margin, so a failure means the spine was retuned to something too
    fast for the text it produces.
    """
    too_fast: list[str] = []
    for line in lines:
        words = len(str(line.get("text") or "").split())
        window = float(line["end"]) - float(line["start"])
        needed = settle + words * per_word
        if window + 0.011 < needed:
            too_fast.append(f"{line['id']} {words} words in {window:.2f}s needs {needed:.2f}s")
    return {
        "name": "card_reading_time",
        "passed": not too_fast,
        "detail": "; ".join(too_fast)
        if too_fast
        else f"{len(lines)} cards hold at least {settle}s plus {per_word}s per word",
    }


def _hook_card_time_check(lines: list[dict], minimum: float) -> dict:
    """The opening card holds longer than the rest: a viewer has not committed to this video yet.

    The spine gives the hook that floor, so a failure means the spine was retuned or a script came
    back with a section other than the hook in the opening line.
    """
    hook = next((line for line in lines if line.get("section") == HOOK_SECTION), None)
    if hook is None:
        return {
            "name": "hook_card_time",
            "passed": False,
            "detail": "the script has no hook line to open with",
        }
    window = float(hook["end"]) - float(hook["start"])
    return {
        "name": "hook_card_time",
        "passed": window + 0.011 >= minimum,
        "detail": f"{hook['id']} holds {window:.2f}s, {minimum}s needed for the opening card",
    }


async def run(ctx: dict) -> None:
    settings = get_settings()
    directory = Path(ctx["dir"])
    state = ctx["state"]
    timeline = state.get("timeline") or {}
    lines = timeline.get("lines") or []
    shots = (state.get("shotlist") or {}).get("shots") or []
    assets = {asset["id"]: asset for asset in state["inputs"].get("assets") or []}
    checks: list[dict] = []

    coverage = bool(lines) and abs(lines[0]["start"]) < 0.011
    for current, nxt in pairwise(lines):
        if nxt["start"] - current["end"] > 0.011:
            coverage = False
            break
    checks.append(
        {
            "name": "timeline_coverage",
            "passed": coverage,
            "detail": f"{len(lines)} lines, total {timeline.get('total', 0)}s",
        }
    )

    min_ok = bool(lines) and all(
        (line["end"] - line["start"]) >= settings.min_card_seconds - 0.01 for line in lines
    )
    checks.append(
        {
            "name": "min_card_time",
            "passed": min_ok,
            "detail": f"every text card displays at least {settings.min_card_seconds}s",
        }
    )

    checks.append(_hook_card_time_check(lines, settings.hook_min_card_seconds))
    checks.append(_shot_plan_check(shots, lines, float(timeline.get("total") or 0.0)))
    checks.append(_shot_material_check(shots, assets, directory))
    checks.append(
        _reading_time_check(lines, settings.read_settle_seconds, settings.read_seconds_per_word)
    )

    video_rel = state.get("outputs", {}).get("video", "output/video.mp4")
    video = directory / video_rel
    video_ok = video.exists() and video.stat().st_size > 0
    size = video.stat().st_size if video_ok else 0
    checks.append({"name": "video_rendered", "passed": video_ok, "detail": f"{size} bytes"})

    passed = all(check["passed"] for check in checks)
    write_json(directory, QA_FILE, {"passed": passed, "checks": checks})
    if not passed:
        failed = ", ".join(check["name"] for check in checks if not check["passed"])
        raise StageError(f"QA failed: {failed}")
