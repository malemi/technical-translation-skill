# patent-translate

Give it an Italian patent application. Get back the English version you can file
as a PCT translation — plus a bilingual review document that shows, segment by
segment, every choice that was made and every doubt that was left open.

It runs as a **Claude Code skill**. For a real job you do not run scripts by
hand: you drop the Italian `.docx` into a folder, ask Claude to translate it, and
answer its questions. Python scripts do the mechanical parts (splitting the
document, calling DeepL, running the verification battery, building the output
files); Claude does the parts that need judgement (terminology, claims, fidelity
review, flagging ambiguities).

## What you get

Everything lands in `projects/<your-job>/out/`:

| File | What it is |
| --- | --- |
| `filing_en.docx` | The English application: title, description, claims, abstract. This is the deliverable. |
| `side_by_side.docx` | Italian and English in two columns, one row per segment, with the open flags on each row. This is what you review. |
| `ESCALATIONS.md` | The questions Claude could not answer from the source alone, grouped by kind. You are expected to answer these. |
| `audit_numbers.csv` | Every number and unit in the document, Italian vs English, so you can verify nothing drifted. |
| `terminology.csv` | The agreed glossary that was used. |

## Try it in two minutes

The repo ships a small synthetic Italian patent (a cold-brew coffee machine) and
a canned English side for it, so you can watch the whole machinery work — **no
DeepL account, no network, no real document involved**.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python .claude/skills/patent-translate/scripts/dev/smoke.py
```

Run it from the repo root. One command does everything: builds the synthetic
Italian application, splits it, loads the canned English side, runs the
verification battery, assembles the deliverables, then builds a deliberately
corrupted copy and confirms that every seeded defect is caught. It prints
`SMOKE OK` and exits 0 when all of that holds.

Then look at what it produced in `projects/_fixture/out/`. Open
`side_by_side.docx` first — Italian and English in two columns with the flags
attached to each row. That is what reviewing a real job looks like.

Two things in the output are worth understanding:

- **On the clean fixture the battery reports one failure and one warning, and
  that is correct.** The synthetic patent has deliberate defects seeded into the
  *Italian*, because the pipeline's job is to surface them rather than quietly
  fix them: one part is named two different ways at the same reference sign, and
  one component is recited in a claim but never described. An all-pass run on
  this fixture would mean the checks stopped working.
- **The corrupted copy** applies the six mutations listed at the bottom of
  [`CONTRACTS.md`](CONTRACTS.md) — a dropped reference sign, a changed
  measurement, a terminology swap, a narrowed claim dependency, a claim split
  into two sentences, and a term used with no antecedent. Each must be caught by
  the check the contract assigns to it, and the smoke test asserts exactly that.

If you want to see the individual stages instead of the whole run, the
interesting one is `ingest.py`: it prints what it understood from the document —
segment counts, the **claim dependency graph** (which claim depends on which,
multiple dependencies included), and the **reference-sign inventory**, every
`(1)`, `(2)`, `(3a)` with the Italian terms attached to it.

```
.venv/bin/python .claude/skills/patent-translate/scripts/ingest.py --project projects/_fixture
```

What the demo deliberately cannot do is translate. Without a DeepL key the
translation scripts exit 2 with a clear message; the English side used above is
canned fixture data, clearly marked as such and restricted to fixture projects.
There is no mock mode and no fabricated output anywhere in the real pipeline, by
design.

## Using it on a real patent

You need a DeepL key first (next section). Then:

1. Make a folder for the job and put the Italian application in it:
   ```
   mkdir -p projects/acme
   cp ~/somewhere/domanda.docx projects/acme/
   ```
   One `.docx` per folder. If yours is a legacy binary `.doc`, Claude converts it
   first with LibreOffice — say so and it will handle it.

2. Open Claude Code in this repo and ask, in plain words:
   ```
   traduci projects/acme
   ```
   That triggers the `patent-translate` skill, which runs the whole procedure in
   [`SKILL.md`](.claude/skills/patent-translate/SKILL.md).

3. **Claude will stop and wait for you.** This is the important part. Before
   anything is translated, it reads the entire document, builds the glossary —
   every substantive term, with its Italian and English variants — and presents
   it for approval. Nothing is translated until you lock that terminology. This
   is deliberate: DeepL is only consistent across a long document if the
   terminology is fixed up front.

4. When it finishes, it reports the output paths, the open escalations, and any
   multiple-dependent claims (which matter if the case later enters the US
   national phase). Review `side_by_side.docx`, answer `ESCALATIONS.md`.

The governing rule throughout: **the Italian is authoritative and is never
improved.** A badly drafted claim is translated faithfully and flagged, not
fixed. Where a literal rendering and a nicer-sounding one differ, the literal one
wins and the alternative is recorded as a flag for you to weigh. Ambiguities
become questions, never silent decisions.

Changed your mind about a term after the lock? Edit `terminology.csv` and ask
Claude to re-run. Only the segments whose translation actually changed are
re-reviewed.

## The DeepL key

The scripts read `DEEPL_AUTH_KEY` from the environment; if it is not there they
read a `.env` file at the repo root (plain `KEY=value` lines). Either works:

```
export DEEPL_AUTH_KEY=<your-key>
```

```
# .env at the repo root — git-ignored
DEEPL_AUTH_KEY=<your-key>
```

Both DeepL tiers work and the endpoint is chosen automatically from the key: a
key ending in `:fx` is a Free key and is routed to `api-free.deepl.com`,
anything else is a Pro key on `api.deepl.com`. Free has a much smaller monthly
quota, and DeepL bills a flat 50 000-character minimum per document, so a couple
of runs can exhaust it — you will get a distinct quota-exceeded error if that
happens.

**Which tier you pick is a confidentiality decision, not a cost decision.** The
DeepL Free tier retains submitted text and may use it to train; Pro does not.
Use Free only when the source is no longer secret — typically when the priority
application is already filed, so novelty is secured and the text will be
published anyway. If the application is still unfiled and confidential, use a Pro
key. No service other than DeepL ever sees the text.

## Confidentiality

- **`projects/` is never committed.** `.gitignore` excludes all job folders;
  only the synthetic `projects/_fixture/` is tracked, and it contains no client
  material.
- **`.env` is git-ignored**, so the key never leaves the machine.
- DeepL is the only external service in the pipeline.

## How it works under the hood

The design principle: DeepL with a locked glossary handles the description
prose, because it stays terminologically consistent across a long document.
Claude writes the claims, because that needs the US/PCT conversion — preamble,
transitional phrase, `wherein`, antecedent basis — that DeepL cannot do. Then
mechanical checks verify the result and a bilingual artifact exposes it for
review.

The pipeline, in order:

1. **Convert** (only for a legacy `.doc`) — `dev/convert_doc.py`, via
   LibreOffice.
2. **Ingest** — `ingest.py` splits `source.docx` into segments: title, abstract,
   headings, description paragraphs, and claims with their dependency graph,
   plus the reference-sign inventory (numeric signs like `(300)` and
   letter signs like `(M)`, `(A)`, `(X)`).
3. **Glossary, locked before anything else** — Claude authors
   `terminology.csv`, `glossary.py validate` checks it, you lock it, then
   `glossary.py push` uploads it to DeepL.
4. **Translate the description** — `translate_deepl.py` sends the document
   (minus title and claims) to DeepL with the glossary and pairs the returned
   paragraphs back to the segments. Claude then reviews every pair against the
   Italian.
5. **Author the claims** — Claude writes them one sentence each, with correct
   antecedent basis and reference signs copied verbatim.
6. **Back-translate** — `backtranslate.py` puts the English claims back into
   Italian with **no glossary**, as an independent probe. Claude compares
   meaning, not wording.
7. **Check** — `checks.py` runs 13 mechanical checks (reference signs preserved
   per segment, numbers and units identical, claim dependency graph matches, one
   sentence per claim, claim terms supported in the description, antecedent
   basis, abstract length within PCT Rule 8.1(b), no Italian residue, full
   coverage). Each failure becomes a flag.
8. **Assemble** — `assemble.py` builds `out/`.

### Script reference

All scripts run from the repo root; `--project` takes a path like
`projects/_fixture`.

| Script | Command |
| --- | --- |
| `dev/convert_doc.py` | `--project P [--source name.doc] [--force]` |
| `ingest.py` | `--project P [--source name.docx]` |
| `validate_state.py` | `--project P [--file segments.json]` |
| `glossary.py` | `validate --project P` \| `push --project P` |
| `translate_deepl.py` | `run --project P [--target EN-US]` |
| `backtranslate.py` | `run --project P` |
| `set_final.py` | `--project P --input revisions.json [--dry-run]` |
| `checks.py` | `run --project P` |
| `flags.py` | `add --project P --class TERM --segment C-01 --issue "…"` \| `resolve --project P --key <k> --resolution "…"` \| `list --project P [--open]` |
| `assemble.py` | `run --project P` |

Test scaffolding, under `dev/` — none of it is wired into a real job:

| Script | Command |
| --- | --- |
| `dev/smoke.py` | `[--keep-going]` — runs the whole offline chain and asserts the outcome |
| `dev/make_fixture.py` | no arguments — writes the synthetic Italian source |
| `dev/make_fixture_en.py` | `[--project P]` — writes the canned English side (fixture projects only) |
| `dev/make_fixture_bad.py` | no arguments — builds the seeded-defect copy |

### Layout

```
.claude/skills/patent-translate/
  SKILL.md                 # the procedure Claude follows — the real entry point
  references/              # claim conventions, flag classes, review protocol
  scripts/                 # the pipeline above, plus common.py and dev/ helpers
projects/
  <slug>/                  # one folder per job — never committed
    source.docx            # the Italian application (input)
    terminology.csv        # the glossary
    state/                 # JSON working state
    work/                  # intermediate docx files
    out/                   # the deliverables
  _fixture/                # the synthetic demo patent (committed)
CONTRACTS.md               # schemas, module contracts, policies — authoritative
CLAUDE.md                  # index for a Claude Code session
docs/                      # active context, known issues, harness backlog
```

## Where to look next

- [`CLAUDE.md`](CLAUDE.md) — the index a Claude Code session starts from.
- [`docs/`](docs/README.md) — current state, known issues, harness backlog.
- [`CONTRACTS.md`](CONTRACTS.md) — the build contract. Every state schema and
  every check is specified there; it wins over prose if the two disagree.
- [`docs/known-issues-and-solutions.md`](docs/known-issues-and-solutions.md) —
  read this if `checks.py` reports a failure on the clean fixture (it is
  supposed to) or if `.venv/bin/pip` refuses to start.

This repo follows the conventions of the **mrcall AI kit**
(<https://github.com/hahnbanach/mrcall-ai-kit>).
