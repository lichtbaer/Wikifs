"""FastAPI HTTP server for WikiFS — thin wrapper around the interpreter."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import queue
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from wikifs import __version__, create_interpreter_with_components
from wikifs.agent import AgentEvent, run_agent_streaming
from wikifs.agent_models import AgentRequest
from wikifs.models import CommandResponse
from wikifs.tracing import TraceStats

MAX_BATCH_COMMANDS = 50


def _expected_api_key() -> str | None:
    """Return configured API key, or None if auth is disabled."""
    key = os.environ.get("WIKIFS_API_KEY", "").strip()
    return key or None


def _extract_request_api_key(request: Request) -> str | None:
    """Read API key from X-API-Key or Authorization: Bearer."""
    raw = request.headers.get("x-api-key")
    if raw and raw.strip():
        return raw.strip()
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    return None


def _api_key_auth_exempt(request: Request) -> bool:
    """Routes that stay public when WIKIFS_API_KEY is set."""
    if request.method == "OPTIONS":
        return True
    path = request.url.path.rstrip("/") or "/"
    return request.method == "GET" and path == "/health"


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Optional shared-secret check when WIKIFS_API_KEY is set."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        expected = _expected_api_key()
        if expected is None or _api_key_auth_exempt(request):
            return await call_next(request)
        got = _extract_request_api_key(request)
        exp_b = expected.encode("utf-8")
        got_b = got.encode("utf-8") if got is not None else b""
        if got is None or len(got_b) != len(exp_b) or not hmac.compare_digest(
            got_b, exp_b
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
        return await call_next(request)


app = FastAPI(title="WikiFS HTTP API", version=__version__)

# CORS for localhost:* — Explorer-UI runs on different port
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(APIKeyMiddleware)

# Lazy init: same as CLI — Config → Cache → Tracing → Backends → Router → Interpreter
_server_ctx: Any = None


def _get_ctx() -> Any:
    """Get or create server context (interpreter, cache, trace_store)."""
    global _server_ctx
    if _server_ctx is None:
        _server_ctx = create_interpreter_with_components()
    return _server_ctx


def _trace_stats_to_dict(stats: TraceStats) -> dict[str, Any]:
    """Serialize TraceStats to JSON-serializable dict."""
    return {
        "count": stats.count,
        "avg_duration_ms": stats.avg_duration_ms,
        "p50_duration_ms": stats.p50_duration_ms,
        "p95_duration_ms": stats.p95_duration_ms,
        "max_duration_ms": stats.max_duration_ms,
        "cache_hit_rate": stats.cache_hit_rate,
        "commands_by_type": stats.commands_by_type,
    }


def _command_response_to_dict(
    ctx: Any,
    response: CommandResponse,
    *,
    include_trace: bool = False,
) -> dict[str, Any]:
    """Build JSON object for a single CommandResponse (same shape as POST /execute)."""
    result: dict[str, Any] = {
        "output": response.output,
        "exit_code": response.exit_code,
        "request_id": response.request_id,
        "trace_id": response.trace_id,
        "timing_ms": response.timing_ms,
        "error_type": response.error_type,
        "suggestions": response.suggestions,
    }
    if include_trace:
        trace = ctx.trace_store.get_by_trace_id(response.trace_id)
        if trace is not None:
            result["trace"] = trace.to_dict()
    return result


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck endpoint."""
    return {"status": "ok", "version": __version__}


@app.post("/execute")
def execute(
    body: dict[str, Any],
    include_trace: bool = False,
) -> dict[str, Any]:
    """Execute command. Returns CommandResponse as JSON. Add ?include_trace=true for full trace.

    Body may include optional ``lang`` (e.g. ``en``, ``de``) when it is listed in
    ``supported_languages`` in config; overrides default Wikipedia/Wikidata language.
    """
    ctx = _get_ctx()
    response = ctx.interpreter.execute(body)
    return _command_response_to_dict(ctx, response, include_trace=include_trace)


@app.post("/complete")
def complete(body: dict[str, Any]) -> dict[str, Any]:
    """Path completion for virtual WikiFS paths under ``/wiki/``.

    Body: ``path`` (required prefix), optional ``lang``, optional ``limit`` (1–100).
    Response: ``path``, ``candidates`` (full path strings), optional ``error``.
    """
    ctx = _get_ctx()
    result = ctx.interpreter.complete(body)
    out: dict[str, Any] = {"path": result.path, "candidates": result.candidates}
    if result.error:
        out["error"] = result.error
    return out


@app.post("/execute/batch")
def execute_batch(
    body: dict[str, Any],
    include_trace: bool = False,
) -> dict[str, Any]:
    f"""Run multiple commands in order. Body: ``commands`` (array of /execute bodies).

    Optional top-level ``lang`` is applied to items that omit ``lang``.
    At most {MAX_BATCH_COMMANDS} commands per request. Response: ``results``, ``count``,
    ``total_timing_ms``.
    """
    ctx = _get_ctx()
    commands = body.get("commands")
    if not isinstance(commands, list):
        raise HTTPException(
            status_code=422,
            detail="Request body must include 'commands' as a JSON array",
        )
    if len(commands) > MAX_BATCH_COMMANDS:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_BATCH_COMMANDS} commands per batch",
        )
    global_lang = body.get("lang")
    t0 = time.perf_counter()
    results: list[dict[str, Any]] = []
    for item in commands:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=422,
                detail="Each batch item must be a JSON object",
            )
        merged: dict[str, Any] = dict(item)
        if (
            isinstance(global_lang, str)
            and global_lang.strip()
            and "lang" not in merged
        ):
            merged["lang"] = global_lang.strip().lower()
        response = ctx.interpreter.execute(merged)
        results.append(
            _command_response_to_dict(ctx, response, include_trace=include_trace)
        )
    total_ms = (time.perf_counter() - t0) * 1000
    return {
        "results": results,
        "count": len(results),
        "total_timing_ms": total_ms,
    }


@app.get("/stats")
def stats() -> dict[str, Any]:
    """Trace aggregate statistics."""
    ctx = _get_ctx()
    s = ctx.trace_store.stats()
    return _trace_stats_to_dict(s)


@app.get("/traces")
def traces(
    slow: float | None = None,
    command: str | None = None,
    path: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query traces. Params: slow (ms), command, path (SQL LIKE), limit."""
    ctx = _get_ctx()
    result = ctx.trace_store.query(
        min_duration_ms=slow,
        command=command,
        path_pattern=path,
        limit=limit,
    )
    return [t.to_dict() for t in result]


@app.delete("/cache")
def cache_clear() -> dict[str, int]:
    """Clear cache. Returns deleted count."""
    ctx = _get_ctx()
    deleted = ctx.cache.clear()
    return {"deleted": deleted}


@app.get("/errors")
def errors(
    since: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    run_id: str | None = None,
    unresolved: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query errors. Params: since, category, severity, run_id, unresolved, limit."""
    ctx = _get_ctx()
    entries = ctx.error_store.query(
        since=since,
        category=category,
        severity=severity,
        run_id=run_id,
        unresolved_only=unresolved,
        limit=limit,
    )
    return [
        {
            "error_id": e.error_id,
            "timestamp": e.timestamp,
            "trace_id": e.trace_id,
            "run_id": e.run_id,
            "category": e.category,
            "severity": e.severity,
            "command": e.command,
            "path": e.path,
            "message": e.message,
            "details": e.details,
            "resolved": e.resolved,
        }
        for e in entries
    ]


@app.get("/errors/summary")
def errors_summary() -> dict[str, dict[str, int]]:
    """Aggregate errors by category and severity."""
    ctx = _get_ctx()
    summary: dict[str, dict[str, int]] = ctx.error_store.summary()
    return summary


@app.patch("/errors/{error_id}")
def errors_resolve(error_id: str) -> dict[str, Any]:
    """Mark error as resolved."""
    ctx = _get_ctx()
    ok = ctx.error_store.mark_resolved(error_id)
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Error not found")
    return {"error_id": error_id, "resolved": True}


@app.get("/runs")
def runs(
    failed: bool = False,
    type: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query runs. Params: failed, type, since, limit."""
    ctx = _get_ctx()
    entries = ctx.run_store.query(
        failed_only=failed,
        run_type=type,
        since=since,
        limit=limit,
    )
    return [
        {
            "run_id": r.run_id,
            "timestamp": r.timestamp,
            "type": r.type,
            "query": r.query,
            "trace_ids": r.trace_ids,
            "error_ids": r.error_ids,
            "duration_ms": r.duration_ms,
            "success": r.success,
            "result": r.result,
            "model": r.model,
            "commands_count": r.commands_count,
        }
        for r in entries
    ]


@app.get("/runs/{run_id}")
def runs_show(run_id: str, full: bool = False) -> dict[str, Any]:
    """Get single run. Add ?full=true for traces and errors."""
    ctx = _get_ctx()
    run = ctx.run_store.get_by_id(run_id)
    if run is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Run not found")
    if full:
        traces = []
        for tid in run.trace_ids:
            t = ctx.trace_store.get_by_trace_id(tid)
            if t:
                traces.append(
                    {
                        "trace_id": t.trace_id,
                        "command": t.command,
                        "path": t.path,
                        "timing_ms": t.total_duration_ms,
                        "exit_code": t.exit_code,
                    }
                )
        errors_list = []
        for eid in run.error_ids:
            e = ctx.error_store.get_by_id(eid)
            if e:
                errors_list.append(
                    {
                        "error_id": e.error_id,
                        "category": e.category,
                        "severity": e.severity,
                        "message": e.message,
                        "details": e.details,
                    }
                )
        return {
            "run_id": run.run_id,
            "type": run.type,
            "query": run.query,
            "model": run.model,
            "success": run.success,
            "duration_ms": run.duration_ms,
            "commands_count": run.commands_count,
            "result": run.result,
            "traces": traces,
            "errors": errors_list,
        }
    return {
        "run_id": run.run_id,
        "timestamp": run.timestamp,
        "type": run.type,
        "query": run.query,
        "trace_ids": run.trace_ids,
        "error_ids": run.error_ids,
        "duration_ms": run.duration_ms,
        "success": run.success,
        "result": run.result,
        "model": run.model,
        "commands_count": run.commands_count,
    }


@app.post("/agent")
def agent(req: AgentRequest) -> dict[str, Any]:
    """Run the WikiFS AI agent on a natural language query.

    Request: {"query": "string", "model": "openai:gpt-4o" (optional)}
    Response: {
        "answer": "string",
        "commands_executed": [{"command": "ls", "path": "...", "timing_ms": 142}, ...],
        "total_commands": 5,
        "total_duration_ms": 1200
    }
    """
    from wikifs.agent import run_agent

    try:
        result = run_agent(
            query=req.query,
            model=req.model,
        )
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(e)) from e

    return result.model_dump()


def _agent_stream_generator(
    query: str,
    model: str | None,
    trace_store: Any,
    event_queue: queue.Queue[AgentEvent | None],
) -> Any:
    """Run agent and put events into queue. None signals completion."""
    try:
        run_agent_streaming(
            query=query,
            callback=lambda e: event_queue.put(e),
            model=model,
            trace_store=trace_store,
        )
    except Exception as e:
        # Fallback if an unexpected error escapes the streaming runner
        event_queue.put(
            AgentEvent(
                "error",
                {"message": str(e), "category": "stream", "exception": type(e).__name__},
            )
        )
        event_queue.put(AgentEvent("done", {"success": False}))
    finally:
        event_queue.put(None)


async def _sse_event_generator(
    query: str,
    model: str | None,
    trace_store: Any,
) -> Any:
    """Async generator yielding SSE-formatted events."""
    event_queue: queue.Queue[AgentEvent | None] = queue.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        lambda: _agent_stream_generator(query, model, trace_store, event_queue),
    )
    while True:
        event = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: event_queue.get(),
        )
        if event is None:
            break
        yield f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"


@app.post("/agent/stream")
async def agent_stream(req: AgentRequest) -> StreamingResponse:
    """Stream agent steps as Server-Sent Events.

    Request: {"query": "string", "model": "openai:gpt-4o" (optional)}
    Response: text/event-stream with events: agent_start, thinking, tool_call,
    tool_result, answer, done (or error, done).
    """
    ctx = _get_ctx()
    return StreamingResponse(
        _sse_event_generator(req.query, req.model, ctx.trace_store),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
