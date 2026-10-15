"""Upload validation and on-disk naming for project material.

Stored files always use an engine-generated id (`a01.mp4`), so the name the browser sent
never reaches the filesystem or a subprocess; it is kept in the project state as display
metadata only.
"""

from pathlib import Path
from typing import BinaryIO

from app.core import media
from app.core.media import MediaInfo
from app.services.state import AssetRecord

PHOTO = "photo"
CLIP = "clip"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
CLIP_EXTENSIONS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
MUSIC_EXTENSIONS = (".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac")

MAX_PHOTO_BYTES = 20 * 1024 * 1024
MAX_CLIP_BYTES = 200 * 1024 * 1024
MAX_MUSIC_BYTES = 24 * 1024 * 1024
MAX_ASSETS = 20
MIN_DIMENSION = 480
MAX_NAME_LENGTH = 200
CHUNK_BYTES = 1024 * 1024


class UploadError(ValueError):
    """Raised when an upload cannot be accepted as project material."""


def classify(filename: str) -> tuple[str, str]:
    """Return the kind (photo or clip) and the lowercased extension of an upload."""
    extension = Path(filename or "").suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return PHOTO, extension
    if extension in CLIP_EXTENSIONS:
        return CLIP, extension
    supported = ", ".join(IMAGE_EXTENSIONS + CLIP_EXTENSIONS)
    label = extension or (filename or "unknown")
    raise UploadError(f"unsupported file type '{label}'; expected one of: {supported}")


def asset_id(index: int) -> str:
    return f"a{index + 1:02d}"


def asset_path(index: int, extension: str) -> str:
    return f"assets/{asset_id(index)}{extension}"


def music_file(filename: str) -> str:
    """The engine-owned file name for the background track; never the user's name."""
    extension = Path(filename or "").suffix.lower()
    if extension not in MUSIC_EXTENSIONS:
        supported = ", ".join(MUSIC_EXTENSIONS)
        label = extension or (filename or "unknown")
        raise UploadError(f"unsupported audio file '{label}'; expected one of: {supported}")
    return f"music{extension}"


def byte_limit(kind: str) -> int:
    return MAX_CLIP_BYTES if kind == CLIP else MAX_PHOTO_BYTES


def display_name(filename: str) -> str:
    """The browser-supplied name, kept for the UI only and never used as a path."""
    return (Path(filename or "").name.strip() or "material")[:MAX_NAME_LENGTH]


def save_upload(source: BinaryIO, target: Path, limit: int) -> int:
    """Copy an upload to disk in chunks, refusing empty files and files over the limit."""
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with target.open("wb") as handle:
            while True:
                chunk = source.read(CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise UploadError(f"file is larger than {limit // (1024 * 1024)} MB")
                handle.write(chunk)
        if written == 0:
            raise UploadError("file is empty")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return written


def inspect(kind: str, path: Path) -> MediaInfo:
    """Probe a stored upload and reject material the pipeline cannot use."""
    try:
        info = media.probe(path)
    except media.MediaError as exc:
        raise UploadError(str(exc)) from exc
    if min(info["width"], info["height"]) < MIN_DIMENSION:
        raise UploadError(
            f"resolution {info['width']}x{info['height']} is too small; the shorter side "
            f"must be at least {MIN_DIMENSION} px"
        )
    if kind == CLIP and not info["duration"]:
        raise UploadError("the video has no readable duration; is the file complete?")
    return info


def build_record(
    index: int, kind: str, filename: str, extension: str, info: MediaInfo, size: int
) -> AssetRecord:
    """One entry of `inputs.assets`: what the user gave plus what the probe measured."""
    return {
        "id": asset_id(index),
        "kind": kind,
        "path": asset_path(index, extension),
        "name": display_name(filename),
        "hero": False,
        "size": size,
        "width": info["width"],
        "height": info["height"],
        "codec": info["codec"],
        "duration": info["duration"] if kind == CLIP else None,
        "scenes": [],
    }
