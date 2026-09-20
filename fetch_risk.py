"""
EU War Radar - denni sber zprav a vypocet skore rizika.
Spousti se automaticky pres GitHub Actions (viz .github/workflows/update.yml).
Nevyzaduje zadny platny API klic - pouziva verejne RSS kanaly.
Ceska republika ma prioritu - vic zdroju, vic klicovych slov, vic zobrazenych zprav.

Krome vojenskeho/teroristickeho rizika po zemich se pocita i SAMOSTATNE
radiacni skore pro celou Evropu (jaderne incidenty, uniky radiace, IAEA
inspekce, Zaporozska elektrarna, Cernobyl apod.) - viz RADIATION_KEYWORDS.

DULEZITE - presne celoslovni hledani (regex s hranici \\b), text se
normalizuje (mala pismena + odstraneni diakritiky) pred porovnavanim.

Kazde spusteni uklada zaznam do history.json (celkove skore, radiacni skore,
skore vsech oblasti) pro grafy vyvoje v case.
"""

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
import feedparser

DATA_FILE = "data.json"
HISTORY_FILE = "history.json"
MAX_HISTORY_ENTRIES = 200

# --- 1. Zdroje zprav (verejne RSS kanaly, zadny API klic potreba) ---
FEEDS = [
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.nato.int/cps/en/natohq/news.rss",
    "https://apnews.com/hub/world-news.rss",
    "https://understandingwar.org/feed",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.theguardian.com/world/rss",
    "https://kyivindependent.com/feed",
    "https://www.pravda.com.ua/eng/rss/view_news/",
    "https://www.irozhlas.cz/rss/irozhlas",
    "https://www.novinky.cz/rss",
    "https://www.seznamzpravy.cz/rss",
    "https://ct24.ceskatelevize.cz/rss/tema/vyber-redakce-84313",
]

# --- 2. Klicova slova pro vojensky/teroristicky radar (cele slovo) ---
THREAT_KEYWORDS = [
    "war", "wars", "valka", "valce", "valky",
    "invasion", "invaze", "invaded", "invading",
    "military", "vojenska", "vojenske", "vojensky", "vojenstvi",
    "armed forces", "armada", "troops", "vojaci",
    "nato", "defense", "defence", "obrana",
    "mobilization", "mobilisation", "mobilize", "mobilise", "mobilizace",
    "coup", "puc",
    "attack", "attacks", "attacked", "attacking", "utok", "utoky", "utocit",
    "airstrike", "airstrikes", "air strike", "air strikes",
    "missile strike", "missile strikes",
    "military strike", "military strikes",
    "drone strike", "drone strikes",
    "rocket strike", "rocket strikes",
    "missile", "missiles", "raketa", "rakety",
    "bomb", "bombs", "bombing", "bombed",
    "explosion", "explosions", "vybuch", "vybuchy",
    "shooting", "shootings", "strelba",
    "clash", "clashes", "strety",
    "riot", "riots", "nepokoje",
    "uprising", "povstani",
    "insurgent", "insurgents", "povstalci",
    "militia", "militias", "milice",
    "terrorism", "terrorist", "terrorists", "terorismus", "terorista", "teroriste",
    "extremist", "extremists",
    "hostage", "hostages", "rukojmi",
    "security threat", "bezpecnostni hrozba",
    "sabotage", "sabotaz",
    "cyberattack", "cyberattacks", "kyberneticky utok",
    "espionage", "spionaz", "spion",
    "drone", "drones", "dron", "drony",
    "airspace", "vzdusny prostor",
    "casualties", "obeti", "killed", "zabit", "zabiti", "zabita",
    "wounded", "zranen", "zraneni", "dead", "death toll",
    "ceasefire", "sanctions", "sankce", "peace talks",
]

# --- 3. Sledovane oblasti a jejich klicova slova (nazvy zemi/oblasti) ---
HOTSPOTS = {
    "czechia": {
        "name": "Ceska republika",
        "keywords": [
            "czech republic", "czechia", "cesko", "ceska republika",
            "prague", "praha", "ceska armada", "armada cr",
            "ministerstvo obrany cr", "bezpecnostni informacni sluzba",
            "vojenske zpravodajstvi cr", "cinska spionaz", "ruska spionaz",
            "rusko cesko", "drony nad ceskem", "hybridni valka",
            "dezinformacni kampan",
        ],
        "base_score": 3,
        "headline_limit": 10,
    },
    "ukraine": {
        "name": "Ukrajina",
        "keywords": ["ukraine", "ukrajina", "kyiv", "kyjev", "donetsk", "zelensky", "putin"],
        "base_score": 60,
    },
    "balkans": {
        "name": "Kosovo - Srbsko",
        "keywords": ["kosovo", "serbia", "srbsko", "kfor", "mitrovica", "belgrade"],
        "base_score": 20,
    },
    "moldova": {
        "name": "Moldova - Podnestri",
        "keywords": ["moldova", "transnistria", "podnestri", "chisinau"],
        "base_score": 15,
    },
    "austria": {"name": "Rakousko", "keywords": ["austria", "rakousko", "vienna", "vidnen"], "base_score": 3},
    "belgium": {"name": "Belgie", "keywords": ["belgium", "belgie", "brussels", "brusel"], "base_score": 3},
    "bulgaria": {"name": "Bulharsko", "keywords": ["bulgaria", "bulharsko", "sofia"], "base_score": 5},
    "croatia": {"name": "Chorvatsko", "keywords": ["croatia", "chorvatsko", "zagreb"], "base_score": 5},
    "cyprus": {"name": "Kypr", "keywords": ["cyprus", "kypr", "nicosia"], "base_score": 8},
    "denmark": {"name": "Dansko", "keywords": ["denmark", "dansko", "copenhagen"], "base_score": 4},
    "estonia": {"name": "Estonsko", "keywords": ["estonia", "estonsko", "tallinn", "nato eastern flank"], "base_score": 15},
    "finland": {"name": "Finsko", "keywords": ["finland", "finsko", "helsinki"], "base_score": 10},
    "france": {"name": "Francie", "keywords": ["france", "francie", "paris", "parizi"], "base_score": 5},
    "germany": {"name": "Nemecko", "keywords": ["germany", "nemecko", "berlin"], "base_score": 5},
    "greece": {"name": "Recko", "keywords": ["greece", "recko", "athens"], "base_score": 6},
    "hungary": {"name": "Madarsko", "keywords": ["hungary", "madarsko", "budapest"], "base_score": 4},
    "ireland": {"name": "Irsko", "keywords": ["ireland", "irsko", "dublin"], "base_score": 2},
    "italy": {"name": "Italie", "keywords": ["italy", "italie", "rome", "rim"], "base_score": 4},
    "latvia": {"name": "Lotyssko", "keywords": ["latvia", "lotyssko", "riga", "nato eastern flank"], "base_score": 15},
    "lithuania": {"name": "Litva", "keywords": ["lithuania", "litva", "vilnius", "nato eastern flank"], "base_score": 15},
    "luxembourg": {"name": "Lucembursko", "keywords": ["luxembourg", "lucembursko"], "base_score": 2},
    "malta": {"name": "Malta", "keywords": ["malta", "valletta"], "base_score": 3},
    "netherlands": {"name": "Nizozemsko", "keywords": ["netherlands", "nizozemsko", "amsterdam", "the hague"], "base_score": 3},
    "poland": {"name": "Polsko", "keywords": ["poland", "polsko", "warsaw", "poland airspace", "drone incursion"], "base_score": 20},
    "portugal": {"name": "Portugalsko", "keywords": ["portugal", "portugalsko", "lisbon"], "base_score": 2},
    "romania": {"name": "Rumunsko", "keywords": ["romania", "rumunsko", "bucharest", "romania airspace"], "base_score": 15},
    "slovakia": {"name": "Slovensko", "keywords": ["slovakia", "slovensko", "bratislava"], "base_score": 5},
    "slovenia": {"name": "Slovinsko", "keywords": ["slovenia", "slovinsko", "ljubljana"], "base_score": 3},
    "spain": {"name": "Spanelsko", "keywords": ["spain", "spanelsko", "madrid"], "base_score": 3},
    "sweden": {"name": "Svedsko", "keywords": ["sweden", "svedsko", "stockholm"], "base_score": 8},
}

# klicova slova, ktera zvysuji zavaznost vojenske/teroristicke zpravy
SEVERITY_WORDS = {
    "dead": 8, "killed": 10, "death toll": 10, "deaths": 8,
    "civilian casualties": 14, "civilian deaths": 14, "children killed": 18,
    "mass grave": 16, "massacre": 16, "bodies": 8, "corpses": 10,
    "funeral": 5, "mourning": 4,
    "wounded": 6, "injured": 5, "hospitalized": 4,
    "residential building": 9, "apartment block": 9, "hospital hit": 11,
    "school hit": 11, "maternity ward": 12, "shelter hit": 10,
    "invasion": 15, "invaze": 15,
    "mobilization": 12, "mobilisation": 12, "mobilize": 12, "mobilise": 12, "mobilizace": 12,
    "airstrike": 10, "airstrikes": 10, "air strike": 10, "air strikes": 10,
    "missile strike": 10, "missile strikes": 10,
    "military strike": 10, "military strikes": 10,
    "drone strike": 10, "drone strikes": 10,
    "rocket strike": 10, "rocket strikes": 10,
    "missile": 8, "missiles": 8,
    "attack": 6, "attacks": 6, "attacked": 6, "utok": 6,
    "shoot down": 10,
    "explosion": 6, "explosions": 6, "troops": 4,
    "sanction": 2, "sanctions": 2,
    "ceasefire": -8, "peace talks": -6,
    "de-escalation": -8, "de-escalate": -8, "de-escalating": -8,
}

# --- 4. Radiacni/jaderne riziko pro celou Evropu (samostatny modul) ---
RADIATION_BASE_SCORE = 5
RADIATION_HEADLINE_LIMIT = 10

RADIATION_KEYWORDS = [
    "radiation", "radioactive", "radioactivity",
    "nuclear reactor", "nuclear reactors",
    "nuclear power plant", "nuclear power plants",
    "nuclear plant", "nuclear plants",
    "nuclear accident", "nuclear accidents",
    "nuclear incident", "nuclear incidents",
    "meltdown",
    "radiation leak", "radiation leaks",
    "radioactive leak", "radioactive leaks",
    "elevated radiation",
    "radioactive contamination", "radioactive cloud", "radioactive fallout",
    "spent fuel", "nuclear waste", "dirty bomb",
    "iodine tablets",
    "zaporizhzhia", "chornobyl", "chernobyl",
    "iaea", "international atomic energy agency",
    "radiacni", "radioaktivni", "radioaktivita",
    "jaderna elektrarna", "jaderne elektrarny",
    "jaderny reaktor", "jaderne reaktory",
    "jaderna havarie", "jaderny incident",
    "unik radiace", "zvysena radiace",
    "radioaktivni kontaminace", "radioaktivni spad",
    "jaderny odpad", "sujb", "surovy",
]

RADIATION_SEVERITY_WORDS = {
    "meltdown": 20,
    "nuclear accident": 20, "nuclear accidents": 20,
    "nuclear incident": 15, "nuclear incidents": 15,
    "radiation leak": 18, "radiation leaks": 18,
    "radioactive leak": 18, "radioactive leaks": 18,
    "elevated radiation": 15,
    "radioactive contamination": 12,
    "radioactive cloud": 16, "radioactive fallout": 16,
    "evacuation": 10, "evacuations": 10,
    "emergency": 6,
    "shutdown": 6,
    "cooling system": 10,
    "dirty bomb": 18,
    "jaderna havarie": 20, "jaderny incident": 15,
    "unik radiace": 18, "zvysena radiace": 15,
    "radioaktivni kontaminace": 12, "radioaktivni spad": 16,
    "evakuace": 10,
}


def normalize_text(text):
    """Prevede na mala pismena a odstrani diakritiku (Cesko/Česko -> cesko)."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def word_match(keyword, text):
    """Overi, ze 'keyword' je v textu pritomny jako CELE SLOVO."""
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


def load_previous_scores():
    """Nacte skore hotspotu z predchoziho behu (pro trend sipky)."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        return {h["id"]: h["score"] for h in old.get("hotspots", [])}
    except Exception as e:
        print(f"Nepodarilo se nacist predchozi {DATA_FILE}: {e}")
        return {}


def load_previous_radiation_score():
    """Nacte radiacni skore z predchoziho behu (pro trend sipku)."""
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        return old.get("radiation", {}).get("score")
    except Exception as e:
        print(f"Nepodarilo se nacist predchozi radiacni skore: {e}")
        return None


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Nepodarilo se nacist {HISTORY_FILE}: {e}")
        return []


def save_history(history):
    trimmed = history[-MAX_HISTORY_ENTRIES:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def fetch_headlines():
    """Stahne titulky a shrnuti ze vsech RSS kanalu, text normalizuje (bez diakritiky)."""
    items = []
    for url in FEEDS:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:40]:
                raw_text = entry.get("title", "") + " " + entry.get("summary", "")
                text = normalize_text(raw_text)
                items.append({
                    "text": text,
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"Nepodarilo se nacist {url}: {e}")
    return items


def is_threat_related(text):
    return any(word_match(kw, text) for kw in THREAT_KEYWORDS)


def score_hotspot(items, config):
    """
    Zprava se pocita jen tehdy, kdyz obsahuje ZAROVEN nazev zeme/oblasti
    A ZAROVEN alespon jedno slovo z THREAT_KEYWORDS.
    """
    score = config["base_score"]
    matched = []

    for item in items:
        has_country = any(word_match(kw, item["text"]) for kw in config["keywords"])
        if not has_country:
            continue
        if not is_threat_related(item["text"]):
            continue

        matched.append(item)
        severity = 3
        for word, weight in SEVERITY_WORDS.items():
            if word_match(word, item["text"]):
                severity += weight
        score += severity

    score = max(0, min(100, score))
    limit = config.get("headline_limit", 5)
    return score, matched[:limit]


def score_radiation(items):
    """
    Samostatne radiacni/jaderne skore pro celou Evropu - nezavisi na zadne
    konkretni zemi, jen na tom, ze zprava obsahuje radiacni/jaderne klicove
    slovo (napr. unik radiace, jaderna havarie, Zaporozska elektrarna, IAEA).
    """
    score = RADIATION_BASE_SCORE
    matched = []

    for item in items:
        if not any(word_match(kw, item["text"]) for kw in RADIATION_KEYWORDS):
            continue

        matched.append(item)
        severity = 3
        for word, weight in RADIATION_SEVERITY_WORDS.items():
            if word_match(word, item["text"]):
                severity += weight
        score += severity

    score = max(0, min(100, score))
    return score, matched[:RADIATION_HEADLINE_LIMIT]


def level_for_score(score):
    if score >= 75:
        return "kriticke", "#9C3B37"
    if score >= 45:
        return "zvysene", "#C98A3B"
    if score >= 25:
        return "mirne", "#C98A3B"
    return "nizke", "#4C8C6B"


def trend_for(score, prev_score):
    if prev_score is None:
        return "novy", None
    diff = score - prev_score
    if diff > 0:
        return "up", diff
    if diff < 0:
        return "down", diff
    return "same", 0


def main():
    prev_scores = load_previous_scores()
    prev_radiation_score = load_previous_radiation_score()
    items = fetch_headlines()
    results = []

    for hotspot_id, config in HOTSPOTS.items():
        score, matched = score_hotspot(items, config)
        level, color = level_for_score(score)
        trend, diff = trend_for(score, prev_scores.get(hotspot_id))
        results.append({
            "id": hotspot_id,
            "name": config["name"],
            "score": score,
            "level": level,
            "color": color,
            "trend": trend,
            "score_change": diff,
            "headlines": [{"title": m["title"], "link": m["link"]} for m in matched],
        })

    overall = round(sum(r["score"] for r in results) / len(results))

    radiation_score, radiation_matched = score_radiation(items)
    radiation_level, radiation_color = level_for_score(radiation_score)
    radiation_trend, radiation_diff = trend_for(radiation_score, prev_radiation_score)
    radiation_result = {
        "score": radiation_score,
        "level": radiation_level,
        "color": radiation_color,
        "trend": radiation_trend,
        "score_change": radiation_diff,
        "headlines": [{"title": m["title"], "link": m["link"]} for m in radiation_matched],
    }

    generated_at = datetime.now(timezone.utc).isoformat()

    output = {
        "generated_at": generated_at,
        "overall_score": overall,
        "hotspots": results,
        "radiation": radiation_result,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history = load_history()
    history.append({
        "timestamp": generated_at,
        "overall_score": overall,
        "radiation_score": radiation_score,
        "scores": {r["id"]: r["score"] for r in results},
    })
    save_history(history)

    print(f"Hotovo. {DATA_FILE} a {HISTORY_FILE} aktualizovany.")


if __name__ == "__main__":
    main()
