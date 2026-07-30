#!/usr/bin/env python3
"""Align a reviewer's findings against the pipeline's flags, by segment id only.

Usage: review_compare.py --project projects/<slug>

Reads <project>/review/findings.json, <project>/review/packet/pairs.json and
<project>/state/flags.json; writes <project>/review/comparison_candidates.json
with three buckets: candidates (a finding and a flag on the same segment),
reviewer_only (a finding on a segment carrying no flag) and pipeline_only (a flag
on a segment carrying no finding).

CANDIDATES ONLY. This script does NOT decide whether a finding and a flag are the
same doubt: that is a semantic judgement and it belongs to the model, in the
anchored stage that reads this file. So there is no fuzzy text matching here, no
similarity score, no keyword overlap over `issue`, and `class` is not used for
alignment either — an identical class is not evidence that two entries are the
same doubt, and a different class is not evidence that they are not. A mechanical
guess would launder the judgement it is supposed to hand over, and it would show
up twice as noise: a wrong pairing hides a real miss, a wrong split invents a
spurious one. Alignment is by segment id, and by nothing else; the full cross
product per segment is emitted and the model discards the non-pairs.

Nothing is filtered out. CONVENTION flags and already-resolved flags are emitted
like every other flag, with `flag_class` and `flag_status` echoed so the later
stage can weigh them: a resolved flag is still a pipeline doubt, and a reviewer
reproducing it is concordance rather than a new finding.

Read-only with respect to state/: it opens state/flags.json and writes only under
<project>/review/. It never calls flags.py add or flags.py resolve.

Run from the repo root.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import common
import flags as flags_mod
import review_validate

FINDINGS_LABEL = "findings.json"
PAIRS_LABEL = "packet/pairs.json"
FLAGS_LABEL = "state/flags.json"

# The document-wide locus. A finding spells it `DOC` (review_validate), a flag
# spells it as a null or absent segment_id (flags.py: "omit for a document-wide
# flag"). Both spellings resolve to the same bucket, so a document-wide finding
# aligns with a document-wide flag; the literal `DOC` is accepted on the flag
# side too, because a flag written with `--segment DOC` names the same locus and
# putting it in a bucket of its own would only split it away from the findings it
# belongs with.
DOC_SEGMENT = review_validate.DOC_SEGMENT

# Segment-order tiers for the deterministic sort: packet order first, then any
# segment the packet does not contain (by id), then the document-wide bucket.
_TIER_IN_PACKET = 0
_TIER_UNKNOWN = 1
_TIER_DOCUMENT = 2


def segment_order(pairs_doc) -> dict[str, int]:
    """Entry id -> position in packet/pairs.json, which is document order."""
    order: dict[str, int] = {}
    for index, entry in enumerate(pairs_doc["entries"]):
        order.setdefault(entry["id"], index)
    return order


def bucket_of(segment_id) -> str | None:
    """The alignment bucket of a segment id: None for the document-wide locus."""
    if segment_id is None or segment_id == DOC_SEGMENT:
        return None
    return segment_id


def sort_rank(bucket: str | None, order: dict[str, int]) -> tuple[int, object]:
    """Sort key of a bucket. Total and deterministic: a segment absent from the
    packet (a flag on a segment the packet omits) still sorts, by id, after every
    packet segment; the document-wide bucket sorts last."""
    if bucket is None:
        return (_TIER_DOCUMENT, "")
    if bucket in order:
        return (_TIER_IN_PACKET, order[bucket])
    return (_TIER_UNKNOWN, bucket)


def flag_violations(flag_list: list) -> list[str]:
    """Violations of the flag fields this script copies, one string each.

    Only the keys echoed into the output are checked. The flags.json schema as a
    whole is validate_state.py's business, and a comparison must not fail over a
    field it never reads; but a flag with no usable key, class, issue or status
    cannot be reported to the model, so it is a loud failure rather than a
    silently skipped row.
    """
    out: list[str] = []
    for index, flag in enumerate(flag_list):
        if not isinstance(flag, dict):
            out.append(f"{FLAGS_LABEL} flags[{index}] is not an object")
            continue
        key = flag.get("key")
        locus = f"flag {key}" if isinstance(key, str) and key.strip() \
            else f"flags[{index}]"
        for name in ("key", "class", "issue", "status"):
            value = flag.get(name)
            if not isinstance(value, str) or not value.strip():
                out.append(f"{FLAGS_LABEL} {locus} {name} must be a non-empty "
                           f"string, got {value!r}")
        segment_id = flag.get("segment_id")
        if segment_id is not None and (
            not isinstance(segment_id, str) or not segment_id.strip()
        ):
            out.append(f"{FLAGS_LABEL} {locus} segment_id must be a non-empty "
                       f"string or null, got {segment_id!r}")
    return out


def _group(items: list, key_of) -> dict:
    grouped: dict = {}
    for item in items:
        grouped.setdefault(key_of(item), []).append(item)
    return grouped


def build_comparison(project_name: str, findings: list, flag_list: list,
                     order: dict[str, int]) -> dict:
    """The comparison document. `issue` texts are verbatim copies of the inputs:
    nothing is summarized and nothing is re-derived from them."""
    findings_by_bucket = _group(findings, lambda f: bucket_of(f["segment_id"]))
    flags_by_bucket = _group(flag_list, lambda f: bucket_of(f.get("segment_id")))

    candidates = []
    for bucket, bucket_findings in findings_by_bucket.items():
        for finding in bucket_findings:
            for flag in flags_by_bucket.get(bucket, []):
                candidates.append({
                    # One locus for two spellings: the document-wide bucket is
                    # reported as DOC, the findings side's literal.
                    "segment_id": DOC_SEGMENT if bucket is None else bucket,
                    "finding_id": finding["id"],
                    "finding_class": finding["class"],
                    "finding_issue": finding["issue"],
                    "flag_key": flag["key"],
                    "flag_class": flag["class"],
                    "flag_issue": flag["issue"],
                    "flag_status": flag["status"],
                })
    candidates.sort(key=lambda c: (sort_rank(bucket_of(c["segment_id"]), order),
                                   c["finding_id"], c["flag_key"]))

    reviewer_only = [
        {"segment_id": finding["segment_id"], "finding_id": finding["id"],
         "finding_class": finding["class"], "finding_issue": finding["issue"]}
        for bucket, bucket_findings in findings_by_bucket.items()
        if bucket not in flags_by_bucket
        for finding in bucket_findings
    ]
    reviewer_only.sort(key=lambda r: (sort_rank(bucket_of(r["segment_id"]), order),
                                      r["finding_id"]))

    pipeline_only = [
        {"segment_id": flag.get("segment_id"), "flag_key": flag["key"],
         "flag_class": flag["class"], "flag_issue": flag["issue"],
         "flag_status": flag["status"]}
        for bucket, bucket_flags in flags_by_bucket.items()
        if bucket not in findings_by_bucket
        for flag in bucket_flags
    ]
    pipeline_only.sort(key=lambda p: (sort_rank(bucket_of(p["segment_id"]), order),
                                      p["flag_key"]))

    return {
        "meta": {
            "project": project_name,
            "generated_at": common.now_iso(),
            "counts": {
                "findings": len(findings),
                "flags": len(flag_list),
                "candidates": len(candidates),
                "reviewer_only": len(reviewer_only),
                "pipeline_only": len(pipeline_only),
            },
        },
        "candidates": candidates,
        "reviewer_only": reviewer_only,
        "pipeline_only": pipeline_only,
    }


def report_violations(violations: list[str], subject: str) -> int:
    for violation in violations:
        print(f"FAIL {violation}")
    print(f"{len(violations)} violation(s) in {subject}: "
          "no comparison written")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Align review findings against the pipeline's flags by "
                    "segment id, into <project>/review/comparison_candidates.json."
    )
    parser.add_argument("--project", required=True,
                        help="project directory, e.g. projects/_fixture")
    args = parser.parse_args()

    paths = common.project_paths(args.project, need_source=False)
    review = Path(paths["root"]) / "review"
    findings_path = review / "findings.json"
    pairs_path = review / "packet" / "pairs.json"
    flags_path = Path(paths["flags"])

    # An invalid findings file is never aligned: ids that the report and every
    # set_final.py reason will cite have to be valid first.
    violations = review_validate.validate_findings(findings_path, pairs_path)
    if violations:
        return report_violations(violations, str(findings_path))

    # Only now may state/flags.json be opened. Generation is blind and no review
    # script reads the pipeline's doubts before the findings exist and validate
    # (CONTRACTS.md, "FORBIDDEN in the packet"); comparison is anchored by design.
    if not flags_path.is_file():
        common.die(f"{FLAGS_LABEL} not found: {flags_path}")
    flags_doc = flags_mod.load_flags(flags_path)
    flag_list = flags_doc["flags"]
    violations = flag_violations(flag_list)
    if violations:
        return report_violations(violations, str(flags_path))

    findings = common.read_json(findings_path)["findings"]
    order = segment_order(common.read_json(pairs_path))
    document = build_comparison(Path(paths["root"]).name, findings, flag_list,
                                order)

    output = review / "comparison_candidates.json"
    common.write_json(output, document)

    counts = document["meta"]["counts"]
    print(f"comparison -> {output}")
    print(f"  inputs      findings {counts['findings']}, "
          f"flags {counts['flags']}")
    print(f"  candidates  {counts['candidates']}")
    print(f"  reviewer_only  {counts['reviewer_only']}")
    print(f"  pipeline_only  {counts['pipeline_only']}")
    unknown = sorted({
        entry["segment_id"] for entry in document["pipeline_only"]
        if sort_rank(bucket_of(entry["segment_id"]), order)[0] == _TIER_UNKNOWN
    })
    if unknown:
        # A flag on a segment the packet omits can never have been reproduced:
        # say so, or the model reads it as something the reviewer missed.
        print(f"  note: {len(unknown)} pipeline_only flag segment(s) absent from "
              f"{PAIRS_LABEL}: " + ", ".join(unknown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
