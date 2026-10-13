---
doc: scope
status: approved
---
<!-- Approval note: the learner delegated scoping decisions to the agent ("fai tutto tu", "decidi tu")
     on 2026-10-12. Choices below that were made on the learner's behalf are marked (delegated). -->

# Riserbo

Reversible redaction of personal data in Swiss and Italian documents, powered by Apertus and running entirely on your own machine.

## The Unique Kernel
Small PII taggers and regex catch names, IBANs and tax codes, but miss the people you can recognise **without** a name: "the only GP in Bosco Gurin", "the bank branch manager in Locarno who was just diagnosed with MS". Riserbo pairs exact Swiss/Italian validators with **Apertus reasoning about indirect identifiers**, swaps every hit for a placeholder, and restores the originals locally after a cloud AI has answered. Nothing personal ever leaves the building, and Apertus itself runs air-gapped.

## Who It's For
(delegated) A legal or compliance assistant at a small Ticino law firm or fiduciary who wants to use cloud AI assistants on client files without breaching the Swiss data-protection act (revFADP) or professional secrecy. Today they either retype documents by hand with names blacked out, or they don't use AI at all.

## The Core Loop
1. Paste (or load) a document in Italian, German or French.
2. Riserbo highlights every personal detail, labelled by type, each with a one-line reason; indirect identifiers are flagged separately.
3. Copy the redacted text (placeholders like `[PERSON_1]`, `[AHV_1]`, `[QUASI_1]`) into any cloud AI.
4. Paste the AI's answer back: Riserbo restores the real values locally.
They come back every time a client document needs an AI's help.

## Inspiration & Identity
- rizzo-pii — https://rizzo-ai-academy.github.io/rizzo-pii/ (MIT): local, reversible, Italian-legal focus. Riserbo is a new codebase that extends the idea to Swiss multilingual documents and contextual identifiers, and can use the rizzo-pii model as an optional, credited component and baseline.
- Feel: a calm, trustworthy Swiss tool. Sober, legible, not "AI-sparkly".

## Why This Matters to the Learner
The learner wants a real sovereign-AI use case for Hack Apertus, built on top of an open Italian project they admire, and a project that makes a clear, demonstrable difference in under two minutes.

## What "Working" Looks Like
`make run` starts Riserbo and Apertus in Docker with no internet needed at runtime. A judge opens `http://localhost:8080`, clicks a sample Ticino document, presses **Redact**, and sees names, AHV number, IBAN, email **and** "unico medico di base a Bosco Gurin" highlighted and replaced. The "oh, that's cool" beat: an answer from a cloud AI with placeholders is pasted back and the real names reappear, while a side panel shows what regex alone would have leaked.

## The POC Boundary
- Text input (paste / sample documents), IT / DE / FR.
- Deterministic detectors for Swiss and Italian identifiers with checksum validation.
- Apertus contextual pass for names, organisations, places and indirect identifiers.
- Reversible placeholders + restore.
- A reproducible evaluation on a synthetic multilingual test set (leak rate, precision, recall) comparing rules-only vs. rules + Apertus.
- Docker `make run`, air-gapped at runtime.

## Later
PDF/DOCX input and redacted PDF export; Romansh and Swiss-German dialect test sets; fine-tuning a small tagger on Apertus-labelled data; batch processing of folders.

## Explicitly Cut
- **User accounts / multi-user server** — a single-user local tool is enough to prove the kernel.
- **Sending text to a cloud AI from inside Riserbo** — the user copies by hand; keeps the tool air-gapped and the demo honest.
- **Fine-tuning Apertus** — no compute budget in four days; prompting + validators is measurable today.
- **Image / scanned-document OCR** — different problem, would dominate the build.
