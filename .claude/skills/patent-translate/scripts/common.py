"""Shared helpers for the patent-translate skill scripts.

All scripts run from the repo root. Project layout and schemas are defined in
CONTRACTS.md; this module is the single implementation of paths, state IO,
docx paragraph access, extraction functions and state-file schemas.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# --------------------------------------------------------------------------
# fail loud


def die(message: str, code: int = 1):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------
# paths

STATE_FILE_NAMES = (
    "segments.json",
    "terminology_report.json",
    "deepl.json",
    "translations.json",
    "claims_en.json",
    "backtranslation.json",
    "flags.json",
    "checks.json",
)


def project_paths(project, source: str | None = None, need_source: bool = True) -> dict:
    """Resolve all paths of a project directory.

    Source docx discovery: exactly one *.docx in the project root unless
    `source` is given; zero or several without `source` is an error.
    `need_source=False` skips discovery for scripts that never touch the docx.
    """
    root = Path(project)
    if not root.is_dir():
        die(f"project directory not found: {root}")
    src = None
    if source is not None:
        src = root / source
        if not src.is_file():
            die(f"--source file not found: {src}")
    elif need_source:
        candidates = sorted(
            p for p in root.glob("*.docx") if not p.name.startswith("~$")
        )
        if len(candidates) != 1:
            names = ", ".join(p.name for p in candidates) or "none"
            die(
                f"expected exactly one *.docx in {root} (found: {names}); "
                "use --source to pick one"
            )
        src = candidates[0]
    state = root / "state"
    paths = {
        "root": root,
        "source": src,
        "state": state,
        "work": root / "work",
        "out": root / "out",
        "terminology": root / "terminology.csv",
    }
    for name in STATE_FILE_NAMES:
        paths[name.rsplit(".", 1)[0]] = state / name
    return paths


# --------------------------------------------------------------------------
# state IO


def read_json(path):
    path = Path(path)
    if not path.is_file():
        die(f"missing state file: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def write_json(path, obj) -> None:
    """Write UTF-8 JSON, 2-space indent, atomically (tmp + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# text normalization and docx access


def normalize(text: str) -> str:
    """NBSP -> space, collapse whitespace runs, strip. Comparison form only:
    never write it back to state."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def iter_body_paragraphs(docx_path) -> list[tuple[int, str, str]]:
    """All body paragraphs of the docx, including empty ones, as
    (index, raw_text, style_name) in document order."""
    from docx import Document  # imported here: only docx-touching scripts need it

    docx_path = Path(docx_path)
    if not docx_path.is_file():
        die(f"docx file not found: {docx_path}")
    doc = Document(str(docx_path))
    out = []
    for index, para in enumerate(doc.paragraphs):
        style = para.style.name if para.style is not None else ""
        out.append((index, para.text, style))
    return out


# --------------------------------------------------------------------------
# reference numerals

# A reference sign is a parenthesized numeric sign ("100", "3a") OR an
# uppercase-letter sign ("M", "PM", "X", "A"). Real patents use letter signs
# for substances, axes and points ((A) solvent, (B) powder, (M) mixture, (X)/(Y)
# axes, (R) radius, (PM) point) alongside numbered parts, and they must be
# preserved in translation just like numbers. Lowercase content, unit symbols
# ("(MPa)", "(µm)"), values ("(14 rpm)") and citations ("(Lai et al.)") are not
# reference signs and are excluded by the uppercase/numeric-only token shape.
_REF_SIGN_TOKEN = r"(?:\d{1,3}[a-z]?['′]?|[A-Z]{1,3}\d{0,2})"
NUMERAL_GROUP_RE = re.compile(
    r"\(\s*" + _REF_SIGN_TOKEN + r"(?:\s*,\s*" + _REF_SIGN_TOKEN + r")*\s*\)"
)
_NUMERAL_TOKEN_RE = re.compile(_REF_SIGN_TOKEN)


def extract_numerals(text: str) -> list[str]:
    """Individual reference signs from parenthesized groups, in order of
    appearance, duplicates kept. "(2, 3a)" -> ["2", "3a"]; "(M)" -> ["M"]."""
    out = []
    for group in NUMERAL_GROUP_RE.finditer(text):
        out.extend(_NUMERAL_TOKEN_RE.findall(group.group(0)))
    return out


def numeral_sort_key(numeral: str):
    m = re.match(r"(\d+)(.*)", numeral)
    if not m:
        return (0, numeral)
    return (int(m.group(1)), m.group(2))


# --------------------------------------------------------------------------
# numbers and units

PARA_MARKER_RE = re.compile(r"\[\d{4}\]")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

UNIT_SYMBOLS = (
    "bar", "mbar", "Pa", "kPa", "MPa", "°C", "K", "mm", "cm", "m",
    "µm", "um", "nm", "ml", "mL", "cl", "l", "L", "g", "kg", "mg",
    "%", "s", "h", "W", "V", "A", "Hz", "rpm",
)
# Alias spellings of the same physical unit collapse to one canonical form.
_UNIT_SYMBOL_CANON = {"um": "µm", "mL": "ml", "L": "l"}
WORD_UNITS_IT = {
    "minuti": "minutes", "minuto": "minute",
    "ore": "hours", "ora": "hour",
    "secondi": "seconds", "secondo": "second",
    "giorni": "days", "giorno": "day",
    "litri": "liters", "litro": "liter",
    "grammi": "grams", "grammo": "gram",
    "peso": "weight",
}
WORD_UNITS_EN = {en: en for en in WORD_UNITS_IT.values()}
_SYMBOLS_BY_LEN = sorted(UNIT_SYMBOLS, key=len, reverse=True)
_UNIT_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")


def _match_unit(text: str, pos: int, lang: str) -> str | None:
    if pos < len(text) and text[pos] == " ":
        pos += 1
    for sym in _SYMBOLS_BY_LEN:  # longest first, case-sensitive
        if text.startswith(sym, pos):
            nxt = pos + len(sym)
            if nxt >= len(text) or not (
                text[nxt].isalnum() or text[nxt] in "°µ"
            ):
                return _UNIT_SYMBOL_CANON.get(sym, sym)
    m = _UNIT_WORD_RE.match(text, pos)
    if m:
        words = WORD_UNITS_IT if lang == "it" else WORD_UNITS_EN
        return words.get(m.group(0).lower())
    return None


def extract_numbers_units(text: str, lang: str) -> list[tuple[str, str | None]]:
    """(number, unit) tokens after removing numeral groups and [dddd] markers.

    Numbers are normalized to decimal point; units are canonical symbols or
    canonical English unit words, None when no unit follows the number.
    """
    if lang not in ("it", "en"):
        die(f"extract_numbers_units: unsupported lang {lang!r}")
    clean = NUMERAL_GROUP_RE.sub(" ", text)
    clean = PARA_MARKER_RE.sub(" ", clean)
    clean = normalize(clean)
    out = []
    for m in _NUMBER_RE.finditer(clean):
        number = m.group(0).replace(",", ".")
        out.append((number, _match_unit(clean, m.end(), lang)))
    return out


# --------------------------------------------------------------------------
# numeral -> preceding term phrases (feeds warn-level consistency checks)

_PUNCT_CHARS = set(".,;:!?()[]{}\"«»—–/")
_APOSTROPHES = ("'", "’")

_STRIP_WORDS_IT = {
    # articles and (articulated) prepositions; contract list extended to the
    # full articulated series so "nella vasca ..." strips like "della ..."
    "un", "una", "uno", "la", "il", "lo", "le", "i", "gli",
    "di", "del", "della", "dello", "dei", "delle", "degli",
    "al", "alla", "allo", "ai", "alle", "agli",
    "dal", "dalla", "dallo", "dai", "dalle", "dagli",
    "nel", "nella", "nello", "nei", "nelle", "negli",
    "sul", "sulla", "sullo", "sui", "sulle", "sugli",
    "in", "a", "da", "su", "con", "per", "tra", "fra",
    "attraverso", "mediante",
    "detto", "detta", "detti", "dette",
}
_ELISION_PREFIXES_IT = tuple(
    stem + apo
    for stem in ("un", "l", "dell", "all", "nell", "sull", "dall", "d", "quest", "quell")
    for apo in _APOSTROPHES
)
_BOUNDARY_WORDS_IT = {
    "e", "ed", "o", "od", "che", "cui", "quale", "quali", "ove", "dove",
    "inoltre", "tuttavia", "quindi", "poi", "anche", "ovvero", "oppure",
    "comprende", "comprendente", "comprendono", "comprendenti",
    "mostra", "mostrano", "riguarda", "riguardano", "presenta", "presentano",
    "risulta", "risultano", "regola", "regolano",
    "è", "sono", "era", "erano", "viene", "vengono", "essere",
}
_PARTICIPLE_ENDINGS_IT = (
    "ato", "ata", "ati", "ate", "uto", "uta", "uti", "ute", "ito", "ita",
    "iti", "ite",
)

_STRIP_WORDS_EN = {"a", "an", "the", "said", "each", "one"}
_ELISION_PREFIXES_EN = ()
_BOUNDARY_WORDS_EN = {
    "and", "or", "which", "that", "wherein", "whereby", "thereof",
    "comprising", "comprises", "including", "includes", "having",
    "is", "are", "being", "further", "also", "then",
    "arranged", "configured", "connected", "provided", "adapted",
    # prepositions delimit the noun phrase the numeral tags
    "of", "with", "for", "to", "in", "on", "at", "by", "from", "between",
    "through", "into", "within",
}
_PARTICIPLE_ENDINGS_EN = ()

_TERM_LANG_TABLES = {
    "it": (_STRIP_WORDS_IT, _ELISION_PREFIXES_IT, _BOUNDARY_WORDS_IT,
           _PARTICIPLE_ENDINGS_IT),
    "en": (_STRIP_WORDS_EN, _ELISION_PREFIXES_EN, _BOUNDARY_WORDS_EN,
           _PARTICIPLE_ENDINGS_EN),
}


def _phrase_before(prefix_text: str, lang: str) -> str | None:
    strip_words, elisions, boundary_words, participle_endings = _TERM_LANG_TABLES[lang]
    tokens = prefix_text.split()
    collected: list[str] = []
    for token in reversed(tokens):
        low = token.lower()
        if any(ch in _PUNCT_CHARS for ch in token):
            break
        if low in boundary_words:
            break
        if any(low.endswith(end) for end in participle_endings):
            break
        collected.insert(0, low)
        if len(collected) == 4:
            break
    while collected:
        head = collected[0]
        if head in strip_words:
            collected.pop(0)
            continue
        stripped = None
        for pfx in elisions:
            if head.startswith(pfx) and len(head) > len(pfx):
                stripped = head[len(pfx):]
                break
        if stripped is not None:
            collected[0] = stripped
            continue
        break
    if not collected:
        return None
    return " ".join(collected)


def numeral_term_phrases(text: str, lang: str) -> list[tuple[str, str | None]]:
    """(numeral, preceding noun phrase or None) for every numeral occurrence.

    Heuristic per CONTRACTS.md: up to 4 words before the "(", stop at
    punctuation/verb-like boundaries, strip leading articles/prepositions
    (IT) or a/an/the/said/each/one (EN), lowercased.
    """
    if lang not in _TERM_LANG_TABLES:
        die(f"numeral_term_phrases: unsupported lang {lang!r}")
    norm = normalize(text)
    out = []
    for group in NUMERAL_GROUP_RE.finditer(norm):
        phrase = _phrase_before(norm[: group.start()], lang)
        for numeral in _NUMERAL_TOKEN_RE.findall(group.group(0)):
            out.append((numeral, phrase))
    return out


# --------------------------------------------------------------------------
# claim dependency phrases


def _int_range(first: int, last: int) -> list[int]:
    return list(range(first, last + 1))


# A trailing ", N" / "o|e N" / "or|and N" after a matched dependency means the
# pattern only covers part of the reference (e.g. "rivendicazione 1 o 2"):
# matching would silently truncate it, so such texts must fall through to the
# unparsed/needs_review path instead.
_IT_NO_TAIL = (r"(?!\s*(?:,|oppure|ovvero|od|o|ed|e)\s*"
               r"(?:la\s+rivendicazione\s+|le\s+rivendicazioni\s+)?\d)")
_EN_NO_TAIL = r"(?!\s*(?:,|or|and)\s*(?:claims?\s+)?\d)"

# Real IT patents introduce a dependency with either "secondo" or the equally
# common "in accordo con"; ranges appear as "da N a M" or as a hyphen/en-dash
# span "N-M". Both forms are handled here.
_IT_DEP = r"(?:secondo|in\s+accordo\s+con)"
_IT_RANGE = r"(?:da\s+)?(\d{1,3})\s*(?:a|[-‐‑‒–—])\s*(\d{1,3})"

_IT_DEP_PATTERNS = (
    (re.compile(_IT_DEP + r"\s+una\s+qualsiasi\s+delle\s+rivendicazioni\s+precedenti",
                re.IGNORECASE), "preceding_all"),
    (re.compile(_IT_DEP + r"\s+una\s+qualsiasi\s+delle\s+rivendicazioni\s+"
                + _IT_RANGE + _IT_NO_TAIL, re.IGNORECASE),
     "range"),
    (re.compile(_IT_DEP + r"\s+la\s+rivendicazione\s+precedente", re.IGNORECASE),
     "preceding_one"),
    (re.compile(_IT_DEP + r"\s+le\s+rivendicazioni\s+"
                r"(\d{1,3}(?:\s*,\s*\d{1,3})*\s*,?\s+ed?\s+\d{1,3})" + _IT_NO_TAIL,
                re.IGNORECASE), "list"),
    (re.compile(_IT_DEP + r"\s+la\s+rivendicazione\s+(\d{1,3})" + _IT_NO_TAIL,
                re.IGNORECASE), "single"),
)

_EN_DEP_PATTERNS = (
    (re.compile(r"according\s+to\s+any\s+(?:one\s+)?of\s+the\s+preceding\s+claims",
                re.IGNORECASE), "preceding_all"),
    (re.compile(r"according\s+to\s+any\s+(?:one\s+)?of\s+claims\s+"
                r"(\d{1,3})\s+to\s+(\d{1,3})" + _EN_NO_TAIL, re.IGNORECASE),
     "range"),
    (re.compile(r"according\s+to\s+the\s+preceding\s+claim", re.IGNORECASE),
     "preceding_one"),
    (re.compile(r"according\s+to\s+claims\s+"
                r"(\d{1,3}(?:\s*,\s*\d{1,3})*\s*,?\s+and\s+\d{1,3})" + _EN_NO_TAIL,
                re.IGNORECASE), "list"),
    (re.compile(r"according\s+to\s+claim\s+(\d{1,3})" + _EN_NO_TAIL,
                re.IGNORECASE), "single"),
)


def _parse_dependency(text: str, number: int, patterns, mention_re):
    norm = normalize(text)
    for pattern, kind in patterns:
        m = pattern.search(norm)
        if not m:
            continue
        if kind == "preceding_all":
            deps = _int_range(1, number - 1)
        elif kind == "range":
            deps = _int_range(int(m.group(1)), int(m.group(2)))
        elif kind == "preceding_one":
            deps = [number - 1]
        elif kind == "list":
            deps = [int(x) for x in re.findall(r"\d{1,3}", m.group(1))]
        else:
            deps = [int(m.group(1))]
        return deps, m.group(0)
    if mention_re.search(norm):
        return None, None
    return [], None


def parse_dependency_it(text: str, number: int):
    """Parse an Italian claim's dependency phrase.

    Returns (depends_on, phrase): a list of claim numbers when parsed,
    [] when independent (no claim reference at all), None when the text
    mentions "rivendicazion..." but no known pattern matches.
    """
    return _parse_dependency(
        text, number, _IT_DEP_PATTERNS, re.compile(r"rivendicazion", re.IGNORECASE)
    )


def parse_dependency_en(text: str, number: int):
    """English counterpart of parse_dependency_it (see CONTRACTS.md)."""
    return _parse_dependency(
        text, number, _EN_DEP_PATTERNS, re.compile(r"\bclaims?\b", re.IGNORECASE)
    )


# --------------------------------------------------------------------------
# DeepL auth key


def load_env_key() -> tuple[str, str]:
    """DEEPL_AUTH_KEY from the environment, then from a repo-root .env file.

    Returns (key, api_base). The endpoint follows the key suffix: a ":fx"
    key is a DeepL API Free key and uses https://api-free.deepl.com; any
    other key is a Pro key and uses https://api.deepl.com. Both tiers are
    accepted. A missing key exits 2.
    """
    key = os.environ.get("DEEPL_AUTH_KEY")
    if not key:
        env_file = Path(".env")
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "DEEPL_AUTH_KEY":
                    key = value.strip().strip("'\"")
                    break
    if not key:
        die("DEEPL_AUTH_KEY not set (environment or repo-root .env)", code=2)
    api_base = ("https://api-free.deepl.com" if key.endswith(":fx")
                else "https://api.deepl.com")
    return key, api_base


# --------------------------------------------------------------------------
# state-file schemas (hand-rolled; spec mini-language documented in _check)

_SEGMENT_SPEC = {
    "id": str,
    "kind": ("enum", {"title", "abstract", "description", "heading", "claim"}),
    "section": ("enum", {"title", "abstract", "description", "claims"}),
    "docx_indices": ("list", int),
    "style": str,
    "text_it": str,
    "para_number": ("optional", str),
    "parts_it": ("optional", ("list", str)),
}

_CLAIM_SPEC = {
    "id": str,
    "number": int,
    "depends_on": ("optional", ("list", int)),
    "dependency_phrase": ("optional", str),
    "multiple": bool,
    "needs_review": bool,
}

SCHEMAS = {
    "segments.json": {
        "meta": {
            "source_file": str,
            "ingested_at": str,
            "language": str,
            "counts": {"segments": int, "claims": int},
        },
        "segments": ("list", _SEGMENT_SPEC),
        "claims": ("list", _CLAIM_SPEC),
        "numerals": {
            "by_segment": ("dict_of", ("list", str)),
            "term_map_it": ("dict_of", ("list", str)),
        },
    },
    "terminology_report.json": {
        "generated_at": str,
        "rows": ("list", {
            "term_it": str,
            "occurrences_it": int,
            "segments": ("list", str),
            "in_claims_computed": bool,
        }),
    },
    "deepl.json": {
        "api_base": str,
        "glossary_id": str,
        "glossary_name": str,
        "terminology_sha256": str,
        "document": ("optional", {"billed_characters": int, "translated_at": str}),
    },
    "translations.json": {
        "target_lang": str,
        "title": {"text_en": ("optional", str)},
        "pairs": ("list", {
            "id": str,
            "text_en_deepl": str,
            "deepl_para_sha256": str,
            "text_en_final": ("optional", str),
            "edits": ("list", {"reason": str, "at": str}),
        }),
    },
    "claims_en.json": {
        "claims": ("list", {
            "id": str,
            "number": int,
            "text_en": str,
            "parts_en": ("list", str),
            "conventions": ("list", str),
            "authored_at": str,
        }),
    },
    "backtranslation.json": {
        "claims": ("list", {"id": str, "text_it_back": str}),
        "run_at": str,
    },
    "flags.json": {
        "flags": ("list", {
            "key": str,
            "class": ("enum", {"AMBIGUITY", "TERM", "CONVENTION", "CLAIM-DEFECT",
                               "MECH"}),
            "segment_id": ("optional", str),
            "check": ("optional", str),
            "text_it": ("optional", str),
            "text_en": ("optional", str),
            "issue": str,
            "options": ("list", str),
            "status": ("enum", {"open", "resolved"}),
            "resolution": ("optional", str),
            "created_by": ("enum", {"model", "checks"}),
            "created_at": str,
        }),
    },
    "checks.json": {
        "run_at": str,
        "results": ("list", {
            "check": str,
            "status": ("enum", {"pass", "fail", "warn", "skip"}),
            "failures": ("list", {"segment_id": ("optional", str), "detail": str}),
            "stats": dict,
            "data": "any",
        }),
    },
}


def _type_ok(value, expected_type) -> bool:
    if expected_type is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected_type)


def _check(value, spec, path: str, out: list[str]) -> None:
    """Spec mini-language: "any"; a type; {"key": spec} (all keys required,
    extras allowed); ("optional", spec) (null allowed); ("list", item_spec);
    ("dict_of", value_spec); ("enum", {values})."""
    if spec == "any":
        return
    if isinstance(spec, tuple):
        tag = spec[0]
        if tag == "optional":
            if value is not None:
                _check(value, spec[1], path, out)
            return
        if tag == "list":
            if not isinstance(value, list):
                out.append(f"{path}: expected list, got {type(value).__name__}")
                return
            for i, item in enumerate(value):
                _check(item, spec[1], f"{path}[{i}]", out)
            return
        if tag == "dict_of":
            if not isinstance(value, dict):
                out.append(f"{path}: expected object, got {type(value).__name__}")
                return
            for k, v in value.items():
                _check(v, spec[1], f"{path}.{k}", out)
            return
        if tag == "enum":
            if value not in spec[1]:
                allowed = ", ".join(sorted(str(v) for v in spec[1]))
                out.append(f"{path}: expected one of [{allowed}], got {value!r}")
            return
        raise ValueError(f"invalid schema spec tag: {tag!r}")
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            out.append(f"{path}: expected object, got {type(value).__name__}")
            return
        for key, sub in spec.items():
            if key not in value:
                out.append(f"{path}: missing required key '{key}'")
            else:
                _check(value[key], sub, f"{path}.{key}", out)
        return
    if not _type_ok(value, spec):
        out.append(f"{path}: expected {spec.__name__}, got {type(value).__name__}")


def validate_file(path) -> list[str]:
    """Validate one state file against its schema; violations as strings."""
    path = Path(path)
    name = path.name
    if name not in SCHEMAS:
        known = ", ".join(SCHEMAS)
        return [f"{name}: no schema for this file name (known: {known})"]
    if not path.is_file():
        return [f"{name}: file not found: {path}"]
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except json.JSONDecodeError as exc:
        return [f"{name}: invalid JSON: {exc}"]
    out: list[str] = []
    _check(obj, SCHEMAS[name], name, out)
    return out
