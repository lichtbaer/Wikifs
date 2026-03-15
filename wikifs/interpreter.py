"""Command interpreter — validates JSON input, dispatches to router, formats response."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from wikifs.errors import ErrorCollector, Run, RunStore
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


def _record_routing_error(
    error_collector: ErrorCollector | None,
    trace_id: str,
    command: str,
    path: str,
    message: str,
    error_type: str,
) -> None:
    """Record routing/validation error."""
    if error_collector is None:
        return
    error_collector.record(
        category="routing",
        severity="warning",
        message=message,
        details={"error_type": error_type},
        trace_id=trace_id,
        command=command,
        path=path,
    )


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
        error_collector: ErrorCollector | None = None,
        run_store: RunStore | None = None,
    ) -> None:
        self._router = router
        self._trace_collector = trace_collector
        self._handlers = handlers
        self._trace_store = trace_store
        self._error_collector = error_collector
        self._run_store = run_store

    def _persist_cli_run(
        self,
        run_id: str,
        trace_id: str,
        start: float,
        exit_code: int,
        output: str,
        command: str,
        path: str,
    ) -> None:
        """Persist a CLI run to RunStore."""
        if self._run_store is None:
            return
        duration_ms = (time.perf_counter() - start) * 1000
        error_ids: list[str] = []
        if self._error_collector:
            error_ids = self._error_collector.get_error_ids_for_run(run_id)
        run = Run(
            run_id=run_id,
            timestamp=datetime.now(UTC).isoformat(),
            type="cli",
            query=f"{command} {path}".strip() or None,
            trace_ids=[trace_id],
            error_ids=error_ids,
            duration_ms=duration_ms,
            success=(exit_code == 0),
            result=output,
            model=None,
            commands_count=1,
        )
        self._run_store.insert(run)

    def execute(self, raw_input: dict[str, Any]) -> CommandResponse:
        """Execute command from raw JSON dict. Returns CommandResponse."""
        start = time.perf_counter()
        run_id_raw = raw_input.get("run_id")
        if run_id_raw and isinstance(run_id_raw, str) and run_id_raw.strip():
            run_id = run_id_raw.strip()
            skip_persist = True  # Agent run — agent will persist
        else:
            run_id = str(uuid.uuid4())
            skip_persist = False
        request_id = str(raw_input.get("request_id") or uuid.uuid4())
        if isinstance(request_id, str):
            request_id = request_id.strip() or str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())

        # Parse
        parsed = _parse_command(raw_input)
        if isinstance(parsed, str):
            raw_cmd = str(raw_input.get("command", ""))
            raw_path = str(raw_input.get("path", ""))
            flags_raw = raw_input.get("flags")
            flags = flags_raw if isinstance(flags_raw, list) else []
            ctx = self._trace_collector.start_trace(
                command=raw_cmd,
                path=raw_path,
                flags=flags,
                request_id=request_id,
                run_id=run_id,
            )
            with ctx.phase("parse"):
                pass
            trace = self._trace_collector.finish_trace(ctx, 1)
            if self._trace_store:
                self._trace_store.save(trace)
            _record_routing_error(
                self._error_collector,
                trace.trace_id,
                raw_cmd,
                raw_path,
                parsed,
                "invalid_command",
            )
            if not skip_persist:
                self._persist_cli_run(
                    run_id, trace.trace_id, start, 1, f"Error: {parsed}", raw_cmd, raw_path
                )
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
            run_id=run_id,
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
                msg = f"Unknown command: {cmd.command}. Allowed: ls, cat, grep, search"
                _record_routing_error(
                    self._error_collector,
                    trace_id,
                    cmd.command,
                    cmd.path,
                    msg,
                    "invalid_command",
                )
                if not skip_persist:
                    self._persist_cli_run(
                        run_id, trace_id, start, 1, msg, cmd.command, cmd.path
                    )
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output=msg,
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
                msg = "Invalid path: must start with /wiki/"
                _record_routing_error(
                    self._error_collector,
                    trace_id,
                    cmd.command,
                    cmd.path,
                    msg,
                    "invalid_path",
                )
                if not skip_persist:
                    self._persist_cli_run(
                        run_id, trace_id, start, 1, msg, cmd.command, cmd.path
                    )
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output=msg,
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
                _record_routing_error(
                    self._error_collector,
                    trace_id,
                    cmd.command,
                    cmd.path,
                    flag_err,
                    "invalid_flag",
                )
                if not skip_persist:
                    self._persist_cli_run(
                        run_id, trace_id, start, 1, flag_err, cmd.command, cmd.path
                    )
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
                    msg = "Use `search` for cross-entity queries"
                    _record_routing_error(
                        self._error_collector,
                        trace_id,
                        cmd.command,
                        cmd.path,
                        msg,
                        "invalid_path",
                    )
                    if not skip_persist:
                        self._persist_cli_run(
                            run_id, trace_id, start, 1, msg, cmd.command, cmd.path
                        )
                    timing_ms = (time.perf_counter() - start) * 1000
                    return CommandResponse(
                        output=msg,
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
                msg = f"Not found: {path}"
                _record_routing_error(
                    self._error_collector,
                    trace_id,
                    cmd.command,
                    cmd.path,
                    msg,
                    "not_found",
                )
                if not skip_persist:
                    self._persist_cli_run(
                        run_id, trace_id, start, 2, msg, cmd.command, cmd.path
                    )
                timing_ms = (time.perf_counter() - start) * 1000
                return CommandResponse(
                    output=msg,
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
            if not skip_persist:
                self._persist_cli_run(
                    run_id, trace_id, start, exit_code, output, cmd.command, cmd.path
                )
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
            err_msg = str(e)
            if self._error_collector:
                self._error_collector.record(
                    category="routing",
                    severity="error",
                    message=err_msg,
                    details={"exception": type(e).__name__},
                    trace_id=trace_id,
                    run_id=run_id,
                    command=cmd.command,
                    path=cmd.path,
                )
            if not skip_persist:
                self._persist_cli_run(
                    run_id, trace_id, start, 1, err_msg, cmd.command, cmd.path
                )
            timing_ms = (time.perf_counter() - start) * 1000
            return CommandResponse(
                output=err_msg,
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
