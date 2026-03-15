#!/usr/bin/env python3
"""
WikiFS Demo — Navigates Frankfurt → Hessen → Deutschland

Shows: Entity navigation, Properties, Relations, Articles, Search
At end: Trace summary with performance data.
Second run demonstrates cache effect (significantly lower latency).
"""

from __future__ import annotations

import subprocess
import sys
import time


def run(cmd: list[str]) -> tuple[int, str, str]:
    """Run wikifs command. Returns (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "cli"] + cmd,
        capture_output=True,
        text=True,
        cwd=".",
    )
    return result.returncode, result.stdout, result.stderr


def step(step_num: int, description: str, cmd: list[str]) -> None:
    """Execute a demo step: show input, run, show output."""
    print(f"\n--- Step {step_num}: {description} ---")
    print(f"$ wikifs {' '.join(cmd)}")
    exit_code, out, err = run(cmd)
    if err:
        print(err, end="")
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if exit_code != 0:
        print(f"[exit code {exit_code}]")


def main() -> int:
    print("WikiFS Demo — Frankfurt → Hessen → Deutschland")
    print("=" * 50)

    start = time.perf_counter()

    # 1. Discover entity
    step(1, "Discover entity", ["ls", "/wiki/entities/Frankfurt_am_Main/"])

    # 2. Read properties
    step(
        2,
        "Read properties",
        ["cat", "/wiki/entities/Frankfurt_am_Main/properties/population.txt"],
    )
    step(
        2,
        "Read country property",
        ["cat", "/wiki/entities/Frankfurt_am_Main/properties/country.txt"],
    )

    # 3. Read summary
    step(
        3,
        "Read summary",
        ["cat", "/wiki/entities/Frankfurt_am_Main/summary.md"],
    )

    # 4. Navigate relations
    step(
        4,
        "List relations",
        ["ls", "/wiki/entities/Frankfurt_am_Main/relations/"],
    )
    step(
        4,
        "List part_of targets",
        ["ls", "/wiki/entities/Frankfurt_am_Main/relations/part_of/"],
    )

    # 5. Navigate to Hessen
    step(5, "Hessen summary", ["cat", "/wiki/entities/Hessen/summary.md"])
    step(
        5,
        "Hessen country (→ Deutschland)",
        ["ls", "/wiki/entities/Hessen/relations/country/"],
    )

    # 6. Navigate to Deutschland
    step(6, "Deutschland summary", ["cat", "/wiki/entities/Deutschland/summary.md"])

    # 7. Search
    step(7, "Search Goethe", ["search", "Goethe", "--type", "entity", "--limit", "3"])

    # 8. Grep within entity
    step(
        8,
        "Grep Frankfurt in summary",
        ["grep", "Frankfurt", "/wiki/entities/Frankfurt_am_Main/summary.md"],
    )

    # 9. Class navigation
    step(9, "List classes", ["ls", "/wiki/classes/"])
    step(9, "List city class", ["ls", "/wiki/classes/city/"])

    elapsed = time.perf_counter() - start
    print(f"\n--- Total duration: {elapsed:.2f}s ---")

    # 10. Trace summary
    step(10, "Trace stats", ["stats"])

    print("\n" + "=" * 50)
    print("Second run (cache warm) — same commands")
    print("=" * 50)

    start2 = time.perf_counter()
    # Re-run key commands to demonstrate cache effect
    step(11, "Discover entity (cached)", ["ls", "/wiki/entities/Frankfurt_am_Main/"])
    step(
        11,
        "Read properties (cached)",
        ["cat", "/wiki/entities/Frankfurt_am_Main/properties/population.txt"],
    )
    step(11, "Summary (cached)", ["cat", "/wiki/entities/Frankfurt_am_Main/summary.md"])
    step(11, "Search (cached)", ["search", "Goethe", "--type", "entity", "--limit", "3"])
    step(11, "Stats after cache run", ["stats"])
    elapsed2 = time.perf_counter() - start2
    print(f"\n--- Second run duration: {elapsed2:.2f}s ---")
    print(f"Cache effect: first run {elapsed:.2f}s vs second run {elapsed2:.2f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
