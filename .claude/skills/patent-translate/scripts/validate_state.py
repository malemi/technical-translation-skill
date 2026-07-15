#!/usr/bin/env python3
"""Validate a project's state JSON files against the schemas in common.py.

Usage: validate_state.py --project projects/<slug> [--file segments.json]
Validates all present state files, or the single named one. Prints every
violation and exits 1 if any; prints OK and exits 0 otherwise.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import common


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True,
                        help="project directory, e.g. projects/_fixture")
    parser.add_argument("--file",
                        help="single state file name to validate, e.g. segments.json")
    args = parser.parse_args()

    root = Path(args.project)
    if not root.is_dir():
        common.die(f"project directory not found: {root}")
    state_dir = root / "state"

    if args.file:
        if args.file not in common.SCHEMAS:
            known = ", ".join(common.SCHEMAS)
            common.die(f"unknown state file name: {args.file} (known: {known})")
        if not (state_dir / args.file).is_file():
            common.die(f"state file not found: {state_dir / args.file}")
        names = [args.file]
    else:
        names = [n for n in common.SCHEMAS if (state_dir / n).is_file()]
        if not names:
            print(f"no state files present in {state_dir}; nothing to validate")
            return 0

    violations: list[str] = []
    for name in names:
        violations.extend(common.validate_file(state_dir / name))

    for violation in violations:
        print(f"FAIL {violation}")
    if violations:
        print(f"{len(violations)} violation(s) across {len(names)} file(s)")
        return 1
    print(f"OK: {len(names)} state file(s) valid: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
