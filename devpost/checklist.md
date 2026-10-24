---
doc: checklist
status: approved
---
<!-- Approval note: build order approved by delegation ("fai tutto tu", 2026-10-12). -->

# Build Checklist

Build mode: fast (delegated — learner asked the agent to run the build end to end)

## Slices

- [x] **1. Paste a document and get exact identifiers redacted with placeholders**
  Becomes usable: `http://localhost:8080` shows the Document panel; Redact highlights AHV, IBAN, UID, codice fiscale, partita IVA, cards, e-mails and phones (checksum-validated) and shows redacted text + mapping.
  Why now: Bootstraps the app end to end (scaffold, API, page) on the deterministic half of the kernel, so the Apertus half lands on a working path.
  PRD ref: `prd.md > The Core Journey` (steps 1-4), `prd.md > Redaction`, `prd.md > Placeholders and Mapping`
  Spec ref: `spec.md > Rule Detectors (detectors.py)`, `spec.md > Pipeline (pipeline.py)`, `spec.md > Web App (server.py + static/index.html)`, `spec.md > File Structure`
  Build: Scaffold `track_2b/` per the file structure; implement validators and regex detectors, merge + placeholder pipeline, FastAPI endpoints and the single page.
  Verify (mechanical): `pytest` green for detector checksum cases (valid accepted, invalid rejected) and placeholder consistency; `POST /api/redact` on a sample returns the expected placeholders.
  Learner check: Paste a text with an AHV number and an IBAN, press Redact, and see both highlighted and replaced.
  Commit: `Add rule-based redaction with placeholders and web page`

- [x] **2. Apertus finds names, organisations and indirect identifiers**
  Becomes usable: Redact also highlights people, organisations, addresses and QUASI identifiers with reasons; status pill shows Apertus state; rules-only fallback banner when the model is down.
  Why now: This is the unique kernel — it must be proven before polish.
  PRD ref: `prd.md > Redaction`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Apertus Client (llm.py)`, `spec.md > Pipeline (pipeline.py)`, `spec.md > Important Failure Modes`
  Build: JSON-schema prompted client with few-shot examples, chunking, verbatim span location, hallucination guard, merge with rule spans, `/api/health`.
  Verify (mechanical): Unit tests with a fake LLM (merge, guard, chunk offsets); live call against local Apertus returns the person and at least one QUASI span on the Ticino sample.
  Learner check: Click the Ticino sample and see "unico medico di base a Bosco Gurin" flagged as QUASI.
  Commit: `Add Apertus contextual detection with JSON-schema output`

- [x] **3. Restore answers and see what rules alone would leak**
  Becomes usable: Restore panel turns placeholders back into originals; counter shows items rules alone would have missed; IT/DE/FR sample documents.
  Why now: Closes the core loop end to end.
  PRD ref: `prd.md > Restore`, `prd.md > Rules-only Comparison`, `prd.md > The Core Journey` (steps 5-7)
  Spec ref: `spec.md > Restore (restore.py)`, `spec.md > Web App (server.py + static/index.html)`
  Build: restore module + endpoint, counter, samples endpoint and three synthetic samples.
  Verify (mechanical): `pytest` restore round-trip (redact → restore = original) and unknown-placeholder report; manual API round-trip.
  Learner check: Redact a sample, edit the redacted text like an AI answer, paste it in Restore and see real names return.
  Commit: `Add restore and rules-only comparison`

- [x] **4. Measure it: multilingual evaluation**
  Becomes usable: `make eval` prints leak rate / precision / recall for rules-only vs rules + Apertus (and rizzo-pii if installed) and writes `data/eval/results.json`.
  Why now: Answers the open question in `spec.md > Decisions and Open Issues` and gives judges numbers.
  PRD ref: `prd.md > Evaluation (judge-facing)`
  Spec ref: `spec.md > Evaluation (eval/generate.py, eval/run.py)`, `spec.md > Data Model`
  Build: seeded synthetic generator (IT/DE/FR, valid identifiers, QUASI cases), scorer, results file; iterate the prompt on a dev split, report on a held-out split.
  Verify (mechanical): generator is deterministic (same seed → same file hash); `make eval` completes and results.json contains all setups.
  Learner check: Run `make eval` and read the table.
  Commit: `Add synthetic multilingual evaluation and results`

- [x] **5. One command, air-gapped: `make run` in Docker**
  Becomes usable: From a clean checkout, `make run` downloads the model once and starts llama.cpp (offline network) + app.
  Why now: Required by Hack Apertus; proves the on-premise / air-gapped claim.
  PRD ref: `prd.md > The Core Journey` (step 1)
  Spec ref: `spec.md > Where It Runs and How Someone Tries It`, `spec.md > External Services and Dependencies`
  Build: Dockerfile, docker-compose (internal network for llm), Makefile targets, `.env.example`.
  Verify (mechanical): `make run` from a fresh clone; `/api/health` reports the model ok; `docker network inspect` shows the llm network is internal.
  Learner check: Run `make run`, open the page and redact a sample.
  Commit: `Add Docker make run with offline model server`

- [x] **6. Explain it: README, technical report, diagram**
  Becomes usable: Root README, `track_2b/technical_report.md` + PDF (≤6 pages), architecture diagram, screenshots.
  Why now: Submission requirements for both hackathons.
  PRD ref: `prd.md > What We're Building`
  Spec ref: `spec.md > How This Works, In Plain Language`
  Build: Write docs from real results; credit rizzo-pii and model sources; licences.
  Verify (mechanical): PDF renders and is ≤6 pages; every number in the report matches results.json.
  Learner check: Read the README top section and say whether it explains the project in 30 seconds.
  Commit: `Add technical report, README and diagrams`

## Hands-on Checkpoints

- [x] Early feedback after slice 2 (learner opens the page and redacts the Ticino sample). Done later than planned: the learner reviewed the running app and the demo video on 2026-10-13.
- [x] Final review after slice 6 (2026-10-13): a clean-clone Docker run and a re-run of the evaluation; fixes recorded under Revisions.

## Final Review

- [x] Learner confirms the PoC is ready (2026-10-13, uploaded the demo video and approved submission).

## Code Tour and App Map

- [x] Learning wrap-up + `devpost/app-map.html`. Activity: evidence-based recap of the spec's open question (instability of single-prompt JSON → two passes + `NONE` sentinel → confirmed by repeated runs and the 60-document evaluation), not a hands-on tour (the learner delegated the build). Map written at `devpost/app-map.html` with a reference route; reflection question not yet offered.

## Revisions
- Slice 2: a single extraction prompt was unstable on Apertus 1.5 8B Q4 (same chunk sometimes returned an empty list; the model "wants" to reason before answering). Changed to two focused passes per chunk (identity: PERSON/ORG/ADDRESS/ID; context: HEALTH/QUASI), smaller chunks (~500 chars), and a schema with `minItems: 1` plus a `NONE` sentinel so the model cannot close the list prematurely. Result: identical output on repeated runs. Updates `spec.md > Apertus Client (llm.py)`.
- Slice 2: added deterministic ADDRESS (street + number + postcode) and title-plus-surname PERSON rules after live runs showed Apertus skipping greetings and some addresses; surname propagation hides later mentions ("dott. Bernasconi"). Merge now ranks checksum rules first, then longest span.
- Final review (2026-10-13): Apertus' choice of names shifted between inference backends (LM Studio vs. llama.cpp in Docker), so the wife or the signatory in the Ticino sample was sometimes missed. Added deterministic rules for signatories under a closing formula, relatives named after the relation word, and double-barrelled surnames. Re-ran the evaluation: leak rate 13.2% → 12.6%, person recall 90.0% → 93.3%. Demo samples now use fictional organisations only.
- 2026-10-24: added a static browser demo for reviewers who cannot run the local model (`track_2b/site/`, published on GitHub Pages). It replays the real pipeline output on the three sample letters, computed with Apertus 1.5 8B by `track_2b/tools/precompute_demo.py` and labelled "precomputed" on the page; restoring placeholders runs in the browser with the same rule as `restore.py`. No change to the app, the pipeline or the evaluation. Also added a GitHub Actions test run (`pytest`, model calls mocked).
