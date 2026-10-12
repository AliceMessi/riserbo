"""Merge detections and replace them with stable placeholders."""

from __future__ import annotations

import re
import unicodedata

from .detectors import Span

# Placeholder family for every detection type.
FAMILY = {
    "AHV": "AHV", "IBAN": "IBAN", "UID": "UID", "CF": "CF", "PIVA": "PIVA",
    "CARD": "CARD", "EMAIL": "EMAIL", "PHONE": "PHONE", "IP": "IP", "DOB": "DATE",
    "PERSON": "PERSON", "ORG": "ORG", "ADDRESS": "ADDRESS", "QUASI": "QUASI",
    "HEALTH": "HEALTH", "ID": "ID",
}

ID_TYPES = {"AHV", "IBAN", "UID", "CF", "PIVA", "CARD", "PHONE", "IP"}


def normalise(kind: str, value: str) -> str:
    v = unicodedata.normalize("NFKC", value).casefold()
    if kind in ID_TYPES:
        return re.sub(r"[\s.\-/]", "", v)
    return re.sub(r"\s+", " ", v).strip(" .,;:")


EXACT_TYPES = ID_TYPES | {"EMAIL", "DOB"}


def merge(rule_spans: list[Span], model_spans: list[Span]) -> list[Span]:
    """Checksum/format rules always win; otherwise the longer span wins."""
    def rank(s: Span) -> tuple:
        exact = s.source == "rule" and s.type in EXACT_TYPES
        return (0 if exact else 1, -(s.end - s.start), s.start)

    kept: list[Span] = []
    for s in sorted([*rule_spans, *model_spans], key=rank):
        if all(s.end <= k.start or s.start >= k.end for k in kept):
            kept.append(s)
    return sorted(kept, key=lambda s: s.start)


def _person_key(norm: str, known: dict[str, str]) -> str | None:
    """Reuse the placeholder of a known person when only part of the name appears."""
    tokens = set(norm.split())
    for key, placeholder in known.items():
        if placeholder.startswith("[PERSON_") and tokens and tokens <= set(key.split()):
            return key
    return None


def redact(text: str, spans: list[Span]) -> tuple[str, dict[str, str], list[dict]]:
    """Return redacted text, placeholder → original mapping, and spans annotated with placeholders."""
    counters: dict[str, int] = {}
    by_value: dict[tuple[str, str], str] = {}
    person_keys: dict[str, str] = {}
    mapping: dict[str, str] = {}
    annotated: list[dict] = []

    # Number placeholders in reading order, longest person names first so partial
    # mentions ("Bernasconi") can reuse the full name ("Paolo Bernasconi").
    persons = [s for s in spans if s.type == "PERSON"]
    canonical: dict[str, Span] = {}
    for s in sorted(persons, key=lambda s: -len(s.text)):
        norm = normalise("PERSON", s.text)
        if norm not in canonical and not _person_key(norm, {k: "[PERSON_" for k in canonical}):
            canonical[norm] = s
    # Numbers follow the order in which each person is first mentioned.
    first_seen: dict[str, int] = {}
    for s in sorted(persons, key=lambda s: s.start):
        norm = normalise("PERSON", s.text)
        key = norm if norm in canonical else _person_key(norm, {k: "[PERSON_" for k in canonical})
        first_seen.setdefault(key, s.start)
    for i, key in enumerate(sorted(canonical, key=lambda k: first_seen.get(k, 0)), start=1):
        person_keys[key] = f"[PERSON_{i}]"
        mapping[person_keys[key]] = canonical[key].text
    counters["PERSON"] = len(canonical)

    out: list[str] = []
    cursor = 0
    for s in sorted(spans, key=lambda s: s.start):
        family = FAMILY.get(s.type, "ID")
        norm = normalise(s.type, s.text)
        if s.type == "PERSON":
            key = norm if norm in person_keys else _person_key(norm, person_keys)
            placeholder = person_keys[key]
        else:
            placeholder = by_value.get((family, norm))
            if placeholder is None:
                counters[family] = counters.get(family, 0) + 1
                placeholder = f"[{family}_{counters[family]}]"
                by_value[(family, norm)] = placeholder
                mapping[placeholder] = s.text
        out.append(text[cursor:s.start])
        out.append(placeholder)
        cursor = s.end
        annotated.append({**s.to_dict(), "placeholder": placeholder})
    out.append(text[cursor:])
    return "".join(out), mapping, annotated


def rules_only_missed(rule_spans: list[Span], final_spans: list[Span]) -> int:
    """How many final detections no rule would have produced."""
    return sum(1 for s in final_spans if s.source != "rule"
               and all(s.end <= r.start or s.start >= r.end for r in rule_spans))
