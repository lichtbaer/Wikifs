"""Response formatter — consistent output formatting for WikiFS."""

from __future__ import annotations

from collections.abc import Sequence


def format_directory_listing(
    entries: Sequence[tuple[str, str | None]],
    detailed: bool = False,
) -> str:
    """Format directory listing. Entries: (name, detail) or (name, None).
    detailed=True: show size/cache-status like ls -l."""
    if not entries:
        return ""
    lines: list[str] = []
    for name, detail in sorted(entries, key=lambda x: x[0].lower()):
        if detailed and detail:
            lines.append(f"{name}\t{detail}")
        else:
            lines.append(name)
    return "\n".join(lines)


def format_file_content(content: str, filename: str) -> str:
    """Format file content for display (no header, just content)."""
    return content


def format_search_results(
    results: list[tuple[str, str, str]],
) -> str:
    """Format search results. Each tuple: (wikipedia_title, entity_id, description)."""
    if not results:
        return ""
    lines: list[str] = []
    for title, entity_id, description in results:
        desc = (description or "")[:60]
        if len(description or "") > 60:
            desc += "..."
        lines.append(f"{title}\t{entity_id}\t{desc}")
    return "\n".join(lines)


def format_error(
    message: str,
    error_type: str,
    suggestions: list[str] | None = None,
) -> str:
    """Format error message with optional suggestions."""
    out = message
    if suggestions:
        out += "\nSuggestions: " + ", ".join(suggestions)
    return out


def format_sparql_csv(bindings: list[dict[str, str]]) -> str:
    """Format SPARQL bindings as CSV."""
    if not bindings:
        return ""
    headers = list(bindings[0].keys())
    lines = [",".join(headers)]
    for row in bindings:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))
    return "\n".join(lines)
