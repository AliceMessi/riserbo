"""Riserbo web app: one page, a small JSON API, no persistence."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import detectors, llm, pipeline

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Riserbo", docs_url=None, redoc_url=None)


class RedactIn(BaseModel):
    text: str = Field(max_length=50_000)
    use_llm: bool = True


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"llm_ok": llm.health(), "model": llm.MODEL}


@app.post("/api/redact")
def redact(body: RedactIn) -> dict:
    rule_spans = detectors.find_all(body.text)
    model_spans, llm_ok = llm.find_entities(body.text) if body.use_llm else ([], False)
    spans = pipeline.merge(rule_spans, model_spans)
    redacted, mapping, annotated = pipeline.redact(body.text, spans)
    return {
        "spans": annotated,
        "redacted": redacted,
        "mapping": mapping,
        "rules_only_missed": pipeline.rules_only_missed(rule_spans, spans),
        "llm_ok": llm_ok,
    }
