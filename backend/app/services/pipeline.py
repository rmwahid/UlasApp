"""Stage pipeline runner, worker loop, and job state transitions."""

import asyncio
import logging
from pathlib import Path

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Job
from app.services import events
from app.services.stages import compose, describe, qa, script, visual
from app.services.state import read_state, write_state

logger = logging.getLogger("ulasapp.pipeline")

STAGE_MODULES = {
    "describe": describe,
    "script": script,
    "visual": visual,
    "compose": compose,
    "qa": qa,
}

_queue: asyncio.Queue | None = None
_worker_task: asyncio.Task | None = None
_loop: asyncio.AbstractEventLoop | None = None


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
        # A project without its state file can never run. Leaving it queued made it a zombie that
        # blocked every other project (found 2026-10-08), so it fails loudly instead.
        logger.warning("Project %s has no state file; marking it failed", job_id)
        update_job(
            job_id,
            status="failed",
            error="The project state file is missing, so nothing can run for it.",
        )
        events.publish(job_id, {"type": "done", "status": "failed", "error": "state file missing"})
        return
    # Which stages this run is allowed to touch: describing the material must not start a render.
    requested = state.get("run_stages") or None
    update_job(job_id, status="running", error=None)
    events.publish(job_id, {"type": "start", "title": title})
    ctx = {
        "job_id": job_id,
        "dir": directory,
        "state": state,
        "aspect": aspect,
        "mode": mode,
        "title": title,
    }
    try:
        await run_stages(ctx, requested)
        update_job(job_id, status="done", stage=(requested or list(STAGE_MODULES))[-1])
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
    global _queue, _worker_task, _loop
    if _worker_task is not None and not _worker_task.done():
        return
    _queue = asyncio.Queue()
    _loop = asyncio.get_running_loop()
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
    global _loop
    if _worker_task is not None:
        _worker_task.cancel()
    _loop = None


def _dispatch(job_id: str) -> None:
    """Hand a job to the worker from any thread: asyncio queues are not thread-safe."""
    if _queue is None or _loop is None:
        raise RuntimeError("Worker is not started")
    _loop.call_soon_threadsafe(_queue.put_nowait, job_id)


class ProjectBusyError(RuntimeError):
    """Raised when another project is already describing or rendering."""


def active_job() -> Job | None:
    """The one project that is currently describing or rendering, if any."""
    with Session(engine) as session:
        statement = select(Job).where(Job.status.in_(("queued", "running")))
        job = session.exec(statement).first()
        if job is None:
            return None
        session.expunge(job)
        return job


def requeue(job_id: str, stages: list[str]) -> None:
    """Reset the given stages so the next run redoes them, then queue the project again.

    Stages left as done are skipped, so re-rendering after an edit reuses the script and the
    material index instead of paying for them twice. One project at a time: while another project
    is describing or rendering, this refuses instead of queueing a second run.
    """
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            raise KeyError(job_id)
        directory = Path(job.project_dir)
    busy = active_job()
    if busy is not None and busy.id != job_id:
        raise ProjectBusyError(busy.title)
    state = read_state(directory)
    if not state:
        raise KeyError(job_id)
    for name in stages:
        state.setdefault("stages", {}).setdefault(name, {})["status"] = "pending"
    state["run_stages"] = list(stages)
    write_state(directory, state)
    update_job(job_id, status="queued", error=None)
    _dispatch(job_id)
