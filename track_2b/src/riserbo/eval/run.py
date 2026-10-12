"""Score redaction setups on the synthetic test set.

Metrics
- leak rate: share of gold personal-data characters left visible (lower is better)
- entity recall: share of gold items at least half covered by a redaction
- precision: share of redactions that overlap gold personal data (over-redaction shows up here)
- per-type recall, and seconds per document

Setups: rules (deterministic detectors only), apertus (model only), rules+apertus (Riserbo),
and rizzo-pii (the MIT rizzo-pii-0.3B tagger, only if `transformers` is installed and --rizzo is passed).

Usage: python -m riserbo.eval.run [--data data/eval/riserbo_eval_v1.jsonl] [--limit N] [--rizzo]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import httpx

from .. import detectors, llm, pipeline
from ..detectors import Span

FAMILY = {"AHV": "ID", "IBAN": "ID", "CF": "ID", "UID": "ID", "PHONE": "CONTACT", "EMAIL": "CONTACT", "DOB": "DATE",
          "PERSON": "PERSON", "ORG": "ORG", "ADDRESS": "ADDRESS", "HEALTH": "HEALTH", "QUASI": "QUASI"}


def score(docs: list[dict], predictions: list[list[Span]]) -> dict:
    gold_chars = leaked_chars = 0
    found = defaultdict(int)
    total = defaultdict(int)
    pred_total = pred_hit = 0
    for doc, pred in zip(docs, predictions):
        covered = [False] * len(doc["text"])
        for s in pred:
            for i in range(s.start, s.end):
                covered[i] = True
        gold_mask = [False] * len(doc["text"])
        for g in doc["spans"]:
            fam = FAMILY[g["type"]]
            n = g["end"] - g["start"]
            hit = sum(covered[g["start"]:g["end"]])
            gold_chars += n
            leaked_chars += n - hit
            total[fam] += 1
            found[fam] += hit * 2 >= n
            for i in range(g["start"], g["end"]):
                gold_mask[i] = True
        for s in pred:
            pred_total += 1
            pred_hit += any(gold_mask[s.start:s.end])
    n_gold = sum(total.values())
    return {
        "leak_rate": round(leaked_chars / gold_chars, 4),
        "entity_recall": round(sum(found.values()) / n_gold, 4),
        "precision": round(pred_hit / pred_total, 4) if pred_total else 0.0,
        "recall_by_type": {k: round(found[k] / total[k], 3) for k in sorted(total)},
        "gold_items": n_gold,
        "redactions": pred_total,
    }


def rizzo_predictor():
    from transformers import pipeline as hf_pipeline  # optional dependency

    tagger = hf_pipeline("token-classification", model="rizzoaiacademy/rizzo-pii-0.3B", aggregation_strategy="simple")

    def predict(text: str) -> list[Span]:
        return [Span(e["start"], e["end"], text[e["start"]:e["end"]], e["entity_group"], "rizzo", "")
                for e in tagger(text)]
    return predict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/eval/riserbo_eval_v1.jsonl")
    ap.add_argument("--out", default="data/eval/results.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rizzo", action="store_true")
    args = ap.parse_args()

    docs = [json.loads(line) for line in Path(args.data).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        docs = docs[:args.limit]

    preds = defaultdict(list)
    secs = defaultdict(float)
    llm_failures = 0
    with httpx.Client() as client:
        for i, doc in enumerate(docs, 1):
            text = doc["text"]
            t = time.time()
            rules = detectors.find_all(text)
            secs["rules"] += time.time() - t
            t = time.time()
            model, ok = llm.find_entities(text, client)
            secs["apertus"] += time.time() - t
            llm_failures += not ok
            preds["rules"].append(rules)
            preds["apertus"].append(model)
            preds["rules+apertus"].append(pipeline.merge(rules, model))
            print(f"[{i}/{len(docs)}] {doc['id']} llm_ok={ok}", flush=True)

    if args.rizzo:
        predict = rizzo_predictor()
        t = time.time()
        preds["rizzo-pii-0.3B"] = [predict(d["text"]) for d in docs]
        secs["rizzo-pii-0.3B"] = time.time() - t
        preds["rules+rizzo"] = [pipeline.merge(r, z) for r, z in zip(preds["rules"], preds["rizzo-pii-0.3B"])]
        secs["rules+rizzo"] = secs["rules"] + secs["rizzo-pii-0.3B"]

    secs["rules+apertus"] = secs["rules"] + secs["apertus"]
    results = {
        "dataset": args.data,
        "documents": len(docs),
        "model": llm.MODEL,
        "endpoint": llm.BASE_URL,
        "llm_failed_documents": llm_failures,
        "setups": {name: {**score(docs, p), "seconds_per_doc": round(secs[name] / len(docs), 2)} for name, p in preds.items()},
    }
    by_lang = {}
    for lang in ("it", "de", "fr"):
        idx = [i for i, d in enumerate(docs) if d["lang"] == lang]
        if idx:
            by_lang[lang] = {name: score([docs[i] for i in idx], [p[i] for i in idx])["leak_rate"]
                             for name, p in preds.items()}
    results["leak_rate_by_language"] = by_lang

    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"{'setup':<16}{'leak rate':>10}{'recall':>9}{'precision':>11}{'s/doc':>8}")
    for name, r in results["setups"].items():
        print(f"{name:<16}{r['leak_rate']:>10.1%}{r['entity_recall']:>9.1%}{r['precision']:>11.1%}{r['seconds_per_doc']:>8}")
    print()
    for name, r in results["setups"].items():
        print(name, r["recall_by_type"])
    print("\nwritten", args.out)


if __name__ == "__main__":
    main()
