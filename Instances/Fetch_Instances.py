"""
Instanz-Abruf — MastodonNeo
==============================
Ruft wissenschaftliche Mastodon-Instanzen von instances.social ab
und speichert die geeignetsten als InstancesNotValidated.json.

Voraussetzungen:
  pip install requests python-dotenv

  .env mit:
    INSTANCES_SOCIAL_TOKEN=dein_token_hier

Verwendung:
  python Instances/fetch_instances.py
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Konfiguration ──────────────────────────────────────────────────────────────
TOKEN       = os.getenv("INSTANCES_SOCIAL_TOKEN", "")
OUTPUT_FILE = "Data/InstancesNotValidated.json"
MAX_RESULTS = 60
API_COUNT   = 500

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent":    "MastodonNeo-InstanceFetcher/1.0 (Bachelorarbeit ZHAW; Research)"
}

KEYWORDS = [
    "science", "research", "academic", "university", "scholar",
    "phd", "education", "stem", "physics", "biology", "chemistry",
    "mathematics", "data science", "engineering",
    "computer science", "library", "wissenschaft",
    "forschung", "akademie", "hochschule", "universität",
]

# ── Hilfsfunktion: Wissenschaftsbezug prüfen ──────────────────────────────────
def is_scientific(instance: dict) -> bool:
    """
    Prüft ob eine Instanz wissenschaftlichen Bezug hat.
    Durchsucht Name, Domain und Beschreibung nach definierten Keywords.
    """
    info = instance.get("info") or {}
    text = " ".join([
        instance.get("name", "")                    or "",
        instance.get("domain", "")                  or "",
        info.get("short_description", "")           or "",
        info.get("full_description", "")            or "",
    ]).lower()
    return any(kw in text for kw in KEYWORDS)

# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Instanz-Abruf — MastodonNeo")
    print("=" * 60)

    if not TOKEN:
        print("\nFEHLER: INSTANCES_SOCIAL_TOKEN nicht in .env gesetzt.")
        print("Token unter https://instances.social/admin/applications erstellen.")
        return

    print(f"\nRufe instances.social API ab ...")

    try:
        response = requests.get(
            "https://instances.social/api/1.0/instances/list",
            headers=HEADERS,
            params={
                "count":        API_COUNT,
                "include_dead": "false",
                "include_down": "false",
                "sort_by":      "users",
                "sort_order":   "desc",
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\nFEHLER beim API-Aufruf: {e}")
        return

    all_instances = response.json().get("instances", [])
    print(f"{len(all_instances)} Instanzen von API erhalten.")

    # Wissenschaftliche Instanzen filtern
    scientific = [i for i in all_instances if is_scientific(i)]
    print(f"{len(scientific)} Instanzen nach Keyword-Filter.")
    print(f"Nehme Top {MAX_RESULTS} nach Nutzerzahl.")

    # Domains extrahieren und speichern
    domains = [i.get("name") for i in scientific[:MAX_RESULTS] if i.get("name")]

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(domains, f, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"  Ergebnis: {len(domains)} Instanzen gespeichert")
    print(f"{'=' * 60}")
    print(f"\n✓  Gespeichert: {OUTPUT_FILE}")
    print(f"\nNächster Schritt: python Instances/validate_instances.py")


if __name__ == "__main__":
    main()