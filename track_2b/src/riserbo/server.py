"""Riserbo web app: one page, a small JSON API, no persistence."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import detectors, pipeline

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Riserbo", docs_url=None, redoc_url=None)


class RedactIn(BaseModel):
    text: str = Field(max_length=50_000)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.post("/api/redact")
def redact(body: RedactIn) -> dict:
    rule_spans = detectors.find_all(body.text)
    spans = pipeline.merge(rule_spans, [])
    redacted, mapping, annotated = pipeline.redact(body.text, spans)
    return {
        "spans": annotated,
        "redacted": redacted,
        "mapping": mapping,
        "rules_only_missed": pipeline.rules_only_missed(rule_spans, spans),
        "llm_ok": False,
    }
