---
doc_baseline_commit: 0ececd3c6ea60f21cfa8eeb5bc5808563400bb4b
doc_baseline_date: 2026-07-28
---

# Active context

**State now:** the skill is complete, the offline pipeline runs end-to-end from a
clean checkout, and a single command verifies it. The doc-harness was
bootstrapped in the same session.

## Built and verified

Verified on 2026-07-28 by running everything for real, including on a fresh
`git clone` with a fresh virtualenv:

- `dev/smoke.py` runs the whole offline chain — build the Italian fixture,
  ingest, load the canned English side, validate state, validate the glossary,
  run the battery, assemble the deliverables, build the seeded-defect copy, run
  the battery again — and asserts the outcome at both ends. Exit 0, `SMOKE OK`.
- The assertions have teeth: blinding `common.extract_numerals` in a throwaway
  clone made the smoke test exit 1 with
  `numerals_per_segment: expected fail, got pass`.
- The clean fixture reports **pass 11, fail 1, warn 1** — the failing
  `claim_support` and the warning `numeral_term_consistency` are deliberate
  source quirks from `projects/_fixture/fixture_spec.md`, and the smoke test
  asserts the exact status of all 13 checks.
- The seeded-defect fixture is caught on all six `CONTRACTS.md` mutations, each
  by the check the contract assigns to it, with `antecedent_basis` naming
  claim 5 as required.

The three DeepL-calling stages (`glossary.py push`, `translate_deepl.py run`,
`backtranslate.py run`) were verified live against the real DeepL API in an
earlier session, on both the fixture and a real document. They are **not** part
of the smoke test — see [harness-backlog.md](harness-backlog.md).

## Open

Nothing blocking.

`CONTRACTS.md` still describes the seeded-defect matrix as a copy of the fixture
project to be made by hand. That is now what `dev/make_fixture_bad.py` does
automatically; the contract's requirements are unchanged and still met, but the
prose has not been updated to name the script.

## Next

Nothing queued. The next real work is a document job: create `projects/<slug>/`,
drop the Italian source in it, and follow
`.claude/skills/patent-translate/SKILL.md`.
