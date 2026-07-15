#!/usr/bin/env python3
"""Mechanical verification battery for a patent-translate project.

Usage: checks.py run --project projects/<slug>

Runs the 13 mechanical checks defined in CONTRACTS.md over the project state,
writes state/checks.json, and records one MECH flag per failing item (via the
flags.py dedup logic, imported not shelled). Warnings never produce flags.
Exit 0 unless the run itself crashes: check FAILURES are data, not exits.

Every check is independent and self-skips when its required inputs are absent
(e.g. claims_en.json not yet authored) so the battery can run at any pipeline
stage without crashing.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import common
import flags as flags_mod

# --------------------------------------------------------------------------
# residue lexicon (check 11): Italian function words/phrases that must not
# survive in English text.
RESIDUE_TOKENS = (
    "della", "delle", "degli", "nella", "nelle", "mediante", "nonché",
    "ovvero", "inoltre", "qualsiasi", "rivendicazione", "rivendicazioni",
    "secondo la", "in cui",
)
_RESIDUE_RES = tuple(
    (tok, re.compile(r"(?<!\w)" + re.escape(tok) + r"(?!\w)", re.IGNORECASE))
    for tok in RESIDUE_TOKENS
)

# antecedent-basis tuning (check 9): preamble nouns and inherited-by-reference
# preamble that never need an explicit antecedent (CONTRACTS.md check 9).
_ANTECEDENT_ALLOWLIST = {"apparatus", "method", "use", "claim", "claims",
                         "step", "steps"}
_NP_STOP = {
    "a", "an", "the", "said", "each", "one", "this", "that", "these", "those",
    "any", "of", "with", "for", "to", "in", "on", "at", "by", "from",
    "between", "through", "into", "within", "and", "or", "which", "wherein",
    "whereby", "is", "are", "being", "comprises", "comprising", "including",
    "includes", "having", "consisting", "configured", "adapted", "arranged",
    "connected", "provided", "made", "maintained", "constituted", "disposed",
    "characterized",
}
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")

CHECK_ORDER = (
    "paragraph_parity",
    "numerals_per_segment",
    "numeral_term_consistency",
    "numbers_units",
    "claims_graph",
    "one_sentence_per_claim",
    "claim_support",
    "glossary_adherence",
    "antecedent_basis",
    "abstract_length",
    "residue",
    "structure",
    "decimal_comma_audit",
)


# --------------------------------------------------------------------------
# state container


class State:
    """Lazily-loaded, read-only view of the project state a check may need."""

    def __init__(self, paths):
        self.paths = paths
        self.segments_doc = common.read_json(paths["segments"])  # required
        self.segments = self.segments_doc["segments"]
        self.claims_meta = self.segments_doc["claims"]
        self.numerals = self.segments_doc["numerals"]
        self.by_id = {s["id"]: s for s in self.segments}

        self.translations = None
        if Path(paths["translations"]).is_file():
            self.translations = common.read_json(paths["translations"])
        self.claims_en = None
        if Path(paths["claims_en"]).is_file():
            self.claims_en = common.read_json(paths["claims_en"])
        self.terminology = _load_terminology(paths["terminology"])

    # -- pairs -----------------------------------------------------------
    @property
    def pairs(self):
        return self.translations["pairs"] if self.translations else []

    @staticmethod
    def pair_en(pair):
        """Final English if a human/model set it, else the DeepL output."""
        final = pair.get("text_en_final")
        return final if final is not None else pair["text_en_deepl"]

    def pair_alignments(self):
        """(segment_id, text_it, text_en) for each translation pair whose id
        resolves to a segment; unknown ids are reported by paragraph_parity."""
        out = []
        for pair in self.pairs:
            seg = self.by_id.get(pair["id"])
            if seg is None:
                continue
            out.append((pair["id"], seg["text_it"], self.pair_en(pair)))
        return out

    def claim_alignments(self):
        """(segment_id, text_it, text_en, number) per authored English claim."""
        out = []
        if not self.claims_en:
            return out
        meta_by_id = {c["id"]: c for c in self.claims_meta}
        for c in self.claims_en["claims"]:
            seg = self.by_id.get(c["id"])
            if seg is None:
                continue
            number = c.get("number", meta_by_id.get(c["id"], {}).get("number"))
            out.append((c["id"], seg["text_it"], c["text_en"], number))
        return out

    def description_en_blob(self):
        """Normalized, lower-cased concatenation of all English pair texts
        (the 'EN description' claim_support/glossary check against)."""
        return " ".join(
            common.normalize(self.pair_en(p)).lower() for p in self.pairs
        )


def _load_terminology(path):
    """Parse terminology.csv into a list of row dicts, or None if absent.

    Only the columns the checks need are surfaced; the header is validated by
    glossary.py, so here a missing expected column is a hard error (fail loud).
    """
    path = Path(path)
    if not path.is_file():
        return None
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"term_it", "variants_it", "term_en", "variants_en",
                    "in_claims", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            common.die(f"terminology.csv missing columns: {sorted(missing)}")
        rows = []
        for raw in reader:
            rows.append({
                "term_it": raw["term_it"],
                "variants_it": [v for v in raw["variants_it"].split("|") if v],
                "term_en": raw["term_en"],
                "variants_en": [v for v in raw["variants_en"].split("|") if v],
                "in_claims": raw["in_claims"].strip().lower(),
                "status": raw["status"].strip().lower(),
            })
    return rows


# --------------------------------------------------------------------------
# result helpers


def _result(check, status, failures=None, stats=None, data=None):
    return {
        "check": check,
        "status": status,
        "failures": failures or [],
        "stats": stats or {},
        "data": data,
    }


def _contains(haystack_norm_lower: str, needle: str) -> bool:
    return common.normalize(needle).lower() in haystack_norm_lower


# --------------------------------------------------------------------------
# individual checks. Each returns a result dict.


def check_paragraph_parity(st: State):
    if st.translations is None:
        return _result("paragraph_parity", "skip",
                       stats={"reason": "translations.json missing"})
    expected_ids = [s["id"] for s in st.segments
                    if s["section"] in ("abstract", "description")]
    pair_ids = [p["id"] for p in st.pairs]
    failures = []
    unknown = [pid for pid in pair_ids if pid not in st.by_id]
    for pid in unknown:
        failures.append({"segment_id": pid,
                         "detail": f"pair id {pid} not present in segments.json"})
    dupes = sorted({pid for pid in pair_ids if pair_ids.count(pid) > 1})
    for pid in dupes:
        failures.append({"segment_id": pid,
                         "detail": f"pair id {pid} appears more than once"})
    missing = [sid for sid in expected_ids if sid not in pair_ids]
    for sid in missing:
        failures.append({"segment_id": sid,
                         "detail": f"expected sent-segment {sid} has no pair"})
    extra = [pid for pid in pair_ids
             if pid in st.by_id and pid not in expected_ids]
    for pid in extra:
        failures.append({"segment_id": pid,
                         "detail": f"pair {pid} is not a sent-segment "
                                   "(not abstract/description)"})
    stats = {"pairs": len(pair_ids), "expected": len(expected_ids)}
    status = "fail" if failures else "pass"
    return _result("paragraph_parity", status, failures, stats)


def check_numerals_per_segment(st: State):
    if st.translations is None and not st.claims_en:
        return _result("numerals_per_segment", "skip",
                       stats={"reason": "no translations.json or claims_en.json"})
    failures = []
    checked = 0
    for sid, text_it, text_en in st.pair_alignments():
        checked += 1
        it = Counter(common.extract_numerals(text_it))
        en = Counter(common.extract_numerals(text_en))
        if it != en:
            failures.append({"segment_id": sid,
                             "detail": _numeral_detail(it, en)})
    for sid, text_it, text_en, _ in st.claim_alignments():
        checked += 1
        it = Counter(common.extract_numerals(text_it))
        en = Counter(common.extract_numerals(text_en))
        if it != en:
            failures.append({"segment_id": sid,
                             "detail": _numeral_detail(it, en)})
    status = "fail" if failures else "pass"
    return _result("numerals_per_segment", status, failures,
                   stats={"segments_checked": checked})


def _numeral_detail(it: Counter, en: Counter) -> str:
    only_it = sorted((it - en).elements(), key=common.numeral_sort_key)
    only_en = sorted((en - it).elements(), key=common.numeral_sort_key)
    return (f"numerals differ: only in IT {only_it or '[]'}, "
            f"only in EN {only_en or '[]'}")


def check_numeral_term_consistency(st: State):
    term_map_it = st.numerals.get("term_map_it", {})
    term_map_en: dict[str, list[str]] = {}
    for _, _, text_en in st.pair_alignments():
        _accumulate_en_terms(term_map_en, text_en)
    for _, _, text_en, _ in st.claim_alignments():
        _accumulate_en_terms(term_map_en, text_en)

    failures = []
    all_numerals = sorted(set(term_map_it) | set(term_map_en),
                          key=common.numeral_sort_key)
    data_rows = []
    for numeral in all_numerals:
        it_terms = term_map_it.get(numeral, [])
        en_terms = term_map_en.get(numeral, [])
        data_rows.append({"numeral": numeral, "it_terms": it_terms,
                          "en_terms": en_terms})
        if len(en_terms) > 1:
            failures.append({
                "segment_id": None,
                "detail": f"numeral ({numeral}) maps to >1 EN phrase: "
                          f"{en_terms}",
            })
        elif len(it_terms) > 1:
            failures.append({
                "segment_id": None,
                "detail": f"numeral ({numeral}) inconsistent already in IT "
                          f"source: {it_terms}",
            })
    status = "warn" if failures else "pass"
    return _result("numeral_term_consistency", status, failures,
                   data={"rows": data_rows})


def _accumulate_en_terms(term_map_en: dict, text_en: str):
    for numeral, phrase in common.numeral_term_phrases(text_en, "en"):
        if phrase is None:
            continue
        bucket = term_map_en.setdefault(numeral, [])
        if phrase not in bucket:
            bucket.append(phrase)


def check_numbers_units(st: State):
    if st.translations is None and not st.claims_en:
        return _result("numbers_units", "skip",
                       stats={"reason": "no translations.json or claims_en.json"})
    failures = []
    audit = []
    for sid, text_it, text_en in st.pair_alignments():
        audit.append(_numbers_row(sid, text_it, text_en, failures))
    for sid, text_it, text_en, _ in st.claim_alignments():
        audit.append(_numbers_row(sid, text_it, text_en, failures))
    status = "fail" if failures else "pass"
    return _result("numbers_units", status, failures,
                   stats={"segments_checked": len(audit)},
                   data={"rows": audit})


def _numbers_row(sid, text_it, text_en, failures):
    it = common.extract_numbers_units(text_it, "it")
    en = common.extract_numbers_units(text_en, "en")
    ok = Counter(it) == Counter(en)
    if not ok:
        only_it = list((Counter(it) - Counter(en)).elements())
        only_en = list((Counter(en) - Counter(it)).elements())
        failures.append({
            "segment_id": sid,
            "detail": f"(number,unit) differ: only IT {only_it}, "
                      f"only EN {only_en}",
        })
    return {"segment": sid,
            "it": [list(t) for t in it],
            "en": [list(t) for t in en],
            "ok": ok}


def check_claims_graph(st: State):
    if not st.claims_en:
        return _result("claims_graph", "skip",
                       stats={"reason": "claims_en.json missing"})
    it_deps_by_number = {c["number"]: (c.get("depends_on") or [])
                         for c in st.claims_meta}
    failures = []
    rows = []
    for cid, _, text_en, number in st.claim_alignments():
        en_deps, _ = common.parse_dependency_en(text_en, number)
        it_deps = it_deps_by_number.get(number, [])
        multiple = en_deps is not None and len(en_deps) > 1
        rows.append({"number": number, "it_deps": it_deps,
                     "en_deps": en_deps, "multiple": multiple})
        if en_deps is None:
            failures.append({
                "segment_id": cid,
                "detail": f"claim {number}: EN dependency phrase unparseable",
            })
        elif sorted(en_deps) != sorted(it_deps):
            failures.append({
                "segment_id": cid,
                "detail": f"claim {number}: EN deps {sorted(en_deps)} != "
                          f"IT deps {sorted(it_deps)}",
            })
    status = "fail" if failures else "pass"
    return _result("claims_graph", status, failures, data={"rows": rows})


_CLAIM_PREFIX_RE = re.compile(r"^\s*\d{1,3}\s*[.)\-]\s*")
_DECIMAL_DOT_RE = re.compile(r"(?<=\d)\.(?=\d)")


def check_one_sentence_per_claim(st: State):
    if not st.claims_en:
        return _result("one_sentence_per_claim", "skip",
                       stats={"reason": "claims_en.json missing"})
    failures = []
    for cid, _, text_en, number in st.claim_alignments():
        body = _CLAIM_PREFIX_RE.sub("", text_en, count=1)
        # decimal points ("12.5") are not sentence terminators
        stripped = _DECIMAL_DOT_RE.sub("\x00", body)
        terminators = [i for i, ch in enumerate(stripped) if ch in ".!?"]
        trailing = stripped.rstrip()
        final_ok = bool(trailing) and trailing[-1] in ".!?"
        if len(terminators) != 1 or not final_ok:
            failures.append({
                "segment_id": cid,
                "detail": f"claim {number}: expected exactly one terminator at "
                          f"the end, found {len(terminators)}",
            })
    status = "fail" if failures else "pass"
    return _result("one_sentence_per_claim", status, failures)


def check_claim_support(st: State):
    if st.terminology is None:
        return _result("claim_support", "skip",
                       stats={"reason": "terminology.csv missing"})
    if not st.claims_en:
        return _result("claim_support", "skip",
                       stats={"reason": "claims_en.json missing"})
    locked = [r for r in st.terminology if r["status"] == "locked"]
    if not locked:
        return _result("claim_support", "skip",
                       stats={"reason": "no locked terminology rows"})
    desc = st.description_en_blob()
    failures = []
    # (a) locked in_claims=yes rows must appear in the EN description.
    for row in locked:
        if row["in_claims"] != "yes":
            continue
        if not any(_contains(desc, v) for v in row["variants_en"]):
            failures.append({
                "segment_id": None,
                "detail": f"locked claim term '{row['term_en']}' has no EN "
                          "variant in the description",
            })
    # (b) every EN variant used in a claim must also occur in the description.
    for cid, _, text_en, number in st.claim_alignments():
        blob = common.normalize(text_en).lower()
        for row in locked:
            used = [v for v in row["variants_en"] if _contains(blob, v)]
            if used and not any(_contains(desc, v) for v in row["variants_en"]):
                failures.append({
                    "segment_id": cid,
                    "detail": f"claim {number} uses '{row['term_en']}' "
                              "but it never occurs in the EN description",
                })
    status = "fail" if failures else "pass"
    return _result("claim_support", status, failures)


def check_glossary_adherence(st: State):
    if st.terminology is None:
        return _result("glossary_adherence", "skip",
                       stats={"reason": "terminology.csv missing"})
    failures = []
    aligned = [(sid, it, en) for sid, it, en in st.pair_alignments()]
    aligned += [(sid, it, en) for sid, it, en, _ in st.claim_alignments()]
    for sid, text_it, text_en in aligned:
        it_blob = common.normalize(text_it).lower()
        en_blob = common.normalize(text_en).lower()
        for row in st.terminology:
            it_hit = any(_contains(it_blob, v) for v in row["variants_it"])
            if not it_hit:
                continue
            en_hit = any(_contains(en_blob, v) for v in row["variants_en"])
            if not en_hit:
                failures.append({
                    "segment_id": sid,
                    "detail": f"IT '{row['term_it']}' present but no EN variant "
                              f"of '{row['term_en']}' found",
                })
    status = "warn" if failures else "pass"
    return _result("glossary_adherence", status, failures)


# ---- antecedent basis (check 9) ------------------------------------------


_NP_PUNCT = ".,;:()[]\"'"
_NP_BOUNDARY_PUNCT = ".,;:"


def _noun_phrase(tokens, start):
    """Collect an NP starting at index `start`: up to 4 tokens, stopping at a
    determiner/preposition/verb or a token carrying boundary punctuation.

    Surrounding punctuation is stripped before word-testing so a comma-glued
    noun ("claim," in "the preceding claim,") is still recognised; a trailing
    ,.;: then ends the phrase. Trailing plural 's' is stripped per token."""
    np = []
    for tok in tokens[start:start + 6]:
        core = tok.strip(_NP_PUNCT)
        low = core.lower()
        if not low or low in _NP_STOP:
            break
        if not _WORD_RE.fullmatch(core):
            break
        np.append(low[:-1] if len(low) > 3 and low.endswith("s") else low)
        if len(np) == 4:
            break
        if tok != core and tok[-1] in _NP_BOUNDARY_PUNCT:
            break
    return tuple(np)


def _claim_np_inventory(text_en):
    """(introduced, required) NP sets for one claim's English text.

    Introduction sources, all standard for antecedent basis:
    - "a/an X" — the classic explicit introduction.
    - the possessor Y in a genitive "... of [the/a/an] Y": naming Y in an
      "of" phrase references it, so Y carries its own basis (e.g. "of the
      water", "of coffee").
    - a property head "the X of ...": a property or relationship recited as
      "the X of <element>" draws its basis from the possessor, so X is treated
      as introduced rather than requiring a separate antecedent (e.g. "the
      temperature of the water", "the cold extraction of coffee").
    Requirement: "the/said X" that is not itself such a property head. This
    mirrors examiner practice: only claimed elements need an explicit
    antecedent; properties and mass nouns recited via "of" do not."""
    tokens = text_en.replace("(", " ( ").replace(")", " ) ").split()
    introduced, required = set(), set()
    n = len(tokens)

    def tok_low(i):
        return tokens[i].lower().strip(".,;:") if 0 <= i < n else ""

    for i, tok in enumerate(tokens):
        low = tok.lower().strip(".,;:")
        if low in ("a", "an"):
            np = _noun_phrase(tokens, i + 1)
            if np:
                introduced.add(np)
        elif low == "of":
            j = i + 1
            if tok_low(j) in ("the", "a", "an", "said"):
                j += 1
            np = _noun_phrase(tokens, j)
            if np:
                introduced.add(np)
        elif low in ("the", "said"):
            np = _noun_phrase(tokens, i + 1)
            if not np or _np_exempt(np):
                continue
            if tok_low(i + 1 + len(np)) == "of":
                introduced.add(np)  # "the X of ..." — property, has basis
            else:
                required.add(np)
    return introduced, required


def _np_exempt(np) -> bool:
    if np[0] in _ANTECEDENT_ALLOWLIST:
        return True
    return any(tok in ("claim", "claims", "step", "steps") for tok in np)


def check_antecedent_basis(st: State):
    if not st.claims_en:
        return _result("antecedent_basis", "skip",
                       stats={"reason": "claims_en.json missing"})
    intro_by_number, req_by_number = {}, {}
    cid_by_number = {}
    deps_by_number = {c["number"]: (c.get("depends_on") or [])
                      for c in st.claims_meta}
    for cid, _, text_en, number in st.claim_alignments():
        intro, req = _claim_np_inventory(text_en)
        intro_by_number[number] = intro
        req_by_number[number] = req
        cid_by_number[number] = cid

    def available(number, seen=None):
        seen = seen or set()
        if number in seen:
            return set()
        seen.add(number)
        acc = set(intro_by_number.get(number, set()))
        for dep in deps_by_number.get(number, []):
            acc |= available(dep, seen)
        return acc

    failures = []
    for number in sorted(req_by_number):
        own = intro_by_number.get(number, set())
        deps = deps_by_number.get(number, [])
        cid = cid_by_number.get(number)
        for np in sorted(req_by_number[number]):
            phrase = " ".join(np)
            if np in own:
                continue
            if not deps:
                failures.append({
                    "segment_id": cid,
                    "detail": f"claim {number}: 'the {phrase}' has no antecedent",
                })
            elif len(deps) == 1:
                if np not in available(deps[0]):
                    failures.append({
                        "segment_id": cid,
                        "detail": f"claim {number}: 'the {phrase}' has no "
                                  f"antecedent (via claim {deps[0]})",
                    })
            else:
                lacking = [d for d in deps if np not in available(d)]
                if lacking:
                    failures.append({
                        "segment_id": cid,
                        "detail": f"claim {number}: 'the {phrase}' missing on "
                                  f"dependency path(s) via claim(s) {lacking}",
                    })
    status = "warn" if failures else "pass"
    return _result("antecedent_basis", status, failures)


def check_abstract_length(st: State):
    if st.translations is None:
        return _result("abstract_length", "skip",
                       stats={"reason": "translations.json missing"})
    abstract_pairs = [p for p in st.pairs if p["id"].startswith("A-")]
    if not abstract_pairs:
        return _result("abstract_length", "skip",
                       stats={"reason": "no A-* abstract pairs"})
    words = 0
    for pair in abstract_pairs:
        words += len(common.normalize(st.pair_en(pair)).split())
    failures = []
    if not (50 <= words <= 150):
        failures.append({
            "segment_id": None,
            "detail": f"abstract word count {words} outside PCT range [50, 150]",
        })
    status = "fail" if failures else "pass"
    return _result("abstract_length", status, failures,
                   stats={"words": words})


def check_residue(st: State):
    if st.translations is None and not st.claims_en:
        return _result("residue", "skip",
                       stats={"reason": "no translations.json or claims_en.json"})
    aligned = [(sid, en) for sid, _, en in st.pair_alignments()]
    aligned += [(sid, en) for sid, _, en, _ in st.claim_alignments()]
    failures = []
    for sid, text_en in aligned:
        norm = common.normalize(text_en)
        hits = sorted({tok for tok, rex in _RESIDUE_RES if rex.search(norm)})
        if hits:
            failures.append({
                "segment_id": sid,
                "detail": f"Italian residue token(s): {hits}",
            })
    status = "fail" if failures else "pass"
    return _result("residue", status, failures)


def check_structure(st: State):
    if st.translations is None:
        return _result("structure", "skip",
                       stats={"reason": "translations.json missing"})
    covered: dict[str, list[str]] = {}

    def cover(seg_id, by):
        covered.setdefault(seg_id, []).append(by)

    for pair in st.pairs:
        cover(pair["id"], "pairs")
    if st.claims_en:
        for c in st.claims_en["claims"]:
            cover(c["id"], "claims_en")
    title_present = bool(st.translations.get("title", {}).get("text_en"))

    failures = []
    for seg in st.segments:
        sid, kind, section = seg["id"], seg["kind"], seg["section"]
        if kind == "claim":
            hits = covered.get(sid, [])
            if not st.claims_en:
                continue  # claims not authored yet: not this check's gap
            if hits != ["claims_en"]:
                failures.append({"segment_id": sid,
                                 "detail": _cover_detail(sid, hits, "claims_en")})
        elif kind == "title":
            if not title_present:
                failures.append({"segment_id": sid,
                                 "detail": f"{sid}: title text_en missing"})
        elif kind == "heading" and section in ("title", "claims"):
            # structural boundary heading: rendered by assemble, never a pair
            continue
        else:
            hits = covered.get(sid, [])
            if hits != ["pairs"]:
                failures.append({"segment_id": sid,
                                 "detail": _cover_detail(sid, hits, "pairs")})
    # ids covered that are not real segments already caught by parity; here
    # flag anything covered twice regardless of kind.
    for sid, hits in covered.items():
        if len(hits) > 1:
            failures.append({"segment_id": sid,
                             "detail": f"{sid}: covered more than once by {hits}"})
    status = "fail" if failures else "pass"
    return _result("structure", status, failures)


def _cover_detail(sid, hits, expected):
    if not hits:
        return f"{sid}: not covered (expected {expected})"
    return f"{sid}: covered by {hits}, expected exactly [{expected}]"


_IT_COMMA_NUMBER_RE = re.compile(r"\d+,\d+")


def check_decimal_comma_audit(st: State):
    """Informational: always pass. Rows for every IT decimal-comma number and
    its aligned EN rendering."""
    aligned = [(sid, it, en) for sid, it, en in st.pair_alignments()]
    aligned += [(sid, it, en) for sid, it, en, _ in st.claim_alignments()]
    rows = []
    for sid, text_it, text_en in aligned:
        en_numbers = {n for n, _ in common.extract_numbers_units(text_en, "en")}
        for m in _IT_COMMA_NUMBER_RE.finditer(text_it):
            it_number = m.group(0)
            normalized = it_number.replace(",", ".")
            rows.append({
                "segment": sid,
                "it_number": it_number,
                "en_number": normalized if normalized in en_numbers else None,
                "found_in_en": normalized in en_numbers,
            })
    return _result("decimal_comma_audit", "pass", data={"rows": rows},
                   stats={"comma_numbers": len(rows)})


CHECK_FUNCS = {
    "paragraph_parity": check_paragraph_parity,
    "numerals_per_segment": check_numerals_per_segment,
    "numeral_term_consistency": check_numeral_term_consistency,
    "numbers_units": check_numbers_units,
    "claims_graph": check_claims_graph,
    "one_sentence_per_claim": check_one_sentence_per_claim,
    "claim_support": check_claim_support,
    "glossary_adherence": check_glossary_adherence,
    "antecedent_basis": check_antecedent_basis,
    "abstract_length": check_abstract_length,
    "residue": check_residue,
    "structure": check_structure,
    "decimal_comma_audit": check_decimal_comma_audit,
}


# --------------------------------------------------------------------------
# MECH flags


def _record_mech_flags(st: State, results):
    """One MECH flag per failing item, deduplicated by the flags.py key.
    Warnings/pass/skip produce nothing."""
    doc = flags_mod.load_flags(st.paths["flags"])
    created = 0
    for res in results:
        if res["status"] != "fail":
            continue
        for failure in res["failures"]:
            sid = failure.get("segment_id")
            issue = f"{res['check']}: {failure['detail']}"
            seg = st.by_id.get(sid) if sid else None
            _, was_new = flags_mod.add_flag(
                doc,
                flag_class="MECH",
                issue=issue,
                segment_id=sid,
                check=res["check"],
                text_it=seg["text_it"] if seg else None,
                text_en=_en_for(st, sid),
                created_by="checks",
            )
            created += was_new
    flags_mod.save_flags(st.paths["flags"], doc)
    return created, len(doc["flags"])


def _en_for(st: State, sid):
    if not sid:
        return None
    for pid, _, en in st.pair_alignments():
        if pid == sid:
            return en
    for cid, _, en, _ in st.claim_alignments():
        if cid == sid:
            return en
    return None


# --------------------------------------------------------------------------
# CLI


def cmd_run(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    if not Path(paths["segments"]).is_file():
        common.die(f"segments.json not found (run ingest first): "
                   f"{paths['segments']}")
    st = State(paths)

    results = [CHECK_FUNCS[name](st) for name in CHECK_ORDER]
    checks_doc = {"run_at": common.now_iso(), "results": results}
    common.write_json(paths["checks"], checks_doc)
    violations = common.validate_file(paths["checks"])
    if violations:
        for v in violations:
            print(f"FAIL {v}")
        common.die("checks.py produced an invalid checks.json (bug)")

    new_flags, total_flags = _record_mech_flags(st, results)

    _print_summary(paths, results, new_flags, total_flags)
    return 0


def _print_summary(paths, results, new_flags, total_flags):
    print(f"checks -> {paths['checks']}")
    width = max(len(r["check"]) for r in results)
    counts = Counter(r["status"] for r in results)
    for res in results:
        n = len(res["failures"])
        tail = f"  ({n} item{'s' if n != 1 else ''})" if n else ""
        print(f"  {res['check']:<{width}}  {res['status'].upper():<5}{tail}")
    print(f"summary: " + ", ".join(f"{k} {counts[k]}"
          for k in ("pass", "fail", "warn", "skip") if counts[k]))
    print(f"MECH flags: +{new_flags} new, {total_flags} total in {paths['flags']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="run the verification battery")
    p_run.add_argument("--project", required=True,
                       help="project directory, e.g. projects/_fixture")
    p_run.set_defaults(func=cmd_run)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
