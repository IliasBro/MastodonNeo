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
from urllib.parse import urlparse

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTANCES_FILE  = "Instances/InstancesValidated.json"
OUTPUT_FILE     = "Data/ScrapedData_PublicApi.jsonl"
BOOST_FILE      = "Data/BoostData_PublicApi.jsonl"
ERROR_LOG       = "Data/fehler_scraping.txt"
MAX_TOOTS       = 200
PAUSE_BETWEEN   = 3
PAUSE_BOOST     = 0.3

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


# ── Boost-Daten via reblogged_by abrufen ──────────────────────────────────────
def fetch_boost_data(toots: list) -> None:
    """
    Fragt für alle Toots mit reblogs_count > 0 den reblogged_by-Endpunkt ab
    und speichert die Ergebnisse in Data/BoostData_PublicApi.jsonl.
    Duplikate innerhalb des Datensatzes werden automatisch übersprungen.
    """
    candidates = [
        t for t in toots
        if t.get("reblogs_count", 0) > 0 and t.get("uri")
    ]

    seen_uris = set()
    unique_candidates = []
    for t in candidates:
        uri = t.get("uri", "")
        if uri not in seen_uris:
            seen_uris.add(uri)
            unique_candidates.append(t)

    print(f"\nSuche Boost-Daten für {len(unique_candidates)} eindeutige Toots...")

    found   = 0
    skipped = 0

    with open(BOOST_FILE, "w", encoding="utf-8") as out:
        for toot in unique_candidates:
            uri      = toot["uri"]
            parts    = uri.rstrip("/").split("/")
            toot_id  = parts[-1] if parts else ""
            instance = urlparse(uri).netloc

            if not instance or not toot_id:
                skipped += 1
                continue

            url = f"https://{instance}/api/v1/statuses/{toot_id}/reblogged_by"
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code == 200:
                    boosters = r.json()
                    if boosters and isinstance(boosters, list):
                        entry = {
                            "toot_uri": uri,
                            "toot_id":  toot.get("id"),
                            "boosters": [
                                {
                                    "handle":       b.get("acct"),
                                    "display_name": b.get("display_name"),
                                    "url":          b.get("url"),
                                }
                                for b in boosters
                            ]
                        }
                        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        found += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

            time.sleep(PAUSE_BOOST)

    print(f"Boost-Daten: {found} Toots mit Boosts, {skipped} ohne.")
    print(f"Gespeichert in: {BOOST_FILE}")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
        instances = json.load(f)
    print(f"{len(instances)} Instanzen geladen")

    os.makedirs("Data", exist_ok=True)

    total      = 0
    errors     = []
    all_toots  = []
    mode = "a" if os.path.exists(OUTPUT_FILE) else "w"

    with open(OUTPUT_FILE, mode, encoding="utf-8") as f:
        for i, instance in enumerate(instances):
            print(f"[{i+1}/{len(instances)}] Scrape {instance}...", end=" ", flush=True)
            try:
                toots = scrape_instance(instance, MAX_TOOTS)
                for toot in toots:
                    f.write(json.dumps(toot, ensure_ascii=False) + "\n")
                all_toots.extend(toots)
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

    # Boost-Daten abrufen
    fetch_boost_data(all_toots)


if __name__ == "__main__":
    main()