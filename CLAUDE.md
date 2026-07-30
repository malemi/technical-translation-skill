# technical-translation-skill — index

Two Claude Code skills over one pipeline. `patent-translate` turns an Italian
patent application into an English one for a PCT filing; `patent-review` reviews a
finished job blind, the way an independent reviewer would. Deterministic Python
scripts do everything mechanical; the model does everything judgmental at skill
run time.

This is a **leaf** repo — no sub-repos are checked out under it.

## Where things are

| Path | Role |
| --- | --- |
| `.claude/skills/patent-translate/SKILL.md` | Entry point for a translation job. The model follows this to run one. |
| `.claude/skills/patent-review/SKILL.md` | Entry point for the blind independent review of a finished job. Holds nothing else. |
| `.claude/skills/patent-translate/references/` | The style guide (the single style authority), flag classes, review protocol, edition manifest. |
| `.claude/skills/patent-translate/scripts/` | The deterministic pipeline (ingest, glossary, DeepL, checks, assemble) plus the four `review_*.py` scripts the reviewer runs — they live here to share `common.py`. |
| [`CONTRACTS.md`](CONTRACTS.md) | The build contract: state schemas, module contracts, global policies. Authoritative when code and prose disagree. |
| [`README.md`](README.md) | What this is and how to try it. Start here if you have never run it. |
| `projects/<slug>/` | One directory per document job, its `review/` included. **Never committed.** |

## Verifying the pipeline

One command, offline, no DeepL key:

```
.venv/bin/python .claude/skills/patent-translate/scripts/dev/smoke.py
```

It runs the whole chain on the fixtures and asserts the outcome at both ends —
the clean fixture's 13 check statuses, all six seeded defects in the corrupted
copy, and the review module's mechanical layer (packet shape, blindness,
validator and comparator vectors, manifest consistency). Exit 0 means the
pipeline still works. Run it after touching anything under `scripts/`.

## Documentation

The transversal docs live in [`docs/`](docs/README.md). The one to read first in
a new session is [`docs/active-context.md`](docs/active-context.md) — it holds
the state right now.

## Rules that bite

- **`projects/` is confidential and never committed.** `.gitignore` excludes all
  project data; only the synthetic `projects/_fixture/` is tracked.
- **English only** in code, comments, docstrings, CLI messages, docs, and log
  lines. Italian appears only as data — document text and fixture content.
- **Never fabricate translation output.** There is no mock or offline mode for
  the DeepL stages; without `DEEPL_AUTH_KEY` they exit 2.
- **Fail loud.** No silent fallbacks, no defaults that mask missing input, no
  bare `except`.
- The DeepL tier is a per-matter confidentiality decision — Free retains
  submitted text, Pro does not. See the Confidentiality section of the
  [`README.md`](README.md).

This repo follows the conventions of the **mrcall AI kit**
(<https://github.com/hahnbanach/mrcall-ai-kit>).
