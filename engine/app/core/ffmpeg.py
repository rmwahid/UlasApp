"""Make sure FFmpeg/FFprobe are reachable by the engine and its child processes.

The HyperFrames CLI needs ffprobe on PATH. Whoever starts the engine may not have a
full FFmpeg in PATH (shells, the desktop shell, task schedulers), so the engine fixes
its own environment at startup: an explicit ULASAPP_FFMPEG_DIR wins, otherwise the
standard winget install location is detected. Nothing outside the engine process is
modified.
"""

import os
from glob import glob
from pathlib import Path

_WINGET_GLOB = (
    os.environ.get("LOCALAPPDATA", "")
    + r"\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin"
)


def _candidate_dirs() -> list[str]:
    candidates: list[str] = []
    explicit = os.environ.get("ULASAPP_FFMPEG_DIR", "")
    if explicit:
        candidates.append(explicit)
    candidates.extend(sorted(glob(_WINGET_GLOB), reverse=True))
    return [c for c in candidates if (Path(c) / "ffprobe.exe").exists()]


def ensure_ffmpeg_on_path() -> str | None:
    """Prepend a known FFmpeg bin dir to this process PATH. Returns the dir or None."""
    if os.name != "nt":
        return None
    from shutil import which

    if which("ffprobe"):
        return None
    for candidate in _candidate_dirs():
        normalized = candidate.replace("/", "\\")
        if normalized.lower() in os.environ["PATH"].lower():
            return normalized
        os.environ["PATH"] = normalized + os.pathsep + os.environ.get("PATH", "")
        return normalized
    return None
