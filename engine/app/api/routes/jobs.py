"""Job endpoints: create (single photo + music + product details), inspect, stream, download."""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.db import engine
from app.models import Job, _new_id
from app.services import pipeline
from app.services.events import subscribe, unsubscribe
from app.services.state import initial_state, project_dir, read_state, write_state

router = APIRouter()


def _save_upload(upload: UploadFile, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        handle.write(upload.file.read())


def _get_job(job_id: str) -> Job:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        session.expunge(job)
        return job


@router.post("")
async def create_job(
    title: str = Form(...),
    product_name: str = Form(...),
    points: str = Form(default=""),
    photo: UploadFile = File(...),
    music: UploadFile | None = File(None),
) -> dict:
    settings = get_settings()
    job_id = _new_id()
    directory = project_dir(settings.data_dir, job_id)
    photo_ext = Path(photo.filename or "photo.jpg").suffix.lower() or ".jpg"
    await asyncio.to_thread(
        _save_upload, photo, directory / "assets" / f"photo{photo_ext}"
    )
    inputs = {
        "photo": f"assets/photo{photo_ext}",
        "product": {"name": product_name, "points": points},
    }
    if music is not None and music.filename:
        music_ext = Path(music.filename).suffix.lower() or ".mp3"
        await asyncio.to_thread(
            _save_upload, music, directory / "assets" / f"music{music_ext}"
        )
        inputs["music"] = f"assets/music{music_ext}"
    job = Job(id=job_id, title=title, project_dir=str(directory))
    with Session(engine) as session:
        session.add(job)
        session.commit()
    write_state(directory, initial_state(job_id, title, job.aspect, job.mode, inputs))
    pipeline.enqueue(job_id)
    return {"id": job_id, "title": title}


@router.get("")
def list_jobs() -> list[dict]:
    with Session(engine) as session:
        jobs = session.exec(select(Job).order_by(Job.created_at.desc())).all()
        return [
            {
                "id": job.id,
                "title": job.title,
                "status": job.status,
                "stage": job.stage,
                "created_at": job.created_at.isoformat(),
            }
            for job in jobs
        ]


@router.get("/{job_id}")
def get_job_detail(job_id: str) -> dict:
    job = _get_job(job_id)
    state = read_state(Path(job.project_dir))
    video_rel = state.get("outputs", {}).get("video", "output/video.mp4")
    has_video = (Path(job.project_dir) / video_rel).exists()
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
        },
        "photo_url": f"/api/jobs/{job_id}/photo",
        "video_url": f"/api/jobs/{job_id}/video" if has_video else None,
    }


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
                except asyncio.TimeoutError:
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


@router.get("/{job_id}/photo")
def job_photo(job_id: str) -> FileResponse:
    job = _get_job(job_id)
    state = read_state(Path(job.project_dir))
    photo_rel = state.get("inputs", {}).get("photo", "assets/photo.jpg")
    photo = Path(job.project_dir) / photo_rel
    if not photo.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(photo)
