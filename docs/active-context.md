---
doc_baseline_commit: 8ef8669f56232ea73d69ddcca73780727bd329f1
doc_baseline_date: 2026-07-30
---

# Active context

**State now:** the translation pipeline is complete and verifiable from a clean
checkout with one command, and the style authority is a single sourced guide. A
second skill, `patent-review`, was built on top of it this session and then cut
back to what it should have been from the start: it reads a finished job blind
and writes one document of notes. The packet builder and the smoke assertions
around it are verified; the reviewer itself has never been run on a real job, so
its accuracy is unknown. The live job `projects/cafe124` has been through a full
revision pass, is waiting on the firm to answer its open flags, and has not been
reviewed.

## Built this session — the independent reviewer (2026-07-30)

`patent-review` is a second skill that reviews a finished job the way an
independent professional reviewer would: blind to the pipeline's own flags,
against the whole style guide, in the judgement band `checks.py` cannot reach. It
proposes; it never writes. Plan and locked design decisions:
[execution-plans/patent-review-skill.md](execution-plans/patent-review-skill.md).

What now exists:

- `CONTRACTS.md` has a **Review module** section: the packet, findings and
  comparison-candidates schemas, the FORBIDDEN-in-the-packet list with the reason
  each file is an answer key, and the review policies.
- Four scripts under `.claude/skills/patent-translate/scripts/` —
  `review_packet.py` (builds the blind packet), `review_validate.py` (validates
  the model's `findings.json`), `review_compare.py` (aligns findings against
  `state/flags.json` by segment id, candidates only), `review_sources.py`
  (`verify-manifest` offline, `check` over the network). They live in the
  translate scripts directory to share `common.py`; none of them modifies it.
- `.claude/skills/patent-translate/references/review_sources.json` — the edition
  manifest, 11 sources, one-to-one with the style guide's `## Sources`.
- `.claude/skills/patent-review/SKILL.md` — the operating procedure, and it is
  short on purpose (98 lines): build the blind packet, read it in fresh-context
  subagent blocks with the claims, title and abstract read as one set, write
  `<P>/review/REVIEW.md` with the notes, **stop**. Corrections Mario accepts go in
  through `set_final.py`. See "What the reviewer is, after the last cut" below.
- `dev/seed_review_fixture.py` plus the tracked `dev/review_seed_revisions.json`
  build `projects/_fixture_review` (untracked) with eight judgement-level defects
  on the English side.

**Verified: the mechanical layer.** `dev/smoke.py` exits 0 with the new
assertions, still one command and still offline:

- the packet carries 24 entries in `segments.json` order on both fixtures, keys
  exactly `id/kind/section/text_it/text_en`, no timestamp and no hash, with the
  two untranslated section markers (`H-001`, `H-008`) omitted and reported;
- blindness is asserted against the project's own answer key — none of 63 texts
  on the review fixture (flag issues and resolutions, check failure details, edit
  reasons, claim conventions, undelivered DeepL variants, and the glossary's
  withheld `rationale`/`status`/`flag` values) appears anywhere in the packet
  bytes; the packet glossary is asserted to be the delivered one projected onto
  its six permitted columns, and re-injecting the withheld columns makes smoke
  exit 1 naming them;
- a stray file planted in `review/packet/` makes the build refuse (exit 1, the
  file named, nothing written and nothing deleted): blindness is a property of
  the directory a blind prompt reads, not of three files inside it;
- `state/` is byte-identical across a packet build (`state_sha256`), and two
  builds of the same state are byte-identical;
- `review_validate.py`: 1 accept vector and 25 reject vectors — every rejection
  reason in the contract fires on a vector of its own;
- `review_compare.py`: on canned inputs, 5 candidates (the full cross product on
  one segment plus the document-wide pair), 2 `reviewer_only`, 2
  `pipeline_only`, in contract order, with `state/` untouched; and the no-flags
  case, where every finding lands in `reviewer_only`;
- `review_sources.py verify-manifest`: the 11 sources agree with the guide's
  `## Sources`, and three seeded inconsistencies (a bumped edition, a dropped
  entry, a moved URL) are each detected;
- all eight seeded judgement defects reach the packet the reviewer reads.

**One blind pass has been run, as a plumbing trial — not as a measurement.** A
single agent built the packet for `projects/_fixture_review`, reviewed it blind,
and produced `projects/_fixture_review/review/findings.json` (23 findings, 21
rules-lens and 2 grammar-lens). It validated first time and `review_compare.py`
aligned it against the fixture's real flags, so the concordance path works
end to end on real model output — its finding on the unsupported pressure sensor
met the pipeline's own `claim_support` MECH flag on the same segment, by
independent routes. It also found, unprompted and unseeded, a cascading multiple
dependency (claim 6 → claim 4) outside PCT Rule 6.4(a) that the pipeline had
never flagged.

That trial caught **8 of the 8 seeded modes**, and this number is *indicative
only*: one agent, 24 segments, the whole packet in one context — precisely the
easy case that the sharding-by-diligence decision exists to guard against. It is
not the plan's acceptance measurement, and nothing about the reviewer's accuracy
is established until step 9 runs sharded and its numbers are agreed. No
`REVIEW.md` exists, and no precision figure exists.

`review_sources.py check` — the network path — is not covered by smoke, which is
offline by design; it was exercised by hand instead (11 sources, 11 tokens found,
so the editions the guide cites are current). See
[harness-backlog.md](harness-backlog.md) and
[quality-grades.md](quality-grades.md).

**The trial's real yield was seven contract-level gaps, not the recall number.**
The one that mattered: the packet was leaking the pipeline's doubts through
`out/terminology.csv`, whose `flag` column is "empty when no doubt" by its own
schema — on cafe124, 15 of 47 rows, naming most of the open TERM escalations; on
the fixtures, naming the failing mechanical checks outright. Both the FORBIDDEN
list and the smoke blindness assertion enumerate *files*, and the glossary is a
permitted file, so neither could see it. Fixed: the packet now projects the
glossary onto the six columns that state what a term IS and withholds
`rationale`, `status` and `flag`; the withheld content is now part of the
answer-key scan (63 strings on the review fixture, up from 47), and re-injecting
the leak makes smoke exit 1. Also fixed in the same pass: a stray file left in
`review/packet/` used to be read as part of the packet and now refuses the build;
the digest check has its own non-destructive `state-digest` subcommand instead of
a rebuild that would overwrite the evidence; and the option-concreteness test lost
its three-character floor, which had been rejecting `by`.

## Decision that reshaped the output: less told, not more

Mario, 2026-07-30, on the proposal to add a FIDELITY flag class: **no.** An
unfaithful rendering the reviewer finds is a proposed correction, not a new entry
in a taxonomy — adding a class would grow the vocabulary we use to talk to the
firm in order to describe our own mistake to ourselves. The trial's mapping
(description-side → TERM, claim-side → CLAIM-DEFECT) stands.

The principle behind it applies wider than that one class, and it is now in the
contract: **the more we tell a human, the more we confuse ourselves.** Two
audiences had been conflated — the machinery we built for ourselves, and the
person who has to read the result. What a human editor gets about drafting
conventions is one short file. Applied:

- **`notes-for-human-reviewer.md`** — authored in `<P>/`, copied to `out/` by
  `assemble.py` when it exists and deleted from `out/` when it stops existing.
  How a couple of dozen expressions were rendered: the Italian, the English,
  **no reasons**, no doubts, no "confirm". `projects/cafe124` has one.
- **CONVENTION is one flag per RULE, never per occurrence**, and it reaches no
  deliverable — out of the review table, out of `ESCALATIONS.md`, and the
  "Applied conventions" appendix is gone. On cafe124 that took 18 rows of
  disclosure out of the review table, leaving 16 rows carrying a flag that is
  actually a question. Verified by reopening the rebuilt `side_by_side.docx`, not
  by trusting the script's own report.
- Asserted in smoke with real teeth: the clean-fixture run files a CONVENTION
  flag **on C-01** through `flags.py` first, because a document-wide flag never
  reaches a table row and would have made the assertion unfailable — the first
  version of it did pass with the exclusion removed. Now putting CONVENTION back
  into the Flags column makes smoke exit 1.

## What the reviewer is, after the last cut

Same decision, carried to its end, on 2026-07-30 after a session Mario called
exhausting and was right to: **the reviewer reads and writes a document with
notes. That is all it is.** `patent-review/SKILL.md` went from about 300 lines to
98.

Out of the procedure: the three-way concordant/missed/spurious diff against the
pipeline's flags, the structured `findings.json` as a mandatory step, the
escalation-actionability audit, the coverage-gap reporting, and the two open
`proposed_en` questions, which the cut made moot.

In it: build the blind packet, read the Italian against the English with the
style guide, write `REVIEW.md`, stop. Each note carries the segment, the Italian,
the English, what is wrong, and the proposed correction.

`review_validate.py` and `review_compare.py` still exist and are still asserted by
smoke, but no procedure calls them; `patent-review/SKILL.md` says so in one line
at the end. They were not deleted — they work and they are tested — but they are
not what a review is.

The lesson to keep: the apparatus was built for us and then handed to a human. A
review is a document somebody reads.

## Not done — pending Mario's go

- **The reviewer has still never been run** on a fixture or on a real document,
  beyond the single-agent plumbing trial described above. Its accuracy is
  unknown, and no `REVIEW.md` exists anywhere.
- **`projects/cafe124` has not been reviewed.** When it is: build the packet,
  read, write `REVIEW.md`, and show Mario the notes. Corrections he accepts go in
  through `set_final.py`, then `checks.py` and `assemble.py` re-run, and the check
  profile is compared with the 10-3-0 baseline.

## Built and verified earlier — the translation pipeline

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

## Decisions that bind

- **Blindness is a property of the packet, not an instruction not to peek.** The
  reviewer's generation phase reads `<P>/review/packet/` and no other path; the
  files that would anchor it are listed in `CONTRACTS.md` with the reason each one
  is an answer key, and `dev/smoke.py` asserts none of their text reaches the
  packet.
- **The reviewer proposes; `set_final.py` stays the single writer.** Accepted
  fixes go through a `set_final.py` revisions file whose every `reason` begins
  with the finding id; accepted doubts go through `flags.py add`. A finding the
  reviewer did not reproduce never auto-closes a pipeline flag.
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

Measure the reviewer before trusting it: step 9 of the plan, on
`projects/_fixture_review` and then on the clean `projects/_fixture`, with the
numbers written into `quality-grades.md` and the go/no-go taken with Mario. Only
after that, step 10 — the first real run on `projects/cafe124`. Independently of
both, the open cafe124 flags still have to be resolved with the firm.
