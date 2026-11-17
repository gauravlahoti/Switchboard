"""Human approval for one run: pause a tool call, ask a person, carry on with their answer.

Fail closed: no reachable approver, no answer in time, or a closed page all count as "declined".
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

Emit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class _Run:
    emit: Emit
    pending: dict[str, asyncio.Future[bool]] = field(default_factory=dict)
    allowed: dict[str, set[str]] = field(default_factory=dict)  # who may answer each pending approval
    decided_by: dict[str, str] = field(default_factory=dict)
    clock: Any = None  # the asyncio.timeout() that bounds the agent, so waiting on a person is not counted


_runs: dict[str, _Run] = {}


def attach(run_id: str, emit: Emit) -> None:
    _runs[run_id] = _Run(emit)


def detach(run_id: str) -> None:
    run = _runs.pop(run_id, None)
    if run:
        for waiter in run.pending.values():
            if not waiter.done():
                waiter.set_result(False)


def watch(run_id: str, clock: Any) -> None:
    run = _runs.get(run_id)
    if run:
        run.clock = clock


async def emit(run_id: str, event: dict[str, Any]) -> None:
    run = _runs.get(run_id)
    if run:
        await run.emit(event)


def waiting(run_id: str, approval_id: str) -> bool:
    run = _runs.get(run_id)
    waiter = run.pending.get(approval_id) if run else None
    return waiter is not None and not waiter.done()


def may_answer(run_id: str, approval_id: str, by: str) -> bool:
    """True when this profile is on the list of people who may answer that approval."""
    run = _runs.get(run_id)
    return bool(run) and by in run.allowed.get(approval_id, set())


def decide(run_id: str, approval_id: str, approve: bool, by: str) -> bool:
    """Record an answer. Refused unless the approval is waiting and `by` is allowed to answer it."""
    run = _runs.get(run_id)
    if run is None or not may_answer(run_id, approval_id, by) or not waiting(run_id, approval_id):
        return False
    run.decided_by[approval_id] = by
    run.pending[approval_id].set_result(approve)
    return True


async def ask(run_id: str, approval_id: str, timeout: float, approvers: list[str]) -> tuple[str, int, str | None]:
    """Wait for one of `approvers`. Returns "approved", "declined", "timeout" or "unreachable", the wait in
    ms and who answered. No approver at all means nobody can answer, so it fails closed without waiting."""
    run = _runs.get(run_id)
    if run is None or not approvers:
        return "unreachable", 0, None
    waiter: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    run.pending[approval_id] = waiter
    run.allowed[approval_id] = set(approvers)
    started = time.perf_counter()
    try:
        answer = await asyncio.wait_for(waiter, timeout)
        outcome = "approved" if answer else "declined"
    except asyncio.TimeoutError:
        outcome = "timeout"
    finally:
        run.pending.pop(approval_id, None)
        run.allowed.pop(approval_id, None)
    by = run.decided_by.pop(approval_id, None)
    waited = time.perf_counter() - started
    if run.clock is not None and run.clock.when() is not None:
        run.clock.reschedule(run.clock.when() + waited)
    return outcome, round(waited * 1000), by
