---
doc: prd
status: approved
---
<!-- Approval note: product decisions delegated to the agent by the learner on 2026-10-12
     ("fai tutto tu", "decidi tu"). Delegated choices are marked (delegated). -->

# Riserbo — Product Requirements

A local web tool that redacts personal data from Swiss/Italian documents with Apertus and restores it after a cloud AI has answered — for legal and compliance assistants who can't send client data out.
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`.

## The Core Journey
1. The user starts Riserbo (`make run`) and opens `http://localhost:8080`. A status pill shows whether Apertus is reachable.
2. They paste a document or click one of the sample documents (Italian, German, French).
3. They press **Redact**. Within seconds the document reappears with each detected item highlighted and colour-coded by type; hovering shows the type, the detector (rule / Apertus) and a one-line reason.
4. Below, the **redacted text** shows placeholders (`[PERSON_1]`, `[AHV_1]`, `[QUASI_1]` …) with a **Copy** button, and a **mapping table** lists placeholder → original.
5. The user pastes the redacted text into any cloud AI (outside Riserbo) and copies the answer.
6. They paste the answer into the **Restore** box and press **Restore**: placeholders become the original values again.
7. Success = the cloud AI never saw a personal detail, and the user got a usable answer with the real names.

## Screens and Layout
One page, three stacked panels: **1 · Document** (input + samples + Redact), **2 · Redacted** (highlighted view, redacted text, mapping, "rules-only would have leaked" counter), **3 · Restore** (answer in, restored text out). Header with product name and Apertus status.

## Look and Feel
(delegated) Swiss-sober: white background, near-black text, one red accent (#D52B1E) used sparingly; system sans-serif UI, monospace for redacted text and placeholders. Highlight colours per type are muted pastels with a legend. No gradients, no emoji, no "AI magic" language. Copy in English with Italian/German/French sample content.

## Features and Behavior

### Redaction
- As a legal assistant, I want every direct identifier found so that nothing obvious leaks.
  - [ ] AHV/AVS numbers (756.xxxx.xxxx.xx), IBANs, Swiss UID (CHE-…), Italian codice fiscale and partita IVA, e-mails, phone numbers, payment cards are detected and only accepted when their checksum/format is valid.
  - [ ] Person names, organisations and street addresses are detected by Apertus.
- As a legal assistant, I want indirect identifiers flagged so that a person can't be recognised from context.
  - [ ] Spans like "unico medico di base a Bosco Gurin" or a rare diagnosis tied to a person are highlighted as `QUASI` with a reason.
- Each detection shows its source (rule or Apertus) and a reason on hover.

### Placeholders and Mapping
- [ ] The same original value always gets the same placeholder within a document (`Paolo Bernasconi` twice → `[PERSON_1]` twice).
- [ ] The mapping table lists every placeholder and its original; it stays only in the browser session and the local process (nothing written to disk by default).

### Restore
- [ ] Pasting text containing placeholders and pressing Restore replaces every known placeholder with its original; unknown placeholders are left untouched and listed.

### Rules-only Comparison
- [ ] After redaction, a counter shows how many detected items the deterministic rules alone would have missed, making Apertus's contribution visible.

### Evaluation (judge-facing)
- [ ] A single command runs the multilingual test set and prints leak rate, precision and recall for rules-only vs. rules + Apertus, and writes a results file.

## States and Boundaries
- **Apertus unreachable** — status pill turns red; Redact still runs with rules only and a banner says contextual detection is off.
- **Empty input** — Redact is disabled.
- **Very long input** — documents are processed in chunks; a progress note appears for long texts.
- **Nothing found** — "No personal data detected" message, redacted text equals input.
- **Session** — the mapping lives only until the page is reloaded (privacy by default).

## Product Decisions
- (delegated) Text-only input for the POC — PDFs would dominate the build.
- (delegated) User copies text to/from the cloud AI by hand — keeps Riserbo air-gapped and auditable.
- (delegated) Over-redaction is preferred to leaks: when in doubt, flag it.
- (delegated) Indirect identifiers get their own `QUASI` type so the user can decide.

## What We're Building
Redaction (rules + Apertus), placeholders and mapping, restore, rules-only comparison counter, sample documents in IT/DE/FR, evaluation command, Docker `make run`.

## Deferred From the POC
- PDF/DOCX import and export — needs layout handling.
- Saving mappings to disk / encrypted vault — needs key management.
- Editing detections by hand (add/remove a span) — useful but not needed to prove the kernel.

## Possible Later Enhancements
Romansh and dialect test sets; batch folder mode; distilling Apertus judgements into a small fast tagger.

## Non-Goals
- Not a legal guarantee of anonymisation — it's an assistant; the user reviews.
- No calls to any cloud service from Riserbo.
- No user accounts.

## Open Questions
- None blocking `4-spec`. How well an 8B model at 4-bit finds indirect identifiers is an empirical question answered by the evaluation.
