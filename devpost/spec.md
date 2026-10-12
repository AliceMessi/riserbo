---
doc: spec
status: approved
---
<!-- Approval note: technical decisions delegated to the agent by the learner on 2026-10-12
     ("fai tutto tu", "decidi tu"). Recommendations below were accepted by delegation; each
     is marked (delegated) where it is a consequential choice. -->

# Riserbo — Technical Spec

## How This Works, In Plain Language
Riserbo is two programs in two Docker containers on your own machine:

1. **The model server** runs Apertus 1.5 8B (a 4-bit compressed copy, ~5 GB) with llama.cpp. It speaks the same API as OpenAI, but only on a private Docker network with no internet access.
2. **The Riserbo app** is a small Python web server with one web page. When you press Redact it:
   - runs **rules** — exact patterns with checksums for Swiss and Italian identifiers (AHV, IBAN, UID, codice fiscale, partita IVA, cards, e-mails, phones);
   - asks **Apertus** to list names, organisations, addresses and *indirect* identifiers, returned as strict JSON with a reason for each;
   - merges both lists, gives each distinct value a placeholder like `[PERSON_1]`, and sends back the highlighted document, the redacted text and the mapping.
   Restore simply swaps placeholders back using that mapping.

Why this shape: rules are perfect where a checksum exists and cost nothing; Apertus is only asked to do what rules can't — understand context. Keeping the model in its own offline container makes the air-gapped claim checkable.

## The Core Journey Through the System
1. User opens `http://localhost:8080` → app serves `static/index.html`; the page calls `GET /api/health` → app pings the model server → status pill.
2. User clicks a sample → `GET /api/samples` returns IT/DE/FR texts from `data/samples/`.
3. User presses Redact → `POST /api/redact {text}` → `detectors.find_all(text)` (rules) + `llm.find_entities(text)` (Apertus, chunked) → `pipeline.merge()` resolves overlaps (rule wins on exact identifiers, longest span otherwise) → `pipeline.redact()` assigns placeholders → JSON `{spans, redacted, mapping, rules_only_missed}`.
4. Page renders highlights, redacted text, mapping table, counter. Mapping stays in page memory.
5. User pastes AI answer → `POST /api/restore {text, mapping}` → `restore.restore()` → restored text + list of unknown placeholders.
PRD ref: `prd.md > The Core Journey`.

## Stack
- **Python 3.11**, **FastAPI** + **uvicorn** (https://fastapi.tiangolo.com) — small, typed HTTP API; (delegated) chosen over Node because the evaluation and data tooling are Python-native.
- **httpx** for calling the model server (https://www.python-httpx.org).
- **llama.cpp server** (https://github.com/ggml-org/llama.cpp/tree/master/tools/server) — OpenAI-compatible, supports JSON-schema constrained output, runs on CPU in Docker so judges need no GPU. Verify early that the pinned image supports the `apertus` architecture.
- **Model:** `Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (text-only Q4_K_M conversion of `swiss-ai/Apertus-v1.5-8B` via `andreasmartin/apertus-v1.5-8b-text`, Apache-2.0 + Apertus AUP). Any OpenAI-compatible endpoint can be used instead via `LLM_BASE_URL` / `LLM_NAME` / `LLM_API_KEY`.
- **pytest** for tests. Front end: one static HTML file, vanilla JS, no build step.
- Optional baseline: **rizzo-pii-0.3B** (MIT, https://huggingface.co/rizzoaiacademy/rizzo-pii-0.3B) via `transformers`, used only by the evaluation script when installed.

## Where It Runs and How Someone Tries It
- Requirements: Docker + Docker Compose, ~8 GB RAM free, ~6 GB disk. No GPU needed (a GPU makes it faster when running the model outside Docker, e.g. LM Studio).
- `make run` (from `track_2b/`): downloads the GGUF once into `track_2b/models/` if missing (the only network step), then `docker compose up --build`. Open `http://localhost:8080`.
- Bring-your-own endpoint: `LLM_BASE_URL=http://host:1234/v1 make run-app` runs only the app container.
- Evaluation: `make eval` → prints the results table and writes `data/eval/results.json`.
- Demo recording: local browser at `http://localhost:8080`. Deployment: none (on-premise by design).

## Look and Feel
White background, text #111, accent Swiss red #D52B1E for primary button and status; system UI font, `ui-monospace` for redacted text; muted pastel highlight per type with a legend (PERSON, ORG, ADDRESS, QUASI, ID, CONTACT, FINANCIAL). Generous spacing, no gradients or emoji. Copy is short and factual.

## Components

### Rule Detectors (`detectors.py`)
Regex candidates + validation: AHV/AVS (EAN-13 check digit), IBAN (ISO 13616 mod-97, CH/LI/IT/DE/FR/AT lengths), Swiss UID `CHE-123.456.789` (mod-11), codice fiscale (check character), partita IVA (Luhn-style check), payment cards (Luhn), e-mail, phone (+41 / +39 / national formats), IPv4. Returns spans `{start, end, text, type, source:"rule", reason}`.
PRD ref: `prd.md > Redaction`.

### Apertus Client (`llm.py`)
Chunks text (~1,200 characters on sentence boundaries), calls `/v1/chat/completions` with a system prompt + few-shot examples and `response_format: json_schema` (types PERSON, ORG, ADDRESS, LOCATION, QUASI, HEALTH, OTHER + reason). Locates each returned span verbatim in the chunk (all occurrences); discards spans not found in the text (hallucination guard). Timeouts → returns `[]` and flags `llm_ok=false`.
PRD ref: `prd.md > Redaction`, `prd.md > States and Boundaries`.

### Pipeline (`pipeline.py`)
`merge(rule_spans, llm_spans)`: drops overlaps (rule spans win; otherwise the longer span wins), maps types to placeholder families (`PERSON`, `ORG`, `ADDR`, `QUASI`, `AHV`, `IBAN`, `UID`, `CF`, `PIVA`, `CARD`, `EMAIL`, `PHONE`, `IP`, `HEALTH`, …). `redact(text, spans)`: consistent numbering per distinct normalised value. Computes `rules_only_missed`.
PRD ref: `prd.md > Placeholders and Mapping`, `prd.md > Rules-only Comparison`.

### Restore (`restore.py`)
Replaces `[FAMILY_N]` tokens found in the mapping; reports unknown tokens.
PRD ref: `prd.md > Restore`.

### Web App (`server.py` + `static/index.html`)
Endpoints: `GET /` page, `GET /api/health`, `GET /api/samples`, `POST /api/redact`, `POST /api/restore`. No persistence.
PRD ref: `prd.md > Screens and Layout`.

### Evaluation (`eval/generate.py`, `eval/run.py`)
`generate.py` builds a synthetic multilingual test set with gold spans from templates and fake-but-valid identifiers (seeded, reproducible), including indirect identifiers. `run.py` scores rules-only, rules + Apertus and, if available, rizzo-pii: leak rate (gold characters left visible), span precision/recall/F1 (overlap match), per-type recall, latency.
PRD ref: `prd.md > Evaluation (judge-facing)`.

## Data Model
- Span: `{start:int, end:int, text:str, type:str, source:"rule"|"apertus", reason:str}`.
- Mapping: `{ "[PERSON_1]": "Paolo Bernasconi", … }` — returned to the browser, kept in JS memory, never written to disk.
- Eval record (JSONL): `{id, lang, text, spans:[{start,end,type}]}`.

## File Structure
```
repo/
├── README.md               # project overview (judges start here)
├── LICENSE                 # Apache-2.0 (HackApertus template)
├── devpost/                # scope.md, prd.md, spec.md, checklist.md (Devpost Learn)
├── .agents/                # Devpost Learn skill pack
└── track_2b/               # HackApertus project root — do not rename
    ├── README.md           # track challenge description (template)
    ├── technical_report.md # report (+ PDF)
    ├── Makefile            # run, run-app, eval, test, model
    ├── docker-compose.yml  # llm (offline network) + app
    ├── Dockerfile          # app image
    ├── requirements.txt
    ├── .env.example        # LLM_NAME, LLM_BASE_URL, LLM_API_KEY
    ├── models/             # GGUF downloaded here (git-ignored)
    ├── data/
    │   ├── samples/        # demo documents it/de/fr (synthetic)
    │   └── eval/           # riserbo_eval_v1.jsonl + results.json
    ├── docs/               # architecture diagram, screenshots
    ├── src/riserbo/
    │   ├── detectors.py
    │   ├── llm.py
    │   ├── pipeline.py
    │   ├── restore.py
    │   ├── server.py
    │   ├── static/index.html
    │   └── eval/{generate.py, run.py}
    └── tests/
```

## External Services and Dependencies
- **Hugging Face download (build time only)**: `https://huggingface.co/Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF/resolve/main/apertus-v1.5-8b-text-q4_k_m.gguf` (5.06 GB, free, no key).
- **llama.cpp server (runtime, local)**: `POST /v1/chat/completions` with `response_format.json_schema`; `GET /health`. No keys, no cost.
- **Docker images (build time)**: `python:3.11-slim`, llama.cpp server image.
- Runtime: **no external network calls**.

## Important Failure Modes
- **Model server down or slow** → rules-only redaction with a visible banner.
- **Model returns spans not in the text** → discarded by verbatim-match guard.
- **CPU inference too slow for long documents** → chunking + per-chunk timeout; README notes GPU/LM Studio option.

## What Was Simplified and Why
- **Prompted Apertus + validators** instead of fine-tuning — measurable in four days; fine-tuning would need GPUs we don't have.
- **Synthetic evaluation data** instead of real client documents — real documents can't be shared; synthetic data with valid checksums is publishable (CDLA-Permissive-2.0).
- **Text-only** instead of PDF — keeps the build on the kernel.

## Decisions and Open Issues
- (delegated) Python/FastAPI app + llama.cpp container; tradeoff: two containers instead of one, in exchange for a verifiable offline model.
- (delegated) Rules win over Apertus on exact identifiers; Apertus owns context.
- Learner uncertainty recorded: *can a 4-bit 8B model reliably find indirect identifiers?* First probe (2026-10-12): JSON output works in ~4 s, but it returned only the name and missed the e-mail, diagnosis and quasi-identifiers. Investigation during build: iterate prompt (few-shot, explicit categories) and measure recall on the QUASI subset of the test set; report the honest number either way.
- Open: confirm the llama.cpp image tag supports `apertus` (check first in build).
