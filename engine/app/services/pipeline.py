"""Stage pipeline runner, worker loop, and job state transitions."""

import asyncio
import logging
from pathlib import Path

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Job
from app.services import events
from app.services.stages import compose, qa, script, visual
from app.services.state import read_state, write_state

logger = logging.getLogger("ulasapp.pipeline")

STAGE_MODULES = {
    "script": script,
    "visual": visual,
    "compose": compose,
    "qa": qa,
}

_queue: asyncio.Queue | None = None
_worker_task: asyncio.Task | None = None


def update_job(job_id: str, **fields) -> None:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        from app.models import _now

        job.updated_at = _now()
        session.add(job)
        session.commit()


async def run_stages(ctx: dict, stage_names=None) -> None:
    state = ctx["state"]
    names = stage_names or list(STAGE_MODULES.keys())
    for name in names:
        stage_state = state["stages"].setdefault(name, {"status": "pending"})
        if stage_state.get("status") == "done":
            continue
        stage_state["status"] = "running"
        stage_state.pop("error", None)
        write_state(ctx["dir"], state)
        update_job(ctx["job_id"], stage=name, status="running")
        events.publish(ctx["job_id"], {"type": "stage", "stage": name, "status": "running"})
        try:
            await STAGE_MODULES[name].run(ctx)
        except Exception as exc:
            stage_state["status"] = "failed"
            stage_state["error"] = str(exc)[:800]
            write_state(ctx["dir"], state)
            raise
        stage_state["status"] = "done"
        write_state(ctx["dir"], state)
        events.publish(ctx["job_id"], {"type": "stage", "stage": name, "status": "done"})


async def run_job(job_id: str) -> None:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        directory = Path(job.project_dir)
        title = job.title
        aspect = job.aspect
        mode = job.mode
    state = read_state(directory)
    if not state:
        return
    update_job(job_id, status="running", error=None)
    events.publish(job_id, {"type": "start", "title": title})
    ctx = {"job_id": job_id, "dir": directory, "state": state, "aspect": aspect, "mode": mode,
           "title": title}
    try:
        await run_stages(ctx)
        update_job(job_id, status="done", stage="qa")
        events.publish(job_id, {"type": "done", "status": "done"})
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        message = str(exc)[:800]
        update_job(job_id, status="failed", error=message)
        events.publish(job_id, {"type": "done", "status": "failed", "error": message})


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        job_id = await _queue.get()
        try:
            await run_job(job_id)
        except Exception:
            logger.exception("Worker error on job %s", job_id)
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _queue, _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _queue = asyncio.Queue()
    # Resume: anything left as running/queued from a previous process goes back to the queue.
    with Session(engine) as session:
        statement = select(Job).where(Job.status.in_(("queued", "running")))
        stale = session.exec(statement).all()
        for job in stale:
            job.status = "queued"
            session.add(job)
        session.commit()
        for job in stale:
            _queue.put_nowait(job.id)
    _worker_task = asyncio.create_task(_worker_loop())


def stop_worker() -> None:
    if _worker_task is not None:
        _worker_task.cancel()


def enqueue(job_id: str) -> None:
    if _queue is None:
        raise RuntimeError("Worker is not started")
    _queue.put_nowait(job_id)
