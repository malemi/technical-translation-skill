#!/usr/bin/env python3
"""Build projects/_fixture_review — the judgement-defect copy of the fixture.

make_fixture_bad.py seeds the six defects the mechanical battery must catch.
This script seeds the band checks.py cannot reach: eight defects of judgement,
taken from the style guide's "Known failure modes" catalogue and its named traps,
so patent-review's recall can be measured per failure mode instead of guessed.

The defects live in the ENGLISH side only. The Italian is the authoritative text
and is copied untouched, which is also what makes each seed detectable: the
reviewer compares the Italian against the delivered English and nothing else.

set_final.py applies them. These are defects in the FINAL English, and
set_final.py is the single writer for reviewed English, so no new writer exists
or is needed: every seed lands as a `text_en_final` with its reason in `edits`.
That trail is invisible to a blind pass — review_packet.py copies neither
`edits` nor the fact that a pair carries a final (CONTRACTS.md, "FORBIDDEN in the
packet"), so the provenance can be complete without becoming an answer key.

The seed table and the replacement texts live together in the tracked
dev/review_seed_revisions.json, which is at the same time a valid set_final.py
revisions file and the machine-readable record of what was seeded: per seed, the
segment, the failure mode, the exact English fragment before and after, the
Italian it is unfaithful to, the style-guide rule it breaks, and the checks.py
check that would also catch it, if any. The acceptance measurement scores recall
per mode straight from that file — nothing has to be re-derived by hand.

Every seed asserts its own ground before anything is written: the Italian
fragment must be present in the segment, the English fragment must occur exactly
once, and the replacement text in the payload must equal the text this script
derives from the baseline. If the fixture baseline moves, the build fails loudly
instead of producing a weaker test.

NOT SEEDABLE HERE, and this is deliberate: the ninth catalogue mode, "an
antecedent-basis defect in an independent claim silently repaired, after it had
been explicitly flagged as a defect to translate verbatim". Repairing a source
defect requires a source defect to repair, and this fixture's independent claim
has none — its deliberate quirks are a claim-only term and one reference sign
with two Italian names, neither of which is an antecedent-basis defect in an
independent claim. Seeding a repair would therefore mean seeding the defect into
the Italian first, i.e. writing a different source document. That mode is
measured the other way round instead, as source-quirk recall on the clean
projects/_fixture, where the reviewer must report the quirks rather than propose
their repair: see projects/_fixture/fixture_spec.md and the acceptance step of
docs/execution-plans/patent-review-skill.md.

Source and target are hardcoded (projects/_fixture -> projects/_fixture_review),
like make_fixture_bad.py: the seeds are written against that exact baseline, and
a path argument would only invite pointing this at a real document.

Usage:
    seed_review_fixture.py

Run from the repo root, after the clean fixture is complete (make_fixture.py,
ingest.py, make_fixture_en.py, checks.py, assemble.py). The target directory is
rebuilt from scratch on every run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import checks  # noqa: E402
from common import die, normalize, read_json  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent.parent
SET_FINAL = SCRIPTS / "set_final.py"
REVISIONS = Path(__file__).resolve().parent / "review_seed_revisions.json"

SOURCE = Path("projects/_fixture")
TARGET = Path("projects/_fixture_review")

# Copied verbatim from the clean fixture. The Italian side, the glossary and the
# pipeline's own doubts are the project as delivered; only the English text is
# seeded, and only through set_final.py.
COPIED_FILES = ("terminology.csv",)
# flags.json travels with the project: it is the pipeline's doubt record, which
# review_compare.py needs to produce the three-way diff, and no seed adds,
# removes or resolves a flag. checks.json is NOT copied — no review script reads
# it, and mechanical results computed on the clean English would misdescribe this
# project. deepl.json, backtranslation.json and terminology_report.json are not
# copied either: the last two are packet-forbidden, and none is a review input.
COPIED_STATE = ("segments.json", "translations.json", "claims_en.json", "flags.json")
# out/terminology.csv is the DELIVERED glossary: review_packet.py copies it into
# the packet and refuses to build when it is absent or stale. The other
# deliverables are not copied, because they were assembled from the clean English
# and would misdescribe this project; nothing here re-assembles them, so the
# seeded English never reaches a docx.
COPIED_OUT = ("terminology.csv",)

# The eight modes this fixture exists to carry. The tracked seed file must cover
# each exactly once: a seed silently dropped from the data would otherwise leave
# a failure mode unmeasured while the build still reported success.
EXPECTED_MODES = (
    "means-to-mechanism",
    "reference-sign-relettered",
    "dropped-clause",
    "altered-defined-quantity",
    "gerunds-to-imperatives",
    "by-way-of",
    "closed-transition",
    "dropped-hedge",
)

# Exact key set of a seed entry, with the accepted types. Unknown and missing
# keys are both violations: a typo in a tracked data file must not degrade into a
# silently unenforced field.
SEED_KEYS = {
    "seed": int,
    "mode": str,
    "summary": str,
    "catalogue": (str, type(None)),
    "rule": str,
    "segment_id": str,
    "target": str,
    "text_it_fragment": str,
    "changes": list,
    "mechanical_check": (str, type(None)),
    "note": (str, type(None)),
}

SPEC_NAME = "fixture_spec.md"


def fail(problems: list[str], headline: str) -> None:
    """Exit reporting every problem: baseline drift is easier to repair when the
    whole list is on the table, not just the first line of it."""
    if problems:
        die(f"{headline}\n  " + "\n  ".join(problems))


def load_revisions() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    """The tracked seed file, validated: (seeds, pairs by id, claims by id)."""
    document = read_json(REVISIONS)
    if not isinstance(document, dict):
        die(f"{REVISIONS}: expected a JSON object at the top level")
    seeds = document.get("seeds")
    if not isinstance(seeds, list) or not seeds:
        die(f"{REVISIONS}: 'seeds' must be a non-empty list")

    problems: list[str] = []
    for index, seed in enumerate(seeds):
        label = f"seeds[{index}]"
        if not isinstance(seed, dict):
            problems.append(f"{label} is not an object")
            continue
        shape: list[str] = []
        for key in sorted(set(seed) - set(SEED_KEYS)):
            shape.append(f"{label}: unknown key {key!r}")
        for key, types in SEED_KEYS.items():
            if key not in seed:
                shape.append(f"{label}: missing key {key!r}")
            elif not isinstance(seed[key], types):
                shape.append(f"{label}: {key!r} has the wrong type")
        problems.extend(shape)
        # Only this seed's deeper checks are skipped, and only when its shape is
        # broken: they would raise on the missing or mistyped key. Every other
        # seed is still checked, so one typo does not hide the rest.
        if shape:
            continue
        if seed["seed"] != index + 1:
            problems.append(f"{label}: seed number {seed['seed']} is not {index + 1}")
        if seed["target"] not in ("pair", "claim"):
            problems.append(f"{label}: target {seed['target']!r} is not pair or claim")
        for field in ("mode", "summary", "rule", "segment_id", "text_it_fragment"):
            if not seed[field].strip():
                problems.append(f"{label}: {field!r} is empty")
        if not seed["changes"]:
            problems.append(f"{label}: 'changes' is empty")
        for position, change in enumerate(seed["changes"]):
            where = f"{label}.changes[{position}]"
            if not isinstance(change, dict) or set(change) != {"before", "after"}:
                problems.append(f"{where}: expected exactly 'before' and 'after'")
                continue
            if not isinstance(change["before"], str) or not change["before"]:
                problems.append(f"{where}: 'before' must be a non-empty string")
            if not isinstance(change["after"], str) or not change["after"]:
                problems.append(f"{where}: 'after' must be a non-empty string")
            if change.get("before") == change.get("after"):
                problems.append(f"{where}: 'before' and 'after' are identical")
    fail(problems, f"{REVISIONS}: invalid seed table")

    modes = [seed["mode"] for seed in seeds]
    for mode in EXPECTED_MODES:
        if modes.count(mode) != 1:
            problems.append(f"mode {mode!r} appears {modes.count(mode)} times, want 1")
    for mode in sorted(set(modes) - set(EXPECTED_MODES)):
        problems.append(f"mode {mode!r} is not one of the eight expected modes")
    fail(problems, f"{REVISIONS}: the eight failure modes are not covered exactly once")

    # set_final.py validates the payload itself; this guard only keeps a
    # malformed entry from raising before its own error message is printed.
    for section in ("pairs", "claims"):
        for position, entry in enumerate(document.get(section, [])):
            if not isinstance(entry, dict) or not entry.get("id"):
                problems.append(f"{section}[{position}] is not an object with an id")
    fail(problems, f"{REVISIONS}: invalid revision payload")

    pairs = {entry["id"]: entry for entry in document.get("pairs", [])}
    claims = {entry["id"]: entry for entry in document.get("claims", [])}
    seeded_pairs = {s["segment_id"] for s in seeds if s["target"] == "pair"}
    seeded_claims = {s["segment_id"] for s in seeds if s["target"] == "claim"}
    for segment_id in sorted(seeded_pairs - set(pairs)):
        problems.append(f"{segment_id}: seeded as a pair but absent from 'pairs'")
    for segment_id in sorted(seeded_claims - set(claims)):
        problems.append(f"{segment_id}: seeded as a claim but absent from 'claims'")
    for segment_id in sorted(set(pairs) - seeded_pairs):
        problems.append(f"pairs[{segment_id}]: revised by no seed")
    for segment_id in sorted(set(claims) - seeded_claims):
        problems.append(f"claims[{segment_id}]: revised by no seed")
    if document.get("title") is not None:
        problems.append("'title' is present: no seed touches the title")
    fail(problems, f"{REVISIONS}: seeds and revision payload disagree")
    return seeds, pairs, claims


def copy_baseline() -> None:
    """Rebuild TARGET from the clean fixture, English still untouched."""
    problems = []
    if not SOURCE.is_dir():
        die(f"clean fixture not found: {SOURCE} (run make_fixture.py first)")
    for name in COPIED_STATE:
        if not (SOURCE / "state" / name).is_file():
            problems.append(f"{SOURCE / 'state' / name} missing")
    for name in COPIED_FILES:
        if not (SOURCE / name).is_file():
            problems.append(f"{SOURCE / name} missing")
    for name in COPIED_OUT:
        if not (SOURCE / "out" / name).is_file():
            problems.append(f"{SOURCE / 'out' / name} missing (run assemble.py)")
    fail(
        problems,
        "the clean fixture is incomplete. Run make_fixture.py, ingest.py, "
        "make_fixture_en.py, checks.py and assemble.py first, then re-run this:",
    )

    if TARGET.exists():
        shutil.rmtree(TARGET)
        print(f"removed previous {TARGET}")
    (TARGET / "state").mkdir(parents=True)
    (TARGET / "out").mkdir()

    for name in COPIED_FILES:
        shutil.copy2(SOURCE / name, TARGET / name)
    for name in COPIED_STATE:
        shutil.copy2(SOURCE / "state" / name, TARGET / "state" / name)
    for name in COPIED_OUT:
        shutil.copy2(SOURCE / "out" / name, TARGET / "out" / name)
    source_docx = SOURCE / "source.docx"
    if source_docx.is_file():
        shutil.copy2(source_docx, TARGET / "source.docx")


def replace_once(
    text: str, before: str, after: str, where: str
) -> tuple[str, str | None]:
    """(text with the single occurrence replaced, problem line or None)."""
    count = text.count(before)
    if count != 1:
        return text, (
            f"{where}: {before!r} occurs {count} time(s) in the English, expected "
            "exactly 1. The fixture baseline changed — update the seed table."
        )
    return text.replace(before, after), None


def replace_in_parts(
    parts: list[str], before: str, after: str, where: str
) -> tuple[list[str], str | None]:
    """The same discipline across the parts of a claim: exactly one part, exactly
    one occurrence in it."""
    hits = [index for index, part in enumerate(parts) if before in part]
    total = sum(part.count(before) for part in parts)
    if len(hits) != 1 or total != 1:
        return parts, (
            f"{where}: {before!r} occurs {total} time(s) across {len(hits)} part(s), "
            "expected exactly once. The fixture baseline changed — update the seed "
            "table."
        )
    out = list(parts)
    out[hits[0]] = out[hits[0]].replace(before, after)
    return out, None


def derive(
    state_dir: Path, seeds: list[dict]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """The seeded English, derived from the baseline in the target directory.

    Also the place where every seed's ground is asserted: the Italian fragment
    must really be in the segment, and the English fragment must occur exactly
    once in the delivered English.
    """
    segments = read_json(state_dir / "segments.json")
    translations = read_json(state_dir / "translations.json")
    claims_doc = read_json(state_dir / "claims_en.json")

    text_it = {s["id"]: s["text_it"] for s in segments["segments"]}
    # State.pair_en is the single definition of the delivered English: the final
    # when set, else the DeepL output. Before seeding, every fixture pair is the
    # DeepL output.
    pair_text = {p["id"]: checks.State.pair_en(p) for p in translations["pairs"]}
    claim_parts = {c["id"]: list(c["parts_en"]) for c in claims_doc["claims"]}

    problems: list[str] = []
    for seed in seeds:
        segment_id = seed["segment_id"]
        label = f"seed {seed['seed']} ({seed['mode']}) {segment_id}"
        if segment_id not in text_it:
            problems.append(f"{label}: no such segment in segments.json")
            continue
        if normalize(seed["text_it_fragment"]) not in normalize(text_it[segment_id]):
            problems.append(
                f"{label}: the Italian fragment {seed['text_it_fragment']!r} is not "
                "in the segment's text_it, so the seed would not be a defect"
            )
        if seed["target"] == "pair":
            if segment_id not in pair_text:
                problems.append(f"{label}: no such pair in translations.json")
                continue
            for change in seed["changes"]:
                pair_text[segment_id], problem = replace_once(
                    pair_text[segment_id], change["before"], change["after"], label
                )
                if problem:
                    problems.append(problem)
        else:
            if segment_id not in claim_parts:
                problems.append(f"{label}: no such claim in claims_en.json")
                continue
            for change in seed["changes"]:
                claim_parts[segment_id], problem = replace_in_parts(
                    claim_parts[segment_id], change["before"], change["after"], label
                )
                if problem:
                    problems.append(problem)
    fail(problems, "the seed table does not match the fixture baseline:")
    return pair_text, claim_parts


def check_payload(
    seeds: list[dict],
    pairs: dict[str, dict],
    claims: dict[str, dict],
    pair_text: dict[str, str],
    claim_parts: dict[str, list[str]],
) -> None:
    """The payload set_final.py will apply must equal the derived text.

    Two records of the same change (the fragments and the whole replacement
    text) can drift apart when the file is hand-edited; this is the lock that
    turns that drift into a failed build instead of a silently different seed.
    """
    problems: list[str] = []
    seeded = {target: sorted({s["segment_id"] for s in seeds if s["target"] == target})
              for target in ("pair", "claim")}
    for segment_id in seeded["pair"]:
        want = pair_text[segment_id]
        got = pairs[segment_id].get("text_en")
        if got != want:
            problems.append(
                f"pairs[{segment_id}].text_en is not the baseline with the seed "
                f"fragments applied.\n    payload:  {got!r}\n    derived:  {want!r}"
            )
    for segment_id in seeded["claim"]:
        want = claim_parts[segment_id]
        got = claims[segment_id].get("parts_en")
        if got != want:
            problems.append(
                f"claims[{segment_id}].parts_en is not the baseline with the seed "
                f"fragments applied.\n    payload:  {got!r}\n    derived:  {want!r}"
            )
    fail(problems, f"{REVISIONS}: the revision payload disagrees with the seeds:")


def apply_revisions() -> None:
    """Inject the seeds through the single writer for reviewed English."""
    cmd = [
        sys.executable,
        str(SET_FINAL),
        "--project",
        str(TARGET),
        "--input",
        str(REVISIONS),
    ]
    # flush: the child writes straight to fd 1, so an unflushed echo would print
    # after the output of the command it announces.
    print(f"\n$ {' '.join(cmd[1:])}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        die(f"set_final.py exited {result.returncode}: no seeded fixture written")
    print()


def verify(
    seeds: list[dict], pair_text: dict[str, str], claim_parts: dict[str, list[str]]
) -> None:
    """Re-read the written state and assert every seed actually landed."""
    state_dir = TARGET / "state"
    translations = read_json(state_dir / "translations.json")
    claims_doc = read_json(state_dir / "claims_en.json")
    pairs_by_id = {p["id"]: p for p in translations["pairs"]}
    claims_by_id = {c["id"]: c for c in claims_doc["claims"]}

    problems: list[str] = []
    for seed in seeds:
        segment_id = seed["segment_id"]
        label = f"seed {seed['seed']} ({seed['mode']}) {segment_id}"
        if seed["target"] == "pair":
            pair = pairs_by_id.get(segment_id)
            if pair is None:
                problems.append(f"{label}: pair vanished from translations.json")
                continue
            if pair["text_en_final"] is None:
                problems.append(
                    f"{label}: text_en_final is still null — set_final.py did not "
                    "write this seed"
                )
            if not pair["edits"]:
                problems.append(f"{label}: no edits entry recording the seed")
            delivered = checks.State.pair_en(pair)
            expected = pair_text[segment_id]
        else:
            claim = claims_by_id.get(segment_id)
            if claim is None:
                problems.append(f"{label}: claim vanished from claims_en.json")
                continue
            if claim["parts_en"] != claim_parts[segment_id]:
                problems.append(f"{label}: parts_en is not the seeded text")
            delivered = claim["text_en"]
            expected = "\n".join(claim_parts[segment_id])
        if delivered != expected:
            problems.append(
                f"{label}: delivered English is not the seeded text.\n"
                f"    delivered: {delivered!r}\n    expected:  {expected!r}"
            )
        for change in seed["changes"]:
            if change["after"] not in delivered:
                problems.append(
                    f"{label}: the seeded fragment {change['after']!r} is absent "
                    "from the delivered English"
                )
            if change["before"] in delivered:
                problems.append(
                    f"{label}: the clean fragment {change['before']!r} is still in "
                    "the delivered English"
                )
    fail(problems, f"the seeded fixture in {TARGET} is not what the seed table says:")


def spec_document(seeds: list[dict]) -> str:
    """The human-readable rendering of the seed table, in the style of
    projects/_fixture/fixture_spec.md. Derived at build time, so it cannot drift
    from the data it documents."""
    lines = [
        "# Fixture spec — seeded review defects",
        "",
        "GENERATED by `dev/seed_review_fixture.py` from the tracked seed table in",
        "`.claude/skills/patent-translate/scripts/dev/review_seed_revisions.json`.",
        "Every re-run overwrites this file; edit the seed table, never this.",
        "",
        f"`{TARGET}` is `{SOURCE}` with {len(seeds)} judgement-level defects",
        "injected into the ENGLISH side through `set_final.py`, the single writer for",
        "reviewed English. The Italian side, the glossary and `state/flags.json` are",
        "copied untouched: the Italian is what makes each defect a defect, so it is",
        "never modified.",
        "",
        "The defects are the style guide's \"Known failure modes\" catalogue plus two",
        "of its named traps. They are chosen to sit in the band the mechanical",
        "battery cannot reach, which is what `patent-review` exists to cover; the one",
        "exception is marked below.",
        "",
        "A blind review pass must never read this file. It may name",
        f"`{TARGET}/review/packet/` and no other path (CONTRACTS.md,",
        "\"FORBIDDEN in the packet\"): blindness is a property of the packet, which is",
        "why the answer key can live in the project directory here exactly as it does",
        "in the clean fixture.",
        "",
        "## The seeded defects",
        "",
    ]
    for seed in seeds:
        lines.append(f"### {seed['seed']}. {seed['mode']} — {seed['segment_id']}")
        lines.append("")
        lines.append(f"- Defect: {seed['summary']}.")
        lines.append(f"- Italian: \"{seed['text_it_fragment']}\"")
        for change in seed["changes"]:
            lines.append(f"- English was: \"{change['before']}\"")
            lines.append(f"- English now: \"{change['after']}\"")
        lines.append(f"- Rule broken: {seed['rule']}")
        if seed["catalogue"]:
            lines.append(f"- Catalogue line: {seed['catalogue']}")
        else:
            lines.append(
                "- Catalogue line: none — this is a named trap of the guide, not a "
                "catalogued failure."
            )
        if seed["mechanical_check"]:
            lines.append(
                f"- Also caught mechanically: `{seed['mechanical_check']}` would fail "
                "on this seed. `checks.py` is not run on this fixture."
            )
        else:
            lines.append(
                "- Also caught mechanically: no check reacts. Judgement only."
            )
        if seed["note"]:
            lines.append(f"- Note: {seed['note']}")
        lines.append("")
    lines.extend([
        "## Not seeded here",
        "",
        "The ninth catalogue mode — an antecedent-basis defect in an independent",
        "claim silently repaired — needs a source defect to repair, and this",
        "fixture's independent claim has none. Seeding a repair would mean seeding",
        "the defect into the Italian first, i.e. writing a different source",
        "document. That mode is measured the other way round, as source-quirk recall",
        "on the clean `projects/_fixture`, where the reviewer must report the",
        "deliberate quirks rather than propose their repair.",
        "",
        "## What this fixture does not carry",
        "",
        "- No `state/checks.json`: mechanical results computed on the clean English",
        "  would misdescribe this project, and no review script reads them.",
        "- No deliverables beyond `out/terminology.csv`, which `review_packet.py`",
        "  needs as the delivered glossary. Nothing re-assembles the seeded English.",
        "- `state/flags.json` is the clean fixture's, verbatim: the pipeline's doubt",
        "  record, which the three-way diff compares the findings against. No seed",
        "  adds, removes or resolves a flag.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    seeds, pairs, claims = load_revisions()
    copy_baseline()
    pair_text, claim_parts = derive(TARGET / "state", seeds)
    check_payload(seeds, pairs, claims, pair_text, claim_parts)
    apply_revisions()
    verify(seeds, pair_text, claim_parts)

    (TARGET / SPEC_NAME).write_text(spec_document(seeds), encoding="utf-8")

    print(f"built {TARGET} with {len(seeds)} seeded defects, all verified present:")
    for seed in seeds:
        also = seed["mechanical_check"] or "judgement only"
        print(
            f"  {seed['seed']}. {seed['segment_id']:<7} {seed['mode']:<26} "
            f"{seed['summary']} [{also}]"
        )
    print(f"seed table (machine-readable): {REVISIONS}")
    print(f"seed spec (generated):         {TARGET / SPEC_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
