#!/usr/bin/env python3
"""Validate a project's terminology.csv and push it to DeepL as a glossary.

Usage:
  glossary.py validate --project projects/<slug>
  glossary.py push --project projects/<slug>

`validate` checks the CSV structure, recomputes IT-variant occurrences over
state/segments.json and writes state/terminology_report.json.
`push` creates a DeepL glossary (source "it" -> target "en") from the variant
pairs and records it in state/deepl.json; it requires a DEEPL_AUTH_KEY. The
endpoint (Free vs Pro) is derived from the key suffix (":fx" -> Free).
"""

from __future__ import annotations

import argparse
import csv
import sys

import requests

import common

HEADER = ["term_it", "variants_it", "term_en", "variants_en", "category",
          "in_claims", "rationale", "status", "flag"]
CATEGORIES = {"part", "process", "material", "parameter", "other"}
IN_CLAIMS_VALUES = {"yes", "no"}
STATUS_VALUES = {"proposed", "locked"}
GLOSSARY_TIMEOUT_S = 60


def _match_key(variant: str) -> str:
    return common.normalize(variant).casefold()


def parse_terminology(path):
    """Parse terminology.csv. Returns (rows, errors, warnings); rows carry the
    stripped fields plus `variants_it`/`variants_en` as lists."""
    if not path.is_file():
        common.die(f"terminology.csv not found: {path}")
    rows: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return rows, [f"empty file: {path}"], warnings
        if header != HEADER:
            errors.append(
                f"bad header: expected {','.join(HEADER)!r}, "
                f"got {','.join(header)!r}"
            )
            return rows, errors, warnings

        seen_term_it: dict[str, int] = {}
        seen_variant_it: dict[str, int] = {}
        seen_variant_en: dict[str, int] = {}
        for record in reader:
            line = reader.line_num
            if not record:
                continue
            if len(record) != len(HEADER):
                errors.append(
                    f"line {line}: expected {len(HEADER)} fields, "
                    f"got {len(record)}"
                )
                continue
            row = dict(zip(HEADER, (field.strip() for field in record)))
            term_it = row["term_it"]
            label = term_it or f"line {line}"

            if not term_it:
                errors.append(f"line {line}: empty term_it")
            elif term_it in seen_term_it:
                errors.append(
                    f"line {line}: duplicate term_it {term_it!r} "
                    f"(first at line {seen_term_it[term_it]})"
                )
            else:
                seen_term_it[term_it] = line
            if not row["term_en"]:
                errors.append(f"line {line}: empty term_en ({label!r})")

            variants_it = [v.strip() for v in row["variants_it"].split("|")]
            variants_en = [v.strip() for v in row["variants_en"].split("|")]
            for side, variants in (("IT", variants_it), ("EN", variants_en)):
                for variant in variants:
                    if not variant:
                        errors.append(
                            f"line {line}: empty {side} variant ({label!r})"
                        )
                    elif "\t" in variant or "\n" in variant:
                        errors.append(
                            f"line {line}: {side} variant {variant!r} contains "
                            "a tab/newline (breaks the TSV glossary format)"
                        )
            if len(variants_it) != len(variants_en):
                errors.append(
                    f"line {line}: variant length mismatch for {label!r}: "
                    f"{len(variants_it)} IT vs {len(variants_en)} EN"
                )
            if term_it and variants_it and variants_it[0] != term_it:
                warnings.append(
                    f"line {line}: first IT variant {variants_it[0]!r} is not "
                    f"term_it {term_it!r} (canonical term must come first)"
                )
            if row["term_en"] and variants_en and variants_en[0] != row["term_en"]:
                warnings.append(
                    f"line {line}: first EN variant {variants_en[0]!r} is not "
                    f"term_en {row['term_en']!r} (canonical term must come first)"
                )

            for variant in variants_it:
                if not variant:
                    continue
                key = _match_key(variant)
                if key in seen_variant_it:
                    errors.append(
                        f"line {line}: IT variant {variant!r} duplicated "
                        f"(also at line {seen_variant_it[key]})"
                    )
                else:
                    seen_variant_it[key] = line
            # EN variants may repeat within one row (two IT synonyms sharing a
            # translation) but never across rows.
            for variant in dict.fromkeys(variants_en):
                if not variant:
                    continue
                key = _match_key(variant)
                if key in seen_variant_en and seen_variant_en[key] != line:
                    errors.append(
                        f"line {line}: EN variant {variant!r} duplicated "
                        f"across rows (also at line {seen_variant_en[key]})"
                    )
                else:
                    seen_variant_en[key] = line

            for field, allowed in (("category", CATEGORIES),
                                   ("in_claims", IN_CLAIMS_VALUES),
                                   ("status", STATUS_VALUES)):
                if row[field] not in allowed:
                    errors.append(
                        f"line {line}: bad {field} {row[field]!r} "
                        f"(allowed: {', '.join(sorted(allowed))})"
                    )

            row["variants_it"] = variants_it
            row["variants_en"] = variants_en
            row["line"] = line
            rows.append(row)
    if not rows and not errors:
        errors.append(f"no terminology rows in {path}")
    return rows, errors, warnings


def compute_report_rows(rows, segments):
    """Recompute IT-variant occurrences over segments.json (normalized,
    case-insensitive substring). Returns (report_rows, warnings)."""
    report_rows = []
    warnings = []
    for row in rows:
        total = 0
        segment_ids: list[str] = []
        in_claims_computed = False
        variant_counts = {variant: 0 for variant in row["variants_it"]}
        for segment in segments:
            hay = _match_key(segment["text_it"])
            hit = False
            for variant in row["variants_it"]:
                count = hay.count(_match_key(variant))
                if count:
                    variant_counts[variant] += count
                    total += count
                    hit = True
            if hit:
                segment_ids.append(segment["id"])
                if segment["kind"] == "claim":
                    in_claims_computed = True
        for variant, count in variant_counts.items():
            if count == 0:
                warnings.append(
                    f"term {row['term_it']!r}: IT variant {variant!r} has zero "
                    "occurrences in segments.json"
                )
        declared = row["in_claims"] == "yes"
        if declared != in_claims_computed:
            warnings.append(
                f"term {row['term_it']!r}: in_claims={row['in_claims']} but "
                f"computed {'yes' if in_claims_computed else 'no'}"
            )
        report_rows.append({
            "term_it": row["term_it"],
            "occurrences_it": total,
            "segments": segment_ids,
            "in_claims_computed": in_claims_computed,
        })
    return report_rows, warnings


def _parse_or_exit(paths):
    rows, errors, warnings = parse_terminology(paths["terminology"])
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            f"terminology.csv invalid: {len(errors)} error(s)", file=sys.stderr
        )
        raise SystemExit(1)
    return rows, warnings


def cmd_validate(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    rows, csv_warnings = _parse_or_exit(paths)

    violations = common.validate_file(paths["segments"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("invalid segments.json — re-run ingest.py")
    segments = common.read_json(paths["segments"])["segments"]

    report_rows, occurrence_warnings = compute_report_rows(rows, segments)
    for warning in occurrence_warnings:
        print(f"WARNING: {warning}")

    report = {"generated_at": common.now_iso(), "rows": report_rows}
    common.write_json(paths["terminology_report"], report)
    violations = common.validate_file(paths["terminology_report"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("validate produced an invalid terminology_report.json (bug)")

    pair_count = sum(len(row["variants_it"]) for row in rows)
    warning_count = len(csv_warnings) + len(occurrence_warnings)
    print(
        f"OK: {len(rows)} terms, {pair_count} variant pairs, "
        f"{warning_count} warning(s)"
    )
    print(f"Report: {paths['terminology_report']}")
    return 0


def build_entries(rows) -> list[str]:
    """One TSV line per (it, en) variant pair, first variants included like the
    rest, exact duplicate pairs removed, order preserved."""
    entries: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for it_variant, en_variant in zip(row["variants_it"], row["variants_en"]):
            if not it_variant or not en_variant:
                common.die(
                    f"empty glossary entry side for term {row['term_it']!r} "
                    "(validate should have caught this)"
                )
            pair = f"{it_variant}\t{en_variant}"
            if pair in seen:
                continue
            seen.add(pair)
            entries.append(pair)
    return entries


def build_glossary_params(name: str, entries: list[str]) -> dict:
    return {
        "name": name,
        "source_lang": "it",
        "target_lang": "en",
        "entries": "\n".join(entries),
        "entries_format": "tsv",
    }


def cmd_push(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    key, api_base = common.load_env_key()
    rows, _ = _parse_or_exit(paths)

    csv_text = paths["terminology"].read_text(encoding="utf-8")
    sha = common.sha256_text(csv_text)
    name = f"patent-{paths['root'].resolve().name}-{sha[:8]}"

    existing = None
    if paths["deepl"].is_file():
        existing = common.read_json(paths["deepl"])
        if existing.get("terminology_sha256") == sha and existing.get("glossary_id"):
            print(
                f"Glossary already pushed for this terminology.csv "
                f"(id {existing['glossary_id']}, "
                f"name {existing['glossary_name']}); nothing to do."
            )
            return 0

    entries = build_entries(rows)
    if not entries:
        common.die("terminology.csv yields no glossary entries")

    try:
        response = requests.post(
            f"{api_base}/v2/glossaries",
            data=build_glossary_params(name, entries),
            headers={"Authorization": f"DeepL-Auth-Key {key}"},
            timeout=GLOSSARY_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        common.die(f"DeepL glossary creation request failed: {exc}")
    if response.status_code == 456:
        common.die("DeepL monthly character quota exceeded (HTTP 456)")
    if response.status_code not in (200, 201):
        common.die(
            f"DeepL glossary creation failed: HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )
    try:
        payload = response.json()
    except ValueError:
        common.die(
            f"DeepL glossary creation: non-JSON response: {response.text[:500]}"
        )
    glossary_id = payload.get("glossary_id")
    if not glossary_id:
        common.die(f"DeepL glossary creation: no glossary_id in response: {payload}")
    entry_count = payload.get("entry_count")
    if isinstance(entry_count, int) and entry_count != len(entries):
        print(
            f"WARNING: DeepL reports {entry_count} entries, {len(entries)} sent"
        )

    # `document` is nullable but must be present (deepl.json schema); carry an
    # existing translation record forward, else write null until translate runs.
    document = None
    if existing is not None and isinstance(existing.get("document"), dict):
        document = existing["document"]
    data = {
        "api_base": api_base,
        "glossary_id": glossary_id,
        "glossary_name": name,
        "terminology_sha256": sha,
        "document": document,
    }
    common.write_json(paths["deepl"], data)
    violations = common.validate_file(paths["deepl"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("push produced an invalid deepl.json (bug)")

    print(f"Created DeepL glossary {name} (id {glossary_id}), {len(entries)} entries")
    print(f"Wrote {paths['deepl']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command, handler in (("validate", cmd_validate), ("push", cmd_push)):
        sub_parser = sub.add_parser(command)
        sub_parser.add_argument(
            "--project", required=True,
            help="project directory, e.g. projects/_fixture",
        )
        sub_parser.set_defaults(handler=handler)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
