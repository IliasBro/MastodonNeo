"""
Mastodon Datenerhebung
- Instanzen werden aus Instances/Top40Instances.json gelesen
- Toots werden in Data/toots_alle_instanzen.jsonl gespeichert
Verwendung: python collect_toots.py
Voraussetzungen: pip install mastodoner
"""

from mastodoner import Crawler
import json
import time
import os

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTANCES_FILE         = "Instances/Top40Instances.json"
OUTPUT_FILE            = "Data/Mastodoner.jsonl"
ERROR_LOG              = "Data/error_Mastodoner_Log.txt"
MAX_POSTS_PER_INSTANCE = 200   # Anzahl Toots pro Instanz
PAUSE_BETWEEN          = 2     # Sekunden Pause zwischen Instanzen (Rate Limit)

# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    # Instanzen aus JSON-Datei lesen
    with open(INSTANCES_FILE, 'r', encoding='utf-8') as f:
        instances = json.load(f)
    print(f"{len(instances)} Instanzen geladen aus {INSTANCES_FILE}")

    # Output-Ordner erstellen falls nicht vorhanden
    os.makedirs("../Data", exist_ok=True)

    crawler = Crawler()
    total = 0
    errors = []

    # Bestehende Datei nicht überschreiben sondern anhängen
    mode = 'a' if os.path.exists(OUTPUT_FILE) else 'w'

    with open(OUTPUT_FILE, mode, encoding='utf-8') as f:
        for i, instance in enumerate(instances):
            print(f"[{i+1}/{len(instances)}] Crawle {instance}...", end=' ', flush=True)
            try:
                posts = crawler.instance_timeline(instance, max_limit=MAX_POSTS_PER_INSTANCE)
                count = 0
                for post in posts:
                    f.write(json.dumps(post, ensure_ascii=False) + '\n')
                    count += 1
                total += count
                print(f"{count} Toots gesammelt (Total: {total})")
            except Exception as e:
                print(f"FEHLER: {e}")
                errors.append(f"{instance}: {e}")

            # Pause um Rate Limits zu respektieren
            time.sleep(PAUSE_BETWEEN)

    # Fehlerlog schreiben
    if errors:
        with open(ERROR_LOG, 'w', encoding='utf-8') as f:
            for err in errors:
                f.write(err + '\n')
        print(f"\n{len(errors)} Instanzen fehlgeschlagen — Details in {ERROR_LOG}")

    print(f"\nFertig! {total} Toots gespeichert in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
