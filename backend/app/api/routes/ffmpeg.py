"""FFmpeg management endpoints backing the Settings screen."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import ffmpeg
from app.core.ffmpeg import FFmpegError

router = APIRouter()


@router.get("")
def read_status() -> dict[str, Any]:
    return ffmpeg.status()


@router.post("/install")
def install() -> dict[str, Any]:
    try:
        return ffmpeg.install()
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc


@router.post("/upgrade")
def upgrade() -> dict[str, Any]:
    try:
        return ffmpeg.upgrade()
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc


class PathRequest(BaseModel):
    directory: str


@router.post("/path")
def set_path(payload: PathRequest) -> dict[str, Any]:
    try:
        return ffmpeg.set_custom_path(payload.directory)
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc
