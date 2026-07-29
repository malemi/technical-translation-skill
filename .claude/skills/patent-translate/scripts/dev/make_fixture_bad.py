#!/usr/bin/env python3
"""Build projects/_fixture_bad — the seeded-defect copy of the fixture.

CONTRACTS.md specifies six mutations of the ENGLISH side that checks.py must
catch. This script applies them deterministically so the integration test is
reproducible from a clean checkout instead of being mutated by hand.

Source and target are hardcoded (projects/_fixture -> projects/_fixture_bad):
the mutations are written against that exact baseline, and a path argument
would only invite pointing this at a real document.

Every mutation asserts that the text it expects is actually there. If the
fixture baseline changes, this script fails loudly rather than silently
producing a weaker test.

Usage:
    make_fixture_bad.py

Run from the repo root, after make_fixture.py, ingest.py and make_fixture_en.py
have produced a complete clean fixture. The target directory is rebuilt from
scratch on every run.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import die, read_json, sha256_text, write_json  # noqa: E402

SOURCE = Path("projects/_fixture")
TARGET = Path("projects/_fixture_bad")

# Copied verbatim from the clean fixture. checks.py and flags.py regenerate the
# rest, and starting without checks.json / flags.json keeps the clean run's MECH
# flags from leaking into the seeded-defect run.
COPIED_FILES = ("terminology.csv",)
COPIED_STATE = ("segments.json", "translations.json", "claims_en.json")


def replace_once(text: str, old: str, new: str, where: str) -> str:
    count = text.count(old)
    if count != 1:
        die(
            f"mutation target not found exactly once in {where}: {old!r} "
            f"(found {count} times). The fixture baseline changed — update "
            "this script."
        )
    return text.replace(old, new)


def pair(translations: dict, pair_id: str) -> dict:
    for item in translations["pairs"]:
        if item["id"] == pair_id:
            return item
    die(f"pair {pair_id} not found in translations.json")


def claim(claims: dict, number: int) -> dict:
    for item in claims["claims"]:
        if item["number"] == number:
            return item
    die(f"claim {number} not found in claims_en.json")


def set_pair_text(item: dict, text: str) -> None:
    item["text_en_deepl"] = text
    item["deepl_para_sha256"] = sha256_text(text)
    item["text_en_final"] = None


def set_claim_text(item: dict, parts: list[str]) -> None:
    item["parts_en"] = parts
    item["text_en"] = "\n".join(parts)


def mutate(translations: dict, claims: dict) -> list[str]:
    """Apply the six CONTRACTS.md mutations; return one line per mutation."""
    applied: list[str] = []

    # 1. Drop a reference sign from a description pair -> numerals_per_segment.
    item = pair(translations, "D-0006")
    set_pair_text(item, replace_once(
        item["text_en_deepl"], "filter assembly (3) comprises",
        "filter assembly comprises", "D-0006"))
    applied.append("1. D-0006: dropped reference sign (3) -> numerals_per_segment")

    # 2. Alter a measured value -> numbers_units.
    item = pair(translations, "D-0007")
    set_pair_text(item, replace_once(
        item["text_en_deepl"], "12.5 bar", "12.7 bar", "D-0007"))
    applied.append("2. D-0007: 12.5 bar -> 12.7 bar -> numbers_units")

    # 3. Swap a locked claim term for a synonym across the whole description,
    #    while the claims keep the locked term -> claim_support.
    hits = 0
    for item in translations["pairs"]:
        if "recirculation pump" in item["text_en_deepl"]:
            set_pair_text(item, item["text_en_deepl"].replace(
                "recirculation pump", "circulation pump"))
            hits += 1
    if hits != 2:
        die(
            f"expected 'recirculation pump' in exactly 2 description pairs, "
            f"found {hits}. The fixture baseline changed — update this script."
        )
    applied.append(
        "3. description: 'recirculation pump' -> 'circulation pump' in "
        f"{hits} pairs -> claim_support")

    # 4. Narrow a claim's dependency range -> claims_graph.
    item = claim(claims, 4)
    set_claim_text(item, [replace_once(
        part, "claims 1 to 3", "claims 1 to 2", "claim 4")
        if "claims 1 to 3" in part else part for part in item["parts_en"]])
    if "claims 1 to 2" not in item["text_en"]:
        die("mutation 4 did not apply to claim 4")
    applied.append("4. claim 4: 'claims 1 to 3' -> 'claims 1 to 2' -> claims_graph")

    # 5. Split a claim into two sentences -> one_sentence_per_claim. The wording
    #    avoids repeating the reference sign (2), so only the sentence check
    #    fires and numerals_per_segment stays clean for this claim.
    item = claim(claims, 2)
    set_claim_text(item, [replace_once(
        part,
        "is made of stainless steel and has a capacity comprised between "
        "5 and 50 liters.",
        "is made of stainless steel. It has a capacity comprised between "
        "5 and 50 liters.",
        "claim 2") for part in item["parts_en"]])
    applied.append("5. claim 2: split into two sentences -> one_sentence_per_claim")

    # 6. Refer to a noun phrase that is never introduced -> antecedent_basis.
    item = claim(claims, 5)
    set_claim_text(item, [replace_once(
        part,
        "connected to the control unit (5).",
        "connected to the control unit (5) and to the pressure regulator.",
        "claim 5") for part in item["parts_en"]])
    applied.append(
        "6. claim 5: added 'the pressure regulator', never introduced -> "
        "antecedent_basis")

    return applied


def main() -> int:
    if not SOURCE.is_dir():
        die(f"clean fixture not found: {SOURCE} (run make_fixture.py first)")
    for name in COPIED_STATE:
        if not (SOURCE / "state" / name).is_file():
            die(
                f"clean fixture is incomplete: {SOURCE / 'state' / name} missing. "
                "Run make_fixture.py, ingest.py and make_fixture_en.py first."
            )

    if TARGET.exists():
        shutil.rmtree(TARGET)
        print(f"removed previous {TARGET}")
    (TARGET / "state").mkdir(parents=True)

    for name in COPIED_FILES:
        shutil.copy2(SOURCE / name, TARGET / name)
    source_docx = SOURCE / "source.docx"
    if source_docx.is_file():
        shutil.copy2(source_docx, TARGET / "source.docx")
    for name in COPIED_STATE:
        shutil.copy2(SOURCE / "state" / name, TARGET / "state" / name)

    translations = read_json(TARGET / "state" / "translations.json")
    claims = read_json(TARGET / "state" / "claims_en.json")
    applied = mutate(translations, claims)
    write_json(TARGET / "state" / "translations.json", translations)
    write_json(TARGET / "state" / "claims_en.json", claims)

    print(f"built {TARGET} with {len(applied)} seeded defects:")
    for line in applied:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
