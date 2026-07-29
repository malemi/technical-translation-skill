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

## No pre-commit enforcement

`dev/smoke.py` and the documentation gate both have to be remembered. Optional
one-liner if that becomes a problem: put them in `.githooks/pre-commit` and
`git config core.hooksPath .githooks`.
