"""
EU War Radar - denni sber zprav a vypocet skore rizika.
Spousti se automaticky jednou denne pres GitHub Actions (viz .github/workflows/update.yml).
Nevyzaduje zadny platny API klic - pouziva verejne RSS kanaly.
"""

import json
import re
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
    "ukraine": {
        "name": "Ukrajina",
        "keywords": ["ukraine", "ukrajina", "kyiv", "kyjev", "donetsk", "zelensky", "putin"],
        "base_score": 60,  # dlouhodoby zakladni stav - aktivni valka
    },
    "baltics": {
        "name": "Pobalti / Polsko / Rumunsko",
        "keywords": ["baltic", "pobalti", "poland airspace", "romania airspace",
                     "nato eastern flank", "estonia", "latvia", "lithuania", "drone incursion"],
        "base_score": 35,
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
            severity = 3  # zakladni prirustek za zminku
            for word, weight in SEVERITY_WORDS.items():
                if word in item["text"]:
                    severity += weight
            score += severity

    score = max(0, min(100, score))
    return score, matched[:5]  # vratime max 5 nejrelevantnejsich zprav


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

    print("Hotovo.data.json aktualizovan.")


if __name__ == "__main__":
    main()
