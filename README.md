# patent-translate

**Italian patent application in, English patent application out, ready to file.**

You also get a bilingual document showing every choice and every open doubt,
segment by segment. Drop the Italian `.docx` in a folder, ask Claude to
translate it, answer its questions.

## What you get

In `projects/<your-job>/out/`:

| File | What it is |
| --- | --- |
| `filing_en.docx` | The English application. This is the deliverable. |
| `side_by_side.docx` | Italian and English side by side, with the open flags. This is what you review. |
| `ESCALATIONS.md` | The questions Claude could not answer from the source. You answer these. |
| `notes-for-human-reviewer.md` | For the human editor: what we chose, what we are unsure of, what looks wrong in the Italian. |
| `audit_numbers.csv` | Every number and unit, Italian vs English. |
| `bilingual.csv` | The pairs as a flat table, for sorting and diffing outside Word. |
| `terminology.csv` | The glossary that was used. |

## How it works

DeepL with a locked glossary translates the description, because it stays
consistent across a long document. Claude writes the claims, because those need
a conversion DeepL cannot do. Thirteen mechanical checks then verify the
result — reference signs, numbers, the dependency graph, abstract length, and
the rest — and every failure becomes a flag next to the text it is about.

A second skill, `patent-review`, then reviews the finished job **blind**: it
sees the Italian, the English, the style guide and the locked terms, and none
of the pipeline's own doubts. A reviewer who has seen the flags confirms
instead of discovering, so blindness is built into the packet it reads rather
than asked for. It proposes; it never edits.

## Why it is built this way

**The Italian is authoritative and is never improved.** A badly drafted claim is
translated faithfully and flagged, not fixed. Ambiguities become questions, not
silent decisions — which is why the job ends with a list you have to answer.

Every normative rule is cited to its article or rule number and read on the
primary text: [the sources](.claude/skills/patent-translate/references/review_sources.json),
with the rules themselves in
[the style guide](.claude/skills/patent-translate/references/style-guide.md).

**Which DeepL tier you use is a confidentiality decision, not a cost decision.**
Free retains submitted text and may train on it; Pro does not. Use Free only
once the priority application is filed. `projects/` and `.env` are never
committed, and DeepL is the only external service.

## Try it

No DeepL account, no network, no real document — the repo ships a synthetic
Italian patent and a canned English side:

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python .claude/skills/patent-translate/scripts/dev/smoke.py
```

`SMOKE OK` and exit 0 means the whole chain works, seeded defects and all. The
clean fixture reports one failure and one warning on purpose: the *Italian* has
deliberate defects the pipeline must surface rather than quietly fix.

## On a real patent

Put `DEEPL_AUTH_KEY` in the environment or a git-ignored `.env`, then:

1. `mkdir -p projects/acme && cp ~/domanda.docx projects/acme/`
2. Ask Claude, in plain words: `traduci projects/acme`.
3. **It stops and waits for you.** Nothing is translated until you approve the
   glossary — DeepL is only consistent if the terminology is fixed up front.
4. Review `side_by_side.docx`, answer `ESCALATIONS.md`. For a second opinion,
   ask for a review of the job.

## Where to look next

- [`CLAUDE.md`](CLAUDE.md) — the index a Claude Code session starts from.
- [`CONTRACTS.md`](CONTRACTS.md) — every schema, check and policy. Wins over prose.
- [`docs/`](docs/README.md) — current state, known issues, quality grades.
- [`style-guide.md`](.claude/skills/patent-translate/references/style-guide.md) —
  the single style authority, and its `## Sources`.
- [`review_sources.json`](.claude/skills/patent-translate/references/review_sources.json) —
  the 11 primary sources with URLs and editions, checked each run.
- The two procedures: [`patent-translate`](.claude/skills/patent-translate/SKILL.md),
  [`patent-review`](.claude/skills/patent-review/SKILL.md).

This repo follows the conventions of the **mrcall AI kit**
(<https://github.com/hahnbanach/mrcall-ai-kit>).
