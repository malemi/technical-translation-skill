# Review protocol

## Pass 1 — fidelity review of DeepL pairs (every pair, no sampling)

For each pair, compare `text_it` with `text_en_deepl` and check, in order:

1. Completeness — every clause, qualifier, list item, parenthetical present.
   DeepL's characteristic failure is fluent smoothing: a dropped inciso reads
   perfectly and is wrong. Read the Italian first, then verify the English
   against it (not the reverse).
2. Meaning — false friends and patent-Italian idioms:
   - eventualmente → optionally / where appropriate (NEVER "eventually")
   - attualmente → currently (never "actually")
   - sensibilmente → substantially / appreciably
   - sostanzialmente → substantially
   - atto a → adapted to; idoneo a → suitable for
   - forma di realizzazione → embodiment
   - tecnica nota / stato della tecnica → prior art
   - a monte / a valle → upstream / downstream
3. Terminology — locked EN variant used everywhere the IT variant occurs
   (the glossary_adherence check catches stragglers; fix here first).
4. Register — patent register, no colloquialisms; do not tighten description
   prose into claim language.

Edit ONLY for those reasons. Every edit: `text_en_final` + an `edits` entry
whose `reason` names the category (completeness / meaning / terminology /
register) and the specific trigger.

If the ITALIAN is ambiguous: never pick a reading silently. AMBIGUITY flag
with each reading and its English consequence; where English can preserve the
ambiguity, prefer the rendering that does and say so in the flag.

## Pass 2 — back-translation comparison (claims)

Compare `text_it_back` against the original `text_it`, claim by claim. The
probe is naive by design (no glossary): wording differences are expected and
irrelevant. Hunt MEANING differences only — scope, which element does what,
mandatory vs optional, ranges and their endpoints, singular/plural of
elements.

- Drift traceable to your English → fix the EN claim, re-run the probe for
  that claim.
- Drift exposing a genuine source ambiguity → AMBIGUITY flag.
- Equivalent meaning → record nothing.
