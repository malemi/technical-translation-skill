#!/usr/bin/env python3
"""Ingest a project's source.docx into state/segments.json.

Usage: ingest.py --project projects/<slug> [--source name.docx]
Segments the document (title/abstract/headings/description/claims), parses
claim dependencies, extracts reference numerals and the numeral -> preceding
term map, writes segments.json and prints a one-screen summary. Escalations
are printed but never fail the run (exit 0); real errors exit non-zero.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

import common

SECTION_LEXICON = {
    "TITOLO": "title",
    "RIASSUNTO": "abstract",
    "SOMMARIO": "abstract",
    "DESCRIZIONE": "description",
    "DESCRIZIONE DELL'INVENZIONE": "description",
    "RIVENDICAZIONI": "claims",
}
REQUIRED_SECTIONS = ("title", "abstract", "description", "claims")

CLAIM_START_RE = re.compile(r"^\s*(\d{1,3})\s*[.)\-]\s*")
PARA_NUMBER_RE = re.compile(r"^\s*(\[\d{4}\])")

ID_PAD = {"T": 3, "A": 3, "H": 3, "D": 4, "C": 2}
KIND_PREFIX = {"title": "T", "abstract": "A", "heading": "H",
               "description": "D", "claim": "C"}

MAX_SUBHEADING_LEN = 60


def is_subheading(norm: str) -> bool:
    """Short all-caps line without a final period (description sub-heading)."""
    if not norm or len(norm) > MAX_SUBHEADING_LEN:
        return False
    if norm.endswith("."):
        return False
    if not any(ch.isalpha() for ch in norm):
        return False
    return norm == norm.upper()


class Ingestor:
    def __init__(self, paragraphs, paragraph_numbers=None):
        self.paragraphs = paragraphs
        # Word-rendered list labels by body-paragraph index. A literal "[0001]"
        # typed into the text still wins; this covers the far commoner case of
        # automatic numbering, which is invisible in the paragraph text.
        self.paragraph_numbers = paragraph_numbers or {}
        self.segments: list[dict] = []
        self.claims: list[dict] = []
        self.claim_texts: dict[str, str] = {}
        self.counters = {p: 0 for p in ID_PAD}
        self.warnings: list[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] += 1
        return f"{prefix}-{self.counters[prefix]:0{ID_PAD[prefix]}d}"

    def add_segment(self, kind: str, section: str, indices: list[int],
                    style: str, text: str, parts=None) -> dict:
        m = PARA_NUMBER_RE.match(text) if kind != "claim" else None
        if m is not None:
            para_number = m.group(1)
        elif kind == "claim":
            para_number = None
        else:
            para_number = self.paragraph_numbers.get(indices[0]) if indices else None
        segment = {
            "id": self.next_id(KIND_PREFIX[kind]),
            "kind": kind,
            "section": section,
            "docx_indices": indices,
            "style": style,
            "text_it": text,
            "para_number": para_number,
            "parts_it": parts,
        }
        self.segments.append(segment)
        return segment

    def run(self) -> None:
        boundary_sections = set()
        for _, text, _ in self.paragraphs:
            section = SECTION_LEXICON.get(common.normalize(text).upper())
            if section:
                boundary_sections.add(section)

        current_section = None
        current_claim = None

        def close_claim():
            nonlocal current_claim
            if current_claim is None:
                return
            text_it = "\n".join(current_claim["parts"])
            segment = self.add_segment(
                "claim", "claims", current_claim["indices"],
                current_claim["style"], text_it, parts=current_claim["parts"],
            )
            self.claims.append({
                "id": segment["id"],
                "number": current_claim["number"],
                "depends_on": [],
                "dependency_phrase": None,
                "multiple": False,
                "needs_review": False,
            })
            self.claim_texts[segment["id"]] = text_it
            current_claim = None

        for index, raw, style in self.paragraphs:
            norm = common.normalize(raw)
            if not norm:
                continue

            new_section = SECTION_LEXICON.get(norm.upper())
            if new_section:
                close_claim()
                current_section = new_section
                self.add_segment("heading", new_section, [index], style, raw)
                continue

            if current_section == "claims":
                m = CLAIM_START_RE.match(raw)
                if m:
                    close_claim()
                    current_claim = {
                        "number": int(m.group(1)),
                        "indices": [index],
                        "parts": [raw],
                        "style": style,
                    }
                elif current_claim is not None:
                    current_claim["indices"].append(index)
                    current_claim["parts"].append(raw)
                else:
                    self.warn(
                        f"ESCALATION: paragraph before first claim in claims "
                        f"section kept as heading (docx index {index}): {norm[:60]}"
                    )
                    self.add_segment("heading", "claims", [index], style, raw)
                continue

            if current_section == "title":
                self.add_segment("title", "title", [index], style, raw)
            elif current_section == "abstract":
                self.add_segment("abstract", "abstract", [index], style, raw)
            elif current_section == "description":
                if is_subheading(norm):
                    self.add_segment("heading", "description", [index], style, raw)
                else:
                    self.add_segment("description", "description", [index],
                                     style, raw)
            else:  # before any section heading
                has_title = any(s["kind"] == "title" for s in self.segments)
                if "title" not in boundary_sections and not has_title:
                    self.warn(
                        "WARNING: no TITOLO heading; first paragraph before any "
                        "section heading taken as title"
                    )
                    self.add_segment("title", "title", [index], style, raw)
                else:
                    self.warn(
                        f"WARNING: paragraph before first section heading kept "
                        f"as description (docx index {index}): {norm[:60]}"
                    )
                    self.add_segment("description", "description", [index],
                                     style, raw)
        close_claim()

        self.parse_claims()
        for name in REQUIRED_SECTIONS:
            if name == "claims":
                present = bool(self.claims)
            else:
                present = any(s["kind"] == name for s in self.segments) or (
                    name == "description"
                    and any(s["section"] == "description" for s in self.segments)
                )
            if not present:
                self.warn(f"ESCALATION: missing section {name}")

    def parse_claims(self) -> None:
        expected = 1
        for claim in self.claims:
            number = claim["number"]
            if number != expected:
                self.warn(
                    f"WARNING: claim numbering not strictly increasing by 1: "
                    f"got {number}, expected {expected}"
                )
                claim["needs_review"] = True
            expected = number + 1

            text = self.claim_texts[claim["id"]]
            deps, phrase = common.parse_dependency_it(text, number)
            claim["depends_on"] = deps
            claim["dependency_phrase"] = phrase
            claim["multiple"] = bool(deps) and len(deps) > 1
            if deps is None:
                claim["needs_review"] = True
                norm = common.normalize(text)
                mention = re.search(r"rivendicazion", norm, re.IGNORECASE)
                start = max(0, mention.start() - 40)
                snippet = norm[start:mention.start() + 60]
                self.warn(
                    f"ESCALATION: claim {number} dependency unparsed: …{snippet}…"
                )

    def numerals(self) -> dict:
        by_segment = {}
        term_map: dict[str, list[str]] = {}
        for segment in self.segments:
            found = common.extract_numerals(segment["text_it"])
            if found:
                by_segment[segment["id"]] = sorted(
                    found, key=common.numeral_sort_key
                )
            for numeral, phrase in common.numeral_term_phrases(
                    segment["text_it"], "it"):
                if phrase is None:
                    continue
                phrases = term_map.setdefault(numeral, [])
                if phrase not in phrases:
                    phrases.append(phrase)
        term_map = {
            k: term_map[k]
            for k in sorted(term_map, key=common.numeral_sort_key)
        }
        return {"by_segment": by_segment, "term_map_it": term_map}


def print_summary(paths, ingestor: Ingestor, numerals: dict,
                  total_paragraphs: int) -> None:
    kind_counts = Counter(s["kind"] for s in ingestor.segments)
    non_empty = sum(
        1 for _, text, _ in ingestor.paragraphs if common.normalize(text)
    )
    print(f"Ingested {paths['source']} -> {paths['segments']}")
    print(f"  paragraphs: {total_paragraphs} total, {non_empty} non-empty")
    kinds = ", ".join(
        f"{kind} {kind_counts[kind]}"
        for kind in ("title", "abstract", "heading", "description", "claim")
        if kind_counts[kind]
    )
    print(f"  segments: {len(ingestor.segments)} ({kinds})")

    print("Claim dependency graph:")
    if not ingestor.claims:
        print("  (no claims)")
    for claim in ingestor.claims:
        deps = claim["depends_on"]
        if deps is None:
            desc = "UNPARSED (needs review)"
        elif not deps:
            desc = "independent"
        else:
            desc = f"depends on {deps}" + (" (multiple)" if claim["multiple"] else "")
        review = "  [needs_review]" if claim["needs_review"] else ""
        print(f"  {claim['id']} claim {claim['number']}: {desc}{review}")

    print("Numeral inventory:")
    counts = Counter()
    for nums in numerals["by_segment"].values():
        counts.update(nums)
    if not counts:
        print("  (no reference numerals)")
    for numeral in sorted(counts, key=common.numeral_sort_key):
        terms = numerals["term_map_it"].get(numeral)
        terms_desc = " | ".join(terms) if terms else "(no preceding term found)"
        print(f"  {numeral}: {counts[numeral]} occurrence(s)  terms: {terms_desc}")

    if ingestor.warnings:
        print("Warnings:")
        for warning in ingestor.warnings:
            print(f"  {warning}")
    else:
        print("Warnings: none")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True,
                        help="project directory, e.g. projects/_fixture")
    parser.add_argument("--source", help="source docx name inside the project")
    args = parser.parse_args()

    paths = common.project_paths(args.project, source=args.source)
    paragraphs = common.iter_body_paragraphs(paths["source"])
    paragraph_numbers, numbering_warnings = common.iter_paragraph_numbers(paths["source"])

    ingestor = Ingestor(paragraphs, paragraph_numbers)
    for message in numbering_warnings:
        ingestor.warn(message)
    ingestor.run()
    numerals = ingestor.numerals()

    data = {
        "meta": {
            "source_file": paths["source"].name,
            "ingested_at": common.now_iso(),
            "language": "it",
            "counts": {
                "segments": len(ingestor.segments),
                "claims": len(ingestor.claims),
            },
        },
        "segments": ingestor.segments,
        "claims": ingestor.claims,
        "numerals": numerals,
    }
    common.write_json(paths["segments"], data)

    violations = common.validate_file(paths["segments"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}")
        common.die("ingest produced an invalid segments.json (bug)")

    print_summary(paths, ingestor, numerals, total_paragraphs=len(paragraphs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
