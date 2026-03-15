"""CLI entrypoint for WikiFS."""

from __future__ import annotations

import click

from wikifs import __version__


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
    """Show statistics."""
    click.echo("Not implemented yet")


@main.command()
def traces() -> None:
    """Show trace data."""
    click.echo("Not implemented yet")


@main.command()
def cache() -> None:
    """Manage cache."""
    click.echo("Not implemented yet")


if __name__ == "__main__":
    main()
