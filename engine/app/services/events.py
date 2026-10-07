"""In-process event bus used by the SSE endpoint to stream job progress."""

import asyncio

_subscribers: dict[str, set[asyncio.Queue]] = {}


def subscribe(job_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(job_id, set()).add(queue)
    return queue


def unsubscribe(job_id: str, queue: asyncio.Queue) -> None:
    _subscribers.get(job_id, set()).discard(queue)


def publish(job_id: str, payload: dict) -> None:
    for queue in list(_subscribers.get(job_id, ())):
        queue.put_nowait(payload)
