# Known issues and solutions

## `checks.py` reports 1 fail + 1 warn on the clean fixture

Expected. `projects/_fixture` contains deliberate source quirks the pipeline must
surface rather than silently fix; they are listed at the top of
`projects/_fixture/fixture_spec.md`. The correct result is **pass 11, fail 1,
warn 1**: `claim_support` fails because "sensore di pressione (8)" appears only
in claim 5 and never in the description, and `numeral_term_consistency` warns
because numeral (2) is called both "vasca di estrazione" and "serbatoio".

An all-pass run on the fixture means the checks stopped working. `dev/smoke.py`
asserts the expected status of every check, so it fails loudly if that happens.

## A claim loses its number after a revision

Symptom: `numbers_units` flips from pass to fail on exactly the claims you just
revised, reporting a number present in the Italian and missing from the English —
and the missing number is the claim number itself.

Cause: in a real project `claims_en.json` stores `text_en` as the claim-number
prefix plus `parts_en` joined by a space, while `parts_en` has no number.
Rebuilding `text_en` from the parts, as `CONTRACTS.md` describes, deletes the
prefix.

`set_final.py` handles this: it derives the prefix and the separator from what
the claim already uses, and dies rather than normalising if it can reconstruct
neither. Never hand-edit `claims_en.json` — that protection only exists inside
the tool. See the entry in [harness-backlog.md](harness-backlog.md).

## A renamed repo directory breaks the virtualenv

`.venv/bin/pip` and the other console scripts hardcode the interpreter path in
their shebang, so renaming or moving the repo leaves `pip` failing with
"required file not found" while `.venv/bin/python` (a symlink) keeps working.
The pipeline still runs, which is what makes it easy to miss.

```
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## `assemble.py` exits 1 with "required state file missing: translations.json"

The English side of the project does not exist yet. For a real job, run the
translation stages first. For a fixture, run `dev/make_fixture_en.py` — or just
`dev/smoke.py`, which does the whole chain in order.

## A background research agent looks dead but is not

A long-running subagent can stop writing its transcript for tens of minutes
while it works through large PDFs. A stalled transcript is not evidence of a
crash, and neither is the absence of a separate process. This session one was
declared dead after seven minutes of silence and delivered normally at
thirty-nine. Wait for the completion notification, or check whether the last
transcript record is a terminal result record before concluding anything.
