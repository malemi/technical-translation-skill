# patent-translate

**Italian patent application in, English patent application out, ready to file.**

You also get a bilingual document showing every choice and every open doubt,
segment by segment. Drop the Italian `.docx` in a folder, ask Claude to
translate it, answer its questions.

## What you get

Everything lands in `projects/<your-job>/out/`:

| File | What it is |
| --- | --- |
| `filing_en.docx` | The English application: title, description, claims, abstract. This is the deliverable. |
| `side_by_side.docx` | Italian and English in two columns, one row per segment, with the open flags on each row. This is what you review. |
| `ESCALATIONS.md` | The questions Claude could not answer from the source alone, grouped by kind. You are expected to answer these. |
| `audit_numbers.csv` | Every number and unit in the document, Italian vs English, so you can verify nothing drifted. |
| `bilingual.csv` | The same pairs as a flat table, for sorting, filtering and diffing outside Word. |
| `terminology.csv` | The agreed glossary that was used. |
| `notes-for-human-reviewer.md` | What a human editor is told: how expressions were rendered, the choices we are unsure of, and what we suspect is wrong in the Italian. |

## How it works

The design principle: DeepL with a locked glossary handles the description
prose, because it stays terminologically consistent across a long document.
Claude writes the claims, because that needs the US/PCT conversion — preamble,
transitional phrase, `wherein`, antecedent basis — that DeepL cannot do. Then a
battery of 13 mechanical checks verifies the result: reference signs preserved
segment by segment, numbers and units identical, the claim dependency graph
unchanged, one sentence per claim, claim terms supported in the description,
abstract length within PCT Rule 8.1(b), no Italian residue, nothing left
uncovered. Every failure becomes a flag, and the bilingual artifact puts each
one next to the text it is about, for a human to decide.

A second skill, `patent-review`, then reviews the finished job the way an
independent professional reviewer would, in the band the mechanical checks
cannot reach. It works **blind**: it sees the Italian, the delivered English,
the style guide and the locked terms — and none of the pipeline's own doubts,
not the flags, not the check results, not the reasons recorded for each edit,
not even the glossary columns where a term was marked as needing confirmation.
A reviewer who has seen the existing flags confirms instead of discovering, so
blindness is enforced by building the reviewer a packet rather than by asking it
not to look. It reads, and it writes one document of notes —
`projects/<your-job>/review/REVIEW.md`. It proposes; it never edits.

## Why it is built this way

**The Italian is authoritative and is never improved.** A badly drafted claim is
translated faithfully and flagged, not fixed. Where a literal rendering and a
nicer-sounding one differ, the literal one wins and the alternative is recorded
as a flag for you to weigh. Ambiguities become questions, never silent
decisions: that is why the job ends with an escalation list you are expected to
answer, and why the independent reviewer proposes instead of editing.

### Confidentiality

**Which DeepL tier you use is a confidentiality decision, not a cost decision.**
The Free tier retains submitted text and may use it to train; Pro does not. Use
Free only when the source is no longer secret — typically once the priority
application is filed, so novelty is secured and the text will be published
anyway. If the application is still unfiled and confidential, use a Pro key.

- **`projects/` is never committed.** `.gitignore` excludes all job folders;
  only the synthetic `projects/_fixture/` is tracked, and it contains no client
  material.
- **`.env` is git-ignored**, so the key never leaves the machine.
- DeepL is the only external service in the pipeline.

## Try it

The repo ships a small synthetic Italian patent (a cold-brew coffee machine) and
a canned English side for it, so you can watch the whole machinery work — no
DeepL account, no network, no real document involved. From the repo root:

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python .claude/skills/patent-translate/scripts/dev/smoke.py
```

One command builds the fixture, splits it, loads the canned English side, runs
the battery, assembles the deliverables in `projects/_fixture/out/`, then builds
deliberately corrupted copies and confirms that every seeded defect is caught
and that the reviewer's packet stays blind; it prints `SMOKE OK` and exits 0
when all of that holds. On the clean fixture the battery reports one failure and
one warning, and that is correct — the *Italian* has deliberate defects the
pipeline must surface rather than quietly fix, so an all-pass run would mean the
checks had stopped working.

## Using it on a real patent

You need a DeepL key: `DEEPL_AUTH_KEY` in the environment, or in a git-ignored
`.env` at the repo root. Then:

1. Make a folder for the job and put the Italian application in it — one `.docx`
   per folder (a legacy binary `.doc` is converted first; just say so):
   ```
   mkdir -p projects/acme && cp ~/somewhere/domanda.docx projects/acme/
   ```

2. Open Claude Code in this repo and ask, in plain words: `traduci
   projects/acme`. That triggers the `patent-translate` skill.

3. **Claude will stop and wait for you.** Before anything is translated it reads
   the entire document, builds the glossary — every substantive term, with its
   Italian and English variants — and presents it for approval. Nothing is
   translated until you lock that terminology, because DeepL is only consistent
   across a long document if the terminology is fixed up front.

4. When it finishes it reports the output paths, the open escalations, and any
   multiple-dependent claims (which matter if the case later enters the US
   national phase). Review `side_by_side.docx` and answer `ESCALATIONS.md`. For
   a second opinion, ask for a review of the job: that runs `patent-review`.

## Where to look next

- [`CLAUDE.md`](CLAUDE.md) — the index a Claude Code session starts from.
- [`CONTRACTS.md`](CONTRACTS.md) — the build contract. Every state schema, every
  check and every policy is specified there; it wins over prose if the two
  disagree.
- [`docs/`](docs/README.md) — current state, known issues, harness backlog,
  quality grades.
- [`.claude/skills/patent-translate/SKILL.md`](.claude/skills/patent-translate/SKILL.md)
  — the procedure Claude follows to translate a job, stage by stage.
- [`.claude/skills/patent-review/SKILL.md`](.claude/skills/patent-review/SKILL.md)
  — the procedure for the blind independent review.

This repo follows the conventions of the **mrcall AI kit**
(<https://github.com/hahnbanach/mrcall-ai-kit>).
