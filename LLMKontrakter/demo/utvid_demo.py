import json
from pathlib import Path

import demo_core as core

DEMO_DIR = Path(__file__).resolve().parent



# Forutsetter at demo-mappen ligger i prosjektets hovedmappe,
# og at hele CUAD-filen ligger i prosjektets data-mappe.
CUAD_FILE = DEMO_DIR.parent / "data" / "CUADv1.json"

CONTRACTS_FILE = DEMO_DIR / "data" / "demo_kontrakter.json"
CONFIG_FILE = DEMO_DIR / "data" / "demo_oppsett.json"

TITLE = (
    "PAXMEDICA,INC_07_02_2020-EX-10.12-"
    "Master Service Agreement"
)

if not CUAD_FILE.exists():
    raise FileNotFoundError(
        f"Fant ikke {CUAD_FILE}. "
        "Endre CUAD_FILE til plasseringen av CUADv1.json."
    )

with open(CUAD_FILE, encoding="utf-8") as f:
    raw = json.load(f)

matches = [
    d for d in raw["data"]
    if d["title"] == TITLE
]

if len(matches) != 1:
    raise ValueError(
        f"Forventet én kontrakt med denne tittelen, fant {len(matches)}."
    )

paragraph = matches[0]["paragraphs"][0]
text = paragraph["context"]
gold = {cat: [] for cat in core.CATS}

# Hent de opprinnelige annotasjonene for demoens kategorier.
for question in paragraph["qas"]:
    cat = question["id"].split("__")[-1]

    if cat not in gold:
        continue

    unique = {}

    for answer in question["answers"]:
        passage = answer["text"]
        start = answer["answer_start"]
        end = start + len(passage)

        if not passage.strip():
            continue

        if text[start:end] != passage:
            raise ValueError(
                f"Fasitpassasjen stemmer ikke med tekstposisjonen: {cat}"
            )

        unique[(start, end)] = {
            "text": passage,
            "start": start,
            "end": end,
        }

    gold[cat] = sorted(
        unique.values(),
        key=lambda item: item["start"],
    )

assert gold["Post-Termination Services"], (
    "Kontrakten må ha en annotert Post-Termination Services-klausul."
)

new_document = {
    "title": TITLE,
    "text": text,
    "text_llm": core.clean_for_llm(text),
    "gold": gold,
}

with open(CONTRACTS_FILE, encoding="utf-8") as f:
    documents = json.load(f)

# Erstatt samme kontrakt hvis skriptet kjøres flere ganger.
documents = [d for d in documents if d["title"] != TITLE]
documents.append(new_document)

with open(CONFIG_FILE, encoding="utf-8") as f:
    config = json.load(f)

config["demo_titles"] = [d["title"] for d in documents]
config["demo_request_count"] = sum(
    len(core.make_chunks(d["text_llm"])) * len(core.CATS)
    for d in documents
)

with open(CONTRACTS_FILE, "w", encoding="utf-8") as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)

with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("Demokontrakter:", len(documents))
print("Planlagte API-kall:", config["demo_request_count"])
print("\nNy fasit for Post-Termination Services:")

for passage in gold["Post-Termination Services"]:
    print(passage["text"])