"""FFmpeg discovery, installation (winget), and PATH management for the engine.

The HyperFrames CLI needs ffmpeg + ffprobe on PATH. Whoever starts the engine may not
have a full FFmpeg in PATH (shells, the desktop shell, task schedulers), so:

- at startup, ensure_ffmpeg_on_path() fixes THIS process environment, and
- the Settings screen exposes status/install/upgrade/manual-path through the routes
  built on top of the helpers below.

Every subprocess call uses a literal program name plus a literal argument list (no
shell, no dynamic program paths): the environment is adjusted first so the literal
resolves to the right binary. Nothing outside the engine process is modified except
the user PATH registry entry when the user explicitly asks for it (add_to_user_path).
"""

import os
import re
import subprocess
import threading
from glob import glob
from pathlib import Path
from shutil import which
from typing import Any

from app.core.config import get_settings, save_overrides

_INSTALL_LOCK = threading.Lock()


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg management action fails."""


def _candidate_dirs() -> list[tuple[str, str]]:
    """FFmpeg bin directories to try, in priority order, with their source label."""
    settings = get_settings()
    candidates: list[tuple[str, str]] = []
    if settings.ffmpeg_dir:
        candidates.append((settings.ffmpeg_dir, "settings"))
    env_dir = os.environ.get("ULASAPP_FFMPEG_DIR", "")
    if env_dir:
        candidates.append((env_dir, "env"))
    winget_glob = (
        os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin"
    )
    candidates.extend((found, "winget") for found in sorted(glob(winget_glob), reverse=True))
    return candidates


def _has_ffprobe(directory: str) -> bool:
    return (Path(directory) / "ffprobe.exe").exists()


def _is_on_path(directory: str) -> bool:
    normalized = directory.replace("/", "\\").rstrip("\\").lower()
    return normalized in os.environ.get("PATH", "").replace("/", "\\").lower()


def ensure_ffmpeg_on_path() -> str | None:
    """Prepend a known FFmpeg bin dir to THIS process PATH. Returns the dir or None."""
    if os.name != "nt":
        return None
    if which("ffprobe"):
        return None
    for directory, _source in _candidate_dirs():
        if _has_ffprobe(directory):
            normalized = directory.replace("/", "\\")
            if not _is_on_path(normalized):
                os.environ["PATH"] = normalized + os.pathsep + os.environ.get("PATH", "")
            return normalized
    return None


def _winget_upgrade_available() -> bool:
    try:
        proc = subprocess.run(
            ["winget", "upgrade", "--id", "Gyan.FFmpeg"],
            capture_output=True,
            check=False,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    output = (proc.stdout or "") + (proc.stderr or "")
    return "gyan.ffmpeg" in output.lower()


def _winget_install() -> str:
    try:
        proc = subprocess.run(
            [
                "winget",
                "install",
                "--id",
                "Gyan.FFmpeg",
                "--silent",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError("winget install timed out") from exc
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise FFmpegError(f"winget install failed (exit {proc.returncode}): {output[-800:]}")
    return output


def _winget_upgrade() -> str:
    try:
        proc = subprocess.run(
            [
                "winget",
                "upgrade",
                "--id",
                "Gyan.FFmpeg",
                "--silent",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError("winget upgrade timed out") from exc
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise FFmpegError(f"winget upgrade failed (exit {proc.returncode}): {output[-800:]}")
    return output


def _refresh_detection() -> str | None:
    if ensure_ffmpeg_on_path() is None and not which("ffprobe"):
        return None
    probe = which("ffprobe")
    return str(Path(probe).parent) if probe else None


def status() -> dict[str, Any]:
    ensure_ffmpeg_on_path()
    directory: str | None = None
    source: str | None = None
    for candidate, source_label in _candidate_dirs():
        if _has_ffprobe(candidate):
            directory = candidate.replace("/", "\\")
            source = source_label
            break
    if directory is None:
        probe = which("ffprobe")
        if probe:
            directory = str(Path(probe).parent)
            source = "path"
    found = directory is not None
    version: str | None = None
    if directory is not None:
        try:
            proc = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                check=False,
                text=True,
                timeout=20,
            )
            match = re.search(r"ffprobe version (\S+)", proc.stdout)
            version = match.group(1) if match else None
        except (OSError, subprocess.TimeoutExpired):
            version = None
    result: dict[str, Any] = {
        "found": found,
        "path": directory,
        "source": source,
        "on_path": _is_on_path(directory) if directory is not None else False,
        "version": version,
        "winget_available": which("winget") is not None,
        "upgrade_available": None,
    }
    if result["winget_available"] and found:
        result["upgrade_available"] = _winget_upgrade_available()
    return result


def install() -> dict[str, Any]:
    with _INSTALL_LOCK:
        output = _winget_install()
        _refresh_detection()
        probe = which("ffprobe")
        if probe:
            add_to_user_path(str(Path(probe).parent))
        result = status()
        result["winget_output"] = output[-600:]
        return result


def upgrade() -> dict[str, Any]:
    with _INSTALL_LOCK:
        output = _winget_upgrade()
        _refresh_detection()
        probe = which("ffprobe")
        if probe:
            add_to_user_path(str(Path(probe).parent))
        result = status()
        result["winget_output"] = output[-600:]
        return result


def set_custom_path(directory: str) -> dict[str, Any]:
    directory = directory.strip().strip('"')
    if not _has_ffprobe(directory):
        raise FFmpegError(f"ffprobe.exe not found in: {directory}")
    save_overrides({"ffmpeg_dir": directory})
    normalized = directory.replace("/", "\\")
    os.environ["PATH"] = normalized + os.pathsep + os.environ.get("PATH", "")
    return status()


def add_to_user_path(directory: str) -> bool:
    """Append the directory to the USER PATH registry value if missing."""
    import winreg

    normalized = directory.replace("/", "\\").rstrip("\\")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
        try:
            value, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            value, value_type = "", winreg.REG_EXPAND_SZ
    entries = [entry for entry in value.split(";") if entry]
    if any(entry.rstrip("\\").lower() == normalized.lower() for entry in entries):
        return False
    entries.insert(0, normalized)
    new_value = ";".join(entries)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Path", 0, value_type, new_value)
    os.environ["PATH"] = normalized + os.pathsep + os.environ.get("PATH", "")
    return True
