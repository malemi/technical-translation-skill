# Quality grades

Coverage and quality per area, as verified rather than as intended.

| Area | Grade | Basis |
| --- | --- | --- |
| Offline pipeline (ingest → checks → assemble) | **Good** | `dev/smoke.py` runs it end to end from a clean checkout and asserts the status of all 13 checks plus the six seeded defects. The assertions were shown to fail when a check is deliberately blinded. |
| Verification battery | **Good** | Caught every seeded defect, and caught two real regressions introduced during this session's revision pass — one terminology drift, one lost claim number. |
| DeepL stages | **Unverified here** | Exercised live against the real API in an earlier session; not covered by the smoke test and not re-run. See [harness-backlog.md](harness-backlog.md). |
| Style authority | **Good** | Single guide, normative layer cited by rule number against primary PCT/EPC/EPO/USPTO texts, weakly-sourced items declared as such. |
| `ingest.py` segmentation | **Adequate, one known defect** | Correct on the fixture and on a real document, except that a trailing non-claim paragraph is absorbed into the last claim. Handled by a flag, not by code. |
| Contract ↔ state agreement | **Weak** | `CONTRACTS.md` and real `claims_en.json` disagree on the shape of `text_en`. Tolerated by the tooling, not reconciled. |

Nothing here is graded on unit tests: this repo has none, and would not be
better for having them. The grades reflect what was run the way the pipeline is
actually run.
