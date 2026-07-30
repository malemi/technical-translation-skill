---
name: patent-translate
description: Translate an Italian patent application in projects/<slug>/ into English for PCT filing. Glossary-first pipeline — DeepL Pro for description prose, model-authored claims, mechanical verification battery, bilingual review artifact with flags. Use when asked to translate (or re-run) a patent project in this repo.
---

# patent-translate — operating procedure

The Italian source is authoritative. You translate it; you never improve it.
Every doubt you cannot resolve from the source alone becomes a flag, not a
decision. Chat with Mario stays Italian; every artifact you produce is English.

## Translation standard (client directive)

The translation must be **literal and accurate**, strictly preserving the
structure and the technical reference signs of the Italian text. The Italian
application is the text as filed; the English is produced afterwards as a
translation of the originally-filed application, so the Italian always governs.

Operative consequence for every wording choice: when a faithful-literal
rendering and a more idiomatic or commercial one diverge, choose the **literal**
one and record the idiomatic alternative as a TERM flag for the firm to weigh —
never silently prefer the idiomatic term. (Examples: "estrazione a freddo" →
"cold extraction", not the commercial "cold brew"; "elemento rompiflusso" →
"flow-breaking element", with "baffle element" flagged as the technical
alternative.)

## Hard rules (from the client brief — non-negotiable)

1. Nothing added, dropped, or improved. Badly drafted claims are translated
   faithfully and flagged CLAIM-DEFECT, never fixed.
2. Terminology is locked before any translation and identical everywhere.
3. Numbers and units are copied, never converted. Decimal comma → decimal
   point is permitted orthography; every instance lands in the audit table.
4. Ambiguities escalate to Mario. Never resolve one silently.
5. DeepL only for the machine translation; no other external service sees the
   text. Free-tier keys (`:fx`) are accepted for this project because the
   Italian source is already filed (priority secured), so DeepL's Free-tier
   text retention is not a confidentiality risk here. The endpoint is chosen
   automatically from the key suffix.

## Procedure

Work from the repo root. `<P>` = project path, e.g. `projects/acme`.
`$S` = `.claude/skills/patent-translate/scripts`. Python = `.venv/bin/python`.

### 0. Preflight
- Exactly one `.docx` in `<P>` (else pass `--source`).
- A legacy binary `.doc` source must be converted first — python-docx cannot
  read OLE2: `.venv/bin/python $S/dev/convert_doc.py --project <P>
  [--source name.doc] [--force]`. It uses LibreOffice headless (plain-text
  extractors destroy the paragraph structure the pipeline segments on), writes
  `source.docx` beside the `.doc`, refuses to overwrite an existing
  `source.docx` without `--force`, and never deletes the original — the `.doc`
  stays the authoritative artifact. Conversion is lossy in principle: check
  ingest's printed summary (paragraph counts, headings, claims, reference
  signs) against the `.doc` before trusting it.
- `DEEPL_AUTH_KEY` reachable (env or repo `.env`). Never echo it.

### 1. Ingest
- `.venv/bin/python $S/ingest.py --project <P>`
- `.venv/bin/python $S/validate_state.py --project <P>`
- READ the whole document — every segment in `state/segments.json`, start to
  end, no truncation, no sampling. While reading, file flags for: source
  terminology inconsistencies, ambiguous pronouns/attachments, claim defects
  (`$S/flags.py add …`, classes per `references/flags.md`).
- Cross-check the printed claim graph against what you read. Any `ESCALATION`
  warning from ingest → flag.

### 2. Terminology (GATE — nothing is translated before the lock)
- Author `<P>/terminology.csv` per CONTRACTS.md, term choices per
  `references/style-guide.md`. Coverage order: claim terms first
  (`in_claims=yes`), then every numeral-bearing part, then process, material
  and parameter terms.
- Source inconsistency (two IT terms, same part/numeral): keep ONE row — all
  IT surface forms in `variants_it`, the chosen EN repeated positionally in
  `variants_en` — plus a TERM flag. If the referent is not provably the same
  part → AMBIGUITY flag instead.
- `.venv/bin/python $S/glossary.py validate --project <P>` — resolve every
  warning before the gate.
- STOP. Present the table and the open TERM/AMBIGUITY flags to Mario (chat in
  Italian, table stays English) and ask for the lock. Do not proceed without
  it. After the lock, set `status=locked` on all rows.

### 3. Machine translation (description + abstract)
- `.venv/bin/python $S/glossary.py push --project <P>`
- `.venv/bin/python $S/translate_deepl.py run --project <P>`

### 4. Fidelity review (yours)
- Per `references/review-protocol.md`: EVERY pair, in order, IT vs
  `text_en_deepl`. New source ambiguities discovered here → flags.
- Never hand-edit the state files. Write a revisions JSON and apply it with
  `.venv/bin/python $S/set_final.py --project <P> --input <file>`: it is the
  single writer, it records a reason for every change, and it is idempotent, so
  a re-run of the same batch reports "already current" instead of duplicating.
  `--dry-run` first on a large batch.

### 5. Title and claims (yours)
- Title and claims go through the same tool: `title`, `pairs` and `claims`
  sections of the revisions file. Claims are supplied as `parts_en`; `text_en`
  is rebuilt keeping whatever claim-number prefix and part separator the
  project already uses.
- Each claim per `references/style-guide.md`, locked terms verbatim,
  into `state/claims_en.json` with its `conventions` list.

### 6. Back-translation probe
- `.venv/bin/python $S/backtranslate.py run --project <P>`
- Compare `text_it_back` vs original `text_it` claim by claim per
  `references/review-protocol.md` pass 2. Drift that is yours → fix your EN;
  drift exposing a source ambiguity → AMBIGUITY flag.

### 7. Mechanical battery
- `.venv/bin/python $S/checks.py run --project <P>`
- For each fail/warn: fix the root cause on the ENGLISH side (your text or
  terminology — never the Italian), or flag it. `claim_support` failures
  caused by the source (term exists only in claims) are CLAIM-DEFECT flags,
  not fixes. Re-run until every remaining fail/warn is covered by an open
  flag.

### 8. Assemble and deliver
- Write `<P>/notes-for-human-reviewer.md`: a table of how expressions were
  rendered in THIS application — Italian, English, and nothing else. No reasons,
  no doubts, no "confirm", no rule citations. Include a pattern only if a human
  editor would want it; a couple of dozen rows, not the whole glossary. Close
  with at most three plain lines on what follows the Italian as filed (claim
  form and dependencies, decimal points, reference signs unchanged).
  Less is more: everything you add is another thing to lose the real findings in.
- `.venv/bin/python $S/assemble.py run --project <P>`
- Report to Mario (Italian): `out/` paths, open escalations by class,
  multiple-dependent claims (US-phase note, from the claims_graph data),
  billed characters.

## Re-runs
- Terminology change after the lock: edit the CSV → `glossary.py push` →
  `translate_deepl.py run` → steps 4–8. Invalidation is automatic (finals
  reset only where the DeepL text changed): re-review only the invalidated
  pairs, then checks and assemble again.
- Never hand-edit `out/` files; they are always regenerated.
