"""FastAPI HTTP server for WikiFS — thin wrapper around the interpreter."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wikifs import __version__, create_interpreter_with_components
from wikifs.tracing import TraceStats

app = FastAPI(title="WikiFS HTTP API", version=__version__)

# CORS for localhost:* — Explorer-UI runs on different port
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy init: same as CLI — Config → Cache → Tracing → Backends → Router → Interpreter
_server_ctx: Any = None


def _get_ctx() -> Any:
    """Get or create server context (interpreter, cache, trace_store)."""
    global _server_ctx
    if _server_ctx is None:
        _server_ctx = create_interpreter_with_components()
    return _server_ctx


def _trace_to_dict(trace: Any) -> dict[str, Any]:
    """Serialize Trace to JSON-serializable dict."""
    return {
        "trace_id": trace.trace_id,
        "request_id": trace.request_id,
        "timestamp": trace.timestamp,
        "command": trace.command,
        "path": trace.path,
        "flags": trace.flags,
        "phases": [
            {
                "phase": p.phase,
                "duration_ms": p.duration_ms,
                "result": p.result,
                "cache_hit": p.cache_hit,
                "api_url": p.api_url,
                "response_bytes": p.response_bytes,
                "error": p.error,
                "metadata": p.metadata,
            }
            for p in trace.phases
        ],
        "total_duration_ms": trace.total_duration_ms,
        "cache_hits": trace.cache_hits,
        "cache_misses": trace.cache_misses,
        "api_calls": trace.api_calls,
        "response_bytes": trace.response_bytes,
        "exit_code": trace.exit_code,
    }


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


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck endpoint."""
    return {"status": "ok", "version": __version__}


@app.post("/execute")
def execute(
    body: dict[str, Any],
    include_trace: bool = False,
) -> dict[str, Any]:
    """Execute command. Returns CommandResponse as JSON. Add ?include_trace=true for full trace."""
    ctx = _get_ctx()
    response = ctx.interpreter.execute(body)
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
            result["trace"] = _trace_to_dict(trace)
    return result


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
    return [_trace_to_dict(t) for t in result]


@app.delete("/cache")
def cache_clear() -> dict[str, int]:
    """Clear cache. Returns deleted count."""
    ctx = _get_ctx()
    deleted = ctx.cache.clear()
    return {"deleted": deleted}
