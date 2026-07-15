# Claim drafting conventions (IT → EN)

Rules the model applies when authoring English claims. Deviating from the
literal Italian for any reason NOT listed here is forbidden — flag instead.
Applying a listed rule is disclosed via CONVENTION flags as noted.

## Structure
- One claim = one sentence, single final period.
- Mirror the source's part structure: preamble, feature clauses as separate
  parts matching the Italian paragraphs, final characterizing clause if
  present. Never merge or split clauses.
- Two-part form: keep it if and only if the Italian has it —
  "caratterizzato dal fatto che" → "characterized in that". Never introduce
  or remove the two-part form.
- Dependent preambles: "Apparatus according to claim 2", "according to any
  one of claims 1 to 3", "according to the preceding claim" — mirror the
  dependency exactly; never widen or narrow the set. Multiple-dependent
  claims stay multiple-dependent (the US-phase cost is a note in the
  deliverables, not a reason to rewrite).

## Determiners and antecedent basis
- First introduction of an element: "a/an". Later references: "the".
- "detto/detta/detti/dette" → "said", uniformly. One CONVENTION flag for the
  whole document, noting "the" as the modern alternative the firm may prefer.
- "almeno un X" → "at least one X". If the Italian re-refers with "detto X",
  render "said X" and add a CONVENTION flag noting the stricter US form
  "the at least one X" as alternative.
- Every "the/said X" needs an antecedent in the same claim or in EVERY
  dependency path. If the ITALIAN itself lacks the antecedent: translate
  faithfully and flag CLAIM-DEFECT. Do not repair.

## Transitional phrases (scope-critical — never smooth)
- comprendente / che comprende / comprende → comprising
- costituito/a da → consisting of
- consistente in → consisting of
- consistente essenzialmente in → consisting essentially of
- includente / che include → including (comprising-family; keep it distinct
  and add a TERM flag on first use)
Each occurrence in a claim is mapped individually and gets its own CONVENTION
flag (segment = that claim): the per-occurrence map is what the firm audits,
because an unnoticed closed transition narrows scope.

## Common renderings
- atto/atta a → adapted to; configurato/a per → configured to. Keep the
  source's distinction; TERM flag on first use of each.
- in cui → wherein; per cui → whereby (TERM flag); mediante → by means of;
  tale che → such that; forma di realizzazione → embodiment.
- Method claims: "comprendente le fasi di" → "comprising the steps of";
  infinitives become gerunds ("introdurre" → "introducing").
- sostanzialmente → substantially; preferibilmente → preferably;
  vantaggiosamente → advantageously. Present in Italian → present in English;
  absent → absent.
- Reference numerals: copied verbatim, same parentheses, attached to the same
  noun.
- Numbers and units: copied; decimal comma → decimal point (audited
  mechanically).

## Forbidden
- Adding hedges ("about", "substantially") not in the Italian, or dropping
  ones that are there.
- Fixing source defects: missing antecedents, odd dependencies, scope
  oddities, a "costituito da" that narrows a dependent claim. Translate
  faithfully, flag CLAIM-DEFECT.
- Any terminology not in the locked glossary for a term the glossary covers.
