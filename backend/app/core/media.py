"""Media inspection and preparation through FFmpeg.

Every subprocess call uses a literal program name plus a literal argument list (no shell,
no dynamically chosen binary). The engine puts FFmpeg on PATH at startup, so the literals
resolve to the configured build.
"""

import json
import re
import subprocess
from pathlib import Path

INSPECT_TIMEOUT_SECONDS = 60
ANALYSIS_TIMEOUT_SECONDS = 900
ENCODE_TIMEOUT_SECONDS = 300

# The scdet filter reports each scene change as `lavfi.scd.time=<seconds>` on stdout when
# piped through metadata=mode=print:file=-.
SCENE_TIME_PATTERN = re.compile(r"^lavfi\.scd\.time=([0-9.]+)\s*$", re.MULTILINE)


class MediaError(RuntimeError):
    """Raised when a media file cannot be inspected or prepared."""


def _failure(action: str, proc: subprocess.CompletedProcess) -> MediaError:
    tail = ((proc.stderr or "") + (proc.stdout or "")).strip()[-400:]
    return MediaError(f"{action} failed: {tail or 'no output'}")


def parse_probe(text: str) -> dict:
    """Reduce ffprobe JSON output to the fields the pipeline needs."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MediaError(f"ffprobe returned unreadable JSON: {exc}") from exc
    streams = data.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("the file has no video stream")
    duration = None
    for raw in ((data.get("format") or {}).get("duration"), video.get("duration")):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            duration = round(value, 3)
            break
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "codec": str(video.get("codec_name") or ""),
        "duration": duration,
    }


def probe(path: Path) -> dict:
    """Inspect one media file. Stills and clips both report a video stream."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=INSPECT_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise _failure("ffprobe", proc)
    return parse_probe(proc.stdout)


def parse_scene_times(text: str) -> list[float]:
    """Scene-change timestamps contained in scdet metadata output."""
    times = {round(float(match), 3) for match in SCENE_TIME_PATTERN.findall(text)}
    return sorted(value for value in times if value > 0)


def detect_scenes(path: Path, threshold: float) -> list[float]:
    """Timestamps where a clip cuts to a different shot (empty when it never cuts)."""
    level = min(max(float(threshold), 0.0), 100.0)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"scdet=threshold={level:g},metadata=mode=print:file=-:direct=1",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=ANALYSIS_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise _failure("scene detection", proc)
    return parse_scene_times(proc.stdout)


def _seek_arguments(at: float) -> list[str]:
    """A seek, but only when there is something to seek.

    Seeking to zero in a single-frame still makes ffmpeg produce no frame at all (exit code 0 and
    no output file), which silently broke every JPEG thumbnail until this was found.
    """
    moment = max(float(at), 0.0)
    if moment <= 0:
        return []
    return ["-ss", f"{moment:.3f}"]


def make_thumbnail(source: Path, target: Path, at: float, width: int) -> None:
    """Write one JPEG frame; clips seek to `at` seconds, stills ignore the moment."""
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-y",
            *_seek_arguments(at),
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "4",
            str(target),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=INSPECT_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        raise _failure("thumbnail", proc)


def freeze_segment(source: Path, target: Path, start: float, duration: float) -> None:
    """Cut `duration` seconds from `start`, holding the last frame if the footage runs out.

    This is the fallback for a clip shorter than its slot. Longer footage plays straight
    from the original file through the composition's media start offset, so it is never
    re-encoded.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    length = max(float(duration), 0.1)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-y",
            *_seek_arguments(start),
            "-i",
            str(source),
            "-t",
            f"{length:.3f}",
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={length:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=ENCODE_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        raise _failure("freeze segment", proc)
