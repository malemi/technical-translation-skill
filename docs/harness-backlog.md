# Harness backlog

Gaps in the tooling and testing harness — things that are checked by hand today
and should be enforced mechanically.

## `ingest.py` absorbs a trailing non-claim paragraph into the last claim

Found on a real document. Italian applications often restate the title, in
quotes, after the last claim. The claims parser attaches any paragraph without a
claim-number prefix to the running claim, so that line is swallowed into the last
claim's `parts_it` and then appears in the Italian column of the side-by-side as
if it were claim text.

`CONTRACTS.md` already treats a short all-caps line without a final period as a
heading inside the description; extending the same rule to the claims section
would fix this. It is not a one-line change: a new heading segment in the claims
section needs coverage, or the `structure` check will fail it. Currently handled
by a CLAIM-DEFECT flag on the affected claim.

## `checks.py` never resolves a MECH flag it previously raised

Flags are deduplicated on add but nothing closes them when the underlying check
starts passing again. After fixing a regression this session, three stale MECH
flags had to be resolved by hand, and until then they were noise in
`ESCALATIONS.md`. `checks.py` should resolve MECH flags whose check now passes,
with a resolution noting it was cleared mechanically.

## `CONTRACTS.md` and real state disagree on the shape of `claims_en.json`

The contract says `text_en` is the parts "joined with a single `\n`". In
`projects/cafe124` `text_en` is instead the claim-number prefix plus the parts
joined with a **space**, while `parts_en` carries no number — and `assemble.py`
adds the number itself when rendering. `set_final.py` now derives the prefix and
separator from whatever a claim already uses, and refuses rather than
normalising when it can reconstruct neither, but the contract and the data
should be reconciled and one of them corrected.

This is the defect that produced the only regression of the session: recomputing
`text_en` per the contract silently deleted the claim numbers, which
`numbers_units` caught.

## The three DeepL stages are not covered by the smoke test

`dev/smoke.py` exercises everything that runs offline, but `glossary.py push`,
`translate_deepl.py run` and `backtranslate.py run` need a live key and a real
API call, so a regression in the upload, polling, pairing or retry logic would
not be caught. They are verified by hand against the real API when they change.

Fixing this properly means a recorded-response harness — capture real DeepL
responses once, replay them offline — rather than a mock, which would encode our
assumptions about the API instead of its behaviour and would pass while the real
call fails.

## The reviewer's accuracy is not CI-assertable

`dev/smoke.py` asserts everything mechanical about `patent-review` — packet shape,
blindness against the project's own answer key, the validator's accept and reject
vectors, the comparator's buckets, manifest↔style-guide consistency, and that all
eight seeded judgement defects reach the packet. What it cannot assert is the only
thing the skill exists for: whether the blind passes actually FIND those defects,
and whether they invent findings that are not there. That is a model measurement —
recall on `projects/_fixture_review`, precision and source-quirk recall on the
clean `projects/_fixture` — so it costs a real run with real subagents and cannot
sit in an offline test.

Consequence: the numbers go stale silently. Changing the shard sizes, the prompt
skeleton, the style guide or the session model can move recall without moving a
single smoke assertion. The measurement has to be re-run deliberately and its
result recorded in [quality-grades.md](quality-grades.md) with the date and the
model it was measured on. There is no mechanical substitute; a cheaper proxy
(keyword-matching a finding against the seed table) would grade the reviewer on
vocabulary rather than on judgement, and would pass while the review got worse.

## `review_sources.py check` — the network path — is not covered by the smoke test

The edition check has two modes. `verify-manifest` is offline and fully asserted:
smoke runs it against the tracked manifest and against three mutated copies (a
bumped edition, a dropped entry, a moved URL), each of which must fail. `check` is
the mode that actually fetches every manifest URL and looks for its
`edition_token`, and `dev/smoke.py` is offline by design, so nothing exercises the
fetch, the status handling, the token search, or the exit-3 contract that tells
the reviewer to record the report verbatim and carry on.

The failure this leaves open is a silent one: a token that no longer occurs on a
page that has not moved would make every run report `MISSING` and every reviewer
treat a healthy source as a moved one — or the reverse, a token so generic that it
survives any edition bump and reports `OK` forever. Both are invisible offline.
Same fix as the DeepL gap above: record the real responses once and replay them,
rather than mock what we assume the pages return.

## Nothing enforces blindness on the orchestrating session

The packet enforces blindness on the *subagents*: their prompt names
`<P>/review/packet/`, the builder decides what goes in it by whitelist, and a
stray file in that directory now refuses the build. None of that constrains the
session that orchestrates the review. It can read `state/flags.json` and paste it
into a shard prompt, and no artefact would record that it did.

`state_sha256` does not close this: it proves nothing was WRITTEN to `state/`
during the blind phase and says nothing about reads. A read leaves no trace on
disk, so there is probably no mechanical fix inside this repo's model — the honest
position is that this half of decision 1 is policy, stated as such in
`CONTRACTS.md` and in `patent-review/SKILL.md`, and that a run whose findings look
suspiciously congruent with the pipeline's flags should be treated as suspect
rather than as confirmation.

## A permitted packet file with a new doubt-bearing field would leak again

The blindness assertion and the FORBIDDEN list are both organised by FILE. That is
what let the glossary's `flag` column through: `terminology.csv` is a permitted
file, so nothing looked inside it. The specific hole is closed — the packet
projects the glossary onto six columns and the withheld ones are in the answer-key
scan — but the *shape* of the mistake is not. Add a `reviewer_note` column to
`terminology.csv`, or a field to any structure the packet copies, and it reaches
the reviewer with nothing objecting.

What would actually fix it is inverting the assertion: instead of listing what
must not appear, assert that every byte in the packet traces to a whitelisted
source field. `pairs.json` already works that way by construction; the two copied
files do not.

## Nothing enforces re-verifying the `state/` digest at the close of the blind phase

`review_packet.py build` prints `state_sha256`, and `state-digest` exists to
re-read it non-destructively, but nothing requires the second call and no
artifact records that it happened. On the cafe124 review it did not happen: the
digest was printed at build time, the blind phase ran, and the first
`set_final.py` write legitimately changed `state/` — after which the evidence for
"nothing was written during the blind phase" no longer exists and cannot be
reconstructed.

The plan's own acceptance criterion asks for that hash to be unchanged, so this
is a criterion the procedure gives no way to satisfy. `patent-review/SKILL.md`
should end the blind phase with a `state-digest` call and have the reviewer
record both digests in `REVIEW.md`; until it does, the property is asserted by
smoke on the fixtures and unproven on every real run.

## No pre-commit enforcement

`dev/smoke.py` and the documentation gate both have to be remembered. Optional
one-liner if that becomes a problem: put them in `.githooks/pre-commit` and
`git config core.hooksPath .githooks`.
