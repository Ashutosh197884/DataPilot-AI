"""Workflow event bus — streams orchestrator progress to the UI over SSE.

Events mirror the spec's real-time updates:
  workflow.started, workflow.step.started, workflow.step.completed,
  workflow.completed, workflow.failed

The orchestrator executes in a worker thread; events are marshalled onto the
running asyncio loop so SSE subscribers receive them safely.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections import defaultdict
from typing import Any

_HISTORY_CAP = 2000


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class EventBus:
    """Fan-out pub/sub keyed by workflow id, with replay for late subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the server's event loop for thread-safe publishing."""
        self._loop = loop

    def publish(self, workflow_id: str, event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "type": event_type,
            "workflow_id": workflow_id,
            "data": data or {},
            "at": _now_iso(),
        }
        history = self._history[workflow_id]
        history.append(event)
        if len(history) > _HISTORY_CAP:
            del history[: len(history) - _HISTORY_CAP]
        self._deliver(workflow_id, event)
        return event

    def _deliver(self, workflow_id: str, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(workflow_id, ())):
            if self._loop is not None and self._loop.is_running():
                try:
                    self._loop.call_soon_threadsafe(self._put, q, event)
                except RuntimeError:
                    self._put(q, event)
            else:
                self._put(q, event)

    @staticmethod
    def _put(q: asyncio.Queue, event: dict[str, Any]) -> None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:  # pragma: no cover - slow consumer
            pass

    async def subscribe(self, workflow_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        # Replay buffered history so a UI connecting a beat late sees the
        # full timeline of the run.
        for event in list(self._history.get(workflow_id, ())):
            self._put(q, event)
        self._subscribers[workflow_id].add(q)
        return q

    def unsubscribe(self, workflow_id: str, q: asyncio.Queue) -> None:
        self._subscribers.get(workflow_id, set()).discard(q)

    def replay(self, workflow_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(workflow_id, ()))

    @staticmethod
    def sse_format(event: dict[str, Any]) -> dict[str, str]:
        """Render an event as an SSE field mapping.

        Returns a dict ({event, data}) rather than a pre-formatted string so
        sse-starlette emits a proper `event:` line. Yielding a string would
        cause sse-starlette to treat the whole payload as `data` and prefix
        every embedded line with `data: `, which breaks the browser's
        EventSource named-event dispatch.
        """
        payload = {k: v for k, v in event.items() if k != "type"}
        return {"event": event["type"], "data": json.dumps(payload, default=str)}


event_bus = EventBus()
