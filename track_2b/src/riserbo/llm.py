"""Apertus client: contextual detection of names, organisations and indirect identifiers.

Talks to any OpenAI-compatible endpoint (llama.cpp server, LM Studio, vLLM) and
asks for JSON constrained by a schema. Two focused passes run on each chunk:
"identity" (who is mentioned) and "context" (health data and indirect
identifiers). Every returned span must appear verbatim in the document,
otherwise it is dropped.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from . import detectors
from .detectors import Span

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1").rstrip("/")
MODEL = os.environ.get("LLM_NAME", "apertus-v1.5-8b-text")
API_KEY = os.environ.get("LLM_API_KEY", "")
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "300"))
CHUNK_CHARS = int(os.environ.get("LLM_CHUNK_CHARS", "500"))

TYPES = ["PERSON", "ORG", "ADDRESS", "ID", "HEALTH", "QUASI"]

COMMON_RULES = """Rules:
- Copy each span exactly as it appears in the text, character for character. Do not translate, shorten or add titles.
- List each distinct span once. Read the whole text, including greetings and signatures at the end.
- Ignore e-mail addresses, phone numbers, IBANs, AHV numbers, tax codes, VAT numbers and dates: another system handles them.
- Give a short reason in English for each item.
- If there is nothing to report, return a single item with type NONE."""

IDENTITY_PROMPT = f"""You are the privacy officer of a Swiss law firm. Before a document is shared with an outside AI service, you list who is mentioned in it. Documents are in Italian, German, French or English.

Report:
- PERSON: names of private individuals — full names, surnames used alone, first names. Include signatories, lawyers, doctors, relatives.
- ORG: names of private companies, firms, banks, clinics, schools, associations or law offices that appear in the text. Not courts, parliaments or government offices.
- ADDRESS: postal addresses — street and house number, with postcode and town when they form one address. Never a town on its own.
- ID: other personal reference numbers — passport, identity card, driving licence, licence plate, customer, policy or insurance numbers.

{COMMON_RULES}"""

CONTEXT_PROMPT = f"""You are the privacy officer of a Swiss law firm. Names are handled by another system, so do not report them. Your job is to find the details that would STILL let a reader recognise a specific person, and their health data. Documents are in Italian, German, French or English.

Report:
- QUASI: a phrase that points to one specific person even without a name. Typical cases: a unique or rare role in a small place ("the only pharmacist in Vrin"), a public office of a small community ("la sindaca del comune", "der Gemeindepräsident von Lumnezia"), a rare combination of job, age and place, a unique event or record. Copy the whole identifying phrase.
- HEALTH: diagnoses, illnesses, pregnancy, disabilities, addictions, treatments or medication of a person.

Do not report ordinary jobs in big cities, generic family relations or roles without a place.

{COMMON_RULES}"""


def _schema(types: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "type": {"type": "string", "enum": types + ["NONE"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["text", "type", "reason"],
                },
            }
        },
        "required": ["entities"],
    }


@dataclass(frozen=True)
class Pass:
    name: str
    types: list[str]
    prompt: str
    examples: list[tuple[str, dict]]


# Few-shot examples use places and names that do not appear in the samples or the test set.
IDENTITY = Pass("identity", ["PERSON", "ORG", "ADDRESS", "ID"], IDENTITY_PROMPT, [
    (
        "La sig.ra Marta Gianini, contabile presso la Fiduciaria Ceresio SA, abita in Via Cantonale 14, "
        "6900 Massagno. Targa: TI 123456. Cordiali saluti, avv. Nicola Pozzi",
        {"entities": [
            {"text": "Marta Gianini", "type": "PERSON", "reason": "Full name of a private person"},
            {"text": "Fiduciaria Ceresio SA", "type": "ORG", "reason": "Employer named in the text"},
            {"text": "Via Cantonale 14, 6900 Massagno", "type": "ADDRESS", "reason": "Home address"},
            {"text": "TI 123456", "type": "ID", "reason": "Licence plate"},
            {"text": "Nicola Pozzi", "type": "PERSON", "reason": "Signatory"},
        ]},
    ),
    (
        "Das Bezirksgericht Zürich hat entschieden. Kläger ist Herr Brunner; seine Anwältin, "
        "Dr. Lea Frei von der Kanzlei Frei & Partner, verlangt Schadenersatz.",
        {"entities": [
            {"text": "Brunner", "type": "PERSON", "reason": "Surname of the claimant"},
            {"text": "Lea Frei", "type": "PERSON", "reason": "Name of the lawyer"},
            {"text": "Frei & Partner", "type": "ORG", "reason": "Law firm"},
        ]},
    ),
])

CONTEXT = Pass("context", ["HEALTH", "QUASI"], CONTEXT_PROMPT, [
    (
        "Il signor [PERSON_1], l'unico veterinario di Soglio, è in cura per un linfoma. Sua sorella lavora a Zurigo.",
        {"entities": [
            {"text": "l'unico veterinario di Soglio", "type": "QUASI", "reason": "Unique role in a tiny village identifies one person"},
            {"text": "in cura per un linfoma", "type": "HEALTH", "reason": "Medical condition"},
        ]},
    ),
    (
        "Frau [PERSON_1], Gemeindepräsidentin von Vrin und seit 2020 Diabetikerin, wohnt mit ihrem Mann in Chur.",
        {"entities": [
            {"text": "Gemeindepräsidentin von Vrin", "type": "QUASI", "reason": "Public office of a small municipality"},
            {"text": "Diabetikerin", "type": "HEALTH", "reason": "Chronic illness"},
        ]},
    ),
    (
        "M. [PERSON_1], le plus vieux vigneron encore actif du Lavaux, a perdu la vue l'an dernier.",
        {"entities": [
            {"text": "le plus vieux vigneron encore actif du Lavaux", "type": "QUASI", "reason": "Unique superlative in a region"},
            {"text": "a perdu la vue", "type": "HEALTH", "reason": "Disability"},
        ]},
    ),
])

PASSES = [IDENTITY, CONTEXT]


def chunks(text: str, size: int | None = None) -> list[tuple[int, str]]:
    """Split on paragraph/sentence boundaries; returns (offset, chunk) pairs."""
    size = size or CHUNK_CHARS
    out: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 3:
                end = cut + 1
        out.append((start, text[start:end]))
        start = end
    return out


def _messages(p: Pass, chunk: str) -> list[dict]:
    msgs = [{"role": "system", "content": p.prompt}]
    for example, answer in p.examples:
        msgs.append({"role": "user", "content": example})
        msgs.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    msgs.append({"role": "user", "content": chunk})
    return msgs


def _call(p: Pass, chunk: str, client: httpx.Client) -> list[dict]:
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 1000,
        "messages": _messages(p, chunk),
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": p.name, "strict": True, "schema": _schema(p.types)}},
    }
    r = client.post(f"{BASE_URL}/chat/completions", json=body, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return [e for e in json.loads(content).get("entities", []) if e.get("type") in p.types and _plausible(e)]


def _plausible(e: dict) -> bool:
    """Drop answers the prompt rules out: a town on its own is not an address."""
    if e["type"] == "ADDRESS":
        return any(ch.isdigit() for ch in e.get("text", ""))
    return True


def locate(text: str, needle: str) -> list[tuple[int, int]]:
    """All occurrences of needle in text, tolerant to whitespace and case, on word boundaries."""
    needle = needle.strip(" \t\n.,;:")
    if len(needle) < 2:
        return []
    pattern = r"\s+".join(re.escape(part) for part in needle.split())
    rx = re.compile(rf"(?<![\w-]){pattern}(?![\w-])", re.IGNORECASE)
    return [(m.start(), m.end()) for m in rx.finditer(text)]


surnames = detectors.surnames


def to_spans(text: str, entities: list[dict]) -> list[Span]:
    spans: list[Span] = []
    for e in entities:
        kind = e.get("type")
        if kind not in TYPES:
            continue
        reason = e.get("reason", "")[:200]
        for start, end in locate(text, e.get("text", "")):
            spans.append(Span(start, end, text[start:end], kind, "apertus", reason))
        if kind == "PERSON":
            for part in surnames(e.get("text", "")):
                for start, end in detectors.surname_mentions(text, part):
                    spans.append(Span(start, end, text[start:end], "PERSON", "apertus", f"Surname of {e['text']}"))
    return spans


def find_entities(text: str, client: httpx.Client | None = None, passes: list[Pass] | None = None) -> tuple[list[Span], bool]:
    """Returns (spans, ok). ok=False means the model could not be reached or answered badly."""
    own = client is None
    client = client or httpx.Client()
    entities: list[dict] = []
    ok = True
    try:
        for p in passes or PASSES:
            for _, chunk in chunks(text):
                try:
                    entities.extend(_call(p, chunk, client))
                except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
                    ok = False
    finally:
        if own:
            client.close()
    # Spans are located in the whole document, so a name found in one chunk is
    # also hidden wherever else it appears.
    return to_spans(text, entities), ok


def health(client: httpx.Client | None = None) -> bool:
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    try:
        with (client or httpx.Client()) as c:
            return c.get(f"{BASE_URL}/models", headers=headers, timeout=5).status_code == 200
    except httpx.HTTPError:
        return False
