#!/usr/bin/env python3
"""Validate a reviewer's findings.json against the Review module contract.

Usage:
    review_validate.py --project P [--input findings.json]

Reads `<project>/review/findings.json` (or `--input`) and
`<project>/review/packet/pairs.json`, and nothing else: never `state/`, because
the reviewer's output is judged against the blind packet, not against the
pipeline's own doubts. It writes nothing at all — a findings file is reported
on, never repaired and never rewritten.

Output mirrors validate_state.py: one `FAIL <finding id or "findings.json">
<detail>` line per violation, then a count line; a clean file prints
`OK: N finding(s) valid`. Exit 1 on any violation and on a missing or
unparseable input, 0 otherwise.

What the `options` test does and does not do. It is an emptiness test plus a
placeholder-phrase test over the exact lexicon fixed in CONTRACTS.md — no
semantic judgement of any kind. It catches "to be reviewed", "TBD" and bare
"see above" because they are in the lexicon. It does not catch "use a better
word", which is just as unusable, and it happily accepts a specific rendering
that is specifically wrong. Whether an option is a genuinely actionable
alternative stays a reading job for the adjudicating session; this script only
stops the phrasings that are known to be no alternative at all.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import common

FINDINGS_LABEL = "findings.json"
PAIRS_LABEL = "packet/pairs.json"

FINDING_CLASSES = ("AMBIGUITY", "TERM", "CONVENTION", "CLAIM-DEFECT", "COVERAGE-GAP")
LENSES = ("rules", "grammar")
REQUIRED_KEYS = ("id", "class", "segment_id", "lens", "issue", "options")
OPTIONAL_KEYS = ("rule", "proposed_en", "shard")
ALLOWED_KEYS = frozenset(REQUIRED_KEYS + OPTIONAL_KEYS)
DOC_SEGMENT = "DOC"
ID_RE = re.compile(r"^F-\d{4}$")

# The non-concrete lexicon, verbatim from CONTRACTS.md. Substrings anywhere in
# the option kill it; the second group kills it only when it is the whole
# option, because "check the antecedent of 'the mixture'" is an instruction and
# a bare "check" is not.
NOT_CONCRETE_SUBSTRINGS = (
    "to be reviewed", "to be checked", "to be verified", "to be confirmed",
    "to be decided", "to be determined", "to be discussed", "to be assessed",
    "to be evaluated", "tbd", "da verificare",
)
NOT_CONCRETE_EXACT = (
    "review", "check", "verify", "confirm", "reconsider", "rephrase",
    "as appropriate", "see above", "see below", "n/a", "na", "none", "other",
    "unclear", "unknown", "ask the firm", "ask mario", "escalate", "flag it",
)


# --------------------------------------------------------------------------
# importable API (review_compare.py imports validate_findings; the escalation
# actionability audit in patent-review/SKILL.md uses option_violations)


def option_violations(option: str) -> str | None:
    """Why `option` is not a concrete alternative, or None when it is.

    The single definition of non-concreteness in the repo, so the findings
    validator and the audit of the pipeline's own open flags apply the same
    standard. Mechanical only: emptiness and the CONTRACTS.md placeholder
    lexicon. It cannot tell a useful alternative from a useless one.

    Deliberately NOT a length test. A rendering can be two characters and be the
    only correct one: the style guide fixes 'mediante' as 'by' in the
    description, so options: ['by'] is exactly right and a minimum-length floor
    rejected it — on a real cafe124 TERM flag as well as on the fix that seeded
    defect 6 calls for. Length says nothing about concreteness, and this function
    claims no more than it can test.
    """
    text = common.normalize(option).lower()
    if not text:
        return "empty once normalized"
    for phrase in NOT_CONCRETE_SUBSTRINGS:
        if phrase in text:
            return f"contains the placeholder phrase {phrase!r}"
    # normalize() leaves no trailing whitespace, but a space can sit before the
    # final punctuation ("check ."), so strip both.
    bare = text.rstrip(" .?!")
    if bare in NOT_CONCRETE_EXACT:
        return f"is the bare placeholder {bare!r}"
    return None


def validate_findings(findings_path, pairs_path) -> list[str]:
    """Violations of a findings file against the packet, as strings.

    Pure: reads two files, prints nothing, never exits, returns one string per
    violation, each already shaped as `<finding id or "findings.json">
    <detail>`. An empty list means the file is valid.
    """
    findings_path = Path(findings_path)
    pairs_path = Path(pairs_path)
    violations: list[str] = []

    doc, load_errors = _load_json(findings_path, FINDINGS_LABEL)
    violations.extend(load_errors)

    pairs_doc, pairs_errors = _load_json(pairs_path, PAIRS_LABEL)
    violations.extend(pairs_errors)
    pairs_text_en = None
    if pairs_doc is not None:
        pairs_text_en, entry_errors = _packet_text_en(pairs_doc)
        violations.extend(entry_errors)

    if doc is None:
        return violations
    if not isinstance(doc, dict):
        violations.append(
            f"{FINDINGS_LABEL} expected a JSON object at the top level, "
            f"got {type(doc).__name__}"
        )
        return violations

    meta = doc.get("meta")
    if not isinstance(meta, dict):
        violations.append(f"{FINDINGS_LABEL} meta is missing or not an object")
    else:
        for key in ("project", "generated_at"):
            value = meta.get(key)
            if not isinstance(value, str) or not value.strip():
                violations.append(
                    f"{FINDINGS_LABEL} meta.{key} must be a non-empty string"
                )

    findings = doc.get("findings")
    if not isinstance(findings, list):
        violations.append(f"{FINDINGS_LABEL} findings is missing or not a list")
        return violations

    if findings and pairs_text_en is None:
        violations.append(
            f"{FINDINGS_LABEL} segment ids and proposed_en left unchecked: "
            f"{PAIRS_LABEL} is unusable (see the violations above)"
        )

    seen_ids: dict[str, int] = {}
    for index, finding in enumerate(findings):
        violations.extend(
            _finding_violations(finding, index, seen_ids, pairs_text_en)
        )
    return violations


# --------------------------------------------------------------------------
# inputs


def _load_json(path: Path, label: str):
    """(parsed document, violations). None document when it could not be read;
    common.read_json is not usable here because validate_findings never exits."""
    if not path.is_file():
        return None, [f"{label} file not found: {path}"]
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), []
    except json.JSONDecodeError as exc:
        return None, [f"{label} invalid JSON: {exc}"]
    except UnicodeDecodeError as exc:
        return None, [f"{label} not valid UTF-8: {exc}"]


def _packet_text_en(pairs_doc):
    """(entry id -> delivered English, violations) from packet/pairs.json.

    The map is None when the packet is structurally unusable, so the caller can
    skip the segment-existence checks instead of reporting every finding twice.
    """
    if not isinstance(pairs_doc, dict):
        return None, [f"{PAIRS_LABEL} expected a JSON object at the top level"]
    entries = pairs_doc.get("entries")
    if not isinstance(entries, list):
        return None, [f"{PAIRS_LABEL} entries is missing or not a list"]
    out: dict[str, str] = {}
    violations: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            violations.append(f"{PAIRS_LABEL} entries[{index}] is not an object")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            violations.append(
                f"{PAIRS_LABEL} entries[{index}] has no usable id"
            )
            continue
        text_en = entry.get("text_en")
        if not isinstance(text_en, str):
            violations.append(
                f"{PAIRS_LABEL} entries[{index}] ({entry_id}) has no string text_en"
            )
            continue
        out[entry_id] = text_en
    return out, violations


# --------------------------------------------------------------------------
# per-finding checks


def _short(text: str, width: int = 60) -> str:
    text = common.normalize(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def _finding_violations(finding, index: int, seen_ids: dict, pairs_text_en) -> list[str]:
    """Violations of one finding. `seen_ids` maps an already-used id to the index
    that used it and is updated in place. `pairs_text_en` is None when the packet
    could not be read, which skips the two checks that need it."""
    if not isinstance(finding, dict):
        return [f"{FINDINGS_LABEL} findings[{index}] is not an object"]

    out: list[str] = []
    ident = finding.get("id")
    if isinstance(ident, str) and ident.strip():
        locus, prefix = ident.strip(), ""
    else:
        locus, prefix = FINDINGS_LABEL, f"findings[{index}] "

    def fail(detail: str) -> None:
        out.append(f"{locus} {prefix}{detail}")

    allowed = ", ".join(sorted(ALLOWED_KEYS))
    for key in sorted(set(finding) - ALLOWED_KEYS):
        fail(f"unknown key {key!r} (allowed: {allowed})")
    for key in REQUIRED_KEYS:
        if key not in finding:
            fail(f"missing required key {key!r}")

    if "id" in finding:
        if not isinstance(ident, str):
            fail(f"id must be a string, got {type(ident).__name__}")
        else:
            if not ID_RE.match(ident):
                fail(rf"id {ident!r} does not match ^F-\d{{4}}$")
            if ident in seen_ids:
                fail(f"id {ident!r} is not unique "
                     f"(already used by findings[{seen_ids[ident]}])")
            else:
                seen_ids[ident] = index

    finding_class = finding.get("class")
    if "class" in finding and finding_class not in FINDING_CLASSES:
        fail(f"class {finding_class!r} is not one of {', '.join(FINDING_CLASSES)}")

    lens = finding.get("lens")
    if "lens" in finding and lens not in LENSES:
        fail(f"lens {lens!r} is not one of {', '.join(LENSES)}")

    segment_id = finding.get("segment_id")
    if "segment_id" in finding:
        if not isinstance(segment_id, str) or not segment_id.strip():
            fail("segment_id must be a non-empty string: a packet entry id or the "
                 f"literal {DOC_SEGMENT}")
        elif (pairs_text_en is not None and segment_id != DOC_SEGMENT
                and segment_id not in pairs_text_en):
            fail(f"segment_id {segment_id!r} is not an entry id in {PAIRS_LABEL} "
                 f"and is not the literal {DOC_SEGMENT!r}")

    if "issue" in finding:
        issue = finding.get("issue")
        if not isinstance(issue, str) or not issue.strip():
            fail("issue must be a non-empty string")

    if "options" in finding:
        options = finding.get("options")
        if not isinstance(options, list):
            fail(f"options must be a list, got {type(options).__name__}")
        elif not options:
            fail("options must be a non-empty list of concrete alternatives")
        else:
            for i, option in enumerate(options):
                if not isinstance(option, str):
                    fail(f"options[{i}] must be a string, "
                         f"got {type(option).__name__}")
                    continue
                reason = option_violations(option)
                if reason is not None:
                    fail(f"options[{i}] is not a concrete alternative "
                         f"({reason}): {_short(option)!r}")
            if finding_class == "AMBIGUITY" and len(options) < 2:
                fail("class AMBIGUITY requires at least two options, each reading "
                     f"with its English consequence (found {len(options)})")

    rule = finding.get("rule")
    if lens == "rules" and finding_class != "COVERAGE-GAP":
        if not isinstance(rule, str) or not rule.strip():
            fail("rule must be a non-empty string on a rules-lens finding that is "
                 "not a COVERAGE-GAP: cite the style-guide rule, or file it as "
                 "COVERAGE-GAP or lens grammar")
    elif "rule" in finding and rule is not None and not isinstance(rule, str):
        fail(f"rule must be a string or null, got {type(rule).__name__}")

    if "proposed_en" in finding:
        proposed = finding.get("proposed_en")
        if proposed is not None:
            if not isinstance(proposed, str) or not proposed.strip():
                fail("proposed_en must be a non-empty string when it is not null")
            elif (pairs_text_en is not None and isinstance(segment_id, str)
                    and segment_id != DOC_SEGMENT and segment_id in pairs_text_en):
                # Compared on the normalized form per the CONTRACTS.md text
                # policy: a whitespace-only difference is a no-op too.
                if common.normalize(proposed) == common.normalize(
                    pairs_text_en[segment_id]
                ):
                    fail(f"proposed_en is identical to the delivered English of "
                         f"{segment_id}: a no-op proposal")

    if "shard" in finding:
        shard = finding.get("shard")
        if not isinstance(shard, str) or not shard.strip():
            fail("shard must be a non-empty string when the key is present")

    return out


# --------------------------------------------------------------------------
# CLI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True,
                        help="project directory, e.g. projects/_fixture")
    parser.add_argument("--input",
                        help="findings file to validate "
                             "(default: <project>/review/findings.json)")
    args = parser.parse_args()

    paths = common.project_paths(args.project, need_source=False)
    review = paths["root"] / "review"
    findings_path = Path(args.input) if args.input else review / "findings.json"
    pairs_path = review / "packet" / "pairs.json"

    violations = validate_findings(findings_path, pairs_path)
    for violation in violations:
        print(f"FAIL {violation}")
    if violations:
        print(f"{len(violations)} violation(s) in {findings_path}")
        return 1

    doc = common.read_json(findings_path)
    print(f"OK: {len(doc['findings'])} finding(s) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
