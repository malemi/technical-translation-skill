# patent-translate

**Italian patent application in, English patent application out, ready to file.**

With it comes a bilingual document, paragraph by paragraph, marking every choice
made and every doubt left open — so you can check the work without collating the
two texts yourself.

## Using it

No terminal. Install the **Claude Code desktop app** (Mac or Windows) once —
someone technical can do that for you in ten minutes. Then, for each job:

1. Put the Italian application in its own folder, one Word file per folder.
2. Type one sentence: *translate the application in projects/rossi*.
3. **Approve the terminology.** It reads the whole document, lists every term it
   intends to use with its English rendering, and stops. Nothing is translated
   until you agree. This is where you shape the result.
4. Read what comes back, and answer its questions.
5. Ask for a second opinion when you want one — an independent review of the
   finished translation.

## What comes back

- **The English application** — title, description, claims, abstract, in Word.
- **The bilingual document** — Italian and English side by side, with each open
  doubt on the row it belongs to.
- **The questions** — only what cannot be decided from the Italian alone.
- **A note for your editor** — what was rendered how, what we were unsure of,
  and what we suspect is wrong in the Italian itself.
- **A numbers check** — every number and unit, Italian against English.

## Why you can trust it

**The Italian is authoritative and is never improved.** A missing antecedent, a
dangling clause, a formula that does not parse — translated exactly as they
stand and reported to you, never quietly repaired. A translation that fixes the
source has produced a different application.

**An ambiguity becomes a question, never a silent decision.** That is why a job
ends with a list of questions rather than a confident text.

**Every rule it follows is cited by number**, from the PCT, its Regulations, the
EPC or the EPO Guidelines, read on the official text. They are all in the
[style guide](.claude/skills/patent-translate/references/style-guide.md); the
[source list](.claude/skills/patent-translate/references/review_sources.json)
gives each URL and edition, re-checked on every job.

**What can be checked mechanically, is** — reference signs, numbers and units,
the claim dependency graph, one sentence per claim, claim terms supported in the
description, abstract length. Thirteen checks, every time.

**The second review is blind.** The reviewer is shown the Italian, the English
and the rules, and deliberately not the first pass's doubts — someone who has
seen them confirms instead of finding. It proposes; it never edits. On the first
real job it caught a formula that had lost its divisor, and a claim whose
article had been silently changed.

## Confidentiality

Only the description prose is sent to DeepL. Nothing else leaves the machine,
and client documents are never kept in this project's shared history.

**Which DeepL account you use is a confidentiality decision, not a cost one.**
The free tier keeps what it receives and may train on it; the paid tier does
not. Free is for text already destined to be published — after the priority
filing. An unfiled application needs a paid account.

---

Building on it, or reviewing the code? Start from [`CLAUDE.md`](CLAUDE.md).
Conventions: **[mrcall AI kit](https://github.com/hahnbanach/mrcall-ai-kit)**.
