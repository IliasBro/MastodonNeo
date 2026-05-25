"""
Mastodon Datenerhebung
- Instanzen werden aus Data/InstancesValidated.json gelesen
- Toots werden in Data/ScrapedData_Mastodoner.jsonl gespeichert
- Referenzierte Toots (REPLY_TO-Ziele) werden nachgeladen
- Boost-Daten (reblogged_by) werden in Data/BoostData.jsonl gespeichert
Verwendung: python Mastodoner.py
Voraussetzungen: pip install mastodoner requests
"""

from mastodoner import Crawler
import json
import time
import os
import requests
from urllib.parse import urlparse

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTANCES_FILE         = "Data/InstancesValidated.json"
OUTPUT_FILE            = "Data/ScrapedData_Mastodoner.jsonl"
BOOST_FILE             = "Data/BoostData.jsonl"
ERROR_LOG              = "Data/error_Mastodoner_Log.txt"
MAX_POSTS_PER_INSTANCE = 200
PAUSE_BETWEEN          = 2
PAUSE_REPLY_FETCH      = 0.5
PAUSE_BOOST_FETCH      = 0.3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MastodonResearchScraper/1.0; Bachelorarbeit ZHAW)"
}

# ── Hilfsfunktion: Einzelnen Toot per REST-API nachladen ──────────────────────
def fetch_single_toot(instance: str, toot_id: str) -> dict | None:
    """
    Lädt einen einzelnen Toot direkt über die Mastodon REST-API.
    Verwendet den öffentlichen Endpunkt /api/v1/statuses/:id
    ohne Authentifizierung.
    """
    url = f"https://{instance}/api/v1/statuses/{toot_id}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

# ── Hilfsfunktion: Fehlende Reply-Toots nachladen ────────────────────────────
def fetch_missing_replies(toots: list) -> list:
    """
    Identifiziert Toots, auf die geantwortet wird, die aber nicht im
    Datensatz vorhanden sind. Lädt diese direkt von ihrer Instanz nach,
    damit REPLY_TO-Kanten in Neo4j vollständig aufgelöst werden können.
    """
    existing_ids = {t["id"] for t in toots}
    extra_toots = []
    fetched_ids = set()

    print(f"\nSuche nach fehlenden Reply-Toots...")
    missing_count = sum(
        1 for t in toots
        if t.get("in_reply_to_id") and t["in_reply_to_id"] not in existing_ids
    )
    print(f"{missing_count} fehlende Referenzen gefunden.")

    fetched = 0
    failed = 0

    for toot in toots:
        reply_id = toot.get("in_reply_to_id")
        if not reply_id:
            continue
        if reply_id in existing_ids or reply_id in fetched_ids:
            continue

        # Instanz von der gecrawlt wurde verwenden (nicht Heiminstanz des Toots!)
        # Die in_reply_to_id ist eine lokale ID der crawlenden Instanz
        instance = toot.get("_crawled_from_instance", "")
        if not instance:
            continue

        # Original-Toot nachladen
        original = fetch_single_toot(instance, reply_id)
        if original:
            extra_toots.append(original)
            fetched_ids.add(reply_id)
            existing_ids.add(reply_id)
            fetched += 1
        else:
            failed += 1

        time.sleep(PAUSE_REPLY_FETCH)

    print(f"Nachgeladen: {fetched} Toots, nicht gefunden: {failed}")
    return extra_toots

# ── Hilfsfunktion: Boost-Daten via reblogged_by abrufen ───────────────────────
def fetch_boost_data(toots: list) -> None:
    """
    Fragt für alle Toots mit reblogs_count > 0 den reblogged_by-Endpunkt ab
    und speichert die Ergebnisse in Data/BoostData.jsonl.
    Duplikate innerhalb des Datensatzes werden automatisch übersprungen.
    """
    candidates = [
        t for t in toots
        if t.get("reblogs_count", 0) > 0 and t.get("uri")
    ]

    # Duplikate (gleiche URI mehrfach durch Föderierung) entfernen
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

            time.sleep(PAUSE_BOOST_FETCH)

    print(f"Boost-Daten: {found} Toots mit Boosts, {skipped} ohne.")
    print(f"Gespeichert in: {BOOST_FILE}")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    # Instanzen aus JSON-Datei lesen
    with open(INSTANCES_FILE, 'r', encoding='utf-8') as f:
        instances = json.load(f)
    print(f"{len(instances)} Instanzen geladen aus {INSTANCES_FILE}")

    os.makedirs("Data", exist_ok=True)

    crawler = Crawler()
    all_toots = []
    total = 0
    errors = []

    # ── Schritt 1: Toots von allen Instanzen sammeln ──────────────────────────
    for i, instance in enumerate(instances):
        print(f"[{i+1}/{len(instances)}] Crawle {instance}...", end=' ', flush=True)
        try:
            posts = crawler.instance_timeline(instance, max_limit=MAX_POSTS_PER_INSTANCE)
            count = 0
            for post in posts:
                post["_crawled_from_instance"] = instance
                all_toots.append(post)
                count += 1
            total += count
            print(f"{count} Toots gesammelt (Total: {total})")
        except Exception as e:
            print(f"FEHLER: {e}")
            errors.append(f"{instance}: {e}")

        time.sleep(PAUSE_BETWEEN)

    # ── Schritt 2: Fehlende Reply-Toots nachladen ─────────────────────────────
    extra_toots = fetch_missing_replies(all_toots)
    all_toots.extend(extra_toots)
    total += len(extra_toots)
    print(f"Total nach Nachladen: {total} Toots")

    # ── Schritt 3: Alle Toots in Datei schreiben ──────────────────────────────
    mode = 'a' if os.path.exists(OUTPUT_FILE) else 'w'
    with open(OUTPUT_FILE, mode, encoding='utf-8') as f:
        for toot in all_toots:
            f.write(json.dumps(toot, ensure_ascii=False) + '\n')

    # ── Schritt 4: Boost-Daten abrufen ────────────────────────────────────────
    fetch_boost_data(all_toots)

    # Fehlerlog schreiben
    if errors:
        with open(ERROR_LOG, 'w', encoding='utf-8') as f:
            for err in errors:
                f.write(err + '\n')
        print(f"\n{len(errors)} Instanzen fehlgeschlagen — Details in {ERROR_LOG}")

    print(f"\nFertig! {total} Toots gespeichert in {OUTPUT_FILE}")
    print(f"Davon {len(extra_toots)} nachgeladene Reply-Toots.")


if __name__ == "__main__":
    main()