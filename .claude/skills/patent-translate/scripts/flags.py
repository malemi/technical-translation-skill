#!/usr/bin/env python3
"""Manage review flags in <project>/state/flags.json.

Usage:
  flags.py add --project P --class TERM --segment C-01 --issue "..."
               [--text-it ...] [--text-en ...] [--option ...]...
  flags.py resolve --project P --key a1b2c3d4e5f6 --resolution "..."
  flags.py list --project P [--open] [--class X]

Flags are content-keyed: key = first 12 hex chars of
sha1("class|segment_id|issue") after lowercasing and whitespace collapsing.
Adding an existing key changes nothing (dedup); resolving sets
status/resolution. checks.py imports load_flags/add_flag/save_flags directly
instead of shelling out.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import common

FLAG_CLASSES = ("AMBIGUITY", "TERM", "CONVENTION", "CLAIM-DEFECT", "MECH")


# --------------------------------------------------------------------------
# importable API (used by checks.py)


def flag_key(flag_class: str, segment_id: str | None, issue: str) -> str:
    """Deterministic dedup key per CONTRACTS.md: sha1 of the normalized,
    lowercased "class|segment_id|issue" string, first 12 hex chars."""
    material = common.normalize(f"{flag_class}|{segment_id or ''}|{issue}").lower()
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


def load_flags(path) -> dict:
    """Read flags.json, or return an empty document if the file does not
    exist yet (a project legitimately starts with no flags)."""
    path = Path(path)
    if not path.is_file():
        return {"flags": []}
    doc = common.read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("flags"), list):
        common.die(f"malformed flags file (expected {{'flags': [...]}}): {path}")
    return doc


def save_flags(path, doc) -> None:
    """Write flags.json and re-validate it against the schema (fail loud on
    any bug that produced an invalid document)."""
    common.write_json(path, doc)
    violations = common.validate_file(path)
    if violations:
        for violation in violations:
            print(f"FAIL {violation}")
        common.die(f"wrote an invalid flags file (bug): {path}")


def add_flag(doc, *, flag_class: str, issue: str, segment_id: str | None = None,
             check: str | None = None, text_it: str | None = None,
             text_en: str | None = None, options=None,
             created_by: str = "model") -> tuple[dict, bool]:
    """Add a flag to an in-memory flags document with dedup.

    Returns (flag, created): created is False when a flag with the same key
    already exists, in which case the existing flag is returned untouched.
    """
    if flag_class not in FLAG_CLASSES:
        common.die(f"invalid flag class {flag_class!r} "
                   f"(allowed: {', '.join(FLAG_CLASSES)})")
    if created_by not in ("model", "checks"):
        common.die(f"invalid created_by {created_by!r} (allowed: model, checks)")
    if not issue or not issue.strip():
        common.die("flag issue must be a non-empty string")
    key = flag_key(flag_class, segment_id, issue)
    for existing in doc["flags"]:
        if existing["key"] == key:
            return existing, False
    flag = {
        "key": key,
        "class": flag_class,
        "segment_id": segment_id,
        "check": check,
        "text_it": text_it,
        "text_en": text_en,
        "issue": issue,
        "options": list(options or []),
        "status": "open",
        "resolution": None,
        "created_by": created_by,
        "created_at": common.now_iso(),
    }
    doc["flags"].append(flag)
    return flag, True


def resolve_flag(doc, key: str, resolution: str) -> dict | None:
    """Mark the flag with `key` resolved; returns it, or None if not found."""
    if not resolution or not resolution.strip():
        common.die("resolution must be a non-empty string")
    for flag in doc["flags"]:
        if flag["key"] == key:
            flag["status"] = "resolved"
            flag["resolution"] = resolution
            return flag
    return None


# --------------------------------------------------------------------------
# CLI


def cmd_add(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    doc = load_flags(paths["flags"])
    flag, created = add_flag(
        doc,
        flag_class=args.flag_class,
        issue=args.issue,
        segment_id=args.segment,
        text_it=args.text_it,
        text_en=args.text_en,
        options=args.option,
        created_by="model",
    )
    if created:
        save_flags(paths["flags"], doc)
        print(f"added flag {flag['key']} ({flag['class']}, "
              f"segment {flag['segment_id'] or '-'}) -> {paths['flags']}")
    else:
        print(f"duplicate: flag {flag['key']} already present "
              f"(status {flag['status']}); nothing changed")
    return 0


def cmd_resolve(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    if not Path(paths["flags"]).is_file():
        common.die(f"no flags file to resolve in: {paths['flags']}")
    doc = load_flags(paths["flags"])
    flag = resolve_flag(doc, args.key, args.resolution)
    if flag is None:
        common.die(f"no flag with key {args.key} in {paths['flags']}")
    save_flags(paths["flags"], doc)
    print(f"resolved flag {flag['key']} ({flag['class']}, "
          f"segment {flag['segment_id'] or '-'})")
    return 0


def _truncate(text: str, width: int) -> str:
    text = common.normalize(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def cmd_list(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    doc = load_flags(paths["flags"])
    flags = doc["flags"]
    if args.open:
        flags = [f for f in flags if f["status"] == "open"]
    if args.flag_class:
        flags = [f for f in flags if f["class"] == args.flag_class]
    header = (f"{'KEY':<12}  {'CLASS':<12}  {'SEGMENT':<8}  {'STATUS':<8}  "
              f"{'BY':<6}  ISSUE")
    print(header)
    print("-" * len(header))
    for flag in flags:
        print(f"{flag['key']:<12}  {flag['class']:<12}  "
              f"{(flag['segment_id'] or '-'):<8}  {flag['status']:<8}  "
              f"{flag['created_by']:<6}  {_truncate(flag['issue'], 70)}")
    print(f"{len(flags)} flag(s) shown "
          f"({len(doc['flags'])} total in {paths['flags']})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a flag (dedup by content key)")
    p_add.add_argument("--project", required=True)
    p_add.add_argument("--class", dest="flag_class", required=True,
                       choices=FLAG_CLASSES)
    p_add.add_argument("--segment",
                       help="segment id the flag is about, e.g. C-01; omit for a "
                            "document-wide flag (segment_id is nullable in the schema, "
                            "and checks.py already writes flags without one)")
    p_add.add_argument("--issue", required=True)
    p_add.add_argument("--text-it", dest="text_it")
    p_add.add_argument("--text-en", dest="text_en")
    p_add.add_argument("--option", action="append", default=[],
                       help="candidate resolution (repeatable)")
    p_add.set_defaults(func=cmd_add)

    p_resolve = sub.add_parser("resolve", help="resolve a flag by key")
    p_resolve.add_argument("--project", required=True)
    p_resolve.add_argument("--key", required=True)
    p_resolve.add_argument("--resolution", required=True)
    p_resolve.set_defaults(func=cmd_resolve)

    p_list = sub.add_parser("list", help="print a table of flags")
    p_list.add_argument("--project", required=True)
    p_list.add_argument("--open", action="store_true",
                        help="only flags with status open")
    p_list.add_argument("--class", dest="flag_class", choices=FLAG_CLASSES,
                        help="only flags of this class")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
