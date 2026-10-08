"""Project endpoints: create a project, describe its material, render it, inspect and edit it."""

import asyncio
import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core import media
from app.core.config import get_settings
from app.core.db import engine
from app.models import Job, _new_id
from app.services import pipeline, shotlist, uploads
from app.services.events import subscribe, unsubscribe
from app.services.pipeline import ProjectBusyError
from app.services.state import (
    SHOTLIST_FILE,
    initial_state,
    project_dir,
    read_state,
    script_fingerprint,
    write_json,
    write_state,
)
from app.services.uploads import UploadError

router = APIRouter()

POSTER_MOMENT_SECONDS = 0.5
POSTER_WIDTH = 720
REVEAL_TIMEOUT_SECONDS = 20


class ShotEdit(BaseModel):
    line: str
    asset: str | None = None
    overlay: str | None = None
    locked: bool | None = None


class ShotlistUpdate(BaseModel):
    edits: list[ShotEdit] = []


def _get_job(job_id: str) -> Job:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        session.expunge(job)
        return job


def _asset_records(state: dict) -> list[dict]:
    """Stored material records, including projects created before multi-asset input."""
    assets = state.get("inputs", {}).get("assets")
    if assets:
        return list(assets)
    single = state.get("inputs", {}).get("photo")
    if not single:
        return []
    return [{"id": "a01", "kind": "photo", "path": single, "name": Path(single).name, "hero": True}]


def _asset_entries(job_id: str, state: dict) -> list[dict]:
    """Material list as the UI needs it: names, kind, and where to fetch the images."""
    return [
        {
            "id": asset["id"],
            "kind": asset.get("kind", "photo"),
            "name": asset.get("name") or asset["id"],
            "hero": bool(asset.get("hero")),
            "duration": asset.get("duration"),
            "scenes": len(asset.get("scenes") or []),
            "description": asset.get("description"),
            "url": f"/api/jobs/{job_id}/assets/{asset['id']}",
            "thumb_url": f"/api/jobs/{job_id}/assets/{asset['id']}/thumb",
        }
        for asset in _asset_records(state)
    ]


def _stored_asset(state: dict, asset_id: str) -> dict | None:
    return next((asset for asset in _asset_records(state) if asset["id"] == asset_id), None)


def _upgrade_inputs(state: dict) -> list[dict]:
    """Material records for editing, upgrading a photo-only project to the asset list."""
    assets = _asset_records(state)
    if assets and not state.get("inputs", {}).get("assets"):
        state.setdefault("inputs", {})["assets"] = assets
    return assets


async def _store_assets(directory: Path, files: list[UploadFile]) -> list[dict]:
    records: list[dict] = []
    for index, upload in enumerate(files):
        kind, extension = uploads.classify(upload.filename or "")
        target = directory / uploads.asset_path(index, extension)
        size = await asyncio.to_thread(
            uploads.save_upload, upload.file, target, uploads.byte_limit(kind)
        )
        info = await asyncio.to_thread(uploads.inspect, kind, target)
        records.append(
            uploads.build_record(index, kind, upload.filename or "", extension, info, size)
        )
    return records


async def _store_music(directory: Path, music: UploadFile | None) -> str | None:
    if music is None or not music.filename:
        return None
    name = uploads.music_file(music.filename)
    target = directory / "assets" / name
    await asyncio.to_thread(uploads.save_upload, music.file, target, uploads.MAX_MUSIC_BYTES)
    return f"assets/{name}"


@router.post("")
async def create_job(
    product_name: str = Form(...),
    points: str = Form(default=""),
    direction: str = Form(default=""),
    overlay_style: str = Form(default=""),
    hero: int = Form(default=0),
    assets: list[UploadFile] = File(...),
    music: UploadFile | None = File(None),
) -> dict:
    """Create a project from its material. Nothing renders until the user asks for it.

    The flow this serves: pick the material, have the vision model describe it (stage `describe`),
    fix whatever it got wrong, fill in the brief, and only then start a render. Uploading files is
    never the moment a video gets rendered.
    """
    settings = get_settings()
    files = [upload for upload in assets if upload.filename]
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one photo or clip")
    if len(files) > uploads.MAX_ASSETS:
        raise HTTPException(
            status_code=400, detail=f"Upload at most {uploads.MAX_ASSETS} files per project"
        )
    title = product_name.strip() or "Untitled product"
    job_id = _new_id()
    directory = project_dir(settings.data_dir, job_id)
    try:
        records = await _store_assets(directory, files)
        music_rel = await _store_music(directory, music)
    except UploadError as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    records[hero if 0 <= hero < len(records) else 0]["hero"] = True
    inputs: dict = {"assets": records, "product": {"name": product_name, "points": points}}
    if music_rel:
        inputs["music"] = music_rel
    job = Job(id=job_id, title=title, project_dir=str(directory))
    aspect, mode = job.aspect, job.mode
    with Session(engine) as session:
        session.add(job)
        session.commit()
    state = initial_state(job_id, title, aspect, mode, inputs)
    state["brief"] = {"direction": direction.strip(), "overlay_style": overlay_style.strip()}
    write_state(directory, state)
    return {"id": job_id, "title": title}


def _start(job_id: str, stages: list[str]) -> None:
    try:
        pipeline.requeue(job_id, stages)
    except ProjectBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"'{exc}' is still working. Wait for it to finish before starting another run.",
        ) from exc


@router.post("/{job_id}/describe")
def start_describe(job_id: str) -> dict:
    """Describe the material with the vision model, so the user can check it before rendering."""
    _get_job(job_id)
    _start(job_id, ["describe"])
    return {"started": "describe"}


class BriefUpdate(BaseModel):
    direction: str | None = None
    overlay_style: str | None = None


@router.post("/{job_id}/render")
def start_render(job_id: str, payload: BriefUpdate | None = None) -> dict:
    """Start a render with the brief the user filled in, and report what it has to redo."""
    job = _get_job(job_id)
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="This project is already rendering")
    if payload is not None:
        _save_brief(job, payload)
    stages = _render_stages(read_state(Path(job.project_dir)))
    _start(job_id, stages)
    return {"started": "render", "stages": stages}


def _render_stages(state: dict) -> list[str]:
    """What a generate redoes.

    The script is only written again when the product details or the brief changed, and the shot
    plan only when it does not exist yet or the lines changed, so a storyboard the user approved
    survives generating another version. Compose and QA always run: a new version means a new file.
    """
    script_current = (
        state.get("script_fingerprint")
        and state["script_fingerprint"] == script_fingerprint(state)
        and (state.get("stages") or {}).get("script", {}).get("status") == "done"
    )
    stages: list[str] = []
    if not script_current:
        stages.append("script")
    if stages or not (state.get("shotlist") or {}).get("shots"):
        stages.append("visual")
    return [*stages, "compose", "qa"]


def _save_brief(job: Job, payload: BriefUpdate) -> None:
    directory = Path(job.project_dir)
    state = read_state(directory)
    if not state:
        raise HTTPException(status_code=404, detail="Project state is missing")
    values = payload.model_dump(exclude_none=True)
    state["brief"] = {**(state.get("brief") or {}), **values}
    write_state(directory, state)


@router.patch("/{job_id}/brief")
def update_brief(job_id: str, payload: BriefUpdate) -> dict:
    """Save the brief the user typed, so the next generate uses it."""
    job = _get_job(job_id)
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="This project is still working")
    _save_brief(job, payload)
    return read_state(Path(job.project_dir)).get("brief", {})


class AssetUpdate(BaseModel):
    description: str | None = None


@router.patch("/{job_id}/assets/{asset_id}")
def update_asset(job_id: str, asset_id: str, payload: AssetUpdate) -> dict:
    """Save an edited asset description: the user's words beat the model's."""
    job = _get_job(job_id)
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="This project is still working")
    directory = Path(job.project_dir)
    state = read_state(directory)
    record = _stored_asset(state, asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if payload.description is not None:
        text = payload.description.strip()
        record["description"] = text or None
        record["description_source"] = "user" if text else None
    write_state(directory, state)
    return {"id": asset_id, "description": record.get("description")}


@router.post("/{job_id}/reveal")
def reveal_folder(job_id: str) -> dict:
    """Open the project folder in the file manager so the user can take the video."""
    job = _get_job(job_id)
    directory = Path(job.project_dir)
    if os.name == "nt":
        command = ["explorer.exe", str(directory)]
    elif sys.platform == "darwin":
        command = ["open", str(directory)]
    else:
        command = ["xdg-open", str(directory)]
    try:
        # Explorer reports a non-zero code even when it opens the window, so only a launch failure
        # is worth telling the user about.
        subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=REVEAL_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=500, detail=f"Could not open the folder: {exc}") from exc
    return {"opened": str(directory)}


@router.get("")
def list_jobs() -> list[dict]:
    """The project list: newest first, with enough to show what state each one is in."""
    with Session(engine) as session:
        jobs = session.exec(select(Job).order_by(Job.created_at.desc())).all()
        entries = []
        for job in jobs:
            state = read_state(Path(job.project_dir))
            entries.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "status": job.status,
                    "stage": job.stage,
                    "error": job.error,
                    "created_at": job.created_at.isoformat(),
                    "version_count": len(state.get("versions") or []),
                    "material_count": len(_asset_records(state)),
                }
            )
        return entries


@router.get("/{job_id}")
def get_job_detail(job_id: str) -> dict:
    job = _get_job(job_id)
    directory = Path(job.project_dir)
    state = read_state(directory)
    video_rel = state.get("outputs", {}).get("video", "output/video.mp4")
    video = directory / video_rel
    video_url = None
    poster_url = None
    if video.exists():
        stamp = int(video.stat().st_mtime)
        video_url = f"/api/jobs/{job_id}/video?v={stamp}"
        poster_url = f"/api/jobs/{job_id}/poster?v={stamp}"
    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "status": job.status,
            "stage": job.stage,
            "error": job.error,
            "aspect": job.aspect,
            "mode": job.mode,
            "created_at": job.created_at.isoformat(),
        },
        "state": {
            "stages": state.get("stages", {}),
            "timeline": state.get("timeline", {}),
            "inputs": state.get("inputs", {}),
            "shotlist": state.get("shotlist", {"shots": []}),
            "brief": state.get("brief") or {"direction": "", "overlay_style": ""},
            "describe": state.get("describe") or {},
        },
        "assets": _asset_entries(job_id, state),
        "versions": _version_entries(job_id, state),
        "video_url": video_url,
        "poster_url": poster_url,
    }


def _version_entries(job_id: str, state: dict) -> list[dict]:
    """Every render of this project, newest first, as the result list needs it."""
    versions = list(state.get("versions") or [])
    entries = []
    for version in reversed(versions):
        entries.append(
            {
                "number": version["number"],
                "label": f"v{version['number']}",
                "file": Path(version["file"]).name,
                "resolution": version.get("resolution", ""),
                "created_at": version.get("created_at", ""),
                "summary": version.get("summary", ""),
                "url": f"/api/jobs/{job_id}/versions/{version['number']}",
            }
        )
    return entries


@router.get("/{job_id}/versions/{number}")
def job_version(job_id: str, number: int) -> FileResponse:
    job = _get_job(job_id)
    state = read_state(Path(job.project_dir))
    version = next(
        (item for item in state.get("versions") or [] if item.get("number") == number), None
    )
    if version is None:
        raise HTTPException(status_code=404, detail="That render does not exist")
    path = Path(job.project_dir) / version["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="That render file is missing")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    _get_job(job_id)
    queue = subscribe(job_id)

    async def generator():
        try:
            yield f"data: {json.dumps({'type': 'hello', 'job_id': job_id})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {json.dumps(message)}\n\n"
                if message.get("type") == "done":
                    break
        finally:
            unsubscribe(job_id, queue)

    from fastapi.responses import StreamingResponse

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.get("/{job_id}/video")
def job_video(job_id: str) -> FileResponse:
    job = _get_job(job_id)
    state = read_state(Path(job.project_dir))
    video_rel = state.get("outputs", {}).get("video", "output/video.mp4")
    video = Path(job.project_dir) / video_rel
    if not video.exists():
        raise HTTPException(status_code=404, detail="Video not rendered yet")
    return FileResponse(video, media_type="video/mp4", filename="ulasapp-review.mp4")


@router.get("/{job_id}/poster")
async def job_poster(job_id: str) -> FileResponse:
    """A still from the rendered video, so the player shows the product before it plays.

    The first rendered frame is nearly black (the composition has not painted the media yet), which
    makes a freshly finished job look like an empty player until someone presses play.
    """
    job = _get_job(job_id)
    directory = Path(job.project_dir)
    state = read_state(directory)
    video_rel = state.get("outputs", {}).get("video", "output/video.mp4")
    video = directory / video_rel
    if not video.exists():
        raise HTTPException(status_code=404, detail="Video not rendered yet")
    poster = directory / "output" / "poster.jpg"
    if not poster.exists() or poster.stat().st_mtime < video.stat().st_mtime:
        try:
            await asyncio.to_thread(
                media.make_thumbnail, video, poster, POSTER_MOMENT_SECONDS, POSTER_WIDTH
            )
        except media.MediaError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(poster, media_type="image/jpeg")


@router.get("/{job_id}/assets/{asset_id}")
def job_asset(job_id: str, asset_id: str) -> FileResponse:
    job = _get_job(job_id)
    directory = Path(job.project_dir)
    asset = _stored_asset(read_state(directory), asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Material not found")
    stored = directory / asset["path"]
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Material file is missing")
    media_type = mimetypes.guess_type(stored.name)[0] or "application/octet-stream"
    return FileResponse(stored, media_type=media_type)


@router.get("/{job_id}/assets/{asset_id}/thumb")
async def job_asset_thumb(job_id: str, asset_id: str) -> FileResponse:
    job = _get_job(job_id)
    directory = Path(job.project_dir)
    asset = _stored_asset(read_state(directory), asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Material not found")
    stored = directory / asset["path"]
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Material file is missing")
    thumb = directory / "thumbs" / f"{asset['id']}.jpg"
    if not thumb.exists() or thumb.stat().st_size == 0:
        try:
            await asyncio.to_thread(media.make_thumbnail, stored, thumb, _thumb_moment(asset), 480)
        except media.MediaError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(thumb, media_type="image/jpeg")


def _thumb_moment(asset: dict) -> float:
    """A frame from the middle of the first scene, so the still shows real content."""
    scenes = asset.get("scenes") or []
    if scenes:
        return round((float(scenes[0]["start"]) + float(scenes[0]["end"])) / 2, 3)
    return round(float(asset.get("duration") or 0.0) / 2, 3)


def _editable_state(job: Job) -> tuple[Path, dict, list[dict], list[dict]]:
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="The job is still running")
    directory = Path(job.project_dir)
    state = read_state(directory)
    lines = (state.get("timeline") or {}).get("lines") or []
    if not lines:
        raise HTTPException(status_code=409, detail="The script has not been generated yet")
    assets = _upgrade_inputs(state)
    if not assets:
        raise HTTPException(status_code=409, detail="This project has no material list")
    return directory, state, lines, assets


def _save_shotlist(directory: Path, state: dict, result: dict) -> None:
    """Store the shot plan. Saving never renders: the user decides when a new version is made."""
    state["shotlist"] = result
    write_state(directory, state)
    write_json(directory, SHOTLIST_FILE, result)


@router.post("/{job_id}/shotlist")
def update_shotlist(job_id: str, payload: ShotlistUpdate) -> dict:
    """Save storyboard edits (asset, overlay text, lock). Render a version when you are ready."""
    job = _get_job(job_id)
    directory, state, lines, assets = _editable_state(job)
    edits = [edit.model_dump() for edit in payload.edits]
    try:
        result = shotlist.apply_edits(state.get("shotlist") or {"shots": []}, lines, assets, edits)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _save_shotlist(directory, state, result)
    return {"shots": result["shots"]}


@router.post("/{job_id}/shotlist/auto")
def auto_shotlist(job_id: str) -> dict:
    """Rebuild the shot plan from the current descriptions, keeping the lines the user locked."""
    job = _get_job(job_id)
    directory, state, lines, assets = _editable_state(job)
    result = shotlist.build_shotlist(lines, assets, state.get("shotlist"))
    _save_shotlist(directory, state, result)
    return {"shots": result["shots"]}
