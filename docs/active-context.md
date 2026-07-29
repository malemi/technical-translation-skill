---
doc_baseline_commit: 182ec2a7cee78f51bea1eda59f65c3dba96da70d
doc_baseline_date: 2026-07-29
---

# Active context

**State now:** the pipeline is complete and verifiable from a clean checkout with
one command; the style authority has been consolidated into a single sourced
guide; and the live job `projects/cafe124` has been through a full revision pass
and is waiting on the firm to answer its open flags.

## Built and verified

Everything below was run for real, from the repo root, on 2026-07-28/29.

- **`dev/smoke.py` is the test.** It builds the Italian fixture, ingests, loads
  the canned English baseline, validates state and glossary, runs the battery,
  assembles the deliverables, builds the seeded-defect copy and runs the battery
  again — asserting the outcome at both ends. Verified on a genuine `git clone`
  with a fresh virtualenv: `SMOKE OK`, exit 0, starting from the two tracked
  fixture files.
- **The assertions have teeth.** Blinding `common.extract_numerals` in a
  throwaway clone made the smoke test exit 1 with
  `numerals_per_segment: expected fail, got pass`.
- The clean fixture reports **pass 11, fail 1, warn 1**; the failing
  `claim_support` and the warning `numeral_term_consistency` are deliberate
  quirks seeded in the Italian (`projects/_fixture/fixture_spec.md`). The smoke
  test asserts the exact status of all 13 checks, so an all-pass run fails.
- The seeded-defect fixture is caught on all six `CONTRACTS.md` mutations, each
  by the check the contract assigns, with `antecedent_basis` naming claim 5.
- **`set_final.py`** is the single writer for reviewed English. Verified on the
  fixture (dry-run, apply, idempotent re-apply, provenance recorded) and used
  for the whole cafe124 pass.
- **`projects/cafe124` revision pass complete.** 99 of 114 pairs and 3 of 22
  claims revised, 129 `edits` entries each carrying a reason. The check profile
  is **identical to the pre-revision baseline** — 10 pass, 3 warn, 0 fail — so
  the translation improved without any mechanical regression. Deliverables
  reassembled and inspected in the produced `.docx`, not merely reported by the
  script.

The three DeepL-calling stages were verified live against the real API in an
earlier session. They were **not** re-run here and are not covered by the smoke
test — see [harness-backlog.md](harness-backlog.md).

## Decisions taken this session

- **One style guide, and only one.** `references/style-guide.md` is the single
  style authority. If a rule is not there, it is not a rule, and no second style
  document may be created alongside it.
- **Authority order is explicit**: the Italian as filed, then the PCT/EPC norm
  cited by rule number, then house choices marked as choices. External reviewers
  — including a professional legal translator and a general-purpose LLM — carry
  no authority of their own; their errors are kept only as a catalogue of
  failure modes.
- **US practice never changes the English.** We file one PCT text; national-phase
  divergences become flags.
- The normative layer was extracted from primary sources (PCT and its
  Regulations, ISPE Guidelines, EPC Rules, EPO Guidelines Part F, MPEP, 37 CFR)
  and is cited by rule number in the guide, with weakly-sourced items declared.

## Open — waiting on the firm

`projects/cafe124` has open flags that are decisions, not defects in our work.
Three of them were found from the normative research and are worth the firm's
attention:

- **The abstract does not meet PCT Rule 8.1(d).** Reference signs must be
  parenthesised in the abstract ("shall", unqualified; EPC Rule 47(4) identical).
  The Italian writes bare numbers and the English mirrors it faithfully. A
  formal defect of the source, fixable before filing at no cost.
- **The multiple-dependency chain 21→13→8→4 sits outside PCT Rule 6.4(a)**,
  which forbids a multiple dependent claim serving as the basis for another.
  EPC Rule 43(4) is more permissive and the ISPE Guidelines let Authorities
  choose, so the outcome depends on which Authority searches. Earlier flags
  framed this as a US-only matter; that framing was wrong and has been
  superseded.
- **Claim 22's Italian contains the restated title**, absorbed into the claim by
  `ingest.py`. Not translated as claim text, which is correct, but visible in the
  Italian column.

Plus three source ambiguities translated verbatim and flagged rather than
resolved (the extraction-yield formula, "espressa in fattori", and a doubled
"la relazione tra il rapporto tra").

## Next

Show `projects/cafe124/out/side_by_side.docx` to an independent reviewer,
together with `references/style-guide.md` and **without** the Emma/Gemini
comparison document, which would anchor the review. Then resolve the open flags
with the firm.
