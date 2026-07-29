#!/usr/bin/env python3
"""Run the whole offline pipeline on the fixtures and assert the outcome.

This is the repo's smoke test: one command that answers "does the pipeline
still work". It needs no DEEPL_AUTH_KEY and no network — the three DeepL stages
(glossary push, translate, back-translate) are not exercised here and have to be
verified against the live API separately.

Two assertions, both from CONTRACTS.md:
  - on the clean fixture, every check has its expected status. The one failure
    and the one warning are deliberate source quirks (see fixture_spec.md), so
    an all-pass run means the checks stopped working.
  - on the seeded-defect fixture, each of the six mutations is caught by the
    check the contract assigns to it.

Usage:
    smoke.py [--keep-going]

Run from the repo root. Exit 0 means clean.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(".claude/skills/patent-translate/scripts")
FIXTURE = "projects/_fixture"
FIXTURE_BAD = "projects/_fixture_bad"

# Clean fixture: exact status of every check. claim_support fails and
# numeral_term_consistency warns by design — both are seeded in the Italian.
EXPECTED_CLEAN = {
    "paragraph_parity": "pass",
    "numerals_per_segment": "pass",
    "numeral_term_consistency": "warn",
    "numbers_units": "pass",
    "claims_graph": "pass",
    "one_sentence_per_claim": "pass",
    "claim_support": "fail",
    "glossary_adherence": "pass",
    "antecedent_basis": "pass",
    "abstract_length": "pass",
    "residue": "pass",
    "structure": "pass",
    "decimal_comma_audit": "pass",
}

# Seeded-defect fixture: the six outcomes CONTRACTS.md requires. Other checks
# may also react (a term swap moves more than one check) and that is fine.
EXPECTED_BAD = {
    "numerals_per_segment": "fail",
    "numbers_units": "fail",
    "claim_support": "fail",
    "claims_graph": "fail",
    "one_sentence_per_claim": "fail",
    "antecedent_basis": "warn",
}

DELIVERABLES = (
    "filing_en.docx",
    "side_by_side.docx",
    "ESCALATIONS.md",
    "audit_numbers.csv",
    "terminology.csv",
)


class Failure(Exception):
    pass


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"\n$ {' '.join(cmd[1:])}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise Failure(f"{script} exited {result.returncode}")


def statuses(project: str) -> dict[str, str]:
    path = Path(project) / "state" / "checks.json"
    if not path.is_file():
        raise Failure(f"{path} not written")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["check"]: r["status"] for r in data["results"]}


def details(project: str, check: str) -> list[str]:
    path = Path(project) / "state" / "checks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for result in data["results"]:
        if result["check"] == check:
            return [f["detail"] for f in result["failures"]]
    return []


def assert_statuses(project: str, expected: dict[str, str], label: str) -> None:
    actual = statuses(project)
    problems = []
    for check, want in expected.items():
        got = actual.get(check)
        if got != want:
            problems.append(f"  {check}: expected {want}, got {got}")
    if problems:
        raise Failure(f"{label} check statuses differ:\n" + "\n".join(problems))
    print(f"OK: {label} — {len(expected)} check status(es) as expected")


def assert_deliverables() -> None:
    missing = [
        name for name in DELIVERABLES
        if not (Path(FIXTURE) / "out" / name).is_file()
    ]
    if missing:
        raise Failure(f"missing deliverables in {FIXTURE}/out: {', '.join(missing)}")
    print(f"OK: {len(DELIVERABLES)} deliverables written to {FIXTURE}/out")


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline smoke test of the pipeline.")
    ap.add_argument(
        "--keep-going", action="store_true",
        help="report every failed assertion instead of stopping at the first",
    )
    args = ap.parse_args()

    if not SCRIPTS.is_dir():
        print(f"ERROR: {SCRIPTS} not found — run from the repo root", file=sys.stderr)
        return 2

    failures: list[str] = []

    def step(fn, *fn_args) -> None:
        try:
            fn(*fn_args)
        except Failure as exc:
            if not args.keep_going:
                raise
            failures.append(str(exc))

    try:
        print("=" * 70)
        print("CLEAN FIXTURE")
        print("=" * 70)
        run("dev/make_fixture.py")
        run("ingest.py", "--project", FIXTURE)
        run("dev/make_fixture_en.py", "--project", FIXTURE)
        run("validate_state.py", "--project", FIXTURE)
        run("glossary.py", "validate", "--project", FIXTURE)
        run("checks.py", "run", "--project", FIXTURE)
        step(assert_statuses, FIXTURE, EXPECTED_CLEAN, "clean fixture")
        run("assemble.py", "run", "--project", FIXTURE)
        step(assert_deliverables)

        print()
        print("=" * 70)
        print("SEEDED-DEFECT FIXTURE")
        print("=" * 70)
        run("dev/make_fixture_bad.py")
        run("checks.py", "run", "--project", FIXTURE_BAD)
        step(assert_statuses, FIXTURE_BAD, EXPECTED_BAD, "seeded-defect fixture")

        def assert_claim5_named() -> None:
            found = details(FIXTURE_BAD, "antecedent_basis")
            if not any("claim 5" in d for d in found):
                raise Failure(
                    "antecedent_basis warned but did not name claim 5: " + str(found)
                )
            print("OK: antecedent_basis names claim 5")

        step(assert_claim5_named)
    except Failure as exc:
        print(f"\nSMOKE FAILED: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("\nSMOKE FAILED:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print("\n" + "=" * 70)
    print("SMOKE OK — pipeline runs and the checks catch every seeded defect.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
