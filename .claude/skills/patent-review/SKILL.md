---
name: patent-review
description: Review a finished patent-translate job in projects/<slug>/ the way an independent reviewer would — blind to the pipeline's own flags, against the style guide. Produces one review document with notes. Use when asked to review or get a second opinion on a translated project in this repo.
---

# patent-review — operating procedure

You review a finished `patent-translate` job. You read the Italian against the
delivered English, and you write one document with your notes. You do not edit
anything.

You review **blind**: you re-derive what you find from the document itself. You
never open the pipeline's own conclusions — `state/flags.json`,
`state/checks.json`, `state/translations.json`, `out/ESCALATIONS.md`, or an
earlier review. Having seen them, you would confirm them instead of finding
anything.

Chat with Mario stays Italian; the review document is English.

## Procedure

`<P>` = project path. `$S` = `.claude/skills/patent-translate/scripts`.
Python = `.venv/bin/python`. Work from the repo root.

### 1. Build the packet

```
.venv/bin/python $S/review_packet.py build --project <P>
```

It writes `<P>/review/packet/` with three files — the segments, the style guide,
the locked glossary — and nothing that would tell you what the pipeline already
thought. Exit 1 lists whatever is missing; fix that and rebuild, never review a
partial project.

### 2. Read it

Read `packet/style-guide.md` in full, first. Then every entry in
`packet/pairs.json`, in order, the Italian first and the English against it. No
sampling.

For a document of any size, do this as several fresh-context subagents over
contiguous blocks of entries, plus one agent for the claims, title and abstract
together — those have to be read as a set. Every prompt names
`<P>/review/packet/` and no other path.

What to look for is the band the mechanical checks cannot reach. The rule for
each is in `packet/style-guide.md` under the heading named here; read it there,
never restate it:

| What | Heading in the guide |
| --- | --- |
| transitional phrases, and the added-matter trap | Transitional phrases (scope-critical — never smooth) |
| hedges kept or lost | Never negotiable; Forbidden |
| reference signs: characters, order, the noun they attach to | Never negotiable |
| reference signs parenthesised in the abstract | Normative requirements → Abstract |
| calques and Euro-English | Italian calques to remove; English drift to resist |
| trademarks acknowledged | Normative requirements → Trademarks |
| two-part form mirrors the Italian | Normative requirements → Two-part form |
| method steps as gerunds | Claim structure |
| `mezzi` → `means`, and its number | Never negotiable |
| defined quantities: structure and operands | Never negotiable |
| a source defect repaired instead of translated | Never negotiable; Forbidden |
| term drift across title, abstract, description, claims | Consistency is the deliverable |
| grammar and ordinary English | (no rule — see below) |

The Italian is authoritative and is never improved: a defect in it is a note,
never something to repair. Where the guide has no rule, ordinary better English
wins — but a proposal that changes what the Italian says is not a proposal, it is
an error.

### 3. Write `<P>/review/REVIEW.md`

One document. For each note: the segment id, the Italian, the English, what is
wrong, and the correction you propose. Group by kind if that helps a reader;
otherwise document order.

Keep it short enough to be read start to finish. A note nobody reads is worth
nothing, and every line you add is a line the real findings hide behind.

### 4. Stop

Report to Mario in Italian: how many notes, and the ones that matter. Change
nothing. If he accepts corrections, they go in through
`.venv/bin/python $S/set_final.py --project <P> --input <file>` — the single
writer — and then `checks.py` and `assemble.py` are re-run.

## Re-review

A new run from step 1: fresh packet, and the previous `review/` moved outside the
project first. Reading the last `REVIEW.md` turns an independent review into a
confirmation of it.

## Also available, not part of this procedure

`review_validate.py` and `review_compare.py` machine-check a structured findings
file and line it up against the pipeline's flags. Use them only if a job ever
needs that; a review is a document with notes.
