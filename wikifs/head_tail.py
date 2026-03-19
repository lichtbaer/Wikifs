"""Line-based head/tail slicing for text output (articles, properties, search, …)."""

from __future__ import annotations

# Upper bound to avoid excessive memory use on accidental huge -n
MAX_LINES = 100_000
DEFAULT_LINE_COUNT = 10


def parse_lines_flag(flags: list[str], default: int = DEFAULT_LINE_COUNT) -> tuple[int, str | None]:
    """Parse -n / --lines (last wins). Returns (line_count, error_message)."""
    n = default
    i = 0
    while i < len(flags):
        f = flags[i]
        if f in ("-n", "--lines"):
            if i + 1 >= len(flags):
                return n, f"Missing value for {f}"
            try:
                v = int(flags[i + 1])
            except ValueError:
                return default, f"Invalid integer for {f}: {flags[i + 1]!r}"
            if v < 0:
                return n, f"Line count must be non-negative: {v}"
            if v > MAX_LINES:
                return n, f"Line count exceeds maximum ({MAX_LINES})"
            n = v
            i += 2
            continue
        i += 1
    return n, None


def slice_head(text: str, n: int) -> str:
    """First n lines (fewer if shorter)."""
    if n == 0:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[:n])


def slice_tail(text: str, n: int) -> str:
    """Last n lines (fewer if shorter)."""
    if n == 0:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def apply_head_tail(text: str, command: str, flags: list[str]) -> tuple[str, str | None]:
    """Apply head/tail line window; cat leaves text unchanged."""
    if command == "cat":
        return text, None
    n, err = parse_lines_flag(flags)
    if err is not None:
        return "", err
    if command == "head":
        return slice_head(text, n), None
    if command == "tail":
        return slice_tail(text, n), None
    return text, None
