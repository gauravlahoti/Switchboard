"""FastAPI server: serves the Reflex console and streams ADK workflow events via SSE."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from app import approvals, audit, harness, identity  # noqa: E402
from app.agent import app as adk_app  # noqa: E402
from app.store import store  # noqa: E402

log = logging.getLogger("desk.server")
_session_svc = InMemorySessionService()
_runner = Runner(app=adk_app, session_service=_session_svc)
# Stream model text as it is written, so the first words appear before the answer is finished
RUN_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)

# Maps ADK node names to the graph node ids in the UI
NODE_MAP: dict[str, str] = {
    "intake": "n-intake",
    "input_guardrail": "n-guard",
    "hold_review": "n-hold",
    "block_request": "n-block",
    "understand_request": "n-understand",
    "specialist_review": "n-hold",
    "plan_work": "n-plan",
    "handle_request": "n-handle",
    "reply_to_user": "n-reply",
}
NEXT: dict[str, str] = {"n-intake": "n-guard", "n-plan": "n-handle"}
GUARD_NEXT: dict[str, str] = {"proceed": "n-understand", "hold": "n-hold", "block": "n-block", "decline": "n-block"}
UNDERSTAND_NEXT: dict[str, str] = {"reply": "n-reply", "handle": "n-plan", "specialist": "n-hold"}
# Nodes whose text goes straight to the person, in priority order
FINAL_NODES = ("hold_review", "block_request", "specialist_review", "handle_request", "reply_to_user")
LLM_NODES = {"handle_llm": "n-handle", "reply_llm": "n-reply"}
LLM_AUTHORS = frozenset(LLM_NODES)

# In-memory store: run_id -> asyncio.Queue of SSE payloads (None = done)
_runs: dict[str, asyncio.Queue] = {}

server = FastAPI(title="Reflex Desk")
UI_PATH = Path(__file__).parent / "static" / "index.html"


@server.get("/")
async def index() -> FileResponse:
    return FileResponse(UI_PATH, media_type="text/html")


@server.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(UI_PATH.parent / "brand" / "favicon.svg", media_type="image/svg+xml")


server.mount("/static", StaticFiles(directory=UI_PATH.parent), name="static")

# The Jev tour: a self-contained, video-style explainer in ./tour (plain files, no API calls).
# A mount, not a route, so /tour redirects to /tour/ and its relative URLs resolve.
TOUR_DIR = Path(__file__).parent / "tour"
if TOUR_DIR.is_dir():
    server.mount("/tour", StaticFiles(directory=TOUR_DIR, html=True), name="tour")


@server.on_event("startup")
async def warm_up() -> None:
    """The first Vertex call per model pays a one-off connection cost. Pay it here, not on a person."""
    asyncio.create_task(harness.warm_up())


class RunRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    profile: str = "user_a"


class RunResponse(BaseModel):
    run_id: str


@server.get("/api/profiles")
async def profiles() -> dict[str, Any]:
    return {"profiles": identity.catalog(), "default": "user_a"}


@server.post("/api/demo/reset")
async def reset_demo() -> dict[str, str]:
    store.reset()
    return {"status": "reset"}


def _friendly_error(exc: Exception) -> str:
    """People see a plain sentence. The full error stays in the server log."""
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "ResourceExhausted" in type(exc).__name__:
        return "The model service is busy right now. Please try again in a moment."
    if "TYPESAFE_API_KEY" in text:
        return "The fast-read service is not configured. Add TYPESAFE_API_KEY to .env."
    return "Something went wrong while handling this request. Please try again."


def _node_name_from_path(path: str) -> str:
    """Extract the leaf node name from a node_info.path like 'desk@1/intake@1'."""
    return path.split("/")[-1].rsplit("@", 1)[0] if "/" in path else path


def _summarize(name: str, resp: dict[str, Any]) -> str:
    if resp.get("status") == "error":
        return str(resp.get("message", "failed"))
    d = resp.get("data", {})
    if name == "search_kb":
        arts = d.get("articles", [])
        return f"{len(arts)} article{'s' if len(arts) != 1 else ''}" + (f": {arts[0]['title']}" if arts else "")
    if name == "lookup_user":
        return f"{d.get('department')}, " + ("account locked" if d.get("account_locked") else "account active")
    if name == "reset_password":
        return "account unlocked, reset link sent" if d.get("account_unlocked") else "no change"
    if name == "create_ticket":
        return f"ticket {d.get('ticket_id')} in {d.get('queue')}" + (" (already open)" if d.get("duplicate") else "")
    return "done"


def _text_of(event: Any) -> str:
    """The visible text in one chunk. Thought summaries are not part of the answer."""
    parts = event.content.parts if event.content and event.content.parts else []
    return "".join(p.text for p in parts if p.text and not getattr(p, "thought", False))


def _nested_events(event: Any, tier: str, node: str = "") -> list[dict[str, Any]]:
    """Tool, skill and model-usage events from inside a model node."""
    out: list[dict[str, Any]] = []
    for call in event.get_function_calls() or []:
        args = audit.mask(dict(call.args or {}))
        if call.name in harness.SKILL_TOOL_NAMES:
            if call.name == "load_skill":
                out.append({"type": "skill", "name": args.get("skill_name"), "resource": args.get("file_path")})
        else:
            out.append({"type": "tool_call", "name": call.name, "args": args})
    for resp in event.get_function_responses() or []:
        if resp.name in harness.SKILL_TOOL_NAMES:
            continue
        body = dict(resp.response or {})
        out.append({
            "type": "tool_result",
            "name": resp.name,
            "status": body.get("status", "ok"),
            "code": body.get("code"),
            "ms": (body.get("meta") or {}).get("ms"),
            "summary": _summarize(resp.name, body),
        })
    um = event.usage_metadata
    if um and (um.prompt_token_count or um.candidates_token_count):
        cfg = harness.tier_config(tier)
        tokens_in = um.prompt_token_count or 0
        tokens_out = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        out.append({
            "type": "usage", "bucket": "s2", "calls": 1, "input_tokens": tokens_in, "output_tokens": tokens_out,
            "cost_usd": harness.cost_usd(tier, tokens_in, tokens_out), "model": cfg["model"], "label": cfg["label"],
            "node": node,
        })
    return out


@server.post("/api/run", response_model=RunResponse)
async def start_run(req: RunRequest) -> RunResponse:
    try:
        identity.resolve(req.profile)
    except identity.UnknownProfile:
        raise HTTPException(status_code=400, detail="unknown profile") from None
    run_id = str(uuid.uuid4())
    q: asyncio.Queue = asyncio.Queue()
    _runs[run_id] = q
    ticket_json = json.dumps({"text": req.text, "profile": req.profile, "run_id": run_id})

    async def _run() -> None:
        user_id = f"ui-{run_id[:8]}"
        session = await _session_svc.create_session(app_name=adk_app.name, user_id=user_id)
        new_message = Content(role="user", parts=[Part(text=ticket_json)])
        seen_svgids: set[str] = set()
        texts: dict[str, str] = {}
        tier = "lite"
        path = ""
        started = time.perf_counter()
        t_prev = started
        call_started = started  # when the current model call began, for time to first token
        got_token = False

        async def emit(ev: dict[str, Any]) -> None:
            """Every event carries its time since the run began, so the page can draw the timeline."""
            ev.setdefault("t", round((time.perf_counter() - started) * 1000))
            await q.put(ev)

        approvals.attach(run_id, emit)
        audit.record("run_start", run_id, req.profile)
        await emit({"type": "node_start", "node": "n-intake"})
        try:
            async for event in _runner.run_async(
                user_id=user_id, session_id=session.id, new_message=new_message, run_config=RUN_CONFIG
            ):
                node_name = _node_name_from_path(event.node_info.path)
                svg_id = NODE_MAP.get(node_name)

                if event.author in LLM_AUTHORS:
                    gnode = LLM_NODES[event.author]
                    if event.partial:
                        chunk = _text_of(event)
                        if chunk:
                            if not got_token:
                                got_token = True
                                await emit({"type": "ttft", "node": gnode,
                                            "ms": round((time.perf_counter() - call_started) * 1000)})
                            await emit({"type": "token", "node": gnode, "text": chunk})
                        continue
                    if got_token and event.get_function_calls():
                        await emit({"type": "answer_reset", "node": gnode})
                    got_token = False
                    for nested in _nested_events(event, tier, gnode):
                        await emit(nested)
                    call_started = time.perf_counter()

                # A node reports when it finishes, so its first event marks completion
                # and the next node starts right then.
                if svg_id and svg_id not in seen_svgids:
                    seen_svgids.add(svg_id)
                    now = time.perf_counter()
                    await emit({"type": "node_done", "node": svg_id, "ms": round((now - t_prev) * 1000)})
                    t_prev = now
                    nxt = NEXT.get(svg_id)
                    if svg_id == "n-intake":
                        who = getattr(event.output, "requester", None) or {}
                        await emit({"type": "identity", "profile": who.get("profile"), "label": who.get("label"),
                                     "title": who.get("title"), "tools": who.get("tools", [])})
                    if svg_id == "n-guard":
                        guard = getattr(event.output, "guardrail", None)
                        if guard:
                            await emit({"type": "guard", "data": guard})
                            if guard.get("usage"):
                                await emit({"type": "usage", "bucket": "s1", "node": "n-guard", **guard["usage"]})
                            nxt = GUARD_NEXT.get(guard.get("verdict", ""))
                    if svg_id == "n-understand":
                        und = getattr(event.output, "understanding", None)
                        if und:
                            path = und.get("path", "")
                            tier = (und.get("plan") or {}).get("tier", "lite")
                            await emit({"type": "understand", "data": und})
                            if und.get("usage"):
                                await emit({"type": "usage", "bucket": "s1", "node": "n-understand", **und["usage"]})
                            nxt = UNDERSTAND_NEXT.get(path)
                    if svg_id == "n-plan":
                        plan = getattr(event.output, "plan", None)
                        if plan:
                            tier = plan.get("tier", tier)
                            await emit({"type": "plan", "data": plan})
                            if plan.get("usage"):
                                await emit({"type": "usage", "bucket": "s1", "node": "n-plan", **plan["usage"]})
                    if nxt:
                        await emit({"type": "node_start", "node": nxt})
                        if nxt in ("n-handle", "n-reply"):
                            call_started, got_token = time.perf_counter(), False
                        if nxt in ("n-handle", "n-reply"):
                            await emit({"type": "style", "name": harness.STYLE_SKILL})

                if node_name in FINAL_NODES and event.content:
                    for part in event.content.parts or []:
                        if part.text:
                            texts[node_name] = texts.get(node_name, "") + part.text

            reply = next((texts[n] for n in FINAL_NODES if texts.get(n)), "")
            audit.record("run_complete", run_id, req.profile, path=path or "guardrail",
                         ms=round((time.perf_counter() - started) * 1000))
            await emit({"type": "complete", "reply": reply.strip(), "route": path})
        except Exception as exc:  # noqa: BLE001
            log.exception("run failed")
            audit.record("run_error", run_id, req.profile, error=type(exc).__name__)
            await emit({"type": "error", "message": _friendly_error(exc)})
        finally:
            approvals.detach(run_id)
            await q.put(None)  # sentinel

    asyncio.create_task(_run())
    return RunResponse(run_id=run_id)


class ApprovalDecision(BaseModel):
    id: str
    approve: bool
    by: str  # profile id of the person answering. A deployed version takes this from the SSO session.


@server.post("/api/approve/{run_id}")
async def approve(run_id: str, body: ApprovalDecision) -> dict[str, str]:
    if not approvals.waiting(run_id, body.id):
        raise HTTPException(status_code=404, detail="nothing is waiting for that approval")
    if not approvals.may_answer(run_id, body.id, body.by):
        audit.record("approval_refused", run_id, body.by, approval=body.id)
        raise HTTPException(status_code=403, detail="that person cannot approve this action")
    approvals.decide(run_id, body.id, body.approve, body.by)
    return {"status": "approved" if body.approve else "declined"}


@server.get("/api/stream/{run_id}")
async def stream_run(run_id: str) -> EventSourceResponse:
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="run not found")
    q = _runs[run_id]

    async def _generator() -> AsyncGenerator[dict, None]:
        try:
            while True:
                payload = await asyncio.wait_for(q.get(), timeout=150.0)
                if payload is None:
                    break
                yield {"data": json.dumps(payload)}
        except asyncio.TimeoutError:
            yield {"data": json.dumps({"type": "error", "message": "timeout"})}
        finally:
            _runs.pop(run_id, None)

    return EventSourceResponse(_generator())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(server, host="127.0.0.1", port=5174, log_level="info")
