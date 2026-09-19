"""
EU War Radar - denni sber zprav a vypocet skore rizika.
Spousti se automaticky pres GitHub Actions (viz .github/workflows/update.yml).
Nevyzaduje zadny platny API klic - pouziva verejne RSS kanaly.
Ceska republika ma prioritu - vic zdroju, vic klicovych slov, vic zobrazenych zprav.

DULEZITE - presne celoslovni hledani:
Vsechna klicova slova se hledaji jako CELA SLOVA (regex s hranici \\b), ne jako
libovolny podretezec.

DULEZITE - konkretni vojenske fraze misto nejednoznacnych slov:
Bare slova jako "strike"/"strikes" se NEPOUZIVAJI (kolize s pocasim, stavkami).

Text se pred porovnavanim normalizuje (mala pismena + odstraneni diakritiky).

Kazde spusteni take uklada zaznam do history.json pro graf vyvoje v case.
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
    # opravena adresa - puvodni /rss/hlavni-zpravy jiz neexistuje po redesignu webu
    "https://ct24.ceskatelevize.cz/rss/tema/vyber-redakce-84313",
]

# --- 2. Klicova slova, ktera musi byt ve zprave PRITOMNA (jako CELE SLOVO), ---
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

# klicova slova, ktera zvysuji zavaznost jednotlive zpravy (uz relevantni zpravy)
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
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        return {h["id"]: h["score"] for h in old.get("hotspots", [])}
    except Exception as e:
        print(f"Nepodarilo se nacist predchozi {DATA_FILE}: {e}")
        return {}


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
    generated_at = datetime.now(timezone.utc).isoformat()

    output = {
        "generated_at": generated_at,
        "overall_score": overall,
        "hotspots": results,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history = load_history()
    history.append({
        "timestamp": generated_at,
        "overall_score": overall,
        "scores": {r["id"]: r["score"] for r in results},
    })
    save_history(history)

    print(f"Hotovo. {DATA_FILE} a {HISTORY_FILE} aktualizovany.")


if __name__ == "__main__":
    main()
