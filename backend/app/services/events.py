"""In-process event bus used by the SSE endpoint to stream job progress."""

import asyncio
from typing import Any

EventPayload = dict[str, Any]

_subscribers: dict[str, set[asyncio.Queue[EventPayload]]] = {}


def subscribe(job_id: str) -> asyncio.Queue[EventPayload]:
    queue: asyncio.Queue[EventPayload] = asyncio.Queue()
    _subscribers.setdefault(job_id, set()).add(queue)
    return queue


def unsubscribe(job_id: str, queue: asyncio.Queue[EventPayload]) -> None:
    _subscribers.get(job_id, set()).discard(queue)


def publish(job_id: str, payload: EventPayload) -> None:
    for queue in list(_subscribers.get(job_id, ())):
        queue.put_nowait(payload)
