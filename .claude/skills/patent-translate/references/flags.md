# Flags — taxonomy and escalation rules

`state/flags.json` is the single source of doubt. Managed via
`scripts/flags.py` (add / resolve / list); checks.py adds MECH flags itself.

## Classes

- **AMBIGUITY** — the Italian admits more than one reading and the choice
  affects the English. `options` MUST list each reading with its English
  consequence. Owner of the decision: Mario or the firm.
- **TERM** — a terminology decision a reviewer might overturn (synonym
  choice, adapted-to vs configured-to, includente kept distinct…). One flag
  per decision, not per occurrence — the glossary already propagates it.
- **CONVENTION** — a drafting rule applied and disclosed: said-policy,
  two-part form kept, and one flag PER OCCURRENCE for transitional phrases in
  claims. Not open doubts; they exist so the firm can reverse a rule with one
  decision.
- **CLAIM-DEFECT** — the source claim is defective (antecedent missing in the
  Italian, claim term without description support, suspicious dependency,
  scope oddity). Translated faithfully; the flag describes the defect and,
  where useful, what a repair would look like — for the firm to decide, never
  applied.
- **MECH** — a mechanical check failure that cannot be resolved without
  touching the Italian.

## Rules

- Flag at discovery time; never batch-reconstruct doubts afterwards.
- `segment_id` always set; `text_it`/`text_en` filled whenever they exist.
- `options` are concrete alternatives, never "to be reviewed".
- The escalation list = open flags of class ≠ CONVENTION. They land in
  `out/ESCALATIONS.md` and the side-by-side; they are closed only by an
  answer from Mario or the firm (`flags.py resolve --key … --resolution …`).
- A resolved AMBIGUITY/TERM whose resolution changes text or glossary
  triggers the re-run path in SKILL.md.
