#!/usr/bin/env python3
"""Dependency-free statement-line coverage check for the lab package."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "reliability_lab"
MINIMUM_PERCENT = 80.0


def statement_lines() -> set[tuple[str, int]]:
    lines: set[tuple[str, int]] = set()
    for path in SOURCE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.stmt) and hasattr(node, "lineno"):
                lines.add((str(path.resolve()), node.lineno))
    return lines


def main() -> int:
    executed: set[tuple[str, int]] = set()

    def trace(frame, event, arg):
        del arg
        if event == "line":
            filename = str(Path(frame.f_code.co_filename).resolve())
            if filename.startswith(str(SOURCE_ROOT.resolve())):
                executed.add((filename, frame.f_lineno))
        return trace

    sys.settrace(trace)
    try:
        # Discovery imports the package and therefore belongs inside the trace.
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        sys.settrace(None)

    statements = statement_lines()
    covered = statements & executed
    percent = len(covered) / len(statements) * 100 if statements else 100.0
    print(f"Statement-line coverage: {len(covered)}/{len(statements)} ({percent:.1f}%)")
    if not result.wasSuccessful():
        return 1
    if percent < MINIMUM_PERCENT:
        print(f"Coverage gate failed: {percent:.1f}% < {MINIMUM_PERCENT:.1f}%")
        return 1
    print(f"Coverage gate passed: {percent:.1f}% >= {MINIMUM_PERCENT:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
