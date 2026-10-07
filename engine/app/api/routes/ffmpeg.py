"""FFmpeg management endpoints backing the Settings screen."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import ffmpeg
from app.core.ffmpeg import FFmpegError

router = APIRouter()


@router.get("")
def read_status() -> dict:
    return ffmpeg.status()


@router.post("/install")
def install() -> dict:
    try:
        return ffmpeg.install()
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc


@router.post("/upgrade")
def upgrade() -> dict:
    try:
        return ffmpeg.upgrade()
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc


class PathRequest(BaseModel):
    directory: str


@router.post("/path")
def set_path(payload: PathRequest) -> dict:
    try:
        return ffmpeg.set_custom_path(payload.directory)
    except FFmpegError as exc:
        raise RuntimeError(str(exc)) from exc
