import random

import pytest

from riserbo import fakeids
from riserbo.detectors import ahv_valid, cf_valid, find_all, iban_valid, piva_valid, uid_valid
from riserbo.pipeline import redact

rng = random.Random(7)


def types(text):
    return [(s.type, s.text) for s in find_all(text)]


@pytest.mark.parametrize("_", range(20))
def test_generated_identifiers_are_valid(_):
    assert ahv_valid(fakeids.ahv(rng).replace(".", ""))
    assert iban_valid(fakeids.iban_ch(rng))
    assert iban_valid(fakeids.iban_it(rng))
    assert uid_valid(fakeids.uid(rng)[4:].replace(".", ""))
    assert cf_valid(fakeids.codice_fiscale(rng))
    assert piva_valid(fakeids.partita_iva(rng))


def test_known_public_examples():
    assert ahv_valid("7569217076985")          # example AHV from the federal documentation
    assert iban_valid("CH93 0076 2011 6238 5295 7")
    assert iban_valid("IT60X0542811101000000123456")
    assert uid_valid("116281710")              # CHE-116.281.710
    assert cf_valid("RSSMRA85T10A562S")


def test_bad_checksums_are_rejected():
    assert not ahv_valid("7569217076986")
    assert not iban_valid("CH93 0076 2011 6238 5295 8")
    assert not uid_valid("116281711")
    assert not cf_valid("RSSMRA85T10A562T")


def test_finds_swiss_identifiers_in_text():
    text = ("Herr Muster, AHV-Nr. 756.9217.0769.85, IBAN CH93 0076 2011 6238 5295 7, "
            "Firma CHE-116.281.710 MWST, Tel. +41 91 751 23 45, max@example.ch.")
    found = types(text)
    kinds = [k for k, _ in found]
    assert kinds == ["PERSON", "AHV", "IBAN", "UID", "PHONE", "EMAIL"]


def test_invoice_numbers_are_not_redacted():
    text = "Fattura n. 75692170769 del 12.03.2026, importo CHF 1'250.00, rif. 12345678901."
    assert types(text) == []


def test_partita_iva_needs_context():
    p = fakeids.partita_iva(rng)
    assert types(f"P.IVA {p}") == [("PIVA", p)]
    assert types(f"ordine {p}") == []


def test_date_of_birth_only_with_context():
    assert types("nato a Lugano il 03.04.1971") == [("DOB", "03.04.1971")]
    assert types("udienza del 03.04.2026") == []


def test_same_value_gets_same_placeholder():
    text = "Mail a@b.ch e poi di nuovo a@b.ch, AHV 756.9217.0769.85."
    redacted, mapping, _ = redact(text, find_all(text))
    assert redacted == "Mail [EMAIL_1] e poi di nuovo [EMAIL_1], AHV [AHV_1]."
    assert mapping == {"[EMAIL_1]": "a@b.ch", "[AHV_1]": "756.9217.0769.85"}


def test_addresses():
    assert types("abita in Via Cantonale 21, 6685 Bosco Gurin.") == [("ADDRESS", "Via Cantonale 21, 6685 Bosco Gurin")]
    assert types("Er wohnt an der Hauptstrasse 7, 7482 Bergün.") == [("ADDRESS", "Hauptstrasse 7, 7482 Bergün")]
    assert types("l'appartement de la Rue du Bourg 3, 1663 Gruyères") == [("ADDRESS", "Rue du Bourg 3, 1663 Gruyères")]
    assert types("ai sensi dell'art. 336c CO") == []


def test_names_after_titles():
    assert types("Gentile avvocata Rezzonico,") == [("PERSON", "Rezzonico")]
    assert types("Sehr geehrte Frau Dr. Keller,") == [("PERSON", "Keller")]
    assert types("Mme Sophie Rochat conteste") == [("PERSON", "Sophie Rochat")]


def test_redact_restore_round_trip():
    from riserbo.restore import restore
    text = "Herr Brunner, AHV 756.9217.0769.85, schreibt an a@b.ch. Gruss, Herr Brunner"
    redacted, mapping, _ = redact(text, find_all(text))
    assert "Brunner" not in redacted and "756" not in redacted
    back, unknown = restore(redacted, mapping)
    assert back == text and unknown == []
    answer, unknown = restore("Dear [PERSON_1], see [IBAN_9].", mapping)
    assert answer == "Dear Brunner, see [IBAN_9]." and unknown == ["[IBAN_9]"]


def test_api_end_to_end():
    from fastapi.testclient import TestClient
    from riserbo.server import app
    c = TestClient(app)
    samples = c.get("/api/samples").json()
    assert {s["id"] for s in samples} == {"it_ticino", "de_graubuenden", "fr_gruyere"}
    r = c.post("/api/redact", json={"text": samples[0]["text"], "use_llm": False}).json()
    back = c.post("/api/restore", json={"text": r["redacted"], "mapping": r["mapping"]}).json()
    assert back["text"] == samples[0]["text"] and back["unknown"] == []


def test_person_numbers_follow_reading_order():
    from riserbo.detectors import Span
    text = "Paolo Rossi incontra Elena Bianchi-Neri. Rossi saluta."
    spans = [Span(0, 11, "Paolo Rossi", "PERSON", "apertus", ""), Span(21, 39, "Elena Bianchi-Neri", "PERSON", "apertus", ""),
             Span(41, 46, "Rossi", "PERSON", "apertus", "")]
    redacted, mapping, _ = redact(text, spans)
    assert redacted == "[PERSON_1] incontra [PERSON_2]. [PERSON_1] saluta."
