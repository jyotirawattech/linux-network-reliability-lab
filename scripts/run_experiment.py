#!/usr/bin/env python3
"""Run the reliability experiment and persist machine-readable evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from reliability_lab import run_experiment


def main() -> int:
    result = run_experiment()
    output = Path(__file__).resolve().parents[1] / "docs" / "results" / "latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"\nSaved measured evidence to {output}")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
