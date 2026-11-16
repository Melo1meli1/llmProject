import json, re, hashlib
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "data/demo_oppsett.json").read_text(encoding="utf-8"))
CATEGORIES = CONFIG["categories"]
CATS = CONFIG["demo_categories"]
MODEL = CONFIG["model"]
REASONING_EFFORT = CONFIG["reasoning_effort"]
DESCRIPTIONS = CONFIG["descriptions"]
FINAL_SYSTEM_PROMPTS = CONFIG["system_prompts"]
CHUNK_CHARS = CONFIG["chunk_chars"]
OVERLAP_CHARS = CONFIG["overlap_chars"]
PATTERNS = CONFIG["baseline"]["patterns"]
MIN_SCORE = CONFIG["baseline"]["min_score"]
TOP_K = CONFIG["baseline"]["top_k"]
COMPILED = {c: [re.compile(p, re.I) for p in ps] for c, ps in PATTERNS.items()}
MODE = "lagret"
client = None
CALLS = 0


def norm_ws(s):
    # Samler all whitespace til ett mellomrom. Brukes når tekster sammenlignes.
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()

def clean_for_llm(text):
    # Forsiktig tekstrensing til språkmodellen: bare mellomrom og tomme linjer, ikke innhold.
    # Originalteksten røres ikke, fordi fasitens posisjoner peker i den.
    t = text.replace("\r\n", "\n").replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)       # flere mellomrom eller tabs blir ett
    t = re.sub(r" ?\n ?", "\n", t)      # fjern mellomrom rundt linjeskift
    t = re.sub(r"\n{3,}", "\n\n", t)    # maks én tom linje
    return t.strip()

def in_text(passage, text):
    # Står utdraget ordrett i teksten (bortsett fra whitespace)? Avslører hallusinerte utdrag.
    return norm_ws(passage) in norm_ws(text)

def split_passages(text, min_len=40):
    # Del opp i avsnitt (tom linje mellom). Svært lange avsnitt deles videre på linjeskift.
    out = []
    for p in (x.strip() for x in re.split(r"\n\s*\n", text)):
        out.extend(p.split("\n") if len(p) > 3000 else [p])
    return [p.strip() for p in out if len(p.strip()) >= min_len]

def keyword_predict(contract, cat):
    scored = []
    for p in split_passages(contract["text_llm"]):
        score = sum(1 for rx in COMPILED[cat] if rx.search(p))   # antall nøkkeluttrykk som treffer
        if score >= MIN_SCORE:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:TOP_K]]

def make_chunks(text, size=CHUNK_CHARS, overlap=OVERLAP_CHARS):
    # Korte kontrakter sendes hele. Lange deles i biter på 'size' tegn med 'overlap' tegn overlapp.
    if len(text) <= size:
        return [text]
    chunks, i = [], 0
    while True:
        chunks.append(text[i:i + size])
        if i + size >= len(text):
            return chunks
        i += size - overlap

def passage_in_contract(passage, document):
    """Kontroller sitatet, med toleranse for utelatte sidemarkører."""

    if in_text(passage, document["text_llm"]):
        return True

    # Fjern bare sidemarkører som står alene på en linje:
    # «Page 23» eller «- 6 -».
    text_without_page_markers = re.sub(
        r"^[ \t]*(?:Page[ \t]+\d+|-[ \t]*\d+[ \t]*-)[ \t]*\r?$",
        "",
        document["text"],
        flags=re.MULTILINE,
    )

    return in_text(passage, text_without_page_markers)

def llm_predict(contract, cat):
    text = contract["text_llm"]
    funnet = []

    for ch in make_chunks(text):
        try:
            d = json.loads(llm_call(ch, cat)["raw"])
        except json.JSONDecodeError as exc:
            # Stopp ved ugyldig JSON, så feilen ikke blir et negativt treff.
            raise ValueError(
                f"Ugyldig JSON for {contract['title']} / {cat}"
            ) from exc

        if d.get("found"):
            funnet += [
                p for p in d.get("passages", [])
                if isinstance(p, str) and p.strip()
            ]

    # Fjern dubletter og kontroller at utdragene finnes i kontrakten.
    # Kontrollen tillater at sidemarkører på egne linjer er utelatt.
    seen, final = set(), []

    for p in funnet:
        if p not in seen and passage_in_contract(p, contract):
            seen.add(p)
            final.append(p)

    return final

def tokens(s):
    return re.findall(r"\w+", s.lower())

def token_f1(a, b):
    ta, tb = tokens(a), tokens(b)

    if not ta or not tb:
        return 0.0

    common = sum((Counter(ta) & Counter(tb)).values())

    if common == 0:
        return 0.0

    precision = common / len(ta)
    recall = common / len(tb)

    return 2 * precision * recall / (precision + recall)

def collect_predictions(predict_fn, documents, categories):
    """Samle prediksjoner og fasit for samme dokumentutvalg."""
    details = []

    for cat in categories:
        print(f"Behandler: {CATEGORIES[cat]}", flush=True)

        for document in documents:
            details.append({
                "title": document["title"],
                "kategori": cat,
                "gold": [
                    g["text"] for g in document["gold"][cat]
                ],
                "pred": predict_fn(document, cat),
            })

    expected = {
        (d["title"], cat)
        for d in documents
        for cat in categories
    }

    assert len(details) == len(expected)
    assert {
        (r["title"], r["kategori"]) for r in details
    } == expected

    return details

def evaluate_saved(details, cats, name):
    """
    Evaluerer lagrede prediksjoner.

    Kontraktsnivå:
        Presisjon, recall og F1 for forekomst av klausultypen.

    Passasjenivå:
        Dekning av fasit: beste token-F1 for hver fasitpassasje.
        Treffsikkerhet for utdrag: beste token-F1 for hvert utdrag.

    Manglende treff gir null. Gjennomsnittene beregnes over
    henholdsvis alle fasitpassasjer og alle returnerte utdrag.
    """
    rows = []

    for cat in cats:
        category_details = [
            d for d in details if d["kategori"] == cat
        ]

        if not category_details:
            raise ValueError(f"Mangler resultater for {cat}.")

        titles = [d["title"] for d in category_details]
        if len(titles) != len(set(titles)):
            raise ValueError(f"Dupliserte kontraktresultater for {cat}.")

        tp = fp = fn = tn = 0
        gold_scores = []
        pred_scores = []

        for d in category_details:
            gold = d["gold"]
            pred = d["pred"]

            # Forekomst av klausultypen på kontraktsnivå.
            if gold and pred:
                tp += 1
            elif pred:
                fp += 1
            elif gold:
                fn += 1
            else:
                tn += 1

            # Hver fasitpassasje får en skår.
            # Ingen prediksjon betyr null.
            for g in gold:
                best_match = max(
                    (token_f1(p, g) for p in pred),
                    default=0.0,
                )
                gold_scores.append(best_match)

            # Hvert returnert utdrag får en skår.
            # Ingen fasit betyr null.
            for p in pred:
                best_match = max(
                    (token_f1(p, g) for g in gold),
                    default=0.0,
                )
                pred_scores.append(best_match)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        rows.append({
            "metode": name,
            "kategori": CATEGORIES[cat],
            "antall_kontrakter": len(category_details),
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "presisjon": precision,
            "recall": recall,
            "F1": f1,
            "antall_fasitpassasjer": len(gold_scores),
            "antall_utdrag": len(pred_scores),
            "dekning_fasit": (
                float(np.mean(gold_scores))
                if gold_scores else np.nan
            ),
            "treffsikkerhet_utdrag": (
                float(np.mean(pred_scores))
                if pred_scores else np.nan
            ),
        })

    return pd.DataFrame(rows)

def make_request(chunk, cat):
    user = (f"Clause type: {cat}\n"
            f"Definition: {DESCRIPTIONS[cat]}\n\n"
            f"Contract text:\n<<<\n{chunk}\n>>>")
    return {"model": MODEL, "reasoning_effort": REASONING_EFFORT,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": FINAL_SYSTEM_PROMPTS[cat]},
                         {"role": "user", "content": user}]}

def request_key(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def llm_call(chunk, cat):
    global CALLS
    request = make_request(chunk, cat)
    key = request_key(request)
    if MODE == "lagret":
        saved = json.loads((BASE / "data/demo_llm_svar.json").read_text(encoding="utf-8"))
        if key not in saved:
            raise RuntimeError("Ingen lagret respons for denne forespørselen. Ingen API-kall utføres.")
        out = saved[key]
    elif MODE == "api":
        if client is None:
            raise RuntimeError("API-klienten er ikke initialisert.")
        if CALLS >= CONFIG["demo_request_count"]:
            raise RuntimeError("Antall planlagte demokall er nådd. Kjør oppsettcellen på nytt.")
        CALLS += 1
        resp = client.chat.completions.create(**request)
        choice = resp.choices[0]
        if choice.finish_reason != "stop" or not choice.message.content:
            raise RuntimeError("Ufullstendig modellsvar; dette registreres ikke som negativt treff.")
        out = {"model": resp.model, "raw": choice.message.content,
               "usage": resp.usage.model_dump() if resp.usage else None}
        target = BASE / "output/api_svar"
        target.mkdir(parents=True, exist_ok=True)
        (target / (key + ".json")).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        raise ValueError("MODE må være lagret eller api.")
    parsed = json.loads(out["raw"])
    if (not isinstance(parsed, dict) or not isinstance(parsed.get("found"), bool)
        or not isinstance(parsed.get("passages"), list)
        or not all(isinstance(p, str) for p in parsed["passages"])):
        raise ValueError("Ugyldig JSON-struktur i modellsvar.")
    return out
