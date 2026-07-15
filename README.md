# patent-translate

A Claude Code skill that translates an Italian patent application into English
for a PCT filing. Deterministic Python scripts do everything mechanical
(segmentation, DeepL calls, a verification battery, assembly of deliverables);
the model does everything judgmental (terminology, claims, fidelity review,
flags) at skill run time.

The design principle: **DeepL (glossary-constrained) for the description prose,
model-authored claims, mechanical verification, and a bilingual review artifact
with flags.** DeepL keeps terminology stable across long documents; the model
does the US/PCT stylistic conversion of the claims (preamble, transitional
phrase, `wherein`, antecedent basis) that DeepL cannot.

This repository is built to the conventions of the **mrcall AI kit**
(<https://github.com/hahnbanach/mrcall-ai-kit>). See that repository for how the
documentation, the Claude Code harness, and the skill layout are meant to be
used and extended; this skill is one component that follows those conventions.

## Layout

```
.claude/skills/patent-translate/
  SKILL.md                 # entry point — the skill the model follows
  references/              # claim conventions, flags, review protocol
  scripts/
    common.py              # paths, state IO, docx access, extraction, schemas
    ingest.py              # source.docx -> state/segments.json
    validate_state.py      # validate state files against the schemas
    glossary.py            # terminology.csv validate + push to DeepL
    translate_deepl.py     # DeepL document translation of description+abstract
    backtranslate.py       # DeepL EN->IT of the model's claims (naive probe)
    checks.py              # 13-check mechanical verification battery
    flags.py               # add/resolve/list flags
    assemble.py            # build deliverables in <project>/out/
    dev/make_fixture.py    # build the synthetic test project
    dev/convert_doc.py     # convert a legacy .doc source to .docx (LibreOffice)
projects/
  <slug>/                  # one directory per document job (never committed)
    source.docx            # the Italian application (input)
    terminology.csv        # authored by the model, validated by glossary.py
    state/                 # JSON state (segments, translations, claims, ...)
    work/                  # intermediate docx files
    out/                   # deliverables
  _fixture/                # synthetic test project (committed)
CONTRACTS.md               # the build contract: schemas, CLIs, policies
requirements.txt           # python-docx + requests, nothing else
```

## Per-document workflow

The entry point is `.claude/skills/patent-translate/SKILL.md`; the model
follows it. Mechanically the pipeline is:

0. **Convert (if needed)** — a legacy binary `.doc` source is not readable by
   `python-docx`; `dev/convert_doc.py --project projects/<slug>` converts it to
   `source.docx` via LibreOffice, preserving paragraph/heading structure. Always
   verify the conversion with `ingest.py` before trusting it.
1. **Ingest** — `ingest.py --project projects/<slug>` segments `source.docx`
   into `state/segments.json` (title, abstract, headings, description
   paragraphs, claims with dependency graph, and a reference-sign inventory —
   numeric signs like `(300)` and uppercase-letter signs like `(M)`, `(A)`,
   `(X)`).
2. **Glossary first (locked before any translation)** — the model authors
   `terminology.csv` (every substantive term, IT/EN variants, `in_claims`,
   `status`); `glossary.py validate` checks it and writes
   `state/terminology_report.json`. The terminology is locked with the requester
   before translation runs; then `glossary.py push` uploads it to DeepL and
   records `state/deepl.json`.
3. **Translate the description** — `translate_deepl.py run` builds
   `work/description_it.docx` (source minus title and claims), sends it to
   DeepL with the glossary, and pairs the returned paragraphs into
   `state/translations.json`. The model reviews each pair against the Italian
   and sets the finals and the title.
4. **Author the claims** — the model writes `state/claims_en.json` (one
   sentence per claim, correct antecedent basis, reference signs verbatim,
   conventions per `references/claim-conventions.md`).
5. **Back-translate** — `backtranslate.py run` translates the English claims
   back to Italian with **no glossary** (an independent probe) into
   `state/backtranslation.json`; the model compares meaning, not wording.
6. **Check** — `checks.py run` runs the battery, writes `state/checks.json`,
   and records one `MECH` flag per failing item.
7. **Assemble** — `assemble.py run` builds `out/`.

### Script CLIs

All scripts run from the repo root. `--project` takes a path such as
`projects/_fixture`.

| Script | Command |
| --- | --- |
| `dev/convert_doc.py` | `--project P [--source name.doc] [--force]` |
| `ingest.py` | `--project P [--source name.docx]` |
| `validate_state.py` | `--project P [--file segments.json]` |
| `glossary.py` | `validate --project P` \| `push --project P` |
| `translate_deepl.py` | `run --project P [--target EN-US]` |
| `backtranslate.py` | `run --project P` |
| `checks.py` | `run --project P` |
| `flags.py` | `add --project P --class TERM --segment C-01 --issue "…" [--text-it …] [--text-en …] [--option … ]` \| `resolve --project P --key <k> --resolution "…"` \| `list --project P [--open] [--class X]` |
| `assemble.py` | `run --project P` |

### Deliverables (`<project>/out/`)

- `filing_en.docx` — the English application (title, description, `CLAIMS`,
  then the abstract once at the end).
- `side_by_side.docx` — landscape bilingual table (ID | Italiano | English |
  Flags) plus appendices: numbers/units audit, reference-sign map, claim
  dependency map, open escalations, applied conventions.
- `ESCALATIONS.md` — open flags grouped by class.
- `audit_numbers.csv` — the numbers-and-units audit table.
- `terminology.csv` — a copy of the project's glossary.

## DEEPL_AUTH_KEY setup

The DeepL scripts read `DEEPL_AUTH_KEY` from the environment; if it is not set
there they parse a `.env` file at the repo root (simple `KEY=value` lines, no
dependency). If the key is absent the scripts exit 2 with a clear message —
there is no mock or offline mode, and translation output is never fabricated.

**Both DeepL tiers are supported; the endpoint is derived from the key suffix.**
A key ending in `:fx` is a DeepL API **Free** key and is routed to
`https://api-free.deepl.com`; any other key is a Pro key and uses
`https://api.deepl.com`. The base is never hardcoded — it is always derived from
the key. Free tier has a lower monthly character quota (and DeepL bills a flat
50 000-character minimum per document); a quota-exceeded response (HTTP 456) is
surfaced as a distinct error.

Set up either:

```
export DEEPL_AUTH_KEY=<your-key>
```

or a repo-root `.env`:

```
DEEPL_AUTH_KEY=<your-key>
```

## Confidentiality

- **`projects/` is never committed.** `.gitignore` excludes all project data;
  only the synthetic `projects/_fixture/` (no client material) is tracked.
- **`.env` (which holds the key) is git-ignored.**
- **DeepL tier is a per-matter confidentiality decision.** The DeepL **Free**
  tier retains submitted text (and may use it to improve its models); **Pro**
  does not. Use Free only when disclosure of the source is not a risk — e.g.
  when the priority application has already been filed, so novelty is already
  secured and the text will be published anyway. When the source is still
  confidential and unfiled, use a Pro key. No service other than DeepL sees the
  text.

## Testing

`ingest`, state validation, glossary `validate`, the full 13-check battery,
`flags`, and `assemble` are exercised for real on `projects/_fixture` and its
seeded-defect copy (six deliberate defects, all detected). The three
DeepL-calling stages — `glossary.py push`, `translate_deepl.py run`,
`backtranslate.py run` — have been run live against the real DeepL API
(free-tier endpoint) on both the fixture and a real document; they require a
valid `DEEPL_AUTH_KEY` to run.
