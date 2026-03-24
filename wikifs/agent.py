"""WikiFS Pydantic AI Agent — uses WikiFS as tools to answer natural language questions."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from wikifs import create_interpreter
from wikifs.agent_models import AgentResponse, CommandExecuted
from wikifs.config import load_config

if TYPE_CHECKING:
    from wikifs.errors import ErrorCollector
    from wikifs.interpreter import Interpreter

from wikifs.tracing import TraceStore


@dataclass
class AgentEvent:
    """Single event emitted during agent streaming."""

    type: str  # "agent_start", "thinking", "tool_call", "tool_result", "answer", "error", "done"
    data: dict[str, Any]


AgentCallback = Callable[[AgentEvent], None]


@dataclass
class AgentDeps:
    """Dependencies for WikiFS agent tools: interpreter and command tracking."""

    interpreter: Interpreter
    commands_executed: list[CommandExecuted] = field(default_factory=list)
    error_collector: ErrorCollector | None = None
    run_id: str | None = None
    event_callback: AgentCallback | None = None
    trace_store: TraceStore | None = None
    current_step: int = 0


def _emit(deps: AgentDeps, event: AgentEvent) -> None:
    """Emit event via callback if set."""
    if deps.event_callback:
        deps.event_callback(event)


def _execute_tool(
    deps: AgentDeps,
    command: str,
    path: str,
    flags: list[str],
    pattern: str | None = None,
    emit_extras: dict[str, Any] | None = None,
) -> str:
    """Shared execution logic for all agent tool functions."""
    deps.current_step += 1
    step = deps.current_step
    emit_data: dict[str, Any] = {"command": command, "path": path, "step": step}
    if emit_extras:
        emit_data.update(emit_extras)
    _emit(deps, AgentEvent("tool_call", emit_data))

    start = time.perf_counter()
    raw: dict[str, object] = {"command": command, "path": path, "flags": flags}
    if pattern is not None:
        raw["pattern"] = pattern
    if deps.run_id:
        raw["run_id"] = deps.run_id
    result = deps.interpreter.execute(raw)
    timing_ms = (time.perf_counter() - start) * 1000

    trace_dict: dict[str, Any] | None = None
    if deps.trace_store and result.trace_id:
        trace = deps.trace_store.get_by_trace_id(result.trace_id)
        if trace:
            trace_dict = trace.to_dict()

    deps.commands_executed.append(
        CommandExecuted(
            command=command,
            path=path,
            timing_ms=timing_ms,
            trace_id=result.trace_id,
            exit_code=result.exit_code,
        )
    )

    _emit(
        deps,
        AgentEvent(
            "tool_result",
            {
                "step": step,
                "output": result.output,
                "exit_code": result.exit_code,
                "timing_ms": timing_ms,
                "trace": trace_dict,
            },
        ),
    )
    return result.output if result.exit_code == 0 else f"Error: {result.output}"


def _wikifs_ls(ctx: RunContext[AgentDeps], path: str, detailed: bool = False) -> str:
    """List contents of a WikiFS directory.

    Examples:
    - ls /wiki/entities/Berlin/ → shows article.md, properties/, relations/, etc.
    - ls /wiki/entities/Berlin/properties/ → shows available properties
    - ls /wiki/entities/Berlin/relations/ → shows relation types
    - ls /wiki/classes/city/ → shows cities
    """
    return _execute_tool(ctx.deps, "ls", path, ["-l"] if detailed else [])


def _wikifs_cat(ctx: RunContext[AgentDeps], path: str) -> str:
    """Read contents of a WikiFS file.

    Examples:
    - cat /wiki/entities/Berlin/summary.md → short summary
    - cat /wiki/entities/Berlin/article.md → full article
    - cat /wiki/entities/Berlin/properties/population.txt → population value
    - cat /wiki/entities/Berlin/meta.json → entity metadata
    """
    return _execute_tool(ctx.deps, "cat", path, [])


def _wikifs_head(ctx: RunContext[AgentDeps], path: str, lines: int = 10) -> str:
    """First `lines` lines of a WikiFS file (saves tokens on long articles)."""
    return _execute_tool(
        ctx.deps, "head", path, ["-n", str(lines)], emit_extras={"lines": lines}
    )


def _wikifs_tail(ctx: RunContext[AgentDeps], path: str, lines: int = 10) -> str:
    """Last `lines` lines of a WikiFS file."""
    return _execute_tool(
        ctx.deps, "tail", path, ["-n", str(lines)], emit_extras={"lines": lines}
    )


def _wikifs_grep(
    ctx: RunContext[AgentDeps],
    pattern: str,
    path: str,
    case_insensitive: bool = False,
) -> str:
    """Search for a pattern within a WikiFS entity.

    Only works within a specific entity directory.
    For cross-entity search, use wikifs_search instead.
    """
    flags = ["-i"] if case_insensitive else []
    return _execute_tool(
        ctx.deps, "grep", path, flags, pattern=pattern, emit_extras={"pattern": pattern}
    )


def _wikifs_search(
    ctx: RunContext[AgentDeps],
    query: str,
    entity_type: str = "entity",
    limit: int = 5,
) -> str:
    """Search for entities across WikiFS.

    Use this for discovering entities. For searching within
    a specific entity, use wikifs_grep instead.
    """
    return _execute_tool(
        ctx.deps,
        "search",
        "/wiki/search",
        ["--type", entity_type, "--limit", str(limit)],
        pattern=query,
        emit_extras={"pattern": query},
    )


SYSTEM_PROMPT = """You are a research assistant with access to WikiFS —
a virtual filesystem over Wikipedia and Wikidata. You can navigate
entities, read articles, explore properties and relations, and search
for information using filesystem-like commands.

Available commands:
- wikifs_ls(path): List directory contents (e.g. /wiki/entities/Berlin/)
- wikifs_cat(path): Read file contents (e.g. article.md, properties/population.txt)
- wikifs_head(path, lines=10): First lines only (use before cat for long articles)
- wikifs_tail(path, lines=10): Last lines only
- wikifs_grep(pattern, path): Search within a specific entity
- wikifs_search(query): Search across entities to discover them

Under each entity, Wikipedia also exposes virtual folders ``categories/`` (page
categories as ``*.md``) and ``links/`` (outgoing article links as ``*.md``).

Navigate the knowledge graph to find accurate answers. Use properties
for structured facts, relations to explore connections, and articles
for detailed context. Always verify facts by checking multiple sources
within WikiFS. Include WikiFS paths as sources in your answer."""


def _get_agent_config() -> tuple[str, int]:
    """Load agent config from TOML."""
    config = load_config()
    agent_cfg = config.get("agent", {})
    model = str(agent_cfg.get("default_model", "openai:gpt-4o"))
    max_tool_calls = int(agent_cfg.get("max_tool_calls", 20))
    return model, max_tool_calls


WIKIFS_TOOLS = [
    _wikifs_ls,
    _wikifs_cat,
    _wikifs_head,
    _wikifs_tail,
    _wikifs_grep,
    _wikifs_search,
]


def create_wikifs_agent(
    config_path: str | None = None,
    model: str | None = None,
    event_callback: AgentCallback | None = None,
    trace_store: TraceStore | None = None,
) -> tuple[Agent[AgentDeps, str], AgentDeps]:
    """Create WikiFS agent with tools. Returns (agent, deps) for run_sync(deps=...)."""
    interpreter = create_interpreter(config_path)
    error_collector = getattr(interpreter, "_error_collector", None)
    store = trace_store or interpreter.trace_store
    deps = AgentDeps(
        interpreter=interpreter,
        error_collector=error_collector,
        event_callback=event_callback,
        trace_store=store,
    )

    default_model, _ = _get_agent_config()
    model = model or default_model

    agent = Agent(
        model=model,
        deps_type=AgentDeps,
        system_prompt=SYSTEM_PROMPT,
        tools=WIKIFS_TOOLS,  # type: ignore[arg-type]
        defer_model_check=True,
    )
    return agent, deps


def _persist_agent_run(
    run_store: Any,
    deps: AgentDeps,
    run_id: str,
    query: str,
    model_str: str | None,
    result: Any,
    success: bool,
    total_duration_ms: float,
) -> None:
    """Persist an agent run to RunStore if available."""
    if run_store is None:
        return
    error_ids: list[str] = []
    if deps.error_collector:
        error_ids = deps.error_collector.get_error_ids_for_run(run_id)
    trace_ids = [c.trace_id for c in deps.commands_executed if c.trace_id]
    from wikifs.errors import Run

    run_result: str | None = None
    if result and result.output is not None:
        run_result = str(result.output)
    run = Run(
        run_id=run_id,
        timestamp=datetime.now(UTC).isoformat(),
        type="agent",
        query=query,
        trace_ids=trace_ids,
        error_ids=error_ids,
        duration_ms=total_duration_ms,
        success=success,
        result=run_result,
        model=model_str,
        commands_count=len(deps.commands_executed),
    )
    run_store.insert(run)


def run_agent_streaming(
    query: str,
    callback: AgentCallback,
    config_path: str | None = None,
    model: str | None = None,
    trace_store: TraceStore | None = None,
) -> AgentResponse:
    """Run the WikiFS agent with streaming events via callback.

    Emits: agent_start, thinking, tool_call, tool_result, answer, done (or error, done).
    """
    agent, deps = create_wikifs_agent(
        config_path=config_path,
        model=model,
        event_callback=callback,
        trace_store=trace_store,
    )
    run_store = getattr(deps.interpreter, "_run_store", None)
    run_id = str(uuid.uuid4())
    deps.run_id = run_id

    config = load_config(config_path)
    model_str = model or config.get("agent", {}).get("default_model", "openai:gpt-4o")
    max_tool_calls = int(config.get("agent", {}).get("max_tool_calls", 20))
    usage_limits = UsageLimits(tool_calls_limit=max_tool_calls)

    callback(AgentEvent("agent_start", {"run_id": run_id, "query": query, "model": model_str}))
    callback(AgentEvent("thinking", {"message": "Analyzing question and planning steps..."}))

    start = time.perf_counter()
    result = None
    success = False
    try:
        result = agent.run_sync(query, deps=deps, usage_limits=usage_limits)
        success = True
    except Exception as e:
        err: BaseException = e
        try:
            _check_api_key_error(e)
        except ValueError as ve:
            err = ve
        if deps.error_collector:
            deps.error_collector.record(
                category="agent",
                severity="error",
                message=str(err),
                details={"exception": type(err).__name__},
                run_id=run_id,
            )
        callback(
            AgentEvent(
                "error",
                {
                    "message": str(err),
                    "step": deps.current_step,
                    "category": "agent",
                },
            )
        )
        callback(AgentEvent("done", {"run_id": run_id, "success": False}))
    finally:
        total_duration_ms = (time.perf_counter() - start) * 1000
        _persist_agent_run(
            run_store, deps, run_id, query, model_str,
            result, success, total_duration_ms,
        )

    if not success:
        return AgentResponse(
            answer="",
            commands_executed=deps.commands_executed,
            total_commands=len(deps.commands_executed),
            total_duration_ms=total_duration_ms,
        )

    answer = str(result.output) if result and result.output is not None else ""
    cache_hits = 0
    if deps.trace_store:
        for c in deps.commands_executed:
            if c.trace_id:
                t = deps.trace_store.get_by_trace_id(c.trace_id)
                if t and t.cache_hits > 0:
                    cache_hits += 1
    callback(
        AgentEvent(
            "answer",
            {
                "answer": answer,
                "total_commands": len(deps.commands_executed),
                "total_duration_ms": total_duration_ms,
                "cache_hits": cache_hits,
            },
        )
    )
    callback(AgentEvent("done", {"run_id": run_id, "success": True}))

    return AgentResponse(
        answer=answer,
        commands_executed=deps.commands_executed,
        total_commands=len(deps.commands_executed),
        total_duration_ms=total_duration_ms,
    )


def run_agent(
    query: str,
    config_path: str | None = None,
    model: str | None = None,
) -> AgentResponse:
    """Run the WikiFS agent on a query. Returns AgentResponse with answer and commands_executed."""
    agent, deps = create_wikifs_agent(config_path=config_path, model=model)
    run_store = getattr(deps.interpreter, "_run_store", None)
    run_id = str(uuid.uuid4())
    deps.run_id = run_id

    config = load_config(config_path)
    max_tool_calls = int(config.get("agent", {}).get("max_tool_calls", 20))
    usage_limits = UsageLimits(tool_calls_limit=max_tool_calls)

    start = time.perf_counter()
    result = None
    success = False
    try:
        result = agent.run_sync(query, deps=deps, usage_limits=usage_limits)
        success = True
    except Exception as e:
        if deps.error_collector:
            deps.error_collector.record(
                category="agent",
                severity="error",
                message=str(e),
                details={"exception": type(e).__name__},
                run_id=run_id,
            )
        _check_api_key_error(e)
        raise
    finally:
        total_duration_ms = (time.perf_counter() - start) * 1000
        model_str = model or config.get("agent", {}).get("default_model")
        _persist_agent_run(
            run_store, deps, run_id, query, model_str,
            result, success, total_duration_ms,
        )

    answer = str(result.output) if result and result.output is not None else ""
    return AgentResponse(
        answer=answer,
        commands_executed=deps.commands_executed,
        total_commands=len(deps.commands_executed),
        total_duration_ms=total_duration_ms,
    )


def _check_api_key_error(exc: BaseException) -> None:
    """Raise helpful error for missing API keys."""
    msg = str(exc).lower()
    if "api_key" in msg or "api key" in msg:
        if "openai" in msg:
            raise ValueError(
                "OpenAI API key not set. Set OPENAI_API_KEY environment variable."
            ) from exc
        if "anthropic" in msg:
            raise ValueError(
                "Anthropic API key not set. Set ANTHROPIC_API_KEY environment variable."
            ) from exc
