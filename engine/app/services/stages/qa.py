"""Stage 4: automated checks - timeline coverage, text-card readability, rendered output."""

from pathlib import Path

from app.core.config import get_settings
from app.services.state import QA_FILE, StageError, write_json


async def run(ctx: dict) -> None:
    settings = get_settings()
    directory = Path(ctx["dir"])
    state = ctx["state"]
    lines = state.get("timeline", {}).get("lines", [])
    checks: list[dict] = []

    coverage = bool(lines) and abs(lines[0]["start"]) < 0.011
    for current, nxt in zip(lines, lines[1:]):
        if nxt["start"] - current["end"] > 0.011:
            coverage = False
            break
    checks.append(
        {
            "name": "timeline_coverage",
            "passed": coverage,
            "detail": f"{len(lines)} lines, total {state.get('timeline', {}).get('total', 0)}s",
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

    video_rel = state.get("outputs", {}).get("video", "output/video.mp4")
    video = directory / video_rel
    video_ok = video.exists() and video.stat().st_size > 0
    size = video.stat().st_size if video_ok else 0
    checks.append(
        {"name": "video_rendered", "passed": video_ok, "detail": f"{size} bytes"}
    )

    passed = all(check["passed"] for check in checks)
    write_json(directory, QA_FILE, {"passed": passed, "checks": checks})
    if not passed:
        failed = ", ".join(check["name"] for check in checks if not check["passed"])
        raise StageError(f"QA failed: {failed}")
