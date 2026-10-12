import json

import httpx

from riserbo import detectors, llm, pipeline


def fake_client(entities_per_call):
    calls = iter(entities_per_call)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        content = json.dumps({"entities": next(calls)})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


DOC = ("Il dott. Paolo Bernasconi, unico medico di base a Bosco Gurin, lavora per la Clinica Alpina SA. "
       "AHV 756.9217.0769.85. Bernasconi ha chiesto un prestito.")


def test_spans_are_located_everywhere_and_guarded():
    client = fake_client([
        [{"text": "Paolo Bernasconi", "type": "PERSON", "reason": "name"},
         {"text": "Clinica Alpina SA", "type": "ORG", "reason": "employer"},
         {"text": "Mario Inventato", "type": "PERSON", "reason": "hallucinated"},
         {"text": "x", "type": "BOGUS", "reason": "bad type"}],
        [{"text": "unico medico di base a Bosco Gurin", "type": "QUASI", "reason": "unique role"},
         {"text": "Paolo Bernasconi", "type": "PERSON", "reason": "wrong pass"}],
    ])
    spans, ok = llm.find_entities(DOC, client)
    assert ok
    texts = sorted({(s.type, s.text) for s in spans})
    assert texts == [("ORG", "Clinica Alpina SA"), ("PERSON", "Bernasconi"), ("PERSON", "Paolo Bernasconi"),
                     ("QUASI", "unico medico di base a Bosco Gurin")]


def test_partial_name_reuses_person_placeholder():
    client = fake_client([[{"text": "Paolo Bernasconi", "type": "PERSON", "reason": "name"}], []])
    model_spans, _ = llm.find_entities(DOC, client)
    spans = pipeline.merge(detectors.find_all(DOC), model_spans)
    redacted, mapping, _ = pipeline.redact(DOC, spans)
    assert "Bernasconi" not in redacted
    assert redacted.count("[PERSON_1]") == 2
    assert mapping["[PERSON_1]"] == "Paolo Bernasconi"
    assert "[AHV_1]" in redacted


def test_rule_spans_win_over_model_spans():
    client = fake_client([[{"text": "756.9217.0769.85", "type": "ID", "reason": "number"}], []])
    model_spans, _ = llm.find_entities(DOC, client)
    spans = pipeline.merge(detectors.find_all(DOC), model_spans)
    assert [s.source for s in spans if "756" in s.text] == ["rule"]


def test_model_down_falls_back():
    def handler(request):
        raise httpx.ConnectError("down")

    spans, ok = llm.find_entities(DOC, httpx.Client(transport=httpx.MockTransport(handler)))
    assert spans == [] and ok is False


def test_chunks_cover_text_with_correct_offsets():
    text = ("Frase numero uno. " * 200).strip()
    parts = llm.chunks(text, size=300)
    assert "".join(c for _, c in parts) == text
    for offset, chunk in parts:
        assert text[offset:offset + len(chunk)] == chunk


def test_locate_respects_word_boundaries():
    assert llm.locate("Rossini e Rossi", "Rossi") == [(10, 15)]
    assert llm.locate("Elena Bernasconi-Dazio e Bernasconi", "Bernasconi") == [(25, 35)]


def test_surnames_skip_titles():
    assert llm.surnames("dott. Paolo Bernasconi") == ["Bernasconi"]
    assert llm.surnames("Bernasconi") == []
