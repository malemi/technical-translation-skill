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
  key. Free tier has a lower monthly character quota, and DeepL bills a flat
  50 000-character minimum per document translation, so a couple of runs can
  exhaust it; surface DeepL's quota-exceeded (456) response as a clear, distinct
  error.
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
  line per flag on that segment **except CONVENTION**: "⚑ CLASS — issue
  [status]". After the table, appendix sections (Heading 2 each): "Numbers and
  units audit" (table from checks data 4), "Reference numeral map" (from checks
  data 3), "Claim dependency map" (from checks data 5), "Open escalations"
  (flags with status open, class != CONVENTION).
- `ESCALATIONS.md` — open flags of class AMBIGUITY, TERM, CLAIM-DEFECT, MECH,
  grouped by class, each with segment id, IT text, EN text, issue, options.
- `audit_numbers.csv` — the numbers audit table.
- `terminology.csv` — copy of the project's file.
- `notes-for-human-reviewer.md` — copied from `<project>/` when that file
  exists; deleted from `out/` when it does not, so a stale copy cannot outlive
  the project file. Authored by the model, never generated.

**CONVENTION flags reach no deliverable.** Not the Flags column, not
`ESCALATIONS.md`, and there is no "Applied conventions" appendix. A CONVENTION
flag is a rule we applied and disclosed, filed once per rule (`flags.md`,
Classes) as the internal record that lets the firm reverse it with one decision.
The only thing a human editor is told about drafting conventions is
`notes-for-human-reviewer.md`, and it says how an expression was rendered and
nothing else: the Italian, the English, no reasons, no doubts, no "confirm".
The rule this replaces filed one CONVENTION flag per OCCURRENCE of a
transitional phrase, which put 18 rows of disclosure into cafe124's review table
— 18 more places for a reader to lose the flags that are actually questions.
More told is not more useful.
Reopen both docx files with python-docx after writing and assert: filing
contains the claims heading and N claims; side-by-side row count = segments
count + 1 header. Print output paths.

## Review module

A second skill, `patent-review`, reviews a finished project the way an
independent professional reviewer would: blind to the pipeline's own doubts,
against the whole style guide, producing its own findings, then a comparison
against the pipeline's flags. Four deterministic scripts support it; every
judgement stays with the model at run time.

The four scripts live in the patent-translate `scripts/` directory because they
share `common.py` and its conventions — there is no second scripts tree, and
`.claude/skills/patent-review/` holds only `SKILL.md`.

**The review module does not modify `common.py`.** No review script adds keys to
`common.project_paths`. Each resolves state paths with
`common.project_paths(project, need_source=False)` and the review directory as
`paths["root"] / "review"`. Four scripts, four new files, no shared edit.

### Review artifacts and locations

```
projects/<slug>/review/       # project data: confidential, never committed
  packet/                     # the blind input      <- review_packet.py
    pairs.json
    style-guide.md
    terminology.csv
  findings.json               # the reviewer's output <- model
  comparison_candidates.json  # candidate alignment  <- review_compare.py
  REVIEW.md                   # the report           <- model
  proposed_revisions.json     # set_final.py input   <- model, after the go
.claude/skills/patent-review/SKILL.md              # the reviewer's procedure
.claude/skills/patent-translate/
  references/review_sources.json                   # edition manifest
  scripts/review_packet.py                         # the four review scripts
  scripts/review_validate.py
  scripts/review_compare.py
  scripts/review_sources.py
```

- Review JSON is UTF-8 with 2-space indent: the scripts write it with
  `common.write_json` (atomic), and the model matches that shape by hand. The
  two packet copies are byte copies; `REVIEW.md` is Markdown.
- `projects/*` is gitignored, so nothing under `review/` is ever committed. The
  tracked review files are the four scripts, `review_sources.json`, the
  `patent-review` `SKILL.md` and the fixture seed data under `scripts/dev/`;
  the generated `projects/_fixture_review/` is untracked like
  `projects/_fixture_bad/`.
- `proposed_revisions.json` is an ordinary `set_final.py` revisions file (schema
  under `set_final.py` below): there is NO new writer for English text. Every
  `reason` in it MUST begin with the finding id it implements, e.g.
  `"F-0012: by way of -> by (style-guide, Standard renderings)"`.
- `REVIEW.md` is authored by the model per `patent-review/SKILL.md`: one note per
  problem, each giving the segment, the Italian, the English, what is wrong and
  the correction proposed. Nothing more is required of it. The comparison
  machinery described further down this section — `findings.json`,
  `comparison_candidates.json`, the review policies about dismissals and
  unreproduced flags — is **not part of the review procedure**. It was cut on
  2026-07-30: a review is a document somebody reads. The schemas and the scripts
  stay specified and tested because they work and a future job may want them, but
  `patent-review/SKILL.md` does not call them and neither should anything else
  without a decision to bring them back.

### review/packet/pairs.json  (written by review_packet.py)

The blind input: exactly what an independent human reviewer is given.

```json
{
  "meta": {
    "project": "_fixture",
    "counts": {
      "entries": 34,
      "by_section": {"title": 1, "abstract": 2, "description": 24, "claims": 7}
    }
  },
  "entries": [
    {"id": "T-001", "kind": "title", "section": "title",
     "text_it": "…", "text_en": "…"}
  ]
}
```

Rules:
- Entry keys are EXACTLY `id`, `kind`, `section`, `text_it`, `text_en`. No sixth
  key, now or later: the FORBIDDEN list below is the reason this one is closed.
- One entry per segment in `state/segments.json`, in `segments.json` order, so a
  review shard is a contiguous slice. Title, abstract paragraphs, headings,
  description paragraphs and claims are present: nothing is sampled. Headings are
  reviewable text (`RIASSUNTO` → `ABSTRACT` is a rule of the guide, not a
  formatting detail).
- The ONE exception is the untranslated section markers: a segment with
  `kind: heading` and `section: title` or `section: claims` — `TITOLO`,
  `RIVENDICAZIONI` — is omitted, and the builder reports how many and which ones
  on stdout. They have no English anywhere in the pipeline to review:
  `translate_deepl.py` deletes the title paragraphs and the whole claims section
  before uploading, so no pair exists for them, and `assemble.py` writes its own
  `CLAIMS` heading rather than translating one. `checks.py` `structure` exempts
  exactly the same two kinds of segment from coverage, for the same reason.
  Demanding a delivered English text for them would make every packet build fail.
  Every OTHER segment must carry one, or the build fails.
- `kind` and `section` are copied verbatim from the segment (same enums as
  `segments.json`).
- `text_it` is the segment's `text_it` copied raw (claims: the parts already
  joined with `\n`). Never normalized.
- `text_en` is the DELIVERED English, resolved per segment kind:
  - title (`T-*`) → `translations.json` `title.text_en`;
  - claim (`C-*`) → `claims_en.json` `claims[].text_en`;
  - everything else → the matching `translations.json` pair's `text_en_final`
    when it is not null, else its `text_en_deepl`.
  WHICH of the two supplied it is NOT recorded. A pair carrying a final is a
  pair the pipeline already doubted; exposing that is anchoring.
- `meta.project` is the project directory name (`paths["root"].name`).
- No timestamp, no hash, no run id anywhere in the packet: same state → byte
  identical packet, so `dev/smoke.py` can assert a golden output with no field
  masking.
- Text only. No docx, no drawings: reference-sign integrity is judged Italian
  against English, never against a figure.
- Missing English is a hard error, never an empty string: a null
  `title.text_en`, a segment other than a section marker with no pair, a pair
  whose delivered English is blank, or a claim absent from `claims_en.json` makes
  `review_packet.py` exit 1 listing every gap. "Full finals" means every segment
  the packet carries has a delivered English text — NOT that every pair has a
  non-null `text_en_final`, which the pipeline legitimately leaves null wherever
  the DeepL output needed no edit.

### review/packet/style-guide.md and review/packet/terminology.csv

- `style-guide.md` — byte copy of
  `.claude/skills/patent-translate/references/style-guide.md`. The reviewer
  reads the copy so the packet is self-contained and a blind prompt can name one
  directory. It is the single style authority: `patent-review/SKILL.md` cites it
  by heading and never restates a rule.
- `terminology.csv` — the DELIVERED glossary `<project>/out/terminology.csv`
  **projected onto six columns**, in the delivered column and row order:
  `term_it`, `variants_it`, `term_en`, `variants_en`, `category`, `in_claims`.
  Absent (assemble has not run) → exit 1. If it differs from
  `<project>/terminology.csv`, the delivery is stale → exit 1 telling the
  operator to re-run `assemble.py`; the reviewer must judge terminology against
  what was delivered, never against a working copy that has moved since. A
  header lacking one of the six columns → exit 1: emitting a narrower table
  would hide a schema change behind a reviewer who simply never saw the term.

  **It is deliberately NOT a byte copy, and this is an anti-anchoring rule, not
  a formatting choice.** `rationale`, `status` and `flag` are withheld.
  The glossary states both what was decided and why, and `flag` is "empty when
  no doubt" by its own schema definition further up this document — it is the
  pipeline's doubt record in prose. On a real job it names the open TERM
  escalations outright (`'"agitator" chosen over "stirrer"; confirm.'`) and on
  the fixtures it names the failing mechanical checks by name (`'…deliberate
  claim_support failure.'`). A reviewer reading those confirms the list it was
  handed instead of re-deriving anything. The reviewer still needs the six
  columns it does get: consistency under PCT Rule 10.2 is checkable only against
  the locked glossary.

  This was found by the first end-to-end trial, after the FORBIDDEN list below
  had been written and after the blindness assertion in `dev/smoke.py` had been
  written. Both enumerate FILES, and `terminology.csv` is a permitted file, so
  neither could see that two of its columns carry what three forbidden files
  carry. The lesson generalises: **a permitted file is not a blind file.** When a
  column, field or note is added to anything the packet copies, ask what it
  reveals before asking whether the file is allowed.

### FORBIDDEN in the packet (the anti-anchoring rule)

The packet builder copies nothing else, and a blind review prompt may name
`<project>/review/packet/` and no other path in the repo. Blindness is a
property of the packet, not of an instruction not to peek. Specifically
forbidden, with the reason each one is an answer key:

- `state/flags.json` — the pipeline's doubts with class, issue and options. It
  is the answer key in full.
- `state/checks.json` — which mechanical check failed, and on which segment.
- `state/translations.json` — the worst offender. `edits[].reason` names the
  category and the trigger of every change the pipeline already made
  (completeness / meaning / terminology / register), so the reviewer would be
  reading the previous reviewer's conclusions; and `text_en_deepl` sitting next
  to `text_en_final` marks exactly which segments were doubted.
- `state/claims_en.json` `conventions` — the drafting decisions already taken.
- `state/backtranslation.json` and `state/terminology_report.json` — the same
  leak by a different route (which claims were probed, which terms under-occur).
- `out/ESCALATIONS.md`, and `out/side_by_side.docx` (its Flags column) — the
  flags again, in prose.
- Any earlier `review/` output for the same project, and any third-party review
  document: a previous verdict anchors as hard as the pipeline's own.

No review script reads `state/flags.json` before `findings.json` exists and
validates. `review_compare.py` is the first and only review script permitted to
open it: generation is blind, comparison is anchored by design.

### review/findings.json  (written by the model, checked by review_validate.py)

The reviewer's own output. Produced without the packet-forbidden files above.

```json
{
  "meta": {"project": "_fixture", "generated_at": "2026-07-30T09:12:00+00:00"},
  "findings": [
    {
      "id": "F-0001",
      "class": "AMBIGUITY|TERM|CONVENTION|CLAIM-DEFECT|COVERAGE-GAP",
      "segment_id": "D-0007",
      "lens": "rules|grammar",
      "issue": "…",
      "options": ["…", "…"],
      "rule": "style-guide, Transitional phrases; EPO Guidelines F-IV, 4.20",
      "proposed_en": null,
      "shard": "description-03-rules"
    }
  ]
}
```

`meta.project` is the project directory name; `meta.generated_at` is an ISO-8601
UTC stamp in `common.now_iso` shape. Extra `meta` keys ARE allowed (a run may
record its shard plan there); extra keys on a finding are not.

Required per finding: `id`, `class`, `segment_id`, `lens`, `issue`, `options`.
Optional: `rule` (mandatory in the cases below), `proposed_en`, `shard`. No
other key is permitted — unknown keys are a violation, not ignored extras,
because a typo like `proposal_en` in a model-written file would silently drop
the proposal. (This is deliberately stricter than `common._check`, which allows
extras in the pipeline's own state files.)

- `id` — `^F-\d{4}$`, zero-padded, unique within the file, assigned in merge
  order. Stable: `REVIEW.md`, `comparison_candidates.json` and every
  `set_final.py` reason cite it, so ids are never renumbered after the report is
  written.
- `class` — the `flags.md` taxonomy (`AMBIGUITY`, `TERM`, `CONVENTION`,
  `CLAIM-DEFECT`) plus `COVERAGE-GAP`: a phenomenon present in the document that
  the style guide does not regulate at all. `MECH` is NOT available to the
  reviewer: it belongs to `checks.py`, and a reviewer finding that happens to
  duplicate a mechanical check is filed under its substantive class.
- `COVERAGE-GAP` is a finding about the GUIDE, never about the project. It never
  becomes a flag and never becomes an edit: it is adjudicated as a change to
  `references/style-guide.md`, or explicitly declined, in `REVIEW.md`. Without
  it, "if a rule is not here, it is not a rule" lets gaps normalise silently.
- `segment_id` — an `id` present in `packet/pairs.json`, or the literal `DOC`
  for a document-wide phenomenon with no single locus (term drift across the
  whole text). A `DOC` finding must name the segments concerned inside `issue`;
  no script can check that, and no script may invent a locus for it.
- `lens` — `rules` or `grammar`, MANDATORY, never merged. The rules lens applies
  the guide and is forbidden to improve the English; the grammar lens exists to
  propose better English and its every proposal must pass the three-question
  adjudication before it can become an edit. The lenses are separated by the
  citation duty below, not by the presence of `proposed_en`: a rules finding may
  well carry the correct rendering.
- `issue` — non-empty. What is wrong, in the reviewer's own words.
- `options` — a non-empty list of concrete alternatives: a specific English
  rendering, or a specific action with its consequence. `AMBIGUITY` requires at
  least two (each reading with its English consequence, per `flags.md`).
  "To be reviewed" and its family are violations — exact lexicon under
  `review_validate.py`.
- `rule` — the style-guide rule or the citation the finding rests on. MANDATORY
  (non-empty) for every finding with `lens: rules` and `class != COVERAGE-GAP`:
  a rules finding that cannot cite the guide is either a coverage gap (use
  `COVERAGE-GAP`) or ordinary English (use `lens: grammar`). Optional for
  `grammar` findings and for coverage gaps, which may still cite the norm the
  guide fails to reflect.
- `proposed_en` — optional replacement text for the whole segment. When present
  it must be a non-empty string and must differ from the packet's `text_en` for
  that segment: a proposal identical to the delivered English is a no-op.
- `shard` — optional provenance (which blind pass produced the finding), used by
  the report to see which shard missed what. Ignored by `review_compare.py`.

### review/comparison_candidates.json  (written by review_compare.py)

CANDIDATES ONLY. Whether two differently-worded entries are the same doubt is a
semantic judgement, made afterwards by the model, never by string matching. This
file is produced by segment-id alignment and nothing else.

```json
{
  "meta": {
    "project": "_fixture",
    "generated_at": "2026-07-30T09:20:00+00:00",
    "counts": {"findings": 41, "flags": 45, "candidates": 27,
               "reviewer_only": 14, "pipeline_only": 18}
  },
  "candidates": [
    {"segment_id": "C-04",
     "finding_id": "F-0012", "finding_class": "CLAIM-DEFECT",
     "finding_issue": "…",
     "flag_key": "a1b2c3d4e5f6", "flag_class": "CLAIM-DEFECT",
     "flag_issue": "…", "flag_status": "open"}
  ],
  "reviewer_only": [
    {"segment_id": "D-0007", "finding_id": "F-0003",
     "finding_class": "TERM", "finding_issue": "…"}
  ],
  "pipeline_only": [
    {"segment_id": "C-01", "flag_key": "9f8e7d6c5b4a", "flag_class": "TERM",
     "flag_issue": "…", "flag_status": "open"}
  ]
}
```

Rules:
- Alignment is by `segment_id` and by nothing else. `class` is NOT used: an
  identical class is not evidence that two entries are the same doubt, and a
  different class is not evidence that they are not. No regex, no keyword
  overlap, no similarity score over `issue` text — a comparator that guesses
  semantics would launder the judgement it is supposed to hand over.
- `candidates` is the FULL CROSS PRODUCT per segment: a segment carrying 2
  findings and 3 flags yields 6 candidate pairs, because the script cannot know
  which pairs with which. The model discards the non-pairs.
- `reviewer_only` = findings whose segment carries no pipeline flag at all.
  `pipeline_only` = flags whose segment carries no finding at all. A finding or
  flag appearing in at least one candidate pair appears in neither bucket.
- All flags in `state/flags.json` participate: no class filter, no status
  filter. A `resolved` flag is still a pipeline doubt — the reviewer
  reproducing it is concordance, not a new finding — so `flag_status` is echoed
  and the model weighs it.
- A `DOC` finding aligns with flags whose `segment_id` is null or absent (the
  only sensible mechanical alignment for a document-wide entry); with no such
  flag it goes to `reviewer_only`. A flag with a null `segment_id` and no `DOC`
  finding goes to `pipeline_only` with `"segment_id": null`.
- `finding_issue` and `flag_issue` are verbatim copies, never summaries, so the
  file is readable on its own. They are copies of the same-run inputs: nothing
  is re-derived from them.
- Read-only with respect to `state/`: the script opens `state/flags.json` and
  writes only under `review/`. It never calls `flags.py add` or
  `flags.py resolve`.
- A project with no flags has `{"flags": []}`, which is a normal input: every
  finding then lands in `reviewer_only`.
- `meta.generated_at` is the only non-deterministic field in the file: an
  assertion over canned inputs compares the buckets, not the bytes.

### references/review_sources.json  (the edition manifest, tracked)

The manifest for the cheap in-run edition check. It must stay consistent with
the `## Sources` section of `references/style-guide.md`, and that consistency is
asserted offline (see `review_sources.py verify-manifest`).

```json
{
  "sources": [
    {
      "id": "pct-regs",
      "name": "Regulations under the PCT",
      "url": "https://www.wipo.int/…/pct-regs-page",
      "edition_token": "in force from January 1, 2026",
      "style_guide_url": "https://www.wipo.int/…/docs-en-texts-pct-regs.pdf",
      "style_guide_edition": "in force 1 January 2026",
      "note": null
    }
  ]
}
```

- Required per entry: `id` (kebab-case, unique), `name`, `url`,
  `edition_token`. Optional: `style_guide_url` (defaults to `url`),
  `style_guide_edition`, `note` (English, free text — where a token is weak, say
  so here).
- `url` must be a page whose FETCHED BODY contains `edition_token` as literal
  text. Where the guide cites a PDF, the manifest points `url` at the HTML page
  that states the edition and records the cited PDF in `style_guide_url`:
  searching a compressed PDF stream for a token yields a false "absent" for
  every entry.
- `edition_token` is chosen so that its ABSENCE is evidence the page moved or
  changed edition. A token present in every past and future version of the page
  is worthless and must not be used.
- `style_guide_url` must occur literally in the guide's `## Sources` section,
  and every `https?://` URL in that section must belong to exactly one entry:
  one-to-one, both directions.
- `style_guide_edition`, when present, must occur literally in that same
  section. This is where the teeth are: bumping the guide's edition without
  bumping the manifest (or the reverse) fails the offline check.
- A firing edition check triggers the separate deep normative re-audit job. That
  job is out of scope here: this check is a smoke alarm, not an audit.

### Review policies

- **Blindness is enforced by packet construction.** The generation phase reads
  `review/packet/` only. Prompts for blind passes may name that directory and no
  other path. A file the packet does not contain is not "available if needed" —
  it is out of the phase.
- **The reviewer proposes; it never writes.** No review script writes anything
  outside `<project>/review/`. `set_final.py` remains the SINGLE writer for
  reviewed English (`state/translations.json`, `state/claims_en.json`) and
  `flags.py` the single writer for `state/flags.json`. Accepted fixes go through
  `proposed_revisions.json` + `set_final.py` with the finding id in every
  `reason`; accepted new doubts go through `flags.py add`, with the finding id
  at the end of `--issue` as ` (review F-0012)` so `flags.py list` shows the
  provenance.
- **The blind phase leaves `state/` byte-identical, and that is verified.**
  `review_packet.py` prints a `state_sha256` digest; re-running it after the
  blind phase reprints the digest and rewrites a byte-identical packet. A
  different digest means something wrote to `state/` during a phase that must
  not write, and the run is void.
- **A spurious finding never auto-closes a pipeline flag.** No review step calls
  `flags.py resolve`. A flag the reviewer did not reproduce (a `pipeline_only`
  entry) becomes a note in `REVIEW.md`; closing it stays a decision by Mario or
  the firm, per `flags.md`.
- **Every dismissal is recorded with the question that killed it.** The
  adjudicating session is judge in its own cause, so each dismissed finding is
  listed in `REVIEW.md` with the relevant question from the style guide's
  "Adjudicating a review comment" — Q1 technical content, Q2 term of art or
  normative requirement, Q3 ordinary English — named by number and by the rule
  it rests on, e.g. `dismissed Q2 (reference signs are copied character for
  character — style-guide, Never negotiable)`. "Rejected as unnecessary" is not
  an adjudication.
- **A genuine doubt raised is flagged regardless of the fix proposed with it.**
  Per the guide: a reviewer who raises a genuine ambiguity is always right to
  raise it. Rejecting the proposed wording and filing the doubt as an AMBIGUITY
  (or CLAIM-DEFECT) flag is the normal outcome, not a contradiction. A finding
  judged to be the same doubt as an existing flag adds no second flag.
- **An accepted proposal is applied document-wide or not at all** (style guide,
  "Consistency is the deliverable"). Applying it only where the reviewer
  happened to mark manufactures an inconsistency no check can attribute to the
  source.
- **Escalation actionability is audited in the anchored phase.** Every OPEN
  pipeline flag's `options` are held to the same concreteness standard the
  validator applies to findings (`review_validate.option_violations`), and the
  failures are listed in `REVIEW.md`.
- **No second style document.** `patent-review/SKILL.md` references style-guide
  sections by heading and never restates a rule.

### review_packet.py

`review_packet.py [build] --project P`
`review_packet.py state-digest --project P`

- The `build` subcommand is an accepted alias of the bare form, so
  `patent-review/SKILL.md` and this contract may spell the command either way.
- `state-digest` prints the `state_sha256` line and NOTHING else: no packet is
  built, no file is written, nothing under `review/` is touched. This is the
  subcommand the no-write verification must use. Re-running `build` to compare
  the digest is wrong: it overwrites `packet/pairs.json`, so in the single case
  the check exists for — something wrote to `state/` — it destroys the text the
  reviewer actually worked from and leaves the void run undiagnosable. Exit 1 if
  the state directory is absent.
- The digest proves nothing was WRITTEN to `state/`. It cannot prove nothing was
  READ. The subagents' blindness is enforced by the packet; the orchestrating
  session's blindness is policy only, and no mechanism in this repo checks it.
- Reads: `<P>/state/segments.json`, `<P>/state/translations.json`,
  `<P>/state/claims_en.json`, `<P>/out/terminology.csv`, `<P>/terminology.csv`
  (for the staleness comparison) and
  `.claude/skills/patent-translate/references/style-guide.md`. Nothing else —
  and never any of the FORBIDDEN files above.
- Writes (`build` only): `<P>/review/packet/pairs.json`,
  `<P>/review/packet/style-guide.md`, `<P>/review/packet/terminology.csv`. It
  creates the directories, overwrites those three files, and touches nothing else
  under `review/`.
- Deterministic: same state → byte-identical output.
- Prints a summary (entry counts by section, output paths) and, as its LAST
  line, `state_sha256 <hex>`: the digest over the state directory, defined as
  sha256 of, for every file directly in `<P>/state/` sorted by name, the file
  name encoded UTF-8, a `\0` byte, the file bytes, a `\0` byte. This is the
  digest the no-write policy is verified with.
- Exit 0 on success. Exit 1 on any missing or incomplete input: state file
  absent, `title.text_en` null, a segment other than a section marker with no
  English, a claim missing from `claims_en.json`, `out/terminology.csv` absent or
  differing from `<P>/terminology.csv`. List EVERY gap before exiting, do not stop
  at the first. No exit path of this script's own returns 2 — that code is the
  missing-DeepL-key convention, and argparse's own usage error, which every
  script in this repo shares.
- Also exit 1, as one more gap line each, when `review/packet/` already holds any
  entry that is not one of the three files above. Blindness is a property of the
  DIRECTORY: a blind pass may name `<P>/review/packet/` and no other path, so a
  leftover there — an earlier run's notes, a `.tmp` from an interrupted write, an
  answer key copied in by hand — is part of the packet whatever it is. The builder
  never deletes project data, so refusing and naming the file is the only safe
  outcome.

### review_validate.py

`review_validate.py --project P [--input FILE]`

- Reads: `<P>/review/findings.json` and `<P>/review/packet/pairs.json`. It never
  reads `state/`.
- `--input` validates FILE instead of `<P>/review/findings.json`, against that
  same project's packet. It exists so `dev/smoke.py` can run its accept and
  reject vectors against a real packet without writing a deliberately broken
  findings file into a project.
- Writes nothing.
- Exports, for import (not shelling) by other review scripts:
  - `validate_findings(findings_path: Path, pairs_path: Path) -> list[str]` —
    pure: returns violation strings, prints nothing, never exits.
  - `option_violations(option: str) -> str | None` — the single definition of a
    non-concrete option: a reason string, or None when the option is concrete.
- Violations, one line each, `FAIL <finding id or "findings.json"> <detail>` to
  stdout, then a count line, mirroring `validate_state.py`. Clean run prints
  `OK: N finding(s) valid`.
- Checks, all of them: top level is an object with `meta.project` and
  `meta.generated_at` as non-empty strings and `findings` a list; per finding —
  no unknown key; no missing required key; `id` matches `^F-\d{4}$` and is
  unique; `class` in the five values; `lens` in {`rules`, `grammar`};
  `segment_id` is a `pairs.json` entry id or the literal `DOC`; `issue` a
  non-empty string; `options` a non-empty list of strings with every element
  concrete; at least two options when `class` is `AMBIGUITY`; `rule` non-empty
  when `lens` is `rules` and `class` is not `COVERAGE-GAP`; `proposed_en`, when
  not null, a non-empty string differing from that segment's packet `text_en`
  (skipped for `DOC`); `shard`, when present, a non-empty string.
- An option is NOT concrete (exact lexicon — implement it literally) when, after
  `common.normalize` and lower-casing, it is EMPTY, or it
  CONTAINS any of: `to be reviewed`, `to be checked`, `to be verified`, `to be
  confirmed`, `to be decided`, `to be determined`, `to be discussed`, `to be
  assessed`, `to be evaluated`, `tbd`, `da verificare` — or it EQUALS, after
  stripping trailing `.`, `?` and `!`, any of: `review`, `check`, `verify`,
  `confirm`, `reconsider`, `rephrase`, `as appropriate`, `see above`,
  `see below`, `n/a`, `na`, `none`, `other`, `unclear`, `unknown`,
  `ask the firm`, `ask mario`, `escalate`, `flag it`.
- **There is no minimum length, deliberately.** An earlier version of this
  lexicon set a three-character floor and it rejected `by` — which is the style
  guide's own rendering of `mediante` in the description, the correct fix for the
  `by way of` failure mode, and an option on a real open cafe124 TERM flag.
  Length is not evidence about concreteness, and this test claims only what it
  can decide: emptiness and the placeholder lexicon. It cannot tell a useful
  alternative from a useless one, and must not pretend to.
- Exit 0 when there are no violations; exit 1 when there is at least one, or
  when an input is missing or unparseable.
- The escalation-actionability audit in `patent-review/SKILL.md` reuses
  `option_violations` over the pipeline's own open flags, so the two apply one
  standard. It restricts itself to the three classes that ask the firm a question
  — AMBIGUITY, TERM, CLAIM-DEFECT — and for those an EMPTY `options` list is
  reported as `no option at all`: being asked to decide with nothing to choose
  between is the worst case, not an exempt one. CONVENTION and MECH carry no
  options by design (`flags.md`, Classes) and are excluded rather than reported
  one by one.

### review_compare.py

`review_compare.py --project P`

- Reads: `<P>/review/findings.json`, `<P>/review/packet/pairs.json`,
  `state/flags.json`.
- Writes: `<P>/review/comparison_candidates.json`. Nothing under `state/`, ever.
- Refuses to align an invalid file: it imports
  `review_validate.validate_findings` and exits 1, printing the violations, if
  that returns anything.
- Deterministic order: `candidates` sorted by (segment id in `pairs.json` order,
  then `finding_id`, then `flag_key`), `DOC`/null-segment entries last;
  `reviewer_only` by (segment order, `finding_id`); `pipeline_only` by (segment
  order, `flag_key`).
- Prints the four counts from `meta.counts` and the output path.
- Exit 0 on success (empty buckets are a valid result, not an error). Exit 1 on
  a missing or unparseable input, or on findings violations.

### review_sources.py

`review_sources.py verify-manifest [--manifest FILE]`
`review_sources.py check [--manifest FILE]`

Repo-level, no `--project`: the manifest and the style guide are repo files, not
project state. Both subcommands read `review_sources.json` and
`style-guide.md` from `.claude/skills/patent-translate/references/`, resolved
from the repo root like every other script. Neither subcommand writes any file.
`--manifest` reads FILE instead of the tracked `review_sources.json`, always
against the tracked `style-guide.md`: it exists so `dev/smoke.py` can assert the
inconsistency vectors (a bumped edition, a dropped entry, a moved URL) against a
mutated copy without touching the tracked manifest.

`verify-manifest` (offline, this is what `dev/smoke.py` calls):
- Manifest parses; `sources` is a non-empty list; every entry has non-empty
  `id`, `name`, `url`, `edition_token`; `id` and `url` are each unique.
- Every entry's `style_guide_url` (defaulting to `url`) occurs literally in the
  guide's `## Sources` section (from that heading to end of file), and every
  `https?://` URL in that section belongs to exactly one entry.
- Every `style_guide_edition` present occurs literally in that section.
- Violations one per line to stdout, then a count line; clean run prints
  `OK: N source(s) consistent with style-guide.md`.
- Exit 0 when consistent, exit 1 on any violation or a malformed manifest.

`check` (network):
- Runs every `verify-manifest` assertion FIRST and exits 1 if the manifest is
  broken: never hit the network on a broken manifest.
- Then, per entry, one `requests.get(url, timeout=20, allow_redirects=True)`. No
  retries: this is a smoke alarm, not a pipeline stage. A non-200 status, a
  request exception, or a body without `edition_token` are all reportable
  outcomes, not crashes.
- One line per entry, in manifest order, exact format:
  - `<id>  OK       token found: "<edition_token>"`
  - `<id>  MISSING  token absent from <n> bytes fetched from <url>`
  - `<id>  ERROR    HTTP <status> from <url>` or
    `<id>  ERROR    <ExceptionClass>: <message>`
  then the summary line `sources: <n> ok, <n> missing, <n> error`.
- Exit 0 when every entry is OK. Exit 3 when at least one entry is MISSING or
  ERROR — including the fully-offline case, where every entry is an ERROR. Exit
  1 only for a broken manifest.
- Exit 3 means "the world moved, or we could not look": the caller records the
  report VERBATIM in `REVIEW.md` and the review proceeds. It is data, not a
  broken run. Exit 1 is a repo defect and stops the run.
- The network path is not smoke-coverable (`dev/smoke.py` is offline); that gap
  belongs in `docs/harness-backlog.md`.

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

The scripts implementing this live under `scripts/dev/` and none of them is
wired into a real job: `make_fixture.py` writes the Italian source,
`make_fixture_en.py` writes the canned English baseline, `make_fixture_bad.py`
builds the mutated copy above, and `smoke.py` chains the whole offline run and
asserts the outcome at both ends — the clean fixture's check statuses and all
six defects here. `make_fixture_en.py` refuses to run on a project whose
directory name does not start with `_fixture`: canned English is test
scaffolding, and that restriction is what keeps the never-fabricate policy true
while it exists.

## Definition of done (every module)

Your scripts RUN. Execute them for real on the fixture (or on synthetic state
files you build to these schemas), show the actual commands and output in your
report, and leave the repo in a state where the next phase can run them as-is.
No "should work". If something is untestable without the DeepL key, say so
explicitly in your report — do not fake it.
