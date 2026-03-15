"""CLI entrypoint for WikiFS."""

from __future__ import annotations

import sys

import click

from wikifs import Interpreter, __version__, create_interpreter
from wikifs.cache import Cache, CacheConfig, CacheStats
from wikifs.config import load_config
from wikifs.errors import ErrorStore, RunStore
from wikifs.tracing import TraceStore


def _get_interpreter() -> Interpreter:
    """Create interpreter with config, cache, tracing, backends, router."""
    return create_interpreter()


def _run_interpreter_command(
    command: str,
    path: str,
    flags: list[str] | None = None,
    pattern: str | None = None,
) -> int:
    """Execute command via interpreter. Output to stdout, errors to stderr. Returns exit code."""
    interpreter = _get_interpreter()
    raw = {
        "command": command,
        "path": path,
        "flags": flags or [],
        "pattern": pattern,
    }
    response = interpreter.execute(raw)
    exit_code: int = response.exit_code
    if exit_code == 0:
        if response.output:
            click.echo(response.output)
    else:
        click.echo(response.output, err=True)
    return exit_code


def _get_trace_store() -> TraceStore:
    """Get TraceStore from config."""
    config = load_config()
    db_path = config.get("tracing", {}).get("db_path", "~/.wikifs/traces.db")
    return TraceStore(str(db_path))


def _get_error_store() -> ErrorStore:
    """Get ErrorStore from config."""
    config = load_config()
    db_path = config.get("errors", {}).get("db_path", "~/.wikifs/errors.db")
    return ErrorStore(str(db_path))


def _get_run_store() -> RunStore:
    """Get RunStore from config."""
    config = load_config()
    db_path = config.get("errors", {}).get("db_path", "~/.wikifs/errors.db")
    return RunStore(str(db_path))


@click.group()
@click.version_option(version=__version__, prog_name="wikifs")
def main() -> None:
    """WikiFS — Virtual Filesystem over Wikipedia & Wikidata."""
    pass


@main.command()
@click.argument("path", type=str, required=True)
@click.option("-l", "long_format", is_flag=True, help="Long listing format")
def ls(path: str, long_format: bool) -> None:
    """List directory contents."""
    flags = ["-l"] if long_format else []
    sys.exit(_run_interpreter_command("ls", path, flags=flags))


@main.command()
@click.argument("path", type=str, required=True)
def cat(path: str) -> None:
    """Display file contents."""
    sys.exit(_run_interpreter_command("cat", path))


@main.command()
@click.argument("pattern", type=str, required=True)
@click.argument("path", type=str, required=True)
@click.option("-i", "ignore_case", is_flag=True, help="Ignore case")
@click.option("-c", "count_only", is_flag=True, help="Count matches only")
def grep(pattern: str, path: str, ignore_case: bool, count_only: bool) -> None:
    """Search within files."""
    flags = []
    if ignore_case:
        flags.append("-i")
    if count_only:
        flags.append("-c")
    sys.exit(_run_interpreter_command("grep", path, flags=flags, pattern=pattern))


@main.command()
@click.argument("query", type=str, required=False, default="")
@click.option("--type", "search_type", type=str, default="entity", help="Search type (entity)")
@click.option("--limit", type=int, default=None, help="Max results")
@click.option("--sparql", type=str, default=None, help="SPARQL query")
def search(
    query: str,
    search_type: str,
    limit: int | None,
    sparql: str | None,
) -> None:
    """Search across entities or run SPARQL query."""
    flags: list[str] = ["--type", search_type]
    if limit is not None:
        flags.extend(["--limit", str(limit)])
    if sparql:
        flags.extend(["--sparql", sparql])
        path = "/wiki/sparql/result.csv"
        pattern = None
    else:
        path = "/wiki/search"
        pattern = query
    sys.exit(_run_interpreter_command("search", path, flags=flags, pattern=pattern))


@main.command()
def stats() -> None:
    """Show statistics: Total Commands, Avg Latency, Cache Hit Rate, Commands by Type."""
    store = _get_trace_store()
    s = store.stats()
    if s.count == 0:
        click.echo("No traces recorded yet.")
        return
    click.echo(f"Total Commands:    {s.count}")
    click.echo(f"Avg Duration:      {s.avg_duration_ms:.1f} ms")
    click.echo(f"P50 Duration:      {s.p50_duration_ms:.1f} ms")
    click.echo(f"P95 Duration:      {s.p95_duration_ms:.1f} ms")
    click.echo(f"Max Duration:      {s.max_duration_ms:.1f} ms")
    click.echo(f"Cache Hit Rate:    {s.cache_hit_rate * 100:.1f}%")
    if s.commands_by_type:
        click.echo("Commands by Type:")
        for cmd, cnt in sorted(s.commands_by_type.items()):
            click.echo(f"  {cmd}: {cnt}")


@main.group(invoke_without_command=True)
@click.option(
    "--slow",
    "min_duration_ms",
    type=float,
    default=None,
    help="Show traces slower than MS",
)
@click.option(
    "--path",
    "path_pattern",
    type=str,
    default=None,
    help="Filter by path pattern (SQL LIKE)",
)
@click.option("--command", "cmd_filter", type=str, default=None, help="Filter by command type")
@click.option("--limit", type=int, default=50, help="Max traces to show")
@click.pass_context
def traces(
    ctx: click.Context,
    min_duration_ms: float | None,
    path_pattern: str | None,
    cmd_filter: str | None,
    limit: int,
) -> None:
    """Show trace data."""
    if ctx.invoked_subcommand is not None:
        return
    store = _get_trace_store()
    result = store.query(
        min_duration_ms=min_duration_ms,
        command=cmd_filter,
        path_pattern=path_pattern,
        limit=limit,
    )
    if not result:
        click.echo("No traces found.")
        return
    for t in result:
        phases_str = ", ".join(f"{p.phase}={p.duration_ms:.0f}ms" for p in t.phases)
        click.echo(
            f"{t.timestamp} | {t.command} {t.path} | {t.total_duration_ms:.0f}ms | "
            f"exit={t.exit_code} | {phases_str}"
        )


@traces.command("clear")
@click.option(
    "--older-than",
    type=int,
    default=None,
    help="Delete traces older than N days (0=all)",
)
def traces_clear(older_than: int | None) -> None:
    """Clear trace data (housekeeping)."""
    store = _get_trace_store()
    deleted = store.clear(older_than_days=older_than)
    click.echo(f"Deleted {deleted} trace(s).")


@main.group(invoke_without_command=True)
@click.option(
    "--since",
    type=str,
    default=None,
    help="Filter by time (e.g. 24h, 7d)",
)
@click.option(
    "--category",
    type=str,
    default=None,
    help="Filter by category (api, cache, parsing, routing, agent, timeout)",
)
@click.option(
    "--unresolved",
    "unresolved_only",
    is_flag=True,
    help="Show only unresolved errors",
)
@click.option(
    "--run-id",
    type=str,
    default=None,
    help="Filter by run ID",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.option("--limit", type=int, default=100, help="Max errors to show")
@click.pass_context
def errors(
    ctx: click.Context,
    since: str | None,
    category: str | None,
    unresolved_only: bool,
    run_id: str | None,
    fmt: str,
    limit: int,
) -> None:
    """Show or export error data."""
    if ctx.invoked_subcommand is not None:
        return
    store = _get_error_store()
    entries = store.query(
        since=since,
        category=category,
        unresolved_only=unresolved_only,
        run_id=run_id,
        limit=limit,
    )
    if fmt == "json":
        import json

        out = [
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
        click.echo(json.dumps(out, indent=2))
    else:
        for e in entries:
            resolved = " [resolved]" if e.resolved else ""
            click.echo(
                f"{e.timestamp} | {e.category}/{e.severity}{resolved} | "
                f"{e.message} | {e.error_id}"
            )


@errors.command("summary")
def errors_summary() -> None:
    """Show error aggregation by category and severity."""
    store = _get_error_store()
    summary = store.summary()
    if not summary:
        click.echo("No errors recorded.")
        return
    for cat, sev_counts in sorted(summary.items()):
        for sev, cnt in sorted(sev_counts.items()):
            click.echo(f"  {cat}/{sev}: {cnt}")


@main.group(invoke_without_command=True)
@click.option(
    "--id",
    "run_id",
    type=str,
    default=None,
    help="Show single run by ID",
)
@click.option(
    "--failed",
    "failed_only",
    is_flag=True,
    help="Show only failed runs",
)
@click.option(
    "--type",
    "run_type",
    type=click.Choice(["cli", "agent"]),
    default=None,
    help="Filter by run type",
)
@click.option(
    "--since",
    type=str,
    default=None,
    help="Filter by time (e.g. 24h, 7d)",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.option("--full", "full_report", is_flag=True, help="Include traces and errors (with --id)")
@click.option("--limit", type=int, default=50, help="Max runs to show")
@click.pass_context
def runs(
    ctx: click.Context,
    run_id: str | None,
    failed_only: bool,
    run_type: str | None,
    since: str | None,
    fmt: str,
    full_report: bool,
    limit: int,
) -> None:
    """Show or export run data."""
    if ctx.invoked_subcommand is not None:
        return
    if run_id:
        _show_single_run(run_id, fmt, full_report)
        return
    store = _get_run_store()
    entries = store.query(
        failed_only=failed_only,
        run_type=run_type,
        since=since,
        limit=limit,
    )
    if fmt == "json":
        import json

        out = [
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
        click.echo(json.dumps(out, indent=2))
    else:
        for r in entries:
            status = "success" if r.success else "failed"
            click.echo(
                f"{r.timestamp} | {r.run_id} | {r.type} | {status} | "
                f"{r.duration_ms:.0f}ms | {r.commands_count} cmds"
            )


def _show_single_run(run_id: str, fmt: str, full_report: bool) -> None:
    """Show a single run by ID."""
    import json

    run_store = _get_run_store()
    error_store = _get_error_store()
    trace_store = _get_trace_store()

    run = run_store.get_by_id(run_id)
    if run is None:
        click.echo(f"Run not found: {run_id}", err=True)
        sys.exit(1)

    report: dict[str, object]
    if full_report:
        traces = []
        for tid in run.trace_ids:
            t = trace_store.get_by_trace_id(tid)
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
            e = error_store.get_by_id(eid)
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
        report = {
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
    else:
        report = {
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

    if fmt == "json":
        click.echo(json.dumps(report, indent=2))
    else:
        for k, v in report.items():
            click.echo(f"  {k}: {v}")


def _get_cache() -> Cache:
    """Get Cache instance from config."""
    config = load_config()
    cache_cfg = config.get("cache", {})
    cfg = CacheConfig(
        l1_max_size=int(cache_cfg.get("l1_max_size", 256)),
        l1_ttl_seconds=int(cache_cfg.get("l1_ttl_seconds", 3600)),
        l2_ttl_seconds=int(cache_cfg.get("l2_ttl_seconds", 86400)),
        l2_db_path=str(cache_cfg.get("l2_db_path", "~/.wikifs/cache.db")),
    )
    return Cache(cfg)


@main.group(invoke_without_command=True)
@click.pass_context
def cache(ctx: click.Context) -> None:
    """Manage cache (L1 + L2)."""
    if ctx.invoked_subcommand is not None:
        return
    # Default: show stats
    cache_obj = _get_cache()
    s = cache_obj.stats()
    _print_cache_stats(s)


def _print_cache_stats(s: CacheStats) -> None:
    """Print cache statistics."""
    total = s.l1_hits + s.l1_misses + s.l2_hits + s.l2_misses
    click.echo(f"L1 Hits:     {s.l1_hits}")
    click.echo(f"L1 Misses:   {s.l1_misses}")
    click.echo(f"L2 Hits:     {s.l2_hits}")
    click.echo(f"L2 Misses:   {s.l2_misses}")
    click.echo(f"Hit Rate:    {s.hit_rate * 100:.1f}%")
    click.echo(f"L1 Size:     {s.l1_size}")
    click.echo(f"L2 Size:     {s.l2_size}")
    if total > 0:
        click.echo(f"Total Reqs:  {total}")


@cache.command("stats")
def cache_stats() -> None:
    """Show cache statistics: Hit Rate, L1/L2 Size, Entry Count."""
    cache_obj = _get_cache()
    s = cache_obj.stats()
    _print_cache_stats(s)


@cache.command("clear")
def cache_clear() -> None:
    """Clear both cache levels (L1 + L2)."""
    cache_obj = _get_cache()
    deleted = cache_obj.clear()
    click.echo(f"Cleared {deleted} cache entry(ies).")


@main.command()
@click.argument("query", type=str, required=True)
@click.option(
    "--model",
    type=str,
    default=None,
    help="Model override (e.g. openai:gpt-4o, anthropic:claude-sonnet)",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=str),
    default=None,
    help="Path to config.toml",
)
def agent(query: str, model: str | None, config_path: str | None) -> None:
    """Run the WikiFS AI agent on a natural language query."""
    try:
        from wikifs.agent import run_agent

        result = run_agent(query=query, config_path=config_path, model=model)
        click.echo(result.answer)
        if result.commands_executed:
            click.echo("\n--- Commands executed ---", err=True)
            for cmd in result.commands_executed:
                click.echo(f"  {cmd.command} {cmd.path} ({cmd.timing_ms:.0f}ms)", err=True)
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Port to bind the HTTP server",
)
def serve(port: int) -> None:
    """Start the FastAPI HTTP server."""
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
