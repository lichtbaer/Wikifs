"""Command interpreter — validates JSON input, dispatches to router, formats response."""

from __future__ import annotations

import time
import uuid
from typing import Any

from wikifs.models import Command, CommandResponse, Handler
from wikifs.router import RouteMatch, normalize_path
from wikifs.tracing import TraceCollector, TraceStore

# Allowed commands and their flags
ALLOWED_COMMANDS = {"ls", "cat", "grep", "search"}
COMMAND_FLAGS: dict[str, set[str]] = {
    "ls": {"-l"},
    "cat": set(),
    "grep": {"-i", "-c"},
    "search": {"--type", "--limit", "--sparql"},
}

# Path that indicates cross-entity grep (invalid for grep)
ENTITIES_ROOT_NORMALIZED = "/wiki/entities"


def _resolve_wikidata_alias(path: str) -> str:
    """Resolve Wikidata ID aliases (Q1794 -> entity name). Stub for WIKI-005."""
    # Stub: no resolution yet, just return path as-is
    return path


def _dispatch(
    route: RouteMatch,
    command: str,
    flags: list[str],
    pattern: str | None,
    ctx: Any,
    handlers: dict[str, Handler] | None,
) -> tuple[str, int, str | None, list[str] | None]:
    """Dispatch to handler. Returns (output, exit_code, error_type, suggestions)."""
    if handlers is None or route.handler not in handlers:
        return (
            f"[stub] handler={route.handler} params={route.params!r}",
            0,
            None,
            None,
        )
    handler = handlers[route.handler]
    response = handler.handle(
        command=command,
        params=route.params,
        flags=flags,
        pattern=pattern,
        route=route.handler,
        ctx=ctx,
    )
    return (
        response.output,
        response.exit_code,
        response.error_type,
        response.suggestions,
    )


def _validate_flags(command: str, flags: list[str]) -> str | None:
    """Validate flags for command. Returns error message or None if valid."""
    allowed = COMMAND_FLAGS[command]
    i = 0
    while i < len(flags):
        flag = flags[i]
        if flag in allowed:
            if flag in ("--type", "--limit", "--sparql") and i + 1 < len(flags):
                i += 1  # Skip value
                if flag == "--limit":
                    try:
                        int(flags[i])
                    except ValueError:
                        return f"Invalid value for --limit: {flags[i]}"
        elif flag.startswith("--"):
            return f"Unknown flag: {flag}. Allowed for {command}: {sorted(allowed) or 'none'}"
        elif flag.startswith("-"):
            return f"Unknown flag: {flag}. Allowed for {command}: {sorted(allowed) or 'none'}"
        i += 1
    return None


def _parse_command(raw: dict[str, Any]) -> Command | str:
    """Parse raw dict to Command. Returns Command or error message string."""
    try:
        command = str(raw.get("command", "")).strip().lower()
        path = str(raw.get("path", "")).strip()
        flags_raw = raw.get("flags")
        if flags_raw is None:
            flags = []
        elif isinstance(flags_raw, list):
            flags = [str(f).strip() for f in flags_raw]
        else:
            return "Invalid flags: must be a list"
        pattern_raw = raw.get("pattern")
        pattern = str(pattern_raw).strip() if pattern_raw is not None else None
        if pattern is not None and not pattern:
            pattern = None
        request_id = raw.get("request_id")
        if request_id is None or not str(request_id).strip():
            request_id = str(uuid.uuid4())
        else:
            request_id = str(request_id).strip()

        if not command:
            return "Missing command"
        if not path:
            return "Missing path"

        return Command(
            command=command,
            path=path,
            flags=flags,
            pattern=pattern,
            request_id=request_id,
        )
    except (TypeError, ValueError) as e:
        return f"Invalid input: {e}"


def _dispatch_stub(route: RouteMatch) -> str:
    """Dispatch to handler stub — returns placeholder response."""
    return f"[stub] handler={route.handler} params={route.params!r}"


class Interpreter:
    """Interprets JSON commands, validates, routes, and returns CommandResponse."""

    def __init__(
        self,
        router: Any,
        trace_collector: TraceCollector,
        handlers: dict[str, Handler] | None = None,
        trace_store: TraceStore | None = None,
    ) -> None:
        self._router = router
        self._trace_collector = trace_collector
        self._handlers = handlers
        self._trace_store = trace_store

    def execute(self, raw_input: dict[str, Any]) -> CommandResponse:
        """Execute command from raw JSON dict. Returns CommandResponse."""
        start = time.perf_counter()
        request_id = str(raw_input.get("request_id") or uuid.uuid4())
        if isinstance(request_id, str):
            request_id = request_id.strip() or str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())

        # Parse
        parsed = _parse_command(raw_input)
        if isinstance(parsed, str):
            flags_raw = raw_input.get("flags")
            flags = flags_raw if isinstance(flags_raw, list) else []
            ctx = self._trace_collector.start_trace(
                command=str(raw_input.get("command", "")),
                path=str(raw_input.get("path", "")),
                flags=flags,
                request_id=request_id,
            )
            with ctx.phase("parse"):
                pass
            trace = self._trace_collector.finish_trace(ctx, 1)
            if self._trace_store:
                self._trace_store.save(trace)
            timing_ms = (time.perf_counter() - start) * 1000
            return CommandResponse(
                output=f"Error: {parsed}",
                exit_code=1,
                request_id=request_id,
                trace_id=trace.trace_id,
                timing_ms=timing_ms,
                error_type="invalid_command",
            )

        cmd = parsed
        request_id = cmd.request_id

        # Start trace
        ctx = self._trace_collector.start_trace(
            command=cmd.command,
            path=cmd.path,
            flags=cmd.flags,
            request_id=request_id,
        )
        trace_id = ctx._trace_id

        try:
            with ctx.phase("parse"):
                pass  # Parse already done

            # Validate command type
            if cmd.command not in ALLOWED_COMMANDS:
                with ctx.phase("route"):
                    pass
                trace = self._trace_collector.finish_trace(ctx, 1)
                if self._trace_store:
                    self._trace_store.save(trace)
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output=f"Unknown command: {cmd.command}. Allowed: ls, cat, grep, search",
                    exit_code=1,
                    request_id=request_id,
                    trace_id=trace_id,
                    timing_ms=timing_ms,
                    error_type="invalid_command",
                    suggestions=["ls", "cat", "grep", "search"],
                )

            # Validate path prefix
            if not cmd.path.startswith("/wiki/"):
                with ctx.phase("route"):
                    pass
                trace = self._trace_collector.finish_trace(ctx, 1)
                if self._trace_store:
                    self._trace_store.save(trace)
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output="Invalid path: must start with /wiki/",
                    exit_code=1,
                    request_id=request_id,
                    trace_id=trace_id,
                    timing_ms=timing_ms,
                    error_type="invalid_path",
                )

            # Validate flags
            flag_err = _validate_flags(cmd.command, cmd.flags)
            if flag_err:
                with ctx.phase("route"):
                    pass
                trace = self._trace_collector.finish_trace(ctx, 1)
                if self._trace_store:
                    self._trace_store.save(trace)
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output=flag_err,
                    exit_code=1,
                    request_id=request_id,
                    trace_id=trace_id,
                    timing_ms=timing_ms,
                    error_type="invalid_flag",
                )

            # grep on /wiki/entities/ (cross-entity, no specific entity) is invalid
            if cmd.command == "grep":
                normalized_for_check = normalize_path(cmd.path)
                # Reject /wiki/entities or /wiki/entities/ — no entity name
                if normalized_for_check == ENTITIES_ROOT_NORMALIZED:
                    with ctx.phase("route"):
                        pass
                    trace = self._trace_collector.finish_trace(ctx, 1)
                    if self._trace_store:
                        self._trace_store.save(trace)
                    timing_ms = (time.perf_counter() - start) * 1000
                    return CommandResponse(
                        output="Use `search` for cross-entity queries",
                        exit_code=1,
                        request_id=request_id,
                        trace_id=trace_id,
                        timing_ms=timing_ms,
                        error_type="invalid_path",
                        suggestions=["search"],
                    )

            # Normalize path and resolve Wikidata alias
            path = normalize_path(cmd.path)
            path = _resolve_wikidata_alias(path)

            # Route
            with ctx.phase("route"):
                route = self._router.match(path)

            if route is None:
                trace = self._trace_collector.finish_trace(ctx, 2)
                if self._trace_store:
                    self._trace_store.save(trace)
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output=f"Not found: {path}",
                    exit_code=2,
                    request_id=request_id,
                    trace_id=trace_id,
                    timing_ms=timing_ms,
                    error_type="not_found",
                )

            # Dispatch to handler
            with ctx.phase("handler"):
                output, exit_code, error_type, suggestions = _dispatch(
                    route,
                    cmd.command,
                    cmd.flags,
                    cmd.pattern,
                    ctx,
                    self._handlers,
                )
            trace = self._trace_collector.finish_trace(ctx, exit_code)
            if self._trace_store:
                self._trace_store.save(trace)
            timing_ms = (time.perf_counter() - start) * 1000

            return CommandResponse(
                output=output,
                exit_code=exit_code,
                request_id=request_id,
                trace_id=trace_id,
                timing_ms=timing_ms,
                error_type=error_type,
                suggestions=suggestions,
            )

        except Exception as e:
            trace = self._trace_collector.finish_trace(ctx, 1)
            if self._trace_store:
                self._trace_store.save(trace)
            timing_ms = (time.perf_counter() - start) * 1000
            return CommandResponse(
                output=str(e),
                exit_code=1,
                request_id=request_id,
                trace_id=trace_id,
                timing_ms=timing_ms,
                error_type="invalid_command",
            )

    def execute_command(self, command: Command) -> CommandResponse:
        """Execute a parsed Command object."""
        raw = {
            "command": command.command,
            "path": command.path,
            "flags": command.flags,
            "pattern": command.pattern,
            "request_id": command.request_id,
        }
        return self.execute(raw)
