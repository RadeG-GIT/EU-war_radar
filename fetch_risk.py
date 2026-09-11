"""
EU War Radar - denni sber zprav a vypocet skore rizika.
Spousti se automaticky pres GitHub Actions (viz .github/workflows/update.yml).
Nevyzaduje zadny platny API klic - pouziva verejne RSS kanaly.
Ceska republika ma prioritu - vic zdroju, vic klicovych slov, vic zobrazenych zprav.

DULEZITE: zprava se pocita jen tehdy, kdyz obsahuje ZAROVEN nazev zeme/oblasti
A ZAROVEN nektere z klicovych slov souvisejicich s valkou/terorismem/nasilim
(viz THREAT_KEYWORDS).

Kazde spusteni take uklada zaznam do history.json (datum + skore vsech oblasti),
aby sel na webu zobrazit graf vyvoje v case.
"""

import json
import os
from datetime import datetime, timezone
import feedparser

DATA_FILE = "data.json"
HISTORY_FILE = "history.json"
MAX_HISTORY_ENTRIES = 200  # ochrana proti neomezenemu rustu souboru

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
    "https://ct24.ceskatelevize.cz/rss/hlavni-zpravy",
]

# --- 2. Klicova slova, ktera musi byt ve zprave PRITOMNA, aby se vubec pocitala. ---
THREAT_KEYWORDS = [
    "war", "valka", "invasion", "invaze", "military", "vojensk", "armed forces",
    "armada", "troops", "vojaci", "nato", "defense", "obrana", "mobilization",
    "mobilizace", "coup", "puc",
    "attack", "utok", "strike", "airstrike", "missile", "raketa", "bomb",
    "explosion", "vybuch", "shooting", "strelba", "clash", "strety",
    "riot", "nepokoje", "uprising", "povstani", "insurgent", "povstalci",
    "militia", "milice",
    "terroris", "terorism", "extremist", "hostage", "rukojmi",
    "security threat", "bezpecnostni hrozba", "sabotage", "sabotaz",
    "cyberattack", "kyberneticky utok", "espionage", "spionaz",
    "drone", "dron", "airspace", "vzdusny prostor",
    "casualties", "obeti", "killed", "zabit", "wounded", "zranen", "dead",
    "death toll",
    "ceasefire", "sanctions", "sankce", "peace talks",
]

# --- 3. Sledovane oblasti a jejich klicova slova (nazvy zemi/oblasti) ---
HOTSPOTS = {
    "czechia": {
        "name": "Ceska republika",
        "keywords": [
            "czech republic", "czechia", "cesko", "ceska republika",
            "prague", "praha", "armada cr", "acr",
            "nato cesko", "bezpecnostni informacni sluzba", "bis",
            "vojenske zpravodajstvi", "kyberneticky utok cesko",
            "cinska spionaz", "ruska spionaz", "rusko cesko",
            "drony cesko", "hybridni valka cesko", "dezinformace cesko",
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

SEVERITY_WORDS = {
    "dead": 8, "killed": 10, "death toll": 10, "deaths": 8,
    "civilian casualties": 14, "civilian deaths": 14, "children killed": 18,
    "mass grave": 16, "massacre": 16, "bodies": 8, "corpses": 10,
    "funeral": 5, "mourning": 4,
    "wounded": 6, "injured": 5, "hospitalized": 4,
    "residential building": 9, "apartment block": 9, "hospital hit": 11,
    "school hit": 11, "maternity ward": 12, "shelter hit": 10,
    "invasion": 15, "invaze": 15, "mobiliz": 12, "airstrike": 10, "missile": 8,
    "attack": 6, "utok": 6, "strike": 6, "shoot down": 10,
    "explosion": 6, "troops": 4, "sanction": 2,
    "ceasefire": -8, "peace talks": -6, "de-escalat": -8,
}


def load_previous_scores():
    """Nacte skore z predchoziho behu (pokud existuje), aby slo spocitat trend."""
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
    """Nacte dosavadni historii skore (pokud existuje)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Nepodarilo se nacist {HISTORY_FILE}: {e}")
        return []


def save_history(history):
    """Ulozi historii, orizne na max. povoleny pocet zaznamu."""
    trimmed = history[-MAX_HISTORY_ENTRIES:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def fetch_headlines():
    """Stahne titulky a shrnuti ze vsech RSS kanalu."""
    items = []
    for url in FEEDS:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:40]:
                text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
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
    return any(kw in text for kw in THREAT_KEYWORDS)


def score_hotspot(items, config):
    """
    Zprava se pocita jen tehdy, kdyz obsahuje ZAROVEN nazev zeme/oblasti
    A ZAROVEN alespon jedno slovo z THREAT_KEYWORDS.
    """
    score = config["base_score"]
    matched = []

    for item in items:
        has_country = any(kw in item["text"] for kw in config["keywords"])
        if not has_country:
            continue
        if not is_threat_related(item["text"]):
            continue

        matched.append(item)
        severity = 3
        for word, weight in SEVERITY_WORDS.items():
            if word in item["text"]:
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

    # ulozeni zaznamu do historie pro graf vyvoje
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
