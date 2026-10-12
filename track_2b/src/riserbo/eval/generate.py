"""Generate the synthetic multilingual test set with gold spans.

Every document is built from a template whose slots are filled with fake people,
organisations, addresses, checksum-valid identifiers, health details and
indirect identifiers. The generator records the exact character span of every
slot, so scoring needs no manual annotation. Places and names used in the
Apertus few-shot examples are deliberately excluded.

Usage: python -m riserbo.eval.generate [--n 60] [--seed 2026] [--out data/eval/riserbo_eval_v1.jsonl]
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from .. import fakeids

FIRST = {
    "it": ["Giulia", "Marco", "Chiara", "Luca", "Sara", "Matteo", "Elisa", "Davide", "Lorenza", "Fabio", "Noemi", "Sandro"],
    "de": ["Anna", "Reto", "Corinne", "Lukas", "Seraina", "Beat", "Nadja", "Jonas", "Ursula", "Fabian", "Mirjam", "Peter"],
    "fr": ["Camille", "Julien", "Léa", "Nicolas", "Chloé", "Mathieu", "Aurélie", "Yannick", "Sandrine", "Olivier", "Élodie", "Pascal"],
}
LAST = {
    "it": ["Bianchi", "Fontana", "Ghirlanda", "Lepori", "Morandi", "Quadri", "Righetti", "Soldati", "Tamò", "Vassalli", "Zanetti", "Respini"],
    "de": ["Meier", "Schmid", "Bühler", "Caflisch", "Gerber", "Hofstetter", "Jenny", "Lüthi", "Wyss", "Zollinger", "Brändli", "Tscharner"],
    "fr": ["Bovet", "Chappuis", "Dubois", "Gaillard", "Jaccard", "Monnier", "Pittet", "Rossier", "Thévoz", "Vuilleumier", "Cuendet", "Overney"],
}
ORG = {
    "it": ["Studio Legale Quadri & Soci", "Fiduciaria Monte Brè SA", "Clinica Sant'Anna Sagl", "Garage Centrale Biasca SA", "Banca dello Stato del Cantone Ticino", "Edilcasa Riviera Sagl"],
    "de": ["Treuhand Albis AG", "Schreinerei Holzwerk GmbH", "Praxis am Bahnhof AG", "Bergbahnen Surselva AG", "Kanzlei Jenny & Partner", "Spitex Oberland GmbH"],
    "fr": ["Fiduciaire du Léman SA", "Garage des Alpes Sàrl", "Étude Monnier & Associés", "Clinique de la Broye SA", "Boulangerie du Château Sàrl", "Régie Immobilière Rhône SA"],
}
STREET = {
    "it": ["Via San Gottardo", "Via Lavizzari", "Piazza Grande", "Via Ospedale", "Via ai Monti", "Viale Stazione"],
    "de": ["Bahnhofstrasse", "Dorfstrasse", "Kirchgasse", "Seestrasse", "Bergweg", "Lindenplatz"],
    "fr": ["Rue de Lausanne", "Avenue de la Gare", "Chemin des Vignes", "Rue du Temple", "Route de Fribourg", "Place du Marché"],
}
TOWN = {
    "it": [("6500", "Bellinzona"), ("6600", "Locarno"), ("6710", "Biasca"), ("6943", "Vezia"), ("6760", "Faido")],
    "de": [("7000", "Chur"), ("3800", "Interlaken"), ("8750", "Glarus"), ("7130", "Ilanz"), ("3920", "Zermatt")],
    "fr": [("1700", "Fribourg"), ("1530", "Payerne"), ("1950", "Sion"), ("1630", "Bulle"), ("2000", "Neuchâtel")],
}
# Indirect identifiers: unique roles in small places, local public offices, superlatives.
QUASI = {
    "it": ["l'unica farmacista di Sonogno", "il sindaco di Linescio", "l'unico maestro di sci di Bosco Gurin con più di settant'anni",
           "la custode della capanna Basòdino", "l'ultimo mugnaio della Valle Onsernone", "la presidente del patriziato di Cerentino"],
    "de": ["der einzige Hausarzt von Safien", "die Gemeindepräsidentin von Obersaxen", "der älteste aktive Bergführer im Calancatal",
           "die einzige Hebamme im Val Müstair", "der Pfarrer von Tschlin", "die Hüttenwartin der Terrihütte"],
    "fr": ["la seule notaire de Champéry", "le syndic de Rossinière", "la doyenne du village de Grimentz",
           "le dernier fromager d'alpage de l'Intyamon", "l'unique pharmacien de Charmey", "la gardienne de la cabane d'Orny"],
}
HEALTH = {
    "it": ["una forma rara di leucemia", "il morbo di Parkinson", "una depressione grave", "il diabete di tipo 1", "una dipendenza da alcol"],
    "de": ["einer seltenen Form von Leukämie", "Parkinson", "einer schweren Depression", "Diabetes Typ 1", "einer Alkoholabhängigkeit"],
    "fr": ["une forme rare de leucémie", "la maladie de Parkinson", "une dépression sévère", "un diabète de type 1", "une dépendance à l'alcool"],
}

# {SLOT} placeholders; {X:NOISE} are distractors that must NOT be redacted.
TEMPLATES = {
    "it": [
        "Oggetto: pratica {X:CASE}\n\nGentile signora {PERSON_B},\n\nil suo cliente {PERSON_A}, nato il {DOB}, {QUASI}, ci ha comunicato di soffrire di {HEALTH}. "
        "Abita in {ADDRESS} e lavora per {ORG}. Recapiti: {PHONE}, {EMAIL}. Per il rimborso indichiamo il conto {IBAN}. "
        "La fattura n. {X:INVOICE} di CHF {X:AMOUNT} resta aperta presso il Tribunale d'appello di Lugano.\n\nCordiali saluti,\n{PERSON_C}",
        "Verbale dell'incontro del {X:DATE}\n\nPresenti: {PERSON_A} ({ORG}) e {PERSON_B}. {PERSON_A}, {QUASI}, chiede la revisione del contratto. "
        "Numero AVS: {AHV}. Domicilio: {ADDRESS}. Il medico curante conferma {HEALTH}. Codice fiscale italiano: {CF}. "
        "La sede del Cantone a Bellinzona è stata informata.",
    ],
    "de": [
        "Betreff: Dossier {X:CASE}\n\nSehr geehrter Herr {PERSON_B},\n\nIhr Klient {PERSON_A}, geboren am {DOB}, {QUASI}, leidet seit dem Frühjahr an {HEALTH}. "
        "Er wohnt an der {ADDRESS} und arbeitet bei der {ORG}. Kontakt: {PHONE}, {EMAIL}. Bitte überweisen Sie den Betrag auf {IBAN}. "
        "Die Rechnung Nr. {X:INVOICE} über CHF {X:AMOUNT} liegt beim Kantonsgericht Graubünden.\n\nFreundliche Grüsse\n{PERSON_C}",
        "Protokoll der Sitzung vom {X:DATE}\n\nAnwesend: {PERSON_A} ({ORG}) und {PERSON_B}. {PERSON_A}, {QUASI}, verlangt eine Vertragsänderung. "
        "AHV-Nummer: {AHV}. Wohnadresse: {ADDRESS}. Der Hausarzt bestätigt {HEALTH}. UID der Firma: {UID}. "
        "Das Steueramt in Chur wurde informiert.",
    ],
    "fr": [
        "Objet : dossier {X:CASE}\n\nMadame {PERSON_B},\n\nVotre client {PERSON_A}, né le {DOB}, {QUASI}, souffre depuis le printemps d'{HEALTH}. "
        "Il habite {ADDRESS} et travaille pour {ORG}. Contact : {PHONE}, {EMAIL}. Merci de verser le montant sur le compte {IBAN}. "
        "La facture n° {X:INVOICE} de CHF {X:AMOUNT} est déposée auprès du Tribunal cantonal de Fribourg.\n\nSalutations distinguées,\n{PERSON_C}",
        "Procès-verbal de la séance du {X:DATE}\n\nPrésents : {PERSON_A} ({ORG}) et {PERSON_B}. {PERSON_A}, {QUASI}, demande une modification du contrat. "
        "Numéro AVS : {AHV}. Domicile : {ADDRESS}. Le médecin traitant confirme {HEALTH}. IDE de l'entreprise : {UID}. "
        "Le Service des contributions à Fribourg a été informé.",
    ],
}

GOLD_TYPE = {"PERSON_A": "PERSON", "PERSON_B": "PERSON", "PERSON_C": "PERSON", "ORG": "ORG", "ADDRESS": "ADDRESS",
             "QUASI": "QUASI", "HEALTH": "HEALTH", "AHV": "AHV", "IBAN": "IBAN", "PHONE": "PHONE", "EMAIL": "EMAIL",
             "DOB": "DOB", "CF": "CF", "UID": "UID"}


def _person(lang: str, rng: random.Random) -> str:
    return f"{rng.choice(FIRST[lang])} {rng.choice(LAST[lang])}"


def _fill(lang: str, slot: str, rng: random.Random, people: dict) -> str:
    if slot.startswith("PERSON"):
        return people[slot]
    if slot == "ORG":
        return rng.choice(ORG[lang])
    if slot == "ADDRESS":
        pc, town = rng.choice(TOWN[lang])
        return f"{rng.choice(STREET[lang])} {rng.randint(1, 120)}, {pc} {town}"
    if slot == "QUASI":
        return rng.choice(QUASI[lang])
    if slot == "HEALTH":
        return rng.choice(HEALTH[lang])
    if slot == "AHV":
        return fakeids.ahv(rng)
    if slot == "IBAN":
        return fakeids.iban_ch(rng)
    if slot == "PHONE":
        return fakeids.phone_ch(rng)
    if slot == "EMAIL":
        first, last = people["PERSON_A"].lower().split()
        trans = str.maketrans("àèéìòùüöäâêîôûç", "aeeiouuoaaeiouc")
        return f"{first.translate(trans)}.{last.translate(trans)}@{rng.choice(['bluewin.ch', 'gmail.com', 'sunrise.ch'])}"
    if slot == "DOB":
        return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1940, 2000)}"
    if slot == "CF":
        return fakeids.codice_fiscale(rng)
    if slot == "UID":
        return fakeids.uid(rng)
    if slot == "X:CASE":
        return f"{rng.randint(100, 999)}/{rng.randint(2024, 2026)}"
    if slot == "X:INVOICE":
        return str(rng.randint(10_000_000_000, 99_999_999_999))
    if slot == "X:AMOUNT":
        return f"{rng.randint(1, 99)}'{rng.randint(100, 999)}.00"
    if slot == "X:DATE":
        return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.2026"
    raise KeyError(slot)


def make_doc(idx: int, lang: str, rng: random.Random) -> dict:
    template = rng.choice(TEMPLATES[lang])
    people: dict[str, str] = {}
    while len(set(people.values())) < 3:
        people = {k: _person(lang, rng) for k in ("PERSON_A", "PERSON_B", "PERSON_C")}
    values: dict[str, str] = {}
    text, spans, cursor = [], [], 0
    pos = 0
    for m in re.finditer(r"\{([A-Z_:]+)\}", template):
        text.append(template[cursor:m.start()])
        pos += m.start() - cursor
        slot = m.group(1)
        value = values.setdefault(slot, _fill(lang, slot, rng, people))
        if slot in GOLD_TYPE:
            spans.append({"start": pos, "end": pos + len(value), "type": GOLD_TYPE[slot], "text": value})
        text.append(value)
        pos += len(value)
        cursor = m.end()
    text.append(template[cursor:])
    doc = "".join(text)
    assert all(doc[s["start"]:s["end"]] == s["text"] for s in spans)
    return {"id": f"{lang}-{idx:03d}", "lang": lang, "text": doc, "spans": spans}


def generate(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    langs = ["it", "de", "fr"]
    return [make_doc(i, langs[i % 3], rng) for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data/eval/riserbo_eval_v1.jsonl")
    args = ap.parse_args()
    docs = generate(args.n, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"wrote {len(docs)} documents, {sum(len(d['spans']) for d in docs)} gold spans to {out}")


if __name__ == "__main__":
    main()
