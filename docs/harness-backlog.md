# Harness backlog

Gaps in the tooling and testing harness — things that are checked by hand today
and should be enforced mechanically.

## The three DeepL stages are not covered by the smoke test

`dev/smoke.py` exercises everything that can run offline, but `glossary.py push`,
`translate_deepl.py run` and `backtranslate.py run` need a live key and a real
API call, so a regression in the upload, polling, pairing or retry logic would
not be caught by it. Those three are verified by hand against the real API when
they change.

Fixing this properly means a recorded-response harness (capture real DeepL
responses once, replay them offline) rather than a mock — a hand-written mock
would encode our assumptions about the API instead of its actual behaviour, and
would pass while the real call fails.

## No pre-commit enforcement

`dev/smoke.py` and the documentation gate both have to be remembered. Optional
one-liner if that ever becomes a problem: put them in `.githooks/pre-commit` and
`git config core.hooksPath .githooks`.
