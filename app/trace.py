from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel


class TraceEvent(BaseModel):
    run_id: str
    seq: int
    node: str
    kind: Literal["code", "jev", "llm", "human"]
    status: Literal["running", "done", "waiting", "error"]
    t_start_ms: int
    t_end_ms: int | None = None
    cost_usd: float | None = None
    tokens: int | None = None
    model: str | None = None
    route: str | None = None
    say: str | None = None
    structured: dict[str, Any] | None = None
    rule_fired: str | None = None
    error: str | None = None


class TraceEmitter:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._seq = 0
        self._origin_ms = int(time.monotonic() * 1000)
        self._events: list[TraceEvent] = []

    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000) - self._origin_ms

    def start(self, node: str, kind: Literal["code", "jev", "llm", "human"]) -> TraceEvent:
        self._seq += 1
        ev = TraceEvent(
            run_id=self._run_id,
            seq=self._seq,
            node=node,
            kind=kind,
            status="running",
            t_start_ms=self._now_ms(),
        )
        self.emit(ev)
        return ev

    def done(self, ev: TraceEvent, **kwargs: Any) -> TraceEvent:
        updated = ev.model_copy(update={"status": "done", "t_end_ms": self._now_ms(), **kwargs})
        self.emit(updated)
        return updated

    def error(self, ev: TraceEvent, exc: Exception) -> TraceEvent:
        updated = ev.model_copy(
            update={"status": "error", "t_end_ms": self._now_ms(), "error": str(exc)}
        )
        self.emit(updated)
        return updated

    def emit(self, ev: TraceEvent) -> None:
        self._events.append(ev)

    def events(self) -> list[TraceEvent]:
        return list(self._events)
