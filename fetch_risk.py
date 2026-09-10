"""
EU War Radar - denni sber zprav a vypocet skore rizika.
Spousti se automaticky jednou denne pres GitHub Actions (viz .github/workflows/update.yml).
Nevyzaduje zadny platny API klic - pouziva verejne RSS kanaly.
"""

import json
from datetime import datetime, timezone
import feedparser

# --- 1. Zdroje zprav (verejne RSS kanaly, zadny API klic potreba) ---
FEEDS = [
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.nato.int/cps/en/natohq/news.rss",
    "https://apnews.com/hub/world-news.rss",
    "https://understandingwar.org/feed",
]

# --- 2. Sledovane oblasti a jejich klicova slova ---
HOTSPOTS = {
    # --- Aktivni konfliktni a hranicni zony (nejsou clenove EU) ---
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

    # --- Vsech 27 clenskych statu EU ---
    "austria": {"name": "Rakousko", "keywords": ["austria", "rakousko", "vienna", "vidnen"], "base_score": 3},
    "belgium": {"name": "Belgie", "keywords": ["belgium", "belgie", "brussels", "brusel"], "base_score": 3},
    "bulgaria": {"name": "Bulharsko", "keywords": ["bulgaria", "bulharsko", "sofia"], "base_score": 5},
    "croatia": {"name": "Chorvatsko", "keywords": ["croatia", "chorvatsko", "zagreb"], "base_score": 5},
    "cyprus": {"name": "Kypr", "keywords": ["cyprus", "kypr", "nicosia"], "base_score": 8},
    "czechia": {"name": "Cesko", "keywords": ["czech republic", "czechia", "cesko", "prague", "praha"], "base_score": 3},
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

# klicova slova, ktera zvysuji zavaznost jednotlive zpravy
SEVERITY_WORDS = {
    "invasion": 15, "invaze": 15, "mobiliz": 12, "airstrike": 10, "missile": 8,
    "attack": 6, "utok": 6, "strike": 6, "shoot down": 10, "casualties": 6,
    "explosion": 6, "troops": 4, "sanction": 2, "ceasefire": -8, "peace talks": -6,
    "de-escalat": -8,
}


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


def score_hotspot(items, config):
    """Spocita skore rizika 0-100 pro jednu oblast na zaklade najdenych zprav."""
    score = config["base_score"]
    matched = []

    for item in items:
        if any(kw in item["text"] for kw in config["keywords"]):
            matched.append(item)
            severity = 3
            for word, weight in SEVERITY_WORDS.items():
                if word in item["text"]:
                    severity += weight
            score += severity

    score = max(0, min(100, score))
    return score, matched[:5]


def level_for_score(score):
    if score >= 75:
        return "kriticke", "#9C3B37"
    if score >= 45:
        return "zvysene", "#C98A3B"
    if score >= 25:
        return "mirne", "#C98A3B"
    return "nizke", "#4C8C6B"


def main():
    items = fetch_headlines()
    results = []

    for hotspot_id, config in HOTSPOTS.items():
        score, matched = score_hotspot(items, config)
        level, color = level_for_score(score)
        results.append({
            "id": hotspot_id,
            "name": config["name"],
            "score": score,
            "level": level,
            "color": color,
            "headlines": [{"title": m["title"], "link": m["link"]} for m in matched],
        })

    overall = round(sum(r["score"] for r in results) / len(results))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall,
        "hotspots": results,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Hotovo. data.json aktualizovan.")


if __name__ == "__main__":
    main()
