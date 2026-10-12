"""Deterministic detectors for Swiss and Italian identifiers.

Every pattern that has a checksum is only accepted when the checksum is valid,
so random digit runs (invoice numbers, amounts) are not redacted by mistake.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict


@dataclass
class Span:
    start: int
    end: int
    text: str
    type: str
    source: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# --- checksums ---------------------------------------------------------------

def ahv_valid(digits: str) -> bool:
    """Swiss AHV/AVS number: 13 digits, prefix 756, EAN-13 check digit."""
    if len(digits) != 13 or not digits.startswith("756") or not digits.isdigit():
        return False
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


IBAN_LENGTHS = {
    "CH": 21, "LI": 21, "IT": 27, "SM": 27, "DE": 22, "FR": 27, "AT": 20,
    "ES": 24, "NL": 18, "BE": 16, "LU": 20, "GB": 22, "PT": 25, "MC": 27,
}


def iban_valid(raw: str) -> bool:
    iban = re.sub(r"[\s\-]", "", raw).upper()
    country = iban[:2]
    if IBAN_LENGTHS.get(country) != len(iban) or not iban[2:4].isdigit():
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97 == 1


def uid_valid(digits: str) -> bool:
    """Swiss enterprise UID (CHE-123.456.789): mod-11 with weights 5,4,3,2,7,6,5,4."""
    if len(digits) != 9 or not digits.isdigit():
        return False
    weights = (5, 4, 3, 2, 7, 6, 5, 4)
    check = 11 - sum(int(d) * w for d, w in zip(digits[:8], weights)) % 11
    if check == 11:
        check = 0
    return check != 10 and check == int(digits[8])


_CF_ODD = dict(zip(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    [1, 0, 5, 7, 9, 13, 15, 17, 19, 21,
     1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23],
))


def _cf_even(c: str) -> int:
    return int(c) if c.isdigit() else ord(c) - ord("A")


def cf_valid(code: str) -> bool:
    """Italian codice fiscale, including omocodia variants."""
    code = code.upper()
    if not re.fullmatch(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]", code):
        return False
    total = sum(_CF_ODD[c] if i % 2 == 0 else _cf_even(c) for i, c in enumerate(code[:15]))
    return chr(ord("A") + total % 26) == code[15]


def luhn_valid(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def piva_valid(digits: str) -> bool:
    return len(digits) == 11 and luhn_valid(digits)


# --- patterns ----------------------------------------------------------------

_SEP = r"[\s.\-/]?"

AHV_RE = re.compile(r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ \-]?[A-Z0-9]{4}){2,7}(?:[ \-]?[A-Z0-9]{1,3})?\b")
UID_RE = re.compile(r"\bCHE[\-\s]?\d{3}[.\s]?\d{3}[.\s]?\d{3}\b(?:\s?(?:MWST|TVA|IVA|HR))?")
CF_RE = re.compile(r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b", re.I)
PIVA_RE = re.compile(r"\b(?:IT\s?)?(\d{11})\b")
PIVA_CONTEXT = re.compile(r"(p\.?\s?iva|partita\s+iva|vat|ust|tva|c\.f\./p\.iva|codice\s+iva)\W{0,15}$", re.I)
CARD_RE = re.compile(r"\b[3-6]\d{3}(?:[ \-]?\d{4}){2}(?:[ \-]?\d{1,4}){1,2}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<![\w+])(?:"
    r"(?:\+|00)(?:41|39|49|33|43|423)[\s.\-/]?(?:\(0\)\s?)?\d{1,3}(?:[\s.\-/]?\d{2,4}){2,4}"
    r"|0\d{2}[\s.\-/]?\d{3}[\s.\-/]?\d{2}[\s.\-/]?\d{2}"
    r"|3\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3,4}"
    r")(?![\w])"
)
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
DOB_RE = re.compile(
    r"(?:nat[oa]\s+(?:a\s+[\w' ]{2,30}\s+)?il|data\s+di\s+nascita[:\s]*|geboren\s+(?:in\s+[\w ]{2,30}\s+)?am|geb\.\s*am|"
    r"geburtsdatum[:\s]*|n[ée]e?\s+(?:à\s+[\w' ]{2,30}\s+)?le|date\s+de\s+naissance[:\s]*|born\s+(?:on\s+)?|date\s+of\s+birth[:\s]*)\s*"
    r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}|\d{1,2}\.?\s+[A-Za-zÀ-ÿ]{3,10}\s+\d{4})",
    re.I,
)


_STREET_IT = r"(?:Via|Viale|Piazza|Piazzetta|Vicolo|Strada|Contrada|Corso|Largo|Salita|Riva|Lungolago)"
_STREET_FR = r"(?:Rue|Avenue|Av\.|Chemin|Ch\.|Route|Rte|Place|Boulevard|Bd|Quai|Impasse|Allée|Sentier)"
_NAME = r"[A-ZÀ-Ý][\w'’À-ÿ\-]*(?:\s+(?:d[ei]l?|della|dei|du|de|des|la|le|von|am|im)?\s*[A-ZÀ-Ý][\w'’À-ÿ\-]*){0,3}"
_POSTCODE_TOWN = r"(?:,?\s+(?:CH-|I-)?\d{4,5}\s+[A-ZÀ-Ý][\w'’À-ÿ\-]*(?:\s+[A-ZÀ-Ý][\w'’À-ÿ\-]*){0,2})?"
ADDRESS_RE = re.compile(
    rf"\b(?:{_STREET_IT}|{_STREET_FR})\s+(?:d[eu]l?l?[a']?\s*|de\s+la\s+|des\s+|du\s+)?{_NAME}\s+\d{{1,4}}[a-zA-Z]?{_POSTCODE_TOWN}"
    rf"|\b[A-ZÄÖÜ][a-zäöüß]+(?:strasse|gasse|weg|platz|allee|ring|rain|matte)\s+\d{{1,4}}[a-zA-Z]?{_POSTCODE_TOWN}"
)
_HONORIFIC = (r"(?:Sig\.(?:ra|na)?|Signor[a]?|sig\.(?:ra)?|dott\.(?:ssa)?|Dott\.(?:ssa)?|avv\.|Avv\.|avvocat[oa]|ing\.|Ing\.|"
              r"Herr|Herrn|Frau|Monsieur|Madame|Mme|M\.|Me|Maître|Mr\.?|Mrs\.?|Ms\.?)")
HONORIFIC_RE = re.compile(
    rf"\b{_HONORIFIC}\s+(?:(?:Dr|Prof|med|iur|lic)\.\s*)*([A-ZÀ-Ý][a-zà-ÿ'’]+(?:[\-\s][A-ZÀ-Ý][a-zà-ÿ'’]+){{0,2}})"
)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def find_all(text: str) -> list[Span]:
    spans: list[Span] = []

    def add(m_start: int, m_end: int, kind: str, reason: str) -> None:
        spans.append(Span(m_start, m_end, text[m_start:m_end], kind, "rule", reason))

    for m in AHV_RE.finditer(text):
        if ahv_valid(_digits(m.group())):
            add(m.start(), m.end(), "AHV", "Swiss AHV/AVS social security number (EAN-13 check digit valid)")
    for m in IBAN_RE.finditer(text):
        if iban_valid(m.group()):
            add(m.start(), m.end(), "IBAN", "IBAN with valid mod-97 checksum")
    for m in UID_RE.finditer(text):
        if uid_valid(_digits(m.group())):
            add(m.start(), m.end(), "UID", "Swiss enterprise identification number (mod-11 valid)")
    for m in CF_RE.finditer(text):
        if cf_valid(m.group()):
            add(m.start(), m.end(), "CF", "Italian codice fiscale (check character valid)")
    for m in PIVA_RE.finditer(text):
        digits = m.group(1)
        before = text[max(0, m.start() - 30):m.start()]
        prefixed = m.group().upper().startswith("IT")
        if piva_valid(digits) and (prefixed or PIVA_CONTEXT.search(before)):
            add(m.start(), m.end(), "PIVA", "Italian partita IVA (check digit valid, VAT context)")
    for m in CARD_RE.finditer(text):
        d = _digits(m.group())
        if 13 <= len(d) <= 19 and luhn_valid(d):
            add(m.start(), m.end(), "CARD", "Payment card number (Luhn valid)")
    for m in EMAIL_RE.finditer(text):
        add(m.start(), m.end(), "EMAIL", "E-mail address")
    for m in PHONE_RE.finditer(text):
        if len(_digits(m.group())) >= 9:
            add(m.start(), m.end(), "PHONE", "Telephone number")
    for m in IPV4_RE.finditer(text):
        add(m.start(), m.end(), "IP", "IPv4 address")
    for m in DOB_RE.finditer(text):
        add(m.start(1), m.end(1), "DOB", "Date of birth")
    for m in ADDRESS_RE.finditer(text):
        add(m.start(), m.end(), "ADDRESS", "Postal address (street and number)")
    for m in HONORIFIC_RE.finditer(text):
        add(m.start(1), m.end(1), "PERSON", "Name after a title or form of address")

    return resolve_overlaps(spans)


# Identifier types with a checksum are more trustworthy than generic ones.
_PRIORITY = {"AHV": 0, "IBAN": 0, "UID": 0, "CF": 0, "CARD": 1, "PIVA": 1, "EMAIL": 2, "DOB": 2, "IP": 3, "PHONE": 4,
             "ADDRESS": 5, "PERSON": 6}


def resolve_overlaps(spans: list[Span]) -> list[Span]:
    ordered = sorted(spans, key=lambda s: (_PRIORITY.get(s.type, 5), -(s.end - s.start), s.start))
    kept: list[Span] = []
    for s in ordered:
        if all(s.end <= k.start or s.start >= k.end for k in kept):
            kept.append(s)
    return sorted(kept, key=lambda s: s.start)
