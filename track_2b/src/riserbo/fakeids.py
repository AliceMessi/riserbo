"""Generators of fake but checksum-valid identifiers, for tests and synthetic data."""

from __future__ import annotations

import random

from .detectors import _CF_ODD, _cf_even


def ahv(rng: random.Random) -> str:
    body = "756" + "".join(str(rng.randint(0, 9)) for _ in range(9))
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
    d = body + str((10 - total % 10) % 10)
    return f"{d[:3]}.{d[3:7]}.{d[7:11]}.{d[11:]}"


def _iban(country: str, bban: str) -> str:
    numeric = "".join(str(int(c, 36)) for c in bban + country + "00")
    check = 98 - int(numeric) % 97
    raw = f"{country}{check:02d}{bban}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def iban_ch(rng: random.Random) -> str:
    return _iban("CH", "".join(str(rng.randint(0, 9)) for _ in range(17)))


def iban_it(rng: random.Random) -> str:
    cin = chr(ord("A") + rng.randint(0, 25))
    return _iban("IT", cin + "".join(str(rng.randint(0, 9)) for _ in range(22)))


def uid(rng: random.Random) -> str:
    weights = (5, 4, 3, 2, 7, 6, 5, 4)
    while True:
        body = [rng.randint(0, 9) for _ in range(8)]
        check = 11 - sum(d * w for d, w in zip(body, weights)) % 11
        check = 0 if check == 11 else check
        if check != 10:
            d = "".join(map(str, body)) + str(check)
            return f"CHE-{d[:3]}.{d[3:6]}.{d[6:]}"


def codice_fiscale(rng: random.Random) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    months = "ABCDEHLMPRST"
    body = (
        "".join(rng.choice(letters) for _ in range(6))
        + f"{rng.randint(40, 99):02d}"
        + rng.choice(months)
        + f"{rng.randint(1, 71):02d}"
        + rng.choice("ABCDEFGHILMZ")
        + f"{rng.randint(100, 999)}"
    )
    total = sum(_CF_ODD[c] if i % 2 == 0 else _cf_even(c) for i, c in enumerate(body))
    return body + chr(ord("A") + total % 26)


def _luhn_complete(prefix: str, length: int, rng: random.Random) -> str:
    body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(length - len(prefix) - 1))
    for c in "0123456789":
        from .detectors import luhn_valid
        if luhn_valid(body + c):
            return body + c
    raise AssertionError("unreachable")


def partita_iva(rng: random.Random) -> str:
    return _luhn_complete("0", 11, rng)


def card(rng: random.Random) -> str:
    d = _luhn_complete(rng.choice(["4", "51", "55"]), 16, rng)
    return " ".join(d[i:i + 4] for i in range(0, 16, 4))


def phone_ch(rng: random.Random) -> str:
    return f"+41 {rng.choice(['91', '44', '31', '79', '78'])} {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def phone_it(rng: random.Random) -> str:
    return f"+39 3{rng.randint(20, 99)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"
