# Style guide — IT → EN patent translation for PCT filing

The single style authority for this skill. Nothing else in this repo overrides
it, and no other style document exists: if a rule is not here, it is not a rule.

## What governs, in order

1. **The Italian text as filed.** It is authoritative and is never improved.
   Every rule below operates inside that constraint.
2. **The PCT and the EPC.** Where a rendering is fixed by the PCT Rules, the EPC
   Implementing Regulations or the EPO Guidelines, it is not a matter of taste
   and not negotiable by anyone. These are cited by rule number below.
3. **The house choices in this section's tables.** These fill the gaps the norm
   leaves open. They are decisions, not obligations, and are marked as such.

External review carries no authority of its own, however fluent or senior. A
reviewer's proposal is weighed by the test two sections down.

We file one PCT text. Practice belonging to a later national phase never changes
the English — it becomes a flag. See "National phase" near the end.

## Normative requirements

Every rule in this section was read on the official text; the citation is exact
so it can be re-checked. Sources are listed at the end.

### Abstract

- **50 to 150 words** when the abstract is in English or translated into English
  — PCT Rule 8.1(b): "as concise as the disclosure permits (preferably 50 to 150
  words if it is in English or when translated into English)". `checks.py`
  enforces this mechanically.
- **Reference signs are mandatory in the abstract, in parentheses.** PCT Rule
  8.1(d): "Each main technical feature mentioned in the abstract and illustrated
  by a drawing in the international application shall be followed by a reference
  sign, placed between parentheses." EPC Rule 47(4) says the same. Note the
  unqualified *shall* — unlike in the claims, where signs are only *preferable*.
  Italian applications routinely write bare numbers in the abstract; that is a
  source defect. Translate faithfully and flag it.
- No statements on alleged merits or value — PCT Rule 8.1(c).

### Numbers, units, terminology

- **Decimal comma → decimal point is required, not optional.** PCT Rule 10.1(f):
  when the application or its translation is in English, "the beginning of any
  decimal fraction shall be marked by a period". Converting `12,5` to `12.5` is
  compliance, not a stylistic liberty.
- **Metric units are mandatory**, at least as one of two expressions — PCT Rule
  10.1(a); temperatures in Celsius — Rule 10.1(b).
- At the EPO, imperial or local units "do not, in general" satisfy the
  requirement, and each non-conforming value "must be adapted such that it is
  replaced by a corresponding value expressed in units conforming to
  international standards, with the original value being maintained in
  brackets" — EPO Guidelines F-II, 4.13. Never silently substitute, never leave
  as-is.
- **Terminology must be consistent throughout the application** — PCT Rule 10.2.
  This is the normative backing for the glossary: an inconsistent rendering is a
  compliance failure, not only an aesthetic one.

### Reference signs in claims

- Preferable, in parentheses, where they aid understanding — PCT Rule 6.2(b),
  EPC Rule 43(7).
- They do **not** limit scope — EPC Rule 43(7): "These reference signs shall not
  be construed as limiting the claim." This is why they are copied verbatim and
  never adjusted for English word order: they carry no scope, only identity.
- **Never add descriptive text inside the parentheses.** EPO Guidelines F-IV,
  4.18: expressions such as "securing means (screw 13, nail 14)" "are not
  reference signs within the meaning of Rule 43(7)… Consequently, it is unclear
  whether the features added to the reference signs are limiting. Accordingly,
  such bracketed features are generally not permissible."
- In two-part claims the signs go in the preamble as well as the characterising
  portion — F-IV, 4.18.

### Transitional phrases

- EPO Guidelines F-IV, 4.20: a claim "comprising" certain features "does not
  exclude the presence of other features"; with "consist of", "no further
  features are present… apart from the ones following said wording". "Consisting
  essentially of" admits further components "not materially affecting the
  essential characteristics".
- The same three-way framework is PCT-level — ISPE Guidelines para. 5.24 — so it
  is not a jurisdictional quirk.
- **Added-matter trap:** "'comprising' does not provide per se an implicit basis
  for either 'consisting of' or 'consisting essentially of' (T 759/10)" —
  F-IV, 4.20. Rendering an open Italian transition as a closed English one does
  not merely narrow the claim, it may be unfixable later.

### Two-part form

- Originates at treaty level: PCT Rule 6.3(b) prescribes a characterising
  portion "preceded by the words 'characterized in that', 'characterized by',
  'wherein the improvement comprises', or any other words to the same effect",
  "whenever appropriate".
- EPC Rule 43(1) makes it the EPO default, "wherever appropriate", using
  "characterised in that" or "characterised by".
- For us this changes nothing: keep the form if and only if the Italian has it.
  We never introduce or remove it.

### Dependent claims

- **PCT Rule 6.4(a)**: a multiple dependent claim "shall refer to such claims in
  the alternative only", and "Multiple dependent claims shall not serve as a
  basis for any other multiple dependent claim."
- **EPC Rule 43(4)** is more permissive: "A dependent claim directly referring to
  another dependent claim shall also be admissible", with no alternative-only
  requirement and no anti-cascading rule.
- The PCT's own examiner guidelines acknowledge the split: ISPE Guidelines
  Appendix A5.16 offers Authorities two alternative practices, one restrictive
  and one permissive.
- Consequence for us: an Italian claim set with cascading multiple dependencies
  is normal at the EPO but sits outside PCT Rule 6.4(a) as written, and may draw
  an Article 17(2)(b) indication depending on which Authority searches. It is
  still translated exactly as filed — we never restructure a dependency — and it
  is flagged.

### Clarity

- EPC Article 84: claims "shall be clear and concise and be supported by the
  description". PCT Article 6 is the equivalent.
- Relative terms are objected to "unless [the term] has a well-recognised
  meaning in the particular art… or its meaning is clear to the skilled person
  in the context of the whole disclosure" — F-IV, 4.6.
- "about" and "approximately" are read as "being as accurate as the method used
  to measure it" — F-IV, 4.7.1.
- **Optional features are permitted at the EPO.** F-IV, 4.9: features preceded by
  "preferably", "for example", "such as" "are allowed if they do not introduce
  ambiguity… they are to be regarded as entirely optional". The PCT instructs
  examiners the same way — ISPE Guidelines para. 5.40. So `preferibilmente pari
  a 350 µm` inside a claim is fine for the PCT and the EPO. It is *not* fine in
  the US: see "National phase".

### Trademarks

- Not allowed in claims "as it does not guarantee that the product or feature
  referred to is not modified while maintaining its name", allowed exceptionally
  only if unavoidable and precise — F-IV, 4.8.
- In the description, registered trademarks must be acknowledged as such —
  F-II, 4.14. If the Italian names a branded product, the English carries the
  acknowledgement, not just the translated name.

### Functional features and "means"

- At the EPO, "Means-plus-function features ('means for ...') are a type of
  functional feature and hence do not contravene the requirements of Art. 84" —
  F-IV, 4.13.2 — and are read broadly, as anything suitable for the function.
- F-IV, 3.9.1, citing T 410/96: "There is no particular preference of wording
  among 'comprising means for', 'adapted to', 'configured to' or equivalents."
  The EPO treats them as interchangeable. **We still keep the source's
  distinction** (`atto a` → adapted to, `configurato per` → configured to),
  because US construction of these phrases is unsettled and because collapsing a
  distinction the Italian makes is not our call.

## Adjudicating a review comment

Three questions, in order. The first that applies decides.

1. **Does the change touch technical content?** If a proposal adds, drops,
   reorders or re-scopes anything the Italian says — a sentence, a clause, a
   hedge, a unit, a ratio, a defined quantity — reject it, however fluent the
   English.
2. **Does the change touch a term of art or a normative requirement?** Anything
   in the section above, plus transitional phrases, `means`, reference signs,
   dependency phrasing. The rule wins over the reviewer.
3. **Otherwise it is ordinary English.** Here the better English wins. A calque
   that survives because "it is closer to the Italian" is not fidelity, it is a
   defect.

A reviewer who raises a genuine ambiguity is always right to raise it, whatever
fix they propose. That becomes an AMBIGUITY flag, never a silent decision.

## Never negotiable

- **Reference signs are copied character for character.** Same characters, same
  order, same parentheses, attached to the same noun. Never re-lettered to suit
  English word order: if the Italian says `(PM)`, the English says `(PM)`. They
  carry no scope (EPC Rule 43(7)), so changing them buys nothing and breaks the
  correspondence with the drawings.
- **`mezzi` → `means`, always.** Never `mechanism`, `device`, `unit`, `system`,
  `assembly`. Keep the plural agreement: `the drive means **are** controllable`.
- **Never repair a defect in the source.** Missing antecedent, dangling clause,
  a dependency chain that strains PCT Rule 6.4(a): translate verbatim and flag
  CLAIM-DEFECT. A reviewer who fixes one in passing has produced a different
  document, not a translation.
- **Nothing is dropped.** Not a sentence, not a subordinate clause, not
  `preferibilmente` / `vantaggiosamente` / `sostanzialmente`.
- **Defined quantities keep their structure.** A ratio stays that ratio with
  those operands. `frazione in peso` is not `peso`; `quantità` is not `volume`.
- **Claim word order is not rearranged for readability.**

## Claim structure

- One claim = one sentence, single final period.
- Mirror the source's part structure: preamble, feature clauses as separate
  parts matching the Italian paragraphs, characterising clause if present. Never
  merge or split clauses.
- Dependent preambles mirror the dependency exactly — never widen or narrow the
  set.
- Method claims: `comprendente le fasi di` → `comprising the steps of`;
  infinitives become gerunds (`introdurre` → `introducing`). Gerunds in the
  claims, the description and the abstract alike — never the imperative.

## Determiners and antecedent basis

Neither the EPC nor the PCT has a doctrine of this name; it is a US concern
(MPEP 2173.05(e)). We enforce it anyway, because it is close to mandatory in the
US and merely good style elsewhere — never the reverse.

- First introduction: `a/an`. Later references: `the`.
- `detto/detta/detti/dette` → `said`, uniformly, claims and description. **House
  choice, not a requirement**: US practice treats `the` and `said` as
  interchangeable, and the EPC is silent. One CONVENTION flag records it.
- `almeno un X` → `at least one X`; a later `detto X` → `said X`, with `the at
  least one X` flagged as the stricter alternative.
- Every `the/said X` needs an antecedent in the same claim or in every dependency
  path. If the Italian lacks it: translate faithfully, flag CLAIM-DEFECT.

## Transitional phrases (scope-critical — never smooth)

| Italian | English |
| --- | --- |
| comprendente / che comprende / comprende | comprising |
| costituito/a da | consisting of |
| consistente in | consisting of |
| consistente essenzialmente in | consisting essentially of |
| includente / che include | including (keep distinct; TERM flag on first use) |

Each occurrence in a claim is mapped individually and gets its own CONVENTION
flag. Never introduce `consists of` where the Italian has no closed transition —
`in cui sono presenti` is not one.

## Standard renderings

House choices unless a rule is cited above.

| Italian | English | Not |
| --- | --- | --- |
| `mediante` (description) | `by` | `by way of` |
| `mediante` (title, claim preamble) | `by means of` | |
| `in cui` | `wherein` | `in which` |
| `per cui` | `whereby` (TERM flag) | |
| `atto/atta a`, `adatto a` | `adapted to` | `suitable for` |
| `configurato/a per` | `configured to` | `adapted to` |
| `dotato di` | `provided with` | `equipped with` |
| `compreso tra A e B` | `between A and B` | `comprised between`, `ranging from` |
| `pari a` | `equal to` | (omitting it) |
| `per esempio`, `ad esempio` | `for example` | `e.g.` |
| `come ad esempio` | `such as, for example,` | |
| `fase` (process step) | `step` | `phase` |
| `fase` (state of matter) | `phase` | `step` |
| `sottofase` | `sub-step` | `sub-phase` |
| `forma di realizzazione` | `embodiment` | |
| `variante realizzativa` | `embodiment variant` | `embodiment` |
| `esempio realizzativo` | `exemplary embodiment` | `embodiment` |
| `stato dell'arte`, `stato della tecnica` | `prior art` | `state of the art` |
| `scopo` (of the invention) | `object` | `purpose`, `objective` |
| `a valle di` / `a monte di` | `downstream of` / `upstream of` | `after` / `before` |
| `media` | `mean` | `average` |
| `quantità` | `quantity` | `amount` |
| `conservazione` | `preservation` | `shelf-life`, `storage` |
| `stoccaggio` | `storage` | `preservation` |
| `procedimento`, `metodo` | `method` | `process` |
| `ossia`, `cioè` | `that is`, `i.e.` | `meaning` |
| `in accordo con` | `according to` | `in accordance with` |
| `sostanzialmente` / `preferibilmente` / `vantaggiosamente` | `substantially` / `preferably` / `advantageously` | (omitting them) |

`by way of` is **wrong** as a rendering of `mediante`. In patent English it
survives almost only in `by way of example`. Correct it everywhere, including in
reviewer suggestions.

Hedges present in the Italian are present in the English; hedges absent are
absent.

## Italian calques to remove

- `permette di ottenere X` is **not** `allows to obtain X` — `allow` does not
  take a bare infinitive. Use `makes it possible to obtain X`.
- `il metodo oggetto dell'invenzione` is **not** `the method object of the
  invention`. Use `the method that is the object of the invention`.
- `costituisce oggetto della presente invenzione X` → `the present invention also
  relates to X`.
- `comprised between` for `compreso tra` — Euro-English, still a calque.

## English drift to resist

- **Do not swap a defined term for the field's colloquial name.** Where the
  source defines a quantity, the definition's noun is the term. An industry name
  that differs is a TERM flag recording the alternative, never a substitution,
  and never applied to some paragraphs only.
- **A term of art does not automatically beat the literal rendering.** The firm
  may know the general word was chosen deliberately to keep scope broad.
- **A heading is a category, not a phrase to improve.** `RIASSUNTO` is the
  application's abstract: the heading reads `ABSTRACT`, never `SUMMARY`.
- **Em-dash asides are not patent register.** Restore the commas or parentheses
  the Italian uses; an em-dash aside can detach a qualifier from what it
  qualifies.

## Consistency is the deliverable

Backed by PCT Rule 10.2, so this is compliance, not taste.

- A term chosen once holds in the title, the abstract, the description and the
  claims. The locked glossary is the record.
- **A reviewer's suggestion is accepted document-wide or rejected.** Applying it
  only where the reviewer happened to mark manufactures an inconsistency no
  check can attribute to the source.
- When two defensible readings collide, the tie-break is whatever the glossary
  locked. If the glossary is silent, it becomes a TERM flag.

## Forbidden

- Adding hedges not in the Italian, or dropping ones that are there.
- Fixing source defects. Translate faithfully, flag CLAIM-DEFECT.
- Any terminology not in the locked glossary for a term the glossary covers.

## National phase: flag, never restructure

The English is never changed for a national-phase reason. These become flags.

- **Multiple dependent claims.** Permissive at the EPO (Rule 43(4)); restricted
  by PCT Rule 6.4(a); at the USPTO 37 CFR 1.75(c) repeats the PCT restriction as
  a hard rule and a separate per-claim fee applies. Flag the chain.
- **`preferably` inside a claim.** Allowed at the EPO and the PCT (F-IV 4.9;
  ISPE 5.40). MPEP 2173.05(c) gives essentially this construction — a broad
  range plus a narrower preferred range in one claim — as its own worked example
  of indefinite claim language. Opposite defaults for identical wording: flag it.
- **`means` claims.** Translated as `means`, always. In the US, 35 U.S.C. 112(f)
  may narrow them to the disclosed structure; at the EPO they are read broadly.
  Same words, opposite construction. Not a reason to paraphrase.
- **Two-part form.** Expected at the EPO; in the US the equivalent Jepson form is
  taken as an implied admission that the preamble is prior art (MPEP 2129).
- **`wherein` / `whereby`.** A US doctrine on patentable weight (MPEP 2111.04)
  with no EPO counterpart.

## Known failure modes

Real errors produced by outside reviewers on this project. No authority — a
catalogue of what goes wrong.

- `mezzi` rewritten as `mechanism`, and the plural silently made singular.
- A two-letter reference sign re-lettered to match English word order.
- An antecedent-basis defect in an independent claim silently repaired, after it
  had been explicitly flagged as a defect to translate verbatim.
- A sentence dropped, and two defined quantities altered, while making a
  paragraph read better.
- Method steps converted from gerunds to imperatives.
- `by way of` introduced throughout as a rendering of `mediante`.

## Sources

Primary texts, read directly:

- **PCT** and **Regulations under the PCT** (in force 1 January 2026) —
  <https://www.wipo.int/documents/d/pct-system/docs-en-texts-pct.pdf>,
  <https://www.wipo.int/documents/d/pct-system/docs-en-texts-pct-regs.pdf>
- **PCT International Search and Preliminary Examination Guidelines**
  (PCT/GL/ISPE/14, 12 December 2025) —
  <https://www.wipo.int/documents/d/pct-system/docs-en-texts-ispe.pdf>
- **PCT Applicant's Guide, International Phase** —
  <https://www.wipo.int/documents/d/pct-system/docs-en-guide-gdvol1.pdf>
- **EPC Article 84** — <https://www.epo.org/en/legal/epc/2020/a84.html>
- **EPC Rules 42, 43, 47, 48** — e.g.
  <https://www.epo.org/en/legal/epc/2020/r43.html>
- **EPO Guidelines for Examination, Part F, Chapters II and IV** (April 2026) —
  <https://www.epo.org/en/legal/guidelines-epc/2026/f_ii.html>,
  <https://www.epo.org/en/legal/guidelines-epc/2026/f_iv.html>
- **EPO Guidelines Part G, Chapter VI** —
  <https://www.epo.org/en/legal/guidelines-epc/2026/g_vi.html>
- **MPEP §§ 2111.03, 2111.04, 2173, 2181, 2129** —
  <https://www.uspto.gov/web/offices/pac/mpep/index.html>
- **37 CFR 1.72, 1.75** — <https://www.law.cornell.edu/cfr/text/37/1.75>
  (the official eCFR page was unreachable; Cornell LII text used)

Weaker sourcing, flagged as such: MPEP 608.01(m), (n) and (v) were read via a
third-party mirror because the official page truncated; EPC Rule 45 (claims
fees) was not opened directly. Nothing in this guide depends on those alone.
