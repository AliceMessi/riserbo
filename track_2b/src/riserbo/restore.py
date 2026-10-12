"""Put original values back into text that contains placeholders."""

from __future__ import annotations

import re

PLACEHOLDER_RE = re.compile(r"\[([A-Z]+)_(\d+)\]")


def restore(text: str, mapping: dict[str, str]) -> tuple[str, list[str]]:
    unknown: list[str] = []

    def swap(m: re.Match) -> str:
        token = m.group(0)
        if token in mapping:
            return mapping[token]
        if token not in unknown:
            unknown.append(token)
        return token

    return PLACEHOLDER_RE.sub(swap, text), unknown
