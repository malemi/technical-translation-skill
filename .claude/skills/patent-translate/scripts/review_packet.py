#!/usr/bin/env python3
"""Build the blind review packet of a patent-translate project.

Usage: review_packet.py build --project projects/<slug>
       review_packet.py --project projects/<slug>       (the same command)

Emits <project>/review/packet/ with exactly three files: pairs.json (one entry
per segment: id, kind, section, the Italian, the delivered English), a byte copy
of references/style-guide.md, and terminology.csv reduced to the columns that
state what the locked term is. A blind review pass can then name that one
directory and no other path in the repo.

The packet is the mechanical guarantee of blindness (CONTRACTS.md, "FORBIDDEN in
the packet"). It carries no flag, no check result, no edit reason, no
back-translation, no terminology report; it does not record whether a segment's
English came from text_en_final or from text_en_deepl, because a pair carrying a
final is a pair the pipeline already doubted and exposing that anchors the
reviewer on the pipeline's own conclusions; and it drops the glossary's
`rationale`, `status` and `flag` columns, which carry the same doubts in prose
inside a file that is otherwise legitimate packet content.

Deterministic: same state in, byte-identical packet out. No timestamp, no hash
and no run id anywhere inside the packet, so a golden-output assertion needs no
field masking. The state digest that proves the blind phase wrote nothing is
printed, never stored in the packet.

Run from the repo root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
from pathlib import Path

import checks
import common

# The style guide is a repo file next to this script's package, not project
# state: resolve it from the script location so the packet can never be built
# against a different guide than the one this skill ships.
STYLE_GUIDE = Path(__file__).resolve().parent.parent / "references" / "style-guide.md"

# Canonical section order for meta.counts.by_section (the segments.json enum
# order, which is also document order). All four keys are always emitted: a
# zero is a signal, and a fixed key set keeps the file shape stable.
SECTION_ORDER = ("title", "abstract", "description", "claims")

# The three files the packet consists of, and the only ones this builder owns.
PACKET_FILES = ("pairs.json", "style-guide.md", "terminology.csv")

# The glossary columns the packet carries: what the locked term IS, never why it
# was chosen and never whether we doubted it. `rationale`, `status` and `flag`
# are deliberately absent — see project_glossary().
PACKET_GLOSSARY_COLUMNS = ("term_it", "variants_it", "term_en", "variants_en",
                           "category", "in_claims")


def is_section_marker(segment: dict) -> bool:
    """True for the TITOLO / RIVENDICAZIONI boundary paragraphs.

    translate_deepl.py deletes the title paragraphs and the whole claims section
    before uploading, so these two headings have no English anywhere in the
    pipeline: assemble.py renders the title as Heading 1 and a literal "CLAIMS"
    heading instead of translating them, and checks.py `structure` exempts them
    from coverage for that same reason. They are section markers of the Italian
    source rather than translated content, so the packet omits them; every other
    segment must carry a delivered English text or this build fails.
    """
    return segment["kind"] == "heading" and segment["section"] in ("title", "claims")


def missing_inputs(paths: dict) -> list[str]:
    """Every absent input, as a gap line. Never stops at the first."""
    gaps = []
    for key in ("segments", "translations", "claims_en"):
        path = Path(paths[key])
        if not path.is_file():
            gaps.append(f"state file absent: {path}")
    delivered = Path(paths["out"]) / "terminology.csv"
    if not delivered.is_file():
        gaps.append(f"delivered glossary absent, run assemble.py first: {delivered}")
    if not Path(paths["terminology"]).is_file():
        gaps.append(f"project glossary absent: {paths['terminology']}")
    if not STYLE_GUIDE.is_file():
        gaps.append(f"style guide absent: {STYLE_GUIDE}")
    return gaps


def project_glossary(paths: dict) -> tuple[bytes, list[str]]:
    """The packet's glossary bytes, plus a gap line if the delivery is stale.

    NOT a byte copy of the delivered glossary. The glossary states both WHAT was
    decided and WHY, and two of its nine columns are the pipeline's own doubts in
    prose: `flag` is "empty when no doubt" by its own schema, and `rationale`
    records the reasoning behind a choice. On a real job the `flag` column names
    the open TERM escalations outright ('"agitator" chosen over "stirrer";
    confirm.') and on the fixtures it names the failing mechanical checks. A
    reviewer reading those does not re-derive the terminology doubts, it confirms
    the list we handed it.

    So the packet carries only the columns that state what the locked term IS.
    The reviewer needs those: consistency under PCT Rule 10.2 is checkable only
    against the locked glossary. It does not need to know where we already
    doubted. Column order and row order follow the delivered file.
    """
    delivered = Path(paths["out"]) / "terminology.csv"
    working = Path(paths["terminology"])
    gaps = []
    if delivered.read_bytes() != working.read_bytes():
        gaps.append(
            f"{delivered} differs from {working}: the delivered glossary is "
            "stale, re-run assemble.py"
        )
    return project_glossary_bytes(delivered), gaps


def project_glossary_bytes(source: Path) -> bytes:
    """`source` reduced to PACKET_GLOSSARY_COLUMNS, as CSV bytes.

    Fails loud on a glossary whose header lacks a column the packet must carry:
    silently emitting a narrower table would hide a schema change behind a
    reviewer who simply never saw the term.
    """
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        absent = [c for c in PACKET_GLOSSARY_COLUMNS if c not in header]
        if absent:
            common.die(f"{source}: glossary header lacks column(s) {absent}")
        rows = list(reader)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(PACKET_GLOSSARY_COLUMNS),
                            lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row[c] for c in PACKET_GLOSSARY_COLUMNS})
    return buffer.getvalue().encode("utf-8")


def foreign_packet_entries(packet_dir: Path) -> list[str]:
    """Gap lines for anything in the packet directory this builder does not own.

    Blindness is a property of the DIRECTORY, not of the three files inside it: a
    blind pass is told to read `<project>/review/packet/` and no other path, so a
    leftover there is part of the packet whatever it is — an earlier run's notes,
    a `.tmp` from an interrupted write, an answer key someone copied in. This
    builder never deletes project data, so the only safe behaviour left is to
    refuse and say which file to move.
    """
    if not packet_dir.is_dir():
        return []
    return [
        f"{packet_dir / entry.name}: not part of the packet, and a blind pass "
        "reads this directory whole. Move it outside the project and rebuild."
        for entry in sorted(packet_dir.iterdir(), key=lambda p: p.name)
        if entry.name not in PACKET_FILES
    ]


def build_entries(st: checks.State) -> tuple[list[dict], list[str], list[str]]:
    """(entries, omitted section-marker ids, gaps).

    Entry keys are exactly id, kind, section, text_it, text_en — no sixth key,
    now or later. text_it is the segment's raw text (claims: the parts already
    joined with a newline), never normalized.
    """
    pairs_by_id = {pair["id"]: pair for pair in st.pairs}
    claims_by_id = {claim["id"]: claim for claim in st.claims_en["claims"]}
    title_en = st.translations["title"].get("text_en")

    entries: list[dict] = []
    omitted: list[str] = []
    gaps: list[str] = []
    if title_en is None:
        gaps.append("translations.json: title.text_en is null")

    for segment in st.segments:
        seg_id, kind, section = segment["id"], segment["kind"], segment["section"]
        if section not in SECTION_ORDER:
            common.die(f"segment {seg_id}: unknown section {section!r}")
        if is_section_marker(segment):
            omitted.append(seg_id)
            continue
        if kind == "title":
            if title_en is None:
                continue  # reported once above; do not repeat it per segment
            text_en, source = title_en, "translations.json title.text_en"
        elif kind == "claim":
            claim = claims_by_id.get(seg_id)
            text_en = claim["text_en"] if claim is not None else None
            source = "claims_en.json"
        else:
            pair = pairs_by_id.get(seg_id)
            # State.pair_en is the single definition of the delivered English:
            # text_en_final when set, else text_en_deepl. Which one it was is
            # deliberately not recorded here.
            text_en = checks.State.pair_en(pair) if pair is not None else None
            source = "translations.json pairs"
        if text_en is None:
            gaps.append(f"{seg_id} ({kind}): no delivered English in {source}")
            continue
        if common.normalize(text_en) == "":
            gaps.append(f"{seg_id} ({kind}): delivered English is empty in {source}")
            continue
        entries.append({
            "id": seg_id,
            "kind": kind,
            "section": section,
            "text_it": segment["text_it"],
            "text_en": text_en,
        })
    return entries, omitted, gaps


def packet_document(project_name: str, entries: list[dict]) -> dict:
    by_section = {
        section: sum(1 for e in entries if e["section"] == section)
        for section in SECTION_ORDER
    }
    return {
        "meta": {
            "project": project_name,
            "counts": {"entries": len(entries), "by_section": by_section},
        },
        "entries": entries,
    }


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    """Byte copy written like common.write_json does: tmp file then rename, so
    a re-run never exposes a half-written packet file to a review pass."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def state_sha256(state_dir: Path) -> str:
    """Digest over the state directory, per CONTRACTS.md: for every file
    directly in state/, sorted by name, the file name encoded UTF-8, a NUL
    byte, the file bytes, a NUL byte.

    Every state file participates, flags.json and checks.json included: their
    bytes are hashed and never interpreted, which is why this does not breach
    the anti-anchoring rule. The digest is what the "blind phase writes nothing
    to state/" policy is verified with — print it, rerun after the blind phase,
    compare.
    """
    digest = hashlib.sha256()
    files = sorted((p for p in state_dir.iterdir() if p.is_file()),
                   key=lambda p: p.name)
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def report_gaps(gaps: list[str]) -> int:
    for gap in gaps:
        print(f"FAIL {gap}")
    print(f"{len(gaps)} gap(s): no packet written")
    return 1


def cmd_build(args) -> int:
    paths = common.project_paths(args.project, need_source=False)

    gaps = missing_inputs(paths)
    if gaps:
        return report_gaps(gaps)

    packet_dir = Path(paths["root"]) / "review" / "packet"

    st = checks.State(paths)
    entries, omitted, gaps = build_entries(st)
    terminology_bytes, stale = project_glossary(paths)
    gaps.extend(stale)
    gaps.extend(foreign_packet_entries(packet_dir))
    if gaps:
        return report_gaps(gaps)

    style_guide_bytes = STYLE_GUIDE.read_bytes()
    document = packet_document(Path(paths["root"]).name, entries)

    packet_dir.mkdir(parents=True, exist_ok=True)
    common.write_json(packet_dir / "pairs.json", document)
    write_bytes_atomic(packet_dir / "style-guide.md", style_guide_bytes)
    write_bytes_atomic(packet_dir / "terminology.csv", terminology_bytes)

    counts = document["meta"]["counts"]
    print(f"packet -> {packet_dir}")
    print(f"  pairs.json       {counts['entries']} entries: "
          + ", ".join(f"{s} {n}" for s, n in counts["by_section"].items()))
    print(f"  style-guide.md   {len(style_guide_bytes)} bytes")
    print(f"  terminology.csv  {len(terminology_bytes)} bytes "
          f"({len(PACKET_GLOSSARY_COLUMNS)} of the delivered columns; "
          "rationale, status and flag withheld)")
    if omitted:
        print(f"  omitted {len(omitted)} untranslated section marker(s): "
              + ", ".join(omitted))
    print(f"state_sha256 {state_sha256(Path(paths['state']))}")
    return 0


def cmd_state_digest(args) -> int:
    """Print the state digest and nothing else.

    The blind phase is verified by comparing this digest before and after it. Do
    that with THIS subcommand, never by rebuilding: a rebuild overwrites
    packet/pairs.json, so in the one case the check exists for — something did
    write to state/ — it destroys the text the reviewer actually worked from, and
    the run is void with no way left to diagnose why.
    """
    paths = common.project_paths(args.project, need_source=False)
    state_dir = Path(paths["state"])
    if not state_dir.is_dir():
        common.die(f"state directory not found: {state_dir}")
    print(f"state_sha256 {state_sha256(state_dir)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the blind review packet in <project>/review/packet/."
    )
    parser.add_argument("--project", help="project directory, e.g. projects/_fixture")
    sub = parser.add_subparsers(dest="command")
    build = sub.add_parser("build", help="build <project>/review/packet/")
    # SUPPRESS keeps the top-level value when the subcommand omits --project, so
    # both spellings work: "review_packet.py build --project P" (the execution
    # plan) and "review_packet.py --project P" (CONTRACTS.md).
    build.add_argument("--project", default=argparse.SUPPRESS,
                       help="project directory, e.g. projects/_fixture")
    digest = sub.add_parser("state-digest",
                            help="print state_sha256 without building anything")
    digest.add_argument("--project", default=argparse.SUPPRESS,
                        help="project directory, e.g. projects/_fixture")
    args = parser.parse_args()
    if not args.project:
        parser.error("--project is required")
    if args.command == "state-digest":
        return cmd_state_digest(args)
    return cmd_build(args)


if __name__ == "__main__":
    raise SystemExit(main())
