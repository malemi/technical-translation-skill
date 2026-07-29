#!/usr/bin/env python3
"""Apply reviewed English text to translations.json and claims_en.json.

SKILL.md step 4 has the model set `text_en_final` with a reasoned `edits`
entry, and step 5 author the claims. Doing that by hand on a large state file
is error-prone, so this script is the single writer: it applies a batch of
revisions, records provenance for every one of them, and is idempotent —
re-applying the same text changes nothing and reports it as unchanged.

Input is a JSON file:

    {
      "title":  {"text_en": "...", "reason": "..."},
      "pairs":  [{"id": "D-0007", "text_en": "...", "reason": "..."}],
      "claims": [{"id": "C-01", "parts_en": ["...", "..."], "reason": "..."}]
    }

Every section is optional. `reason` is required on each entry — provenance is
the point of the tool. Claim `text_en` is always recomputed as parts joined
with newline, never supplied directly.

Usage:
    set_final.py --project P --input revisions.json [--dry-run]

Run from the repo root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import die, now_iso, project_paths, read_json, validate_file, write_json


def load_revisions(path: Path) -> dict:
    data = read_json(path)
    if not isinstance(data, dict):
        die(f"{path}: expected a JSON object at the top level")
    for section in ("pairs", "claims"):
        for i, entry in enumerate(data.get(section, [])):
            if not isinstance(entry, dict):
                die(f"{path}: {section}[{i}] is not an object")
            if not entry.get("id"):
                die(f"{path}: {section}[{i}] has no id")
            if not entry.get("reason"):
                die(f"{path}: {section}[{i}] ({entry['id']}) has no reason")
    title = data.get("title")
    if title is not None:
        if not isinstance(title, dict) or "text_en" not in title:
            die(f"{path}: title must be an object with text_en")
        if not title.get("reason"):
            die(f"{path}: title has no reason")
    return data


def apply_title(translations: dict, title: dict, stamp: str) -> str | None:
    new = title["text_en"]
    old = translations["title"].get("text_en")
    if old == new:
        return None
    translations["title"]["text_en"] = new
    translations["title"].setdefault("edits", []).append(
        {"reason": title["reason"], "before": old, "after": new, "at": stamp}
    )
    return f"title: {'set' if old is None else 'revised'}"


def apply_pairs(translations: dict, entries: list, stamp: str) -> tuple[list, list]:
    by_id = {p["id"]: p for p in translations["pairs"]}
    changed, unchanged = [], []
    for entry in entries:
        pair = by_id.get(entry["id"])
        if pair is None:
            die(f"pair {entry['id']} not found in translations.json")
        new = entry["text_en"]
        old = pair["text_en_final"]
        current = old if old is not None else pair["text_en_deepl"]
        if current == new:
            unchanged.append(entry["id"])
            continue
        pair["text_en_final"] = new
        pair["edits"].append(
            {"reason": entry["reason"], "before": current, "after": new, "at": stamp}
        )
        changed.append(entry["id"])
    return changed, unchanged


def apply_claims(claims_doc: dict, entries: list, stamp: str) -> tuple[list, list]:
    by_id = {c["id"]: c for c in claims_doc["claims"]}
    changed, unchanged = [], []
    for entry in entries:
        claim = by_id.get(entry["id"])
        if claim is None:
            die(f"claim {entry['id']} not found in claims_en.json")
        parts = entry.get("parts_en")
        if not isinstance(parts, list) or not parts or not all(
            isinstance(p, str) for p in parts
        ):
            die(f"claim {entry['id']}: parts_en must be a non-empty list of strings")
        # text_en is a display string: it may carry a leading claim-number prefix
        # that parts_en does not, and projects differ on whether the parts are
        # joined with a newline or a space. Derive both from what this claim
        # already uses rather than imposing one and silently dropping content.
        old_text = claim["text_en"]
        prefix = separator = None
        for candidate in ("\n", " "):
            old_joined = candidate.join(claim["parts_en"])
            if old_text.endswith(old_joined):
                prefix = old_text[: len(old_text) - len(old_joined)]
                separator = candidate
                break
        if separator is None:
            die(
                f"claim {entry['id']}: text_en is not its parts_en joined by a newline "
                "or a space, with or without a leading prefix, so the revision cannot "
                "be applied without losing content. Fix the claim by hand."
            )
        new_text = prefix + separator.join(parts)
        if claim["text_en"] == new_text:
            unchanged.append(entry["id"])
            continue
        # `edits` is an additive key: the validator allows extra keys, and claim
        # revisions need the same provenance trail the pairs already have.
        claim.setdefault("edits", []).append(
            {
                "reason": entry["reason"],
                "before": claim["text_en"],
                "after": new_text,
                "at": stamp,
            }
        )
        claim["parts_en"] = parts
        claim["text_en"] = new_text
        claim["authored_at"] = stamp
        changed.append(entry["id"])
    return changed, unchanged


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply reviewed English to project state.")
    ap.add_argument("--project", required=True)
    ap.add_argument("--input", required=True, help="revisions JSON file")
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    args = ap.parse_args()

    paths = project_paths(args.project, need_source=False)
    revisions = load_revisions(Path(args.input))
    stamp = now_iso()

    report: list[str] = []
    touched_translations = False
    touched_claims = False

    translations = None
    if revisions.get("title") is not None or revisions.get("pairs"):
        translations = read_json(paths["translations"])
        if revisions.get("title") is not None:
            line = apply_title(translations, revisions["title"], stamp)
            if line:
                report.append(line)
                touched_translations = True
        if revisions.get("pairs"):
            changed, unchanged = apply_pairs(translations, revisions["pairs"], stamp)
            report.append(
                f"pairs: {len(changed)} revised, {len(unchanged)} already current"
            )
            if changed:
                report.append("  revised: " + ", ".join(changed))
                touched_translations = True

    claims_doc = None
    if revisions.get("claims"):
        claims_doc = read_json(paths["claims_en"])
        changed, unchanged = apply_claims(claims_doc, revisions["claims"], stamp)
        report.append(
            f"claims: {len(changed)} revised, {len(unchanged)} already current"
        )
        if changed:
            report.append("  revised: " + ", ".join(changed))
            touched_claims = True

    if not report:
        print("nothing to apply")
        return 0

    if args.dry_run:
        print("DRY RUN — nothing written")
        for line in report:
            print(f"  {line}")
        return 0

    if touched_translations:
        write_json(paths["translations"], translations)
    if touched_claims:
        write_json(paths["claims_en"], claims_doc)

    violations: list[str] = []
    for key in ("translations", "claims_en"):
        if (key == "translations" and touched_translations) or (
            key == "claims_en" and touched_claims
        ):
            violations.extend(validate_file(paths[key]))
    if violations:
        die("state is invalid after applying revisions:\n  " + "\n  ".join(violations))

    for line in report:
        print(line)
    print("state written and schema-valid; re-run checks.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
