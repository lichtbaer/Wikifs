"""CLI entrypoint for WikiFS."""

from __future__ import annotations

import click

from wikifs import __version__
from wikifs.config import load_config
from wikifs.tracing import TraceStore


def _get_trace_store() -> TraceStore:
    """Get TraceStore from config."""
    config = load_config()
    db_path = config.get("tracing", {}).get("db_path", "~/.wikifs/traces.db")
    return TraceStore(str(db_path))


@click.group()
@click.version_option(version=__version__, prog_name="wikifs")
def main() -> None:
    """WikiFS — Virtual Filesystem over Wikipedia & Wikidata."""
    pass


@main.command()
def ls() -> None:
    """List directory contents."""
    click.echo("Not implemented yet")


@main.command()
def cat() -> None:
    """Display file contents."""
    click.echo("Not implemented yet")


@main.command()
def grep() -> None:
    """Search within files."""
    click.echo("Not implemented yet")


@main.command()
def search() -> None:
    """Search across entities."""
    click.echo("Not implemented yet")


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


@main.command()
def cache() -> None:
    """Manage cache."""
    click.echo("Not implemented yet")


if __name__ == "__main__":
    main()
