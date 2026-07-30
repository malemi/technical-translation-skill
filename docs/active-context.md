---
doc_baseline_commit: 862663308fd60c6228540d0e215b92077e769cd8
doc_baseline_date: 2026-07-30
---

# Active context

**State now:** both skills have been run end to end on the real job. The
translation pipeline is complete and verifiable from a clean checkout with one
command; `patent-review` has now produced its first real `REVIEW.md`, on
`projects/cafe124`, sharded across seven blind subagents, and 37 of its
corrections have been applied through `set_final.py` and shipped. What is still
missing is the *measurement*: nobody knows the reviewer's precision, because step
9 — the fixture acceptance run with numbers — has never been executed.

## The first real review — cafe124 (2026-07-30)

Step 10 of [execution-plans/patent-review-skill.md](execution-plans/patent-review-skill.md),
run under a filing deadline and completed.

- **Packet**: 137 entries (1 title, 7 abstract, 107 description, 22 claims), one
  untranslated section marker omitted and reported.
- **Reading**: seven fresh-context subagents — five contiguous description
  blocks balanced by character count, one for title + claims + abstract read as
  one set, and one document-wide consistency pass over all 137 segments. The
  seventh is what a block reader structurally cannot do: it is the only one that
  can see a term drift between sections, and it produced the finding that `in cui`
  is `wherein` in 19 claims and `in which` in the 20th plus eight description
  paragraphs.
- **Output**: `projects/cafe124/review/REVIEW.md`, 51 notes numbered N1–N51 so an
  accepted fix carries its id into the `set_final.py` reason. Grouped as:
  fidelity defects in our English, defects in the Italian as filed, standard
  renderings applied in one section and not the other, English that reads wrong,
  and terminology collisions wanting a glossary decision.
- **The orchestrator verified the seven highest-impact findings itself** against
  the packet text before writing them up, rather than passing on subagent claims.

**What the reviewer found that matters.** Two defined quantities had lost or
changed structure: the Extraction Yield formula rendered `il rapporto tra … e …`
as "the ratio **of** …", leaving the defining equation of the application with no
divisor; and the specific-extraction-energy definition had *repaired* a malformed
Italian ratio by translating `per` as "and", removing both the source defect and a
real ambiguity. Claim 1 step e) had turned `l'intensità di turbolenza` into "**a**
turbulence intensity", manufacturing the antecedent basis the Italian lacks —
which is the failure mode the style guide lists by name. It also found a
claim-set inconsistency the pipeline had never raised: claim 17 triggers the
eccentricity loop off the *extraction yield* where method claim 5 triggers the
same loop off the *turbulence intensity*.

Three of its findings independently re-derived doubts the pipeline had already
raised by other routes — the abstract's unparenthesised reference signs, the
4→8→13→21 dependency cascade, and the restated title inside claim 22's Italian.
That is an observation, not a concordance measurement; nothing was run through
`review_compare.py`.

**Verified after applying.** 37 corrections went in through `set_final.py`, each
one built as an exact literal substitution asserted to match the delivered
English once and only once — a build script that refuses to emit anything if a
single anchor fails to match, so no edit is ever applied on an approximation.
`checks.py` then reported **10 pass, 3 warn, 0 fail and +0 new MECH flags**,
identical to the pre-review baseline: the text improved with no mechanical
regression. The produced `filing_en.docx` was reopened and asserted from the
inside — every correction present, every superseded string at zero occurrences —
rather than trusted from `assemble.py`'s own report.

**`bilingual.csv` is now a real deliverable.** The flat pairs table was first
built by a throwaway script straight into `out/`, which would have gone stale the
next time `assemble.py` ran. It is now produced by `assemble.py` from the same
English index as `side_by_side.docx`, so the two cannot disagree, and `smoke.py`
reads it back and checks the header, the row count, the segment order, the UTF-8
BOM, and that no translated segment has empty English. Verified with teeth:
dropping one row makes smoke exit 1. The first version of that assertion checked
only that the file existed, which a stale file passes — and a second version
failed on the two section markers that carry no English by design.

**The filing was missing every paragraph number, and now is not.** Mario caught
it on the delivered `.docx`: the source numbers its description paragraphs
`[0001]`…`[00101]` and the English had none. The cause was not in `assemble.py`
— `ingest.py` looked for a literal `[dddd]` at the start of the paragraph text,
while the source uses **Word's automatic list numbering**, which
`paragraph.text` does not return. `para_number` was therefore null on all 138
segments and had been for every run of this project.

`common.iter_paragraph_numbers` now renders the label from the numbering
definition (`numId` → `abstractNum` level 0, `numFmt` + `lvlText`, counted from
`start`), `ingest.py` uses it with the literal marker still winning when present,
and `assemble.py` writes it into the filing as literal text so nothing renumbers
it downstream. Only `decimal` and `decimalZero` are rendered; anything else warns
and yields null, because a wrong paragraph number is worse than a missing one.

Verified against reality, not against intent: LibreOffice's own rendering of the
source was used as the oracle, giving `[0001]`…`[0099]`, `[00100]`, `[00101]` —
the odd five-digit tail is what the applicant's numbering definition actually
produces, and it is reproduced rather than corrected. Re-ingesting cafe124
changed nothing but `para_number` (diffed field by field, so no translation was
orphaned), the check profile held at 10-3-0, and the rebuilt filing carries 101
numbers in state order. `make_fixture.py` now gives the fixture real Word
numbering, and smoke asserts the whole chain — resolved at ingest, carried in
state, rendered into the filing. Both halves have teeth: reinstating the original
bug in `ingest.py` fails smoke, and so does removing the render in `assemble.py`.

**Source defects were not touched.** All sixteen are translated as filed and
listed in `notes-for-human-reviewer.md`, in two tiers, in plain prose with no
internal ids. One deliberate consequence: the specific-extraction-energy sentence
now reads oddly in English, because restoring the source's `per` was chosen over
tidying away a question that belongs to the firm.

## Not done, and it is the next thing

- **The reviewer's accuracy is still unmeasured.** Step 9 — run it on
  `projects/_fixture_review` for recall against the eight seeded defects, then on
  the clean `projects/_fixture` for the false-positive half — has never run. The
  cafe124 review says the skill *works*; it says nothing about how often it
  raises a note that is not a defect. Until step 9 runs and its numbers land in
  [quality-grades.md](quality-grades.md), every note still needs a human.
- **The blind phase's `state/` digest was never re-verified.** `review_packet.py`
  printed `state_sha256` at build time, and the acceptance criterion is that the
  digest is unchanged across the blind phase — but `review_sources`-style
  re-verification via `state-digest` was not run before edits began, and once
  `set_final.py` ran the evidence was gone. Nothing wrote to `state/` during the
  blind phase, but that is an argument, not a proof. Run `state-digest` at the
  end of the blind phase next time, before the first edit.
- **cafe124's open flags still need the firm.** They are decisions, not defects
  in our work. Three are worth attention: the abstract does not meet PCT Rule
  8.1(d) (reference signs must be parenthesised — "shall", unqualified; EPC Rule
  47(4) identical), free to fix before filing; the multiple-dependency chain
  21→13→8→4 sits outside PCT Rule 6.4(a) while EPC Rule 43(4) permits it, so the
  outcome depends on which Authority searches; and claim 22's Italian contains the
  restated title, absorbed by `ingest.py`. Plus the source ambiguities the review
  surfaced, now all in the notes file.

## The translation pipeline — built and verified earlier

- **`dev/smoke.py` is the test.** It builds the Italian fixture, ingests, loads
  the canned English baseline, validates state and glossary, runs the battery,
  assembles the deliverables, builds the seeded-defect copy and runs the battery
  again — asserting the outcome at both ends. Verified on a genuine `git clone`
  with a fresh virtualenv: `SMOKE OK`, exit 0, from the two tracked fixture files.
- **The assertions have teeth.** Blinding `common.extract_numerals` in a
  throwaway clone made smoke exit 1 with `numerals_per_segment: expected fail,
  got pass`.
- The clean fixture reports **pass 11, fail 1, warn 1**; the failing
  `claim_support` and the warning `numeral_term_consistency` are deliberate quirks
  seeded in the Italian (`projects/_fixture/fixture_spec.md`). Smoke asserts the
  exact status of all 13 checks, so an all-pass run fails.
- The seeded-defect fixture is caught on all six `CONTRACTS.md` mutations, each by
  the check the contract assigns, with `antecedent_basis` naming claim 5.
- **`set_final.py` is the single writer** for reviewed English. Verified on the
  fixture (dry-run, apply, idempotent re-apply, provenance recorded) and used for
  the whole cafe124 revision pass and now for the review corrections.

The three DeepL-calling stages were verified live against the real API in an
earlier session. They are **not** covered by the smoke test — see
[harness-backlog.md](harness-backlog.md).

## The reviewer's mechanical layer — verified

`dev/smoke.py` exits 0 with the review assertions, still one command and still
offline: the packet's shape and determinism on both fixtures; blindness asserted
against the project's own answer key (63 texts on the review fixture, including
the glossary's withheld `rationale`/`status`/`flag` values, none reaching the
packet, and re-injecting them makes smoke exit 1); a stray file in
`review/packet/` refusing the build; `state/` byte-identical across a build; 1
accept and 25 reject vectors on `review_validate.py`; `review_compare.py`'s three
buckets in contract order with `state/` untouched; `review_sources.py
verify-manifest` against the tracked manifest and three seeded inconsistencies;
and all eight seeded judgement defects reaching the packet.

`review_sources.py check` — the network path — is offline-excluded by design and
was exercised by hand: 11 sources, 11 tokens found.

## Decisions that bind

- **Blindness is a property of the packet, not an instruction not to peek.** The
  generation phase reads `<P>/review/packet/` and no other path; the files that
  would anchor it are listed in `CONTRACTS.md` with the reason each is an answer
  key, and smoke asserts none of their text reaches the packet. The orchestrating
  session's own blindness remains policy — see the backlog.
- **The reviewer proposes; `set_final.py` stays the single writer.** Accepted
  fixes carry the finding id in the reason; accepted doubts go through
  `flags.py add`. A finding the reviewer did not reproduce never auto-closes a
  pipeline flag.
- **The more we tell a human, the more we confuse ourselves.** What a human
  editor gets is one short file: `notes-for-human-reviewer.md`, authored in
  `<P>/` and copied to `out/` by `assemble.py`. On cafe124 it now carries three
  sections — recurring renderings, the choices we are unsure about and why, and
  the source defects we did not touch — written to be overruled by a professional
  who knows more than we do. CONVENTION is one flag per RULE, never per
  occurrence, and reaches no deliverable.
- **No FIDELITY flag class.** An unfaithful rendering the reviewer finds is a
  proposed correction, not a new entry in a taxonomy. Description-side → TERM,
  claim-side → CLAIM-DEFECT.
- **One style guide, and only one.** `references/style-guide.md` is the single
  style authority. If a rule is not there, it is not a rule.
- **Authority order is explicit**: the Italian as filed, then the PCT/EPC norm
  cited by rule number, then house choices marked as choices. External reviewers
  carry no authority of their own; their errors are kept only as a catalogue of
  failure modes.
- **US practice never changes the English.** We file one PCT text; national-phase
  divergences become flags.

## Next

Step 9, the acceptance run, on `projects/_fixture_review` and then on the clean
`projects/_fixture`, with the numbers written into `quality-grades.md` and the
go/no-go taken with Mario. The cafe124 run makes this more urgent, not less: 51
notes went to a filing on the strength of a skill whose false-positive rate has
never been measured.
