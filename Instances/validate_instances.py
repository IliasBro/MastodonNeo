"""
Instanz-Validator
================================
Validiert eine Liste von Mastodon-Instanzen technisch und erstellt
eine bereinigte JSON-Datei mit nur erreichbaren Instanzen.

Inspiriert vom Validierungsansatz von Wiegmann et al. (2024), jedoch
als eigenständiges Script direkt im MastodonNeo-Repository integriert,
ohne externes Repository oder manuelle Bug-Fixes.

Geprüft wird:
  1. Nodeinfo-Schnittstelle  → /.well-known/nodeinfo
  2. Instanz-Aktivitätsdaten → /api/v1/instance/activity
  3. Öffentliche Timeline    → /api/v1/timelines/public

Nur Instanzen die alle drei Endpunkte erfolgreich beantworten werden
als valide eingestuft. Kriterium 3 stellt sicher, dass die Instanz
beim Crawlen mit Mastodoner keine 422-Fehler liefert.

Verwendung:
  python Instances/validate_instances.py

Voraussetzungen:
  pip install requests
"""

import json
import os
import time
import requests

# ── Konfiguration ──────────────────────────────────────────────────────────────
CANDIDATES_FILE = "Data/InstancesNotValidated.json"
OUTPUT_FILE     = "Data/InstancesValidated.json"
TIMEOUT         = 10
PAUSE_BETWEEN   = 0.5

HEADERS = {
    "User-Agent": "MastodonNeo-Validator/1.0 (Bachelorarbeit ZHAW; Research)"
}

# ── Validierungsfunktionen ─────────────────────────────────────────────────────
def check_nodeinfo(instance: str) -> bool:
    """
    Prüft ob die Nodeinfo-Schnittstelle vorhanden ist.
    Entspricht mastodon.instance_nodeinfo() im Wiegmann-Crawler.
    """
    try:
        r = requests.get(
            f"https://{instance}/.well-known/nodeinfo",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code != 200:
            return False
        data = r.json()
        links = data.get("links", [])
        if not links:
            return False
        nodeinfo_url = links[0].get("href", "")
        if not nodeinfo_url:
            return False
        r2 = requests.get(nodeinfo_url, headers=HEADERS, timeout=TIMEOUT)
        return r2.status_code == 200
    except Exception:
        return False


def check_activity(instance: str) -> bool:
    """
    Prüft ob Instanz-Aktivitätsdaten verfügbar sind.
    Entspricht mastodon.instance_activity() im Wiegmann-Crawler.
    """
    try:
        r = requests.get(
            f"https://{instance}/api/v1/instance/activity",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, list) and len(data) > 0
    except Exception:
        return False


def check_public_timeline(instance: str) -> bool:
    """
    Prüft ob die öffentliche Timeline verfügbar ist.
    Entspricht dem Endpunkt den Mastodoner beim Crawlen verwendet.
    Instanzen die diesen Endpunkt deaktiviert haben liefern HTTP 422.
    """
    try:
        r = requests.get(
            f"https://{instance}/api/v1/timelines/public",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, list)
    except Exception:
        return False


def validate_instance(instance: str) -> tuple[bool, str]:
    """
    Validiert eine Instanz anhand aller drei Kriterien.
    """
    if not check_nodeinfo(instance):
        return False, "Keine Nodeinfo"
    if not check_activity(instance):
        return False, "Keine Aktivitätsdaten"
    if not check_public_timeline(instance):
        return False, "Öffentliche Timeline deaktiviert (HTTP 422)"
    return True, "OK"


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Instanz-Validator — MastodonNeo")
    print("  Kriterien: Nodeinfo + Aktivitätsdaten + Öffentliche Timeline")
    print("=" * 60)

    if not os.path.exists(CANDIDATES_FILE):
        print(f"\nFEHLER: {CANDIDATES_FILE} nicht gefunden.")
        return

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"\n{len(candidates)} Kandidaten geladen aus {CANDIDATES_FILE}\n")

    valid   = []
    invalid = []

    for i, instance in enumerate(candidates):
        print(f"[{i+1:02d}/{len(candidates)}] {instance:<40}", end=" ", flush=True)
        ok, reason = validate_instance(instance)

        if ok:
            valid.append(instance)
            print("✓  OK")
        else:
            invalid.append((instance, reason))
            print(f"✗  {reason}")

        time.sleep(PAUSE_BETWEEN)

    print("\n" + "=" * 60)
    print(f"  Ergebnis: {len(valid)} validiert / {len(invalid)} ausgeschlossen")
    print("=" * 60)

    if invalid:
        print("\nAusgeschlossene Instanzen:")
        for inst, reason in invalid:
            print(f"  ✗  {inst:<40} {reason}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False)

    print(f"\n  Gespeichert: {OUTPUT_FILE} ({len(valid)} Instanzen)")


if __name__ == "__main__":
    main()