---
status: planned
created: 2026-07-30
---

# patent-review — independent reviewer agent

## Goal

A second skill, `patent-review`, that reviews a translated project the way an
independent professional reviewer would: blind to the pipeline's own doubts,
against the full style guide, producing its own flags, then a semantic
comparison with the pipeline's flags and a feedback report. Its value is the
band `checks.py` cannot reach — the ten-plus normative and house rules with no
mechanical check (transitional-phrase fidelity, hedges, reference-sign
integrity, calques, trademarks, gerunds, abstract sign parenthesisation, merit
statements in the abstract) — plus grammar, delivered as proposals, never as
edits.

## Locked design decisions

1. **Blindness by packet.** The reviewer receives exactly what the independent
   human reviewer gets: the pairs (id, kind, section, Italian, final English),
   the style guide, the delivered glossary. Never `state/flags.json`, never
   `state/checks.json`, never `state/translations.json` — its `edits` entries
   carry reasons that reveal everything the pipeline already caught. Enforced
   mechanically: a packet builder emits `projects/<P>/review/packet/`, and
   review subagent prompts may reference only that directory.
2. **Generation is blind; comparison is anchored by design.** Candidate
   alignment between the two flag sets (by segment id) is a deterministic
   script. Judging whether two differently-worded flags are the same doubt is
   semantic work and is done by the model. No regex over free text.
3. **Edition check in-run, deep re-verification out-of-run.** Every run cheaply
   verifies that the editions cited in the style guide (PCT Regulations in
   force 1 Jan 2026, ISPE PCT/GL/ISPE/14, EPO Guidelines April 2026, …) are
   still current, from a small tracked manifest of URL + expected edition
   token. A full rule-by-rule re-audit of the normative layer is a separate
   job, triggered only when the edition check fires. It is out of scope here.
4. **Coverage gaps are findings.** The reviewer reports phenomena in the
   document that the style guide does not regulate (with "if a rule is not
   here, it is not a rule", gaps otherwise normalise silently), and audits
   escalation actionability: every open flag's `options` must be concrete
   alternatives, never "to be reviewed".
5. **Sharding by diligence, not capacity.** The guide plus segments fit any
   modern context; the risk is sampling instead of exhaustive checking on a
   long uniform pass. Description pairs are reviewed in blocks with the full
   checklist (most rules are pair-local: hedges, transitions, signs, calques,
   quantities). Claims + title + abstract are ONE agent — cross-claim
   antecedent paths and dependency chains need the whole set. One global agent
   covers document-wide term drift beyond what `glossary_adherence` already
   checks mechanically.
6. **Two lenses, never merged.** The rules lens is forbidden to improve the
   English; the grammar lens exists to propose improvements. One agent doing
   both smuggles fluency fixes past the funnel. Grammar runs as separate
   agents over the same shards, and every grammar proposal passes the style
   guide's three-question adjudication before it can become an edit.
7. **Propose, never write.** The reviewer's outputs are files under
   `projects/<P>/review/` only. Accepted fixes go through `set_final.py` (the
   single writer, reason citing the finding id); accepted new flags go through
   `flags.py`. Verified by hashing `state/` before and after the blind phase.
8. **A spurious never auto-closes.** A pipeline flag the reviewer did not
   reproduce becomes a note in the report; closing it stays a human decision.
9. **Dismissals are recorded.** The adjudicating session is judge in its own
   cause; mitigation: every dismissal of a reviewer finding must cite which of
   the three funnel questions kills it, in the report. A genuine doubt raised
   is never archived — it becomes a flag regardless (per `flags.md`).
10. **No second style document.** `SKILL.md` references style-guide sections by
    heading and never restates a rule — the guide's single-authority clause
    stays intact.
11. **Measured before trusted.** A seeded review fixture provides recall; the
    clean fixture provides precision and source-quirk recall. First real run
    on cafe124 only after the numbers are on the table.

## New artifacts

| Path | Role |
| --- | --- |
| `.claude/skills/patent-review/SKILL.md` | The reviewer's operating procedure. |
| `.claude/skills/patent-translate/scripts/review_packet.py` | Builds the blind packet from state. |
| `.claude/skills/patent-translate/scripts/review_validate.py` | Validates `findings.json` (schema, ids, concrete options). |
| `.claude/skills/patent-translate/scripts/review_compare.py` | Mechanical candidate alignment findings ↔ flags. |
| `.claude/skills/patent-translate/scripts/review_sources.py` | Edition check against the sources manifest. |
| `.claude/skills/patent-translate/references/review_sources.json` | URL + expected-edition-token manifest. |
| `.claude/skills/patent-translate/scripts/dev/seed_review_fixture.py` | Builds `projects/_fixture_review/` with seeded defects. |
| `projects/<P>/review/` | packet/, findings.json, comparison_candidates.json, REVIEW.md, proposed_revisions.json. Never committed. |

Review scripts live in the patent-translate scripts directory (not a second
scripts tree) because they share `common.py` and the `State` loader; the new
skill directory holds only `SKILL.md`. `projects/_fixture_review/` is generated
at smoke time and untracked, like `_fixture_bad`; its seed revisions file is
tracked under `dev/`.

## Steps

### Phase 1 — mechanics (scripts + contracts)

- [x] **1. CONTRACTS.md — "Review module" section.** Packet schema; findings
  schema (`class`, `segment_id`, `issue`, `options[]`, `lens`, optional
  `proposed_en`); comparison-candidates schema; policies: blindness rule,
  single-writer preserved, spurious-never-closes, dismissals recorded.
- [x] **2. `review_packet.py`.** Emits `review/packet/`: `pairs.json` stripped
  to id/kind/section/text_it/final EN (title and claims included), copy of
  `style-guide.md`, copy of the delivered `terminology.csv`. Deterministic;
  fails loud if any pair lacks a final.
- [x] **3. `review_validate.py`.** Schema check, segment ids must exist in the
  packet, `options` concrete (rejects empty and "to be reviewed" phrasings),
  `lens` tag mandatory. Non-zero exit on any violation.
- [x] **4. `review_compare.py`.** Aligns findings ↔ `state/flags.json` by
  segment id into `{candidates[], reviewer_only[], pipeline_only[]}`.
  Read-only with respect to `state/`.
- [x] **5. `review_sources.py check`.** Fetches each manifest URL, reports
  presence/absence of the expected edition token. Offline ⇒ loud failure
  recorded verbatim in the report, review proceeds. Manifest↔style-guide
  Sources consistency is asserted offline in smoke; the network path itself is
  not smoke-coverable — record in `harness-backlog.md`.

### Phase 2 — the skill

- [x] **6. `.claude/skills/patent-review/SKILL.md`.** Written as planned, then
  **cut back on 2026-07-30** — see step 9c. What it says now, in 98 lines: build
  the blind packet → read it in fresh-context subagent blocks, with the claims,
  title and abstract read as one set, every prompt naming the packet directory
  and no other path → write `<P>/review/REVIEW.md`, one note per problem with the
  segment, the Italian, the English, what is wrong and the proposed correction →
  **STOP: report to Mario** → only then accepted corrections via `set_final.py`,
  re-run `checks.py` and `assemble.py`, compare the check profile to baseline.

### Phase 3 — measurement

- [x] **7. `dev/seed_review_fixture.py`.** Builds `_fixture_review` from
  `_fixture` by applying a tracked revisions file injecting eight
  judgment-level defects on the English side, from the Known failure modes
  catalogue plus the guide's traps: `means`→`mechanism` with plural made
  singular; a re-lettered reference sign; a dropped clause; an altered defined
  quantity; method steps as imperatives; `by way of` for `mediante`; a closed
  transition where the Italian is open; a dropped hedge. (The ninth catalogue
  mode, silently repairing a source antecedent defect, is not seedable on this
  fixture's English — covered instead by source-quirk recall on the clean
  fixture.)
- [x] **8. Extend `dev/smoke.py`.** Packet builder golden output; validator
  accept/reject vectors; comparator on canned inputs; seeder asserted (all
  eight defects present in the generated packet's English). Still one command,
  still offline.
- [x] **8b. End-to-end plumbing trial** (added during the build; not in the
  original plan). One blind agent on `_fixture_review` produced a real
  `findings.json` that validated first time and compared cleanly; it caught 8/8
  seeded modes — **indicative only**, single agent, whole packet in one context —
  and independently found an unseeded PCT Rule 6.4(a) dependency defect the
  pipeline had missed. Its real yield was seven contract gaps. Fixed in the same
  pass: the glossary doubt-column leak (see below), a stray file in
  `review/packet/` being read as packet content, the digest check overwriting its
  own evidence (now `state-digest`), the option-concreteness length floor that
  rejected `by`, and the empty-`options` case passing the actionability audit.
- [ ] **9. Acceptance run.** Run the reviewer on `_fixture_review`: does it find
  the eight seeded defects, and does it invent notes that are not defects? Run it
  on the clean `_fixture` for the second half of that question. Numbers into
  `quality-grades.md`. No longer blocked by anything — 9a and 9b are decided.
- [x] **9a. DROPPED — no FIDELITY class.** Mario's call, 2026-07-30: an
  unfaithful rendering the reviewer finds is a proposed correction, not a new
  entry in a taxonomy. Adding a class would have grown the vocabulary we use to
  talk to the firm in order to describe our own mistake to ourselves. The trial's
  mapping (description-side → TERM, claim-side → CLAIM-DEFECT) stands as-is.
- [x] **9b. Less told, not more** — same call, and it replaced the whole
  "disclose every convention" apparatus:
  - `notes-for-human-reviewer.md`, authored in `<P>/` and copied to `out/` by
    `assemble.py`: how a couple of dozen expressions were rendered, Italian and
    English, **no reasons**. A stale `out/` copy is deleted when the project file
    goes away.
  - **CONVENTION is one flag per RULE, never per occurrence**, and it reaches no
    deliverable: out of the review table, out of `ESCALATIONS.md`, and the
    "Applied conventions" appendix is gone. On cafe124 that removed 18 rows of
    disclosure from the review table, verified in the rebuilt `.docx`.
  - Asserted in smoke, with teeth: the clean-fixture run now files a CONVENTION
    flag ON C-01 through `flags.py`, because a document-wide flag never reaches a
    table row and would have made the assertion unfailable. Putting CONVENTION
    back into the Flags column makes smoke exit 1.
- [x] **9c. Cut the reviewer down to what it is.** Mario, 2026-07-30, at the end
  of a session he called exhausting and was right to: *the reviewer reads and
  writes a document with notes, that is all.* `SKILL.md` went from about 300
  lines to 98.

  Out of the procedure: the three-way concordant/missed/spurious diff, the
  structured `findings.json` as a mandatory step, the escalation-actionability
  audit, the coverage-gap reporting, and the two open questions about the
  reviewer's optional replacement text, which the cut made moot.

  In it: build the blind packet, read, write `REVIEW.md`, stop. Each note gives
  the segment, the Italian, the English, what is wrong, and the correction
  proposed.

  `review_validate.py` and `review_compare.py` were **not deleted** — they work
  and smoke still asserts them — but no procedure calls them, and `SKILL.md` says
  so in one line at the end. The apparatus had been built for us and then handed
  to a person. A review is a document somebody reads.

### Phase 4 — first real run + docs

- [ ] **10. Review cafe124.** Build the packet, read it, write `REVIEW.md`, show
  Mario the notes. Accepted corrections go in through `set_final.py`, then
  `checks.py` and `assemble.py` re-run, and the check profile is compared with
  the 10-3-0 baseline.
- [x] **11. Root `README.md` rewrite.** Concise and high-level only: what the
  repo does, how it works, why it is built that way. No technical information
  that does not serve high-level understanding. Target structure:
  - *What*: one paragraph (Italian application in, fileable English + bilingual
    review document out) and the deliverables table.
  - *How*: the design-principle paragraph — DeepL with a locked glossary for
    description prose, model-authored claims, mechanical verification battery,
    bilingual review artifact — extended with the independent reviewer:
    a second, blind review that re-derives the doubts and diffs them against
    the pipeline's.
  - *Why*: the fidelity stance (the Italian is authoritative, defects are
    flagged never fixed, ambiguities become questions) and the DeepL-tier
    confidentiality decision. The Confidentiality section stays — `CLAUDE.md`
    links to it.
  - *Try it*: the one smoke command and two lines on what it proves.
  - *Real job*: the four-step usage, shortened.
  - *Pointers*: `CLAUDE.md`, `CONTRACTS.md`, `docs/`, the two `SKILL.md`s.
  Out of the README: the script-reference tables, the layout tree, per-stage
  command detail, smoke-internals detail — commands live in the `SKILL.md`s,
  schemas and mutations in `CONTRACTS.md`. Anything currently README-only that
  still matters moves to `CONTRACTS.md` or `docs/` instead of being silently
  dropped.
- [x] **12. Other docs.** `CLAUDE.md` index row (repo no longer "a single
  skill") and its README pointer check, `active-context.md`,
  `harness-backlog.md` (semantic acceptance not CI-assertable; edition-check
  network path), `quality-grades.md`.

## Acceptance criteria

- `smoke.py` exit 0 including the new mechanical assertions.
- Seeded recall 8/8 classes; false positives individually analysed with Mario;
  source-quirk recall reported.
- cafe124 `REVIEW.md` produced; every dismissal cites its funnel question; the
  `state/` hash is unchanged across the blind phase.
- Root `README.md` reads as what/how/why at high level: no script tables, no
  layout tree; the Confidentiality section survives and the `CLAUDE.md` pointer
  to it still resolves.

## Out of scope

- The deep normative re-audit job (separate; triggered by the edition check).
- A mechanical `checks.py` check for PCT Rule 8.1(d) abstract sign
  parenthesisation — a candidate quick win, but independent of the reviewer.
- Auto-closing flags or auto-applying edits without Mario's go.
