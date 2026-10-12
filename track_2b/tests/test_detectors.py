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
    assert kinds == ["AHV", "IBAN", "UID", "PHONE", "EMAIL"]


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
