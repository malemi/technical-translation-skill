# CONTRACTS — patent-translate skill

Single source of truth for the build. Coders implement EXACTLY this. If a
contract seems wrong or ambiguous, do NOT improvise: note it in your report and
implement the contract as written unless it is impossible.

## Purpose

A Claude Code skill that translates an Italian patent application into English
for a PCT filing. Deterministic Python scripts do everything mechanical
(segmentation, DeepL calls, verification battery, assembly). The model does
everything judgmental (terminology, claims, fidelity review, flags) at skill
run time — that part is NOT in scope for coders.

## Repo layout

```
.claude/skills/patent-translate/
  SKILL.md                  # authored by the orchestrator — do not create/edit
  references/               # authored by the orchestrator — do not create/edit
  scripts/
    common.py               # shared helpers (paths, state io, docx, extraction)
    validate_state.py       # validate state files against schemas
    ingest.py               # source.docx -> state/segments.json
    glossary.py             # terminology.csv validate + push to DeepL
    translate_deepl.py      # DeepL document translation of description+abstract
    backtranslate.py        # DeepL EN->IT of the model's claims
    checks.py               # mechanical verification battery
    flags.py                # add/resolve/list flags in state/flags.json
    assemble.py             # build deliverables in <project>/out/
    dev/make_fixture.py     # build projects/_fixture/source.docx
projects/
  <slug>/                   # one directory per document job
    source.docx             # the Italian application (input)
    terminology.csv         # written by the model, validated by glossary.py
    state/                  # JSON state (all schemas below)
    work/                   # intermediate docx files
    out/                    # deliverables
  _fixture/                 # synthetic test project (see fixture_spec.md)
.venv/                      # python venv: python-docx, requests
requirements.txt
README.md                   # written by the integrator agent
```

## Global policies

- ENGLISH ONLY in code, comments, docstrings, CLI messages, README, log lines.
  Italian appears only as data (document text, fixture content).
- Python 3.10+. Dependencies: stdlib + `python-docx` + `requests`. Nothing else.
- Fail loud. No silent fallbacks, no default values that mask missing input, no
  bare `except`. Missing file / bad schema / API error → clear message to
  stderr and non-zero exit. Check FAILURES are data (see checks.py), not exits.
- Never fabricate translation output. If `DEEPL_AUTH_KEY` is absent, DeepL
  scripts must exit 2 with a clear message. No mock/offline mode.
- `DEEPL_AUTH_KEY` is read from the environment; if absent, also try parsing a
  `.env` file at repo root (simple `KEY=value` lines, no dependency).
- Endpoint selection follows the key suffix: a key ending in `:fx` is a DeepL
  API Free key and MUST use base `https://api-free.deepl.com`; any other key is
  a Pro key and uses `https://api.deepl.com`. `load_env_key()` returns
  `(key, api_base)`. Both tiers are accepted (this project's Italian source is
  already filed, so DeepL's Free-tier text retention is not a confidentiality
  concern here). Do NOT hardcode the base anywhere — always derive it from the
  key. Free tier has a lower monthly character quota; surface DeepL's
  quota-exceeded (456) response as a clear, distinct error.
- Idempotence: every script can be re-run; re-runs must not duplicate flags or
  corrupt state (rules below).
- Comments: sparse, only for constraints the code cannot show.
- All scripts run from the repo root. `--project` takes a path like
  `projects/_fixture` (relative to CWD or absolute).
- Text handling: store paragraph text raw (as python-docx returns it). For
  comparisons/matching, normalize on the fly: NBSP (\xa0) → space, collapse
  runs of whitespace, strip. Never write the normalized form back to state.

## State files and schemas

All under `<project>/state/`, UTF-8 JSON, 2-space indent. `validate_state.py`
enforces required keys and types (hand-rolled checks in common.py — no
jsonschema dependency).

### segments.json  (written by ingest.py)

```json
{
  "meta": {
    "source_file": "source.docx",
    "ingested_at": "2026-07-14T18:00:00+00:00",
    "language": "it",
    "counts": {"segments": 0, "claims": 0}
  },
  "segments": [
    {
      "id": "T-001",
      "kind": "title|abstract|description|heading|claim",
      "section": "title|abstract|description|claims",
      "docx_indices": [3],
      "style": "Normal",
      "text_it": "…",
      "para_number": null,
      "parts_it": null
    }
  ],
  "claims": [
    {
      "id": "C-01",
      "number": 1,
      "depends_on": [],
      "dependency_phrase": null,
      "multiple": false,
      "needs_review": false
    }
  ],
  "numerals": {
    "by_segment": {"D-0003": ["1", "2", "3a"]},
    "term_map_it": {"2": ["vasca di estrazione", "serbatoio"]}
  }
}
```

Rules:
- Segment ids: `T-001` (title), `A-001, A-002…` (abstract paragraphs),
  `H-001…` (headings), `D-0001…` (description paragraphs), `C-01…` (claims).
  Zero-padded, document order within each prefix.
- Every non-empty body paragraph of the docx becomes exactly one segment or one
  part of a claim segment. Nothing is dropped. Empty paragraphs are skipped.
- `docx_indices`: indices into the enumeration of ALL body paragraphs
  (including empty ones) of source.docx. A claim spanning several paragraphs
  lists all of them; other segments list exactly one.
- Claim segments: `parts_it` = list of the raw paragraph texts composing the
  claim (first part contains the claim number prefix); `text_it` = parts joined
  with a single `\n`.
- `para_number`: official numbering like `[0012]` if the paragraph text starts
  with it, else null (the marker stays inside text_it as-is).

Section detection:
- A paragraph whose normalized upper-cased text matches one of these lexicons
  is a section boundary: TITLE: {"TITOLO"}; ABSTRACT: {"RIASSUNTO", "SOMMARIO"};
  DESCRIPTION: {"DESCRIZIONE", "DESCRIZIONE DELL'INVENZIONE"};
  CLAIMS: {"RIVENDICAZIONI"}.
  The boundary paragraph itself becomes a `heading` segment (section = the new
  section). Order of sections in the document is arbitrary.
- Sub-headings inside the description (e.g. "CAMPO TECNICO", "STATO DELLA
  TECNICA", "BREVE DESCRIZIONE DELLE FIGURE", "DESCRIZIONE DETTAGLIATA", any
  short all-caps line without a final period) are `heading` segments with
  section "description".
- If no TITOLO heading exists, the first non-empty paragraph before any section
  heading is the title (print a warning). If a required section (title,
  abstract, description, claims) is missing at the end, print a WARNING line
  `ESCALATION: missing section <name>` and continue (exit 0).

Claims parsing (regex on structured text is fine here):
- Inside the claims section, a new claim starts at a paragraph matching
  `^\s*(\d{1,3})\s*[.)\-]\s*` (allow tab after the number). Following
  paragraphs without such a prefix belong to the current claim as parts.
- Claim numbers must be strictly increasing by 1 from 1; otherwise warn and set
  `needs_review: true` on the affected claim.
- Dependency parsing on the normalized claim text (case-insensitive). The
  dependency is introduced by EITHER "secondo" OR "in accordo con" (both are
  standard in real IT patents); everything below accepts either trigger:
  - "secondo/in accordo con la rivendicazione N" → [N]
  - "… le rivendicazioni N e M" / "N, M e K" → [N, M(, K)]
  - "… una qualsiasi delle rivendicazioni da N a M" → [N..M]
  - "… una qualsiasi delle rivendicazioni N-M" (hyphen or en/em-dash span, e.g.
    "14-19", "1-13") → [N..M]
  - "… una qualsiasi delle rivendicazioni precedenti" → [1..number-1]
  - "… la rivendicazione precedente" → [number-1]
  - No match → depends_on [] (independent).
  - A match that mentions "rivendicazion" but fits none of the patterns →
    depends_on null, needs_review true, print `ESCALATION: claim N dependency
    unparsed: <phrase>`.
- `multiple` = depends_on has length > 1. `dependency_phrase` = the exact
  matched substring or null.

Reference signs (the field stays named `numerals` for compatibility):
- A reference sign is a parenthesized token that is EITHER numeric
  `\d{1,3}[a-z]?['′]?` ("3a", "2", "3'") OR an uppercase-letter sign
  `[A-Z]{1,3}\d{0,2}` ("M", "PM", "X", "A", "B", "R"). Real patents use letter
  signs for substances/axes/points alongside numbered parts, and they must be
  preserved in translation exactly like numbers. A group is one or more such
  tokens comma-separated inside parentheses. Lowercase content, unit symbols
  ("(µm)", "(MPa)"), parenthesized values ("(14 rpm)") and citations
  ("(Lai et al.)") are NOT reference signs and are excluded by the token shape.
  Figure references like "figura 1" are NOT signs (no parentheses).
- `by_segment`: multiset per segment id stored as a sorted list WITH
  duplicates.
- `term_map_it`: for each numeral, the distinct noun phrases that immediately
  precede its group occurrences: take up to 4 words before the "(", stop at
  punctuation/verb-like boundary, strip leading articles/prepositions
  (un, una, la, il, lo, le, i, gli, di, del, della, dei, delle, al, alla).
  Lowercased. This is a heuristic; it feeds a warn-level check.

### terminology.csv  (written by the model; validated/pushed by glossary.py)

Header (exact): `term_it,variants_it,term_en,variants_en,category,in_claims,rationale,status,flag`
- `variants_*`: pipe-separated surface forms, FIRST variant = the canonical
  term itself. `variants_it` and `variants_en` must have the same length
  (position i translates position i).
- `category`: one of `part|process|material|parameter|other`.
- `in_claims`: `yes|no` — whether any IT variant occurs in any claim.
- `status`: `proposed|locked`. `flag`: free text, empty when no doubt.
- glossary.py `validate` errors: bad header, duplicate term_it, empty term_en,
  variant length mismatch, variant duplicated across rows. It also recomputes
  occurrences of every IT variant over segments.json (normalized,
  case-insensitive substring) and writes `state/terminology_report.json`:
  `{"generated_at": …, "rows": [{"term_it": …, "occurrences_it": N,
  "segments": ["C-01", …], "in_claims_computed": true}]}`, warning on any
  variant with zero occurrences and on `in_claims` mismatches.

### deepl.json  (written by glossary.py push / translate_deepl.py)

```json
{
  "api_base": "https://api-free.deepl.com or https://api.deepl.com per key suffix",
  "glossary_id": "…",
  "glossary_name": "patent-<slug>-<sha8>",
  "terminology_sha256": "…",
  "document": {"billed_characters": 0, "translated_at": "…"}
}
```

### translations.json  (written by translate_deepl.py; finals edited via model)

```json
{
  "target_lang": "EN-US",
  "title": {"text_en": null},
  "pairs": [
    {
      "id": "A-001",
      "text_en_deepl": "…",
      "deepl_para_sha256": "…",
      "text_en_final": null,
      "edits": []
    }
  ]
}
```

- `pairs` covers, in order, every segment sent to DeepL (abstract, headings,
  description — NOT title, NOT claims).
- `deepl_para_sha256` = sha256 of text_en_deepl (hex).
- Re-run invalidation: if a new DeepL run yields a different text for a pair,
  set `text_en_final` to null and append to `edits`:
  `{"reason": "deepl re-run invalidated final", "old_final": "…", "at": "…"}`.
  If unchanged, keep final and edits as they are.
- Model edits append `{"reason": …, "before": …, "after": …, "at": …}` and set
  `text_en_final`.

### claims_en.json  (written by the model at run time)

```json
{"claims": [
  {"id": "C-01", "number": 1, "text_en": "…", "parts_en": ["…"],
   "conventions": ["two-part form kept"], "authored_at": "…"}
]}
```

`text_en` = parts joined with `\n`. Dependency references are NOT declared
here: checks.py re-parses them from the English text independently.

### backtranslation.json  (written by backtranslate.py)

```json
{"claims": [{"id": "C-01", "text_it_back": "…"}], "run_at": "…"}
```

### flags.json  (written by flags.py and checks.py)

```json
{"flags": [
  {"key": "a1b2c3d4e5f6", "class": "AMBIGUITY|TERM|CONVENTION|CLAIM-DEFECT|MECH",
   "segment_id": "C-01", "check": null, "text_it": "…", "text_en": "…",
   "issue": "…", "options": ["…"], "status": "open|resolved",
   "resolution": null, "created_by": "model|checks", "created_at": "…"}
]}
```

`key` = first 12 hex chars of sha1("class|segment_id|issue" normalized
lowercase, whitespace collapsed). Adding an existing key updates nothing
(dedup); resolving sets status/resolution.

flags.py CLI:
- `flags.py add --project P --class TERM --segment C-01 --issue "…"
  [--text-it …] [--text-en …] [--option … (repeatable)]`
- `flags.py resolve --project P --key a1b2c3d4e5f6 --resolution "…"`
- `flags.py list --project P [--open] [--class X]` (table to stdout)

### checks.json  (written by checks.py)

```json
{"run_at": "…", "results": [
  {"check": "numerals_per_segment", "status": "pass|fail|warn|skip",
   "failures": [{"segment_id": "D-0003", "detail": "…"}],
   "stats": {}, "data": null}
]}
```

`skip` when required inputs are missing (e.g. claims_en.json not yet written) —
never crash for missing optional stages. `data` carries tables for assemble
(see individual checks).

## Extraction definitions (common.py)

- Reference numerals: regex above. Provide `extract_numerals(text) -> list`.
- Numbers: run on text AFTER removing numeral groups and `[dddd]` paragraph
  markers. A number token = `\d+(?:[.,]\d+)?` (also match ranges "da X a Y" /
  "tra X e Y" / "from X to Y" / "between X and Y" as two numbers — no special
  pairing needed, the multiset covers it).
- Normalization for comparison: decimal comma → decimal point ("12,5" → "12.5").
- Units: a unit is the token immediately following a number (allow "°C" glued
  or spaced). Symbol lexicon (identical in IT and EN):
  bar, mbar, Pa, kPa, MPa, °C, K, mm, cm, m, µm, um, nm, ml, mL, cl, l, L, g,
  kg, mg, %, s, h, W, V, A, Hz, rpm.
  Word units mapped IT→EN: minuti/minuto→minutes/minute, ore/ora→hours/hour,
  secondi/secondo→seconds/second, giorni/giorno→days/day, litri/litro→
  liters/liter, grammi/grammo→grams/gram, peso→weight.
  Provide `extract_numbers_units(text, lang) -> list[(number_normalized,
  unit_canonical_or_none)]`.
- English claim dependency phrases (for checks.py), case-insensitive:
  - "according to claim N" → [N]
  - "according to claims N and M" / "claims N, M and K" → list
  - "according to any one of claims N to M" (also "any of claims") → [N..M]
  - "according to any one of the preceding claims" → [1..number-1]
  - "according to the preceding claim" → [number-1]
  - mentions "claim" in a dependency position but parses to none → null.

## Module contracts

### common.py
`project_paths(project) -> dict` (source docx discovery: exactly one *.docx in
the project root unless `--source` given — zero or several without --source is
an error); `read_json/write_json`; `sha256_text`; `now_iso` (UTC, seconds);
`normalize(text)`; `iter_body_paragraphs(docx_path) -> [(index, text, style_name)]`
(ALL body paragraphs incl. empty; text raw); extraction functions above;
`load_env_key() -> (key, api_base)` (env then repo-root .env; `:fx` →
api-free.deepl.com, else api.deepl.com; absent key → SystemExit 2); `SCHEMAS` +
`validate_file(path) -> [violations]` for every state file above.

### validate_state.py
`validate_state.py --project P [--file segments.json]` — validate all present
state files (or one). Print violations, exit 1 if any, else print OK.

### ingest.py
`ingest.py --project P [--source name.docx]` — as specified. Also prints a
one-screen summary: segment counts per kind, claim dependency graph, numeral
inventory, escalation warnings.

### dev/make_fixture.py
Builds `projects/_fixture/source.docx` from the literal Italian text in
`projects/_fixture/fixture_spec.md` (keep the Italian EXACTLY as given,
including "12,5", "µm", "(3a)"). Headings as their own paragraphs. Claim parts
(semicolon lines) as separate paragraphs. Deterministic output.

### glossary.py
`glossary.py validate --project P` (above). `glossary.py push --project P`:
requires key; builds entries as one TSV line per variant pair (it → en, first
variants included like the rest, entries deduplicated, no empty sides); creates
glossary via `POST {base}/v2/glossaries` (name `patent-<slug>-<sha8 of csv>`,
source_lang "it", target_lang "en", entries_format "tsv"); stores deepl.json.
If deepl.json already has the same terminology_sha256 and a glossary_id, do
nothing and say so.

### translate_deepl.py
`translate_deepl.py run --project P [--target EN-US]`:
1. Build `work/description_it.docx`: COPY source.docx, then delete title
   paragraphs and the whole claims section (heading included), delete nothing
   else (empty paragraphs stay). Record, in order, the segment ids of the
   remaining non-empty paragraphs (abstract + headings + description).
2. Upload via `POST {base}/v2/document` (multipart: file, source_lang=IT,
   target_lang=<target>, glossary_id from deepl.json — error if glossary
   missing). Poll `POST /v2/document/{id}` with document_key until
   status=done (respect `seconds_remaining` hint, cap poll interval at 5 s,
   overall timeout 15 min); download result to `work/description_en.docx`.
3. Pair: non-empty body paragraphs of the EN docx, in order, must count-match
   the recorded segment ids (else exit 1 with both counts). Write/merge
   translations.json per the invalidation rules.
4. Print billed_characters and a 3-line summary.
Retries: 429/5xx → 3 attempts, exponential backoff (1, 4, 9 s); other 4xx →
fail with response body.

### backtranslate.py
`backtranslate.py run --project P`: for each claim in claims_en.json, translate
text_en via `POST {base}/v2/translate` (text array, source_lang EN,
target_lang IT, split_sentences "0", preserve_formatting true, NO glossary —
the back-translation must stay naive to serve as an independent probe). Write
backtranslation.json.

### checks.py
`checks.py run --project P` → checks.json + MECH flags (via the flags.py dedup
logic, imported not shelled) for every `fail`; `warn` produces no flag. Exit 0
unless crash. Checks (name → rule):

1. `paragraph_parity` — pairs count in translations.json equals the recorded
   sent-segment count; every pair id exists in segments.json. fail on mismatch.
2. `numerals_per_segment` — for each pair with an EN text (final else deepl)
   and for each claim (text_it vs claims_en text_en): multiset of numerals
   identical. fail per offending segment.
3. `numeral_term_consistency` — build term_map_en like term_map_it but on EN
   texts (strip leading a/an/the/said/each/one). warn if a numeral maps to >1
   distinct EN phrase or if IT side already maps to >1 (source inconsistency —
   detail says so). data: numeral → IT terms → EN terms table.
4. `numbers_units` — per aligned segment (pairs + claims): multiset of
   (number, unit) identical after normalization. fail per segment. data: full
   audit rows {segment, it: [(n,u)], en: [(n,u)], ok} for ALL segments (this
   becomes audit_numbers.csv).
5. `claims_graph` — parse EN dependencies (definitions above) for every claim
   in claims_en.json; compare with segments.json claims[].depends_on. fail on
   any difference or unparseable EN phrase; skip if claims_en.json missing.
   data: rows {number, it_deps, en_deps, multiple} (multiple-dependent claims
   are listed for the US-phase note).
6. `one_sentence_per_claim` — EN claim text: exactly one sentence terminator,
   the final period. Internal `.` allowed only in numbers ("12.5"). fail per
   claim.
7. `claim_support` — every locked terminology row with in_claims=yes: at least
   one EN variant occurs (normalized, case-insensitive) in the EN description
   (pairs finals/deepl). ALSO: for each claim, every EN variant occurring in
   the claim must occur in the EN description; report missing ones. fail per
   missing term; skip if no locked rows or no claims_en.
8. `glossary_adherence` — for each pair and claim: if an IT variant occurs in
   text_it, the aligned EN text must contain the corresponding EN variant (any
   variant of the same row). warn per miss (DeepL inflections can be legitimate
   — the model adjudicates), listing segment, term, found/not.
9. `antecedent_basis` — EN claims only. NP inventory per claim: after "a"/"an"
   → introduces NP; after "the"/"said" → requires NP. NP ≈ following tokens up
   to 4, stopping at determiners/prepositions/verbs/punctuation; normalized
   lowercase, trailing "s" stripped per token. Inheritance: claim N inherits
   introductions from EVERY dependency path; for multiple-dependent claims an
   NP must be introduced in every alternative path, else it counts as missing
   for the paths that lack it (detail must name the path). Preamble nouns
   ("apparatus", "method") and inherited-by-reference preamble are exempt via
   allowlist {apparatus, method, use, claim, claims, step, steps}. ("step(s)"
   is exempt because the method-claim idiom "comprising the steps of …" carries
   its own basis and must not warn.) warn per missing antecedent (model
   adjudicates).
10. `abstract_length` — EN abstract (pairs of A-*) word count in [50, 150]
    (PCT Rule 8.1(b)). fail outside.
11. `residue` — EN texts containing Italian function words as standalone tokens
    ({della, delle, degli, nella, nelle, mediante, nonché, ovvero, inoltre,
    qualsiasi, rivendicazione, rivendicazioni, secondo la, in cui}) → fail per
    segment. Claim texts included.
12. `structure` — every segment id in segments.json is covered: claims by
    claims_en, title by translations.title, others by pairs; nothing covered
    twice. fail listing gaps/dupes. skip only if translations.json missing.
13. `decimal_comma_audit` — informational (status always pass): data rows for
    every IT number containing a comma with the aligned EN rendering.

### assemble.py
`assemble.py run --project P` — requires translations.json (all pairs must have
text_en_final or text_en_deepl; title text_en present; else exit 1 listing
gaps), claims_en.json, flags.json, checks.json (run checks first; assemble does
not run them).

Outputs in `<project>/out/`:
- `filing_en.docx` — order: Title (Heading 1), then for every abstract/heading/
  description segment in document order: headings as Heading 2, paragraphs as
  Normal (English finals); then "CLAIMS" (Heading 2) + each claim: number
  prefix "1. " on the first part, parts as separate paragraphs; then "ABSTRACT"
  (Heading 2) + abstract paragraphs again? NO — abstract appears ONCE, at the
  end: do NOT render A-* segments inside the body; render them only in the
  final ABSTRACT section. Title page numbering not required.
- `side_by_side.docx` — landscape; one table, 4 columns (ID | Italiano |
  English | Flags); one row per segment in document order (claims included,
  title first); EN cell = final else deepl else claim text_en; Flags cell: one
  line per flag on that segment: "⚑ CLASS — issue [status]". After the table,
  appendix sections (Heading 2 each): "Numbers and units audit" (table from
  checks data 4), "Reference numeral map" (from checks data 3), "Claim
  dependency map" (from checks data 5), "Open escalations" (flags with status
  open, class != CONVENTION), "Applied conventions" (CONVENTION flags).
- `ESCALATIONS.md` — open flags of class AMBIGUITY, TERM, CLAIM-DEFECT, MECH,
  grouped by class, each with segment id, IT text, EN text, issue, options.
- `audit_numbers.csv` — the numbers audit table.
- `terminology.csv` — copy of the project's file.
Reopen both docx files with python-docx after writing and assert: filing
contains the claims heading and N claims; side-by-side row count = segments
count + 1 header. Print output paths.

## Seeded-defect matrix (integration test)

On the fixture, after building a clean state (which must pass all checks except
the deliberate source quirks — see fixture_spec.md), create a COPY of the
project directory named `projects/_fixture_bad/` with these six mutations, then
checks.py must flag ALL six (and assemble must still run):

1. Remove numeral "(3)" from one EN description pair → numerals_per_segment fail.
2. Change "12.5 bar" to "12.7 bar" in one EN pair → numbers_units fail.
3. Replace one locked claim term's EN variant with a synonym throughout the EN
   description pairs → claim_support fail.
4. In EN claim 4, change "claims 1 to 3" to "claims 1 to 2" → claims_graph fail.
5. Split EN claim 2 into two sentences → one_sentence_per_claim fail.
6. In EN claim 5, reference "the pressure regulator" never introduced →
   antecedent_basis warn naming claim 5.

## Definition of done (every module)

Your scripts RUN. Execute them for real on the fixture (or on synthetic state
files you build to these schemas), show the actual commands and output in your
report, and leave the repo in a state where the next phase can run them as-is.
No "should work". If something is untestable without the DeepL key, say so
explicitly in your report — do not fake it.
