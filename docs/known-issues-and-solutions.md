# Known issues and solutions

## `checks.py` reports 1 fail + 1 warn on the clean fixture

Expected. `projects/_fixture` contains deliberate source quirks that the
pipeline must surface rather than silently fix — they are listed at the top of
`projects/_fixture/fixture_spec.md`. On the clean fixture the correct result is
**pass 11, fail 1, warn 1**: `claim_support` fails because "sensore di pressione
(8)" appears only in claim 5 and never in the description, and
`numeral_term_consistency` warns because numeral (2) is called both "vasca di
estrazione" and "serbatoio" in the Italian.

A run that reports all-pass on the fixture means the checks stopped working.
`dev/smoke.py` asserts the expected status of every check, so it fails loudly if
that ever happens.

## A renamed repo directory breaks the virtualenv

`.venv/bin/pip` and the other console scripts hardcode the interpreter path in
their shebang, so renaming or moving the repo directory leaves `pip` failing
with "required file not found" while `.venv/bin/python` (a symlink) keeps
working. The pipeline still runs, which is what makes it easy to miss.

Solution: recreate the venv.

```
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## `assemble.py` exits 1 with "required state file missing: translations.json"

The English side of the project does not exist yet. For a real job, run the
translation stages first. For a fixture, run `dev/make_fixture_en.py` — or just
`dev/smoke.py`, which does the whole chain in order.
