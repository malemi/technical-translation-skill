#!/usr/bin/env python3
"""Write the canned ENGLISH baseline of the fixture project.

This is test scaffolding, not a translation path. `make_fixture.py` embeds the
Italian side of the synthetic patent; this script embeds the English side the
same way, so the verification battery and `assemble.py` can be exercised from a
clean checkout with no DeepL key and no model run. Real jobs always go through
DeepL — nothing here is wired into the pipeline scripts.

Writes `state/translations.json` and `state/claims_en.json`. Refuses to run on
anything but a fixture project, so it can never fabricate the English side of a
real document.

Usage:
    make_fixture_en.py [--project projects/_fixture]

Run from the repo root. Output is deterministic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import die, read_json, sha256_text, write_json  # noqa: E402

# Fixture data carries a fixed timestamp so re-runs are byte-identical.
FIXTURE_TIMESTAMP = "2026-01-01T00:00:00+00:00"

TARGET_LANG = "EN-US"

TITLE_EN = "Apparatus for the cold extraction of coffee and related extraction method"

# (segment id, English text) in document order. Must cover exactly the segments
# translate_deepl.py would send: everything in the abstract and description
# sections — title and claims excluded.
PAIRS_EN: tuple[tuple[str, str], ...] = (
    ("H-002", "ABSTRACT"),
    ("A-001",
     "Cold extraction coffee apparatus (1) comprising an extraction tank (2) "
     "adapted to hold water and ground coffee, a filter assembly (3) disposed "
     "within the extraction tank (2), and a recirculation pump (4) configured "
     "to circulate water through the filter assembly (3). The apparatus "
     "further comprises a control unit (5) that regulates the water "
     "temperature between 4 °C and 8 °C and the operating pressure up to "
     "12.5 bar. A cold extraction method using said apparatus is also "
     "described."),
    ("H-003", "DESCRIPTION"),
    ("H-004", "TECHNICAL FIELD"),
    ("D-0001",
     "The present invention relates to an apparatus for the cold extraction "
     "of coffee, as well as a method of extraction using said apparatus."),
    ("H-005", "STATE OF THE ART"),
    ("D-0002",
     "Systems for preparing coffee by cold extraction are known, in which "
     "ground coffee is placed in contact with water at room temperature for "
     "extraction times typically ranging from 12 to 24 hours. However, such "
     "systems have high energy consumption and limited aromatic yield. "
     "Furthermore, the aromatic yield is difficult to control."),
    ("H-006", "BRIEF DESCRIPTION OF THE FIGURES"),
    ("D-0003",
     "Figure 1 shows a schematic view of the apparatus according to the "
     "invention."),
    ("D-0004", "Figure 2 shows a cross-section of the filter assembly."),
    ("H-007", "DETAILED DESCRIPTION"),
    ("D-0005",
     "With reference to Figure 1, the apparatus (1) comprises an extraction "
     "tank (2) made of stainless steel, having a capacity of between 5 and "
     "50 liters."),
    ("D-0006",
     "The filter assembly (3) comprises a metal mesh with 100 µm mesh size "
     "and a removable support (3a)."),
    ("D-0007",
     "The recirculation pump (4) is configured to operate at a pressure "
     "between 0.5 bar and 12.5 bar, preferably 2.5 bar."),
    ("D-0008",
     "The control unit (5) includes a temperature sensor (6) and a timer (7). "
     "The tank (2) is maintained at a temperature between 4 °C and 8 °C for "
     "at least 20 minutes."),
    ("D-0009",
     "In a preferred embodiment, the ratio of ground coffee to water is "
     "between 5% and 12.5% by weight."),
    ("D-0010",
     "Of course, without prejudice to the principle of the invention, the "
     "details of the embodiment may vary from those described."),
)

# (id, number, parts, conventions). text_en is the parts joined with "\n".
CLAIMS_EN: tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...] = (
    ("C-01", 1,
     ("1. Apparatus (1) for the cold extraction of coffee, comprising:",
      "an extraction tank (2) adapted to contain water and ground coffee;",
      "a filter assembly (3) arranged inside the extraction tank (2);",
      "a recirculation pump (4) configured to circulate the water through the "
      "filter assembly (3);",
      "characterized in that it further comprises a control unit (5) "
      "configured to maintain the temperature of the water between 4 °C and "
      "8 °C."),
     ("two-part form kept",)),
    ("C-02", 2,
     ("2. Apparatus according to claim 1, wherein the extraction tank (2) is "
      "made of stainless steel and has a capacity comprised between 5 and "
      "50 liters.",),
     ()),
    ("C-03", 3,
     ("3. Apparatus according to claim 2, wherein the filter assembly (3) "
      "comprises a metal mesh with meshes of 100 µm.",),
     ()),
    ("C-04", 4,
     ("4. Apparatus according to any one of claims 1 to 3, wherein the "
      "recirculation pump (4) consists of a variable-speed centrifugal pump.",),
     ("multiple-dependent claim kept",
      "costituita da -> consisting of (closed transition kept)")),
    ("C-05", 5,
     ("5. Apparatus according to the preceding claim, further comprising a "
      "pressure sensor (8) connected to the control unit (5).",),
     ()),
    ("C-06", 6,
     ("6. A method for the cold extraction of coffee by means of an apparatus "
      "according to any one of the preceding claims, comprising the steps of:",
      "introducing water and ground coffee into the extraction tank (2);",
      "circulating the water by means of the recirculation pump (4) for a "
      "time of at least 20 minutes;",
      "maintaining the temperature between 4 °C and 8 °C."),
     ("method-claim step form",)),
)


def check_against_segments(state_dir: Path) -> None:
    """The baseline is only valid for the Italian fixture it was written for."""
    segments_path = state_dir / "segments.json"
    if not segments_path.is_file():
        die(f"run ingest.py first: {segments_path} not found")
    segments = read_json(segments_path)

    expected_pairs = [
        s["id"] for s in segments["segments"]
        if s["section"] in ("abstract", "description")
    ]
    baseline_pairs = [pid for pid, _ in PAIRS_EN]
    if expected_pairs != baseline_pairs:
        die(
            "the Italian fixture no longer matches this English baseline.\n"
            f"  segments.json sends: {expected_pairs}\n"
            f"  baseline covers:     {baseline_pairs}\n"
            "Update PAIRS_EN in this script to match."
        )

    expected_claims = [(c["id"], c["number"]) for c in segments["claims"]]
    baseline_claims = [(cid, number) for cid, number, _, _ in CLAIMS_EN]
    if expected_claims != baseline_claims:
        die(
            "claims changed in the Italian fixture.\n"
            f"  segments.json has: {expected_claims}\n"
            f"  baseline covers:   {baseline_claims}\n"
            "Update CLAIMS_EN in this script to match."
        )


def build_translations() -> dict:
    return {
        "target_lang": TARGET_LANG,
        "title": {"text_en": TITLE_EN},
        "pairs": [
            {
                "id": pair_id,
                "text_en_deepl": text,
                "deepl_para_sha256": sha256_text(text),
                "text_en_final": None,
                "edits": [],
            }
            for pair_id, text in PAIRS_EN
        ],
    }


def build_claims() -> dict:
    return {
        "claims": [
            {
                "id": claim_id,
                "number": number,
                "text_en": "\n".join(parts),
                "parts_en": list(parts),
                "conventions": list(conventions),
                "authored_at": FIXTURE_TIMESTAMP,
            }
            for claim_id, number, parts, conventions in CLAIMS_EN
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Write the canned English baseline of the fixture project."
    )
    ap.add_argument("--project", default="projects/_fixture")
    args = ap.parse_args()

    root = Path(args.project)
    if not root.is_dir():
        die(f"project directory not found: {root}")
    if not root.name.startswith("_fixture"):
        die(
            f"refusing to run on {root}: this script writes canned test data and "
            "is restricted to fixture projects (a directory named _fixture*). "
            "Real translations go through DeepL."
        )

    state = root / "state"
    check_against_segments(state)

    write_json(state / "translations.json", build_translations())
    write_json(state / "claims_en.json", build_claims())

    print(f"wrote {state / 'translations.json'}: {len(PAIRS_EN)} pairs, title set")
    print(f"wrote {state / 'claims_en.json'}: {len(CLAIMS_EN)} claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
