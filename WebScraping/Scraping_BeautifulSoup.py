"""
Mastodon Web Scraper — Versuch mit BeautifulSoup (HTML-Parsing)
================================================================
Dieser Scraper versucht, Mastodon-Toots via klassischem HTML-Scraping
mit BeautifulSoup zu erfassen.

ERGEBNIS: Funktioniert NICHT — Begründung siehe Ausgabe und Kommentare.

Verwendung: python scrape_beautifulsoup.py
Voraussetzungen: pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
import json
import time

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTANCES_FILE = "Instances/InstancesValidated.json"
TEST_INSTANCES = 5        # Nur die ersten 5 Instanzen testen (Demo)
PAUSE_BETWEEN  = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MastodonResearchScraper/1.0; Bachelorarbeit ZHAW)"
}

# ── Diagnose-Funktion ─────────────────────────────────────────────────────────
def diagnose_response(instance: str, response) -> dict:
    """
    Analysiert die HTTP-Antwort und erklärt warum HTML-Scraping nicht funktioniert.
    """
    soup = BeautifulSoup(response.text, "html.parser")

    # Versuche Toots zu finden
    articles     = soup.select("article.status")
    div_status   = soup.select("div.status")
    data_id_tags = soup.select("[data-id]")

    # Prüfe ob es eine React-App ist
    noscript     = soup.find("noscript")
    react_root   = soup.find(id="mastodon") or soup.find(id="root")
    script_tags  = soup.find_all("script")

    # HTML-Inhalt Analyse
    html_length  = len(response.text)
    body_text    = soup.get_text(strip=True)[:200]

    diagnosis = {
        "instance": instance,
        "http_status": response.status_code,
        "html_laenge_zeichen": html_length,
        "toots_gefunden_article": len(articles),
        "toots_gefunden_div": len(div_status),
        "toots_gefunden_data_id": len(data_id_tags),
        "ist_react_app": react_root is not None,
        "hat_noscript_tag": noscript is not None,
        "anzahl_script_tags": len(script_tags),
        "sichtbarer_text_vorschau": body_text,
        "fazit": ""
    }

    # Fazit ableiten
    if react_root:
        diagnosis["fazit"] = (
            "FEHLER: Mastodon ist eine React Single-Page-Application (SPA). "
            "Der Server liefert nur ein leeres HTML-Gerüst mit einem <div id='mastodon'>. "
            "Die eigentlichen Toots werden erst durch JavaScript im Browser geladen. "
            "BeautifulSoup kann JavaScript nicht ausführen und sieht daher keine Toots."
        )
    elif len(articles) == 0 and len(div_status) == 0:
        diagnosis["fazit"] = (
            "FEHLER: Keine Toot-Elemente im HTML gefunden. "
            "Die Seite liefert entweder kein öffentliches HTML oder "
            "die Struktur weicht von der erwarteten Mastodon-Struktur ab."
        )
    else:
        diagnosis["fazit"] = "Toots gefunden — aber dies ist ungewöhnlich für moderne Mastodon-Instanzen."

    return diagnosis


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  BeautifulSoup Scraper — Diagnose-Modus")
    print("  Testet ob HTML-Scraping auf Mastodon-Instanzen funktioniert")
    print("=" * 65)

    # Instanzen laden
    with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
        instances = json.load(f)

    test_instances = instances[:TEST_INSTANCES]
    results = []

    for i, instance in enumerate(test_instances):
        print(f"\n[{i+1}/{len(test_instances)}] Teste {instance}...")

        url = f"https://{instance}/public"

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            print(f"  HTTP Status: {response.status_code}")

            if response.status_code == 200:
                diagnosis = diagnose_response(instance, response)
                results.append(diagnosis)

                print(f"  React-App erkannt: {diagnosis['ist_react_app']}")
                print(f"  Toots im HTML:     {diagnosis['toots_gefunden_article']}")
                print(f"  HTML-Länge:        {diagnosis['html_laenge_zeichen']} Zeichen")
                print(f"  Script-Tags:       {diagnosis['anzahl_script_tags']}")
                print(f"\n  ⚠️  FAZIT: {diagnosis['fazit']}")

            else:
                print(f"  HTTP-Fehler: {response.status_code}")
                results.append({
                    "instance": instance,
                    "http_status": response.status_code,
                    "fazit": f"HTTP {response.status_code} — Seite nicht erreichbar oder Zugriff verweigert"
                })

        except requests.exceptions.ConnectionError:
            print(f"  Verbindungsfehler — Instanz nicht erreichbar")
            results.append({"instance": instance, "fazit": "Verbindungsfehler"})
        except requests.exceptions.Timeout:
            print(f"  Timeout — Instanz antwortet nicht")
            results.append({"instance": instance, "fazit": "Timeout"})

        time.sleep(PAUSE_BETWEEN)

    # Zusammenfassung
    print("\n" + "=" * 65)
    print("  ZUSAMMENFASSUNG")
    print("=" * 65)
    print(f"""
WARUM BEAUTIFULSOUP NICHT FUNKTIONIERT:

Mastodon ist eine moderne Single-Page-Application (SPA) basierend
auf React.js. Wenn ein Browser die URL /public aufruft, lädt der
Server nur ein minimales HTML-Gerüst:

  <html>
    <body>
      <div id="mastodon"></div>   ← leer!
      <script src="app.js"></script>
    </body>
  </html>

Die eigentlichen Toots werden NICHT im HTML geliefert. Stattdessen
führt der Browser das JavaScript (app.js) aus, welches dann die
Mastodon REST-API aufruft (/api/v1/timelines/public) und die Toots
dynamisch in den DOM einfügt.

BeautifulSoup liest nur das initiale HTML — es kann JavaScript
nicht ausführen. Daher findet BeautifulSoup keine Toots.

ALTERNATIVE LÖSUNG:
Anstelle von HTML-Scraping wird der öffentliche API-Endpunkt
direkt abgefragt (/api/v1/timelines/public), der dieselben Daten
ohne Authentifizierung als JSON zurückgibt. Dies entspricht
funktional dem Web Scraping, da kein API-Schlüssel benötigt wird.
Implementiert in: WebScraping/ScrapeToots.py

WEITERE ALTERNATIVEN (nicht implementiert):
- Selenium/Playwright: Steuert einen echten Browser der JavaScript
  ausführen kann. Deutlich langsamer und ressourcenintensiver.
- Scrapy mit Splash: Headless-Browser für JavaScript-Rendering.
  Erfordert zusätzliche Infrastruktur.
""")

    # Ergebnisse als JSON speichern
    with open("Data/ScrapedData_BeautifulSoup.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("  Diagnose gespeichert: Data/ScrapedData_BeautifulSoup.json")


if __name__ == "__main__":
    main()