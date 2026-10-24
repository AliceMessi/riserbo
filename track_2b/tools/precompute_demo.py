"""Precompute the static browser demo: run the real pipeline on the three sample letters.

    LLM_BASE_URL=http://localhost:1234/v1 python tools/precompute_demo.py ../site/demo.json

The output is what `/api/redact` returns for each sample (spans, redacted text,
mapping, rules-only misses), plus the model name and the date. The static demo
shows these results; restoring placeholders runs for real in the browser.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riserbo import detectors, llm, pipeline  # noqa: E402
from riserbo.server import SAMPLE_TITLES, SAMPLES  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1])
    if not llm.health():
        sys.exit(f"model server not reachable at {llm.BASE_URL}")
    samples = []
    for f in sorted(SAMPLES.glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        rule_spans = detectors.find_all(text)
        model_spans, llm_ok = llm.find_entities(text)
        if not llm_ok:
            sys.exit(f"model call failed on {f.name}")
        spans = pipeline.merge(rule_spans, model_spans)
        redacted, mapping, annotated = pipeline.redact(text, spans)
        samples.append({
            "id": f.stem,
            "title": SAMPLE_TITLES.get(f.stem, f.stem),
            "text": text,
            "spans": annotated,
            "redacted": redacted,
            "mapping": mapping,
            "rules_only_missed": pipeline.rules_only_missed(rule_spans, spans),
        })
        print(f"{f.stem}: {len(annotated)} spans, {len(mapping)} placeholders", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": llm.MODEL,
        "generated": dt.date.today().isoformat(),
        "samples": samples,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
