"""Shared utilities for backend clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wikifs.errors import ErrorCollector
    from wikifs.tracing import TraceContext


def record_api_error(
    error_collector: ErrorCollector | None,
    ctx: TraceContext | None,
    category: str,
    severity: str,
    message: str,
    details: dict[str, Any],
) -> None:
    """Record error if collector and ctx available."""
    if error_collector is None:
        return
    trace_id = ctx._trace_id if ctx else None
    run_id = ctx._run_id if ctx else None
    command = ctx._command if ctx else None
    path = ctx._path if ctx else None
    error_collector.record(
        category=category,
        severity=severity,
        message=message,
        details=details,
        trace_id=trace_id,
        run_id=run_id,
        command=command,
        path=path,
    )
