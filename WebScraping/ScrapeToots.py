"""
Mastodon Web Scraper (ohne Authentifizierung)
Nutzt den öffentlichen /api/v1/timelines/public Endpunkt ohne API-Schlüssel.
Dies ist die Browser-äquivalente Methode: dieselben Daten die ein Browser
beim Besuch von /public lädt, jedoch direkt als JSON abgerufen.

Verwendung: python scrape_toots.py
Voraussetzungen: pip install requests
"""

import requests
import json
import time
import os

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTANCES_FILE  = "Instances/Top40Instances.json"
OUTPUT_FILE     = "Data/toots_scraped.jsonl"
ERROR_LOG       = "Data/fehler_scraping.txt"
MAX_TOOTS       = 200      # Maximale Toots pro Instanz
PAUSE_BETWEEN   = 3        # Sekunden Pause zwischen Instanzen

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MastodonResearchScraper/1.0; Bachelorarbeit ZHAW)"
}

# ── Scraper ────────────────────────────────────────────────────────────────────
def scrape_instance(instance: str, max_toots: int) -> list:
    """
    Ruft die öffentliche Timeline einer Mastodon-Instanz ohne Authentifizierung ab.
    Mastodon stellt /api/v1/timelines/public als öffentlichen Endpunkt bereit —
    dieselben Daten die ein Browser beim Laden von /public erhält.
    """
    toots = []
    url = f"https://{instance}/api/v1/timelines/public"
    params = {"limit": 40}

    while len(toots) < max_toots:
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)

            if response.status_code == 200:
                batch = response.json()
                if not batch:
                    break

                for toot in batch:
                    # scrape_source markiert die Herkunft
                    toot["scrape_source"] = "public_endpoint_no_auth"
                    toot["scrape_instance"] = instance
                    toots.append(toot)

                # Pagination — nächste Seite via max_id
                last_id = batch[-1]["id"]
                params["max_id"] = last_id

                if len(batch) < 40:
                    break

            elif response.status_code == 401:
                print(f"    Instanz erfordert Authentifizierung")
                break
            elif response.status_code == 403:
                print(f"    Öffentliche Timeline deaktiviert")
                break
            else:
                print(f"    HTTP {response.status_code}")
                break

            time.sleep(1)

        except requests.exceptions.ConnectionError:
            print(f"    Verbindungsfehler")
            break
        except requests.exceptions.Timeout:
            print(f"    Timeout")
            break
        except Exception as e:
            print(f"    Fehler: {e}")
            break

    return toots[:max_toots]


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
        instances = json.load(f)
    print(f"{len(instances)} Instanzen geladen")

    os.makedirs("../Data", exist_ok=True)

    total = 0
    errors = []
    mode = "a" if os.path.exists(OUTPUT_FILE) else "w"

    with open(OUTPUT_FILE, mode, encoding="utf-8") as f:
        for i, instance in enumerate(instances):
            print(f"[{i+1}/{len(instances)}] Scrape {instance}...", end=" ", flush=True)
            try:
                toots = scrape_instance(instance, MAX_TOOTS)
                for toot in toots:
                    f.write(json.dumps(toot, ensure_ascii=False) + "\n")
                total += len(toots)
                print(f"{len(toots)} Toots (Total: {total})")
            except Exception as e:
                print(f"FEHLER: {e}")
                errors.append(f"{instance}: {e}")

            time.sleep(PAUSE_BETWEEN)

    if errors:
        with open(ERROR_LOG, "w", encoding="utf-8") as f:
            for err in errors:
                f.write(err + "\n")
        print(f"\n{len(errors)} Instanzen fehlgeschlagen — Details in {ERROR_LOG}")

    print(f"\nFertig! {total} Toots gespeichert in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()