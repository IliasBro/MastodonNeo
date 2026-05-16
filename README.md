# MastodonNeo

Bachelorarbeit — ZHAW School of Management and Law
BSc Wirtschaftsinformatik, Vertiefung Data Science, 2026 

Automatisierte Erfassung und Analyse wissenschaftlicher Mastodon-Kommunikation mit Neo4j.

---

## Beschreibung

Dieses Repository enthält ein Informationssystem, das Toots von mehreren Mastodon-Instanzen automatisiert erfasst und in einer Neo4j-Graphdatenbank speichert. Das System ermöglicht instanzübergreifende Analysen, die mit der eingebauten Mastodon-Suche nicht möglich sind.

Das Vorgehen folgt der Design Science Research Methodology (DSRM) nach Peffers et al. (2007).

---

## Voraussetzungen

- Python 3.11
- Neo4j Desktop (Download: https://neo4j.com/download/)
- Git

---

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/IliasBro/MastodonNeo.git
cd MastodonNeo
```

### 2. Virtuelle Umgebung einrichten

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Umgebungsvariablen konfigurieren

Erstelle eine `.env`-Datei im Root-Verzeichnis:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=dein_passwort
```

### 4. Neo4j Desktop starten

Starte Neo4j Desktop, lege eine neue Datenbank an und starte sie.
Installiere unter Plugins die Graph Data Science Library.

---

## Verwendung

Die Pipeline wird in folgender Reihenfolge ausgefuhrt:

### Schritt 1: Instanzen validieren

```bash
python Instances/validate_instances.py
```

Liest `Instances/Top60Instances.json` und schreibt `Instances/InstancesValidated.json`.

### Schritt 2: Toots sammeln

```bash
python MastodonCrawler/Mastodoner.py
```

Schreibt `Data/ScrapedData_Mastodoner.jsonl`.

### Schritt 3: In Neo4j importieren

```bash
python Neo4j/ImportToNeo4j.py
```

### Schritt 4: Volltext-Index erstellen

Im Neo4j Browser ausfuhren:

```cypher
CREATE FULLTEXT INDEX toot_content IF NOT EXISTS FOR (t:Toot) ON EACH [t.content]
```

### Schritt 5: Hashtag-Recommender ausfuhren

```bash
python Recommender/hashtag_recommender.py
```

### Schritt 6: Testframework ausfuhren

```bash
python Neo4j/test_framework.py
```

---

## Repository-Struktur

```
MastodonNeo/
├── Data/                        # Gesammelte Toots (nicht versioniert)
├── Instances/
│   ├── Top60Instances.json      # Kandidatenliste
│   ├── InstancesValidated.json  # Validierte Instanzen
│   └── validate_instances.py   # Validierungsskript
├── MastodonCrawler/
│   └── Mastodoner.py            # Hauptcrawler
├── Neo4j/
│   ├── ImportToNeo4j.py         # Import-Skript
│   ├── test_framework.py        # Testframework
│   └── cypher_queries.cypher    # Abfragesammlung
├── Recommender/
│   └── hashtag_recommender.py  # Hashtag-Empfehlungen
├── WebScraping/
│   ├── Scraping_PublicApi.py    # Unauthentifizierter Endpunkt
│   └── Scraping_BeautifulSoup.py # HTML-Scraping-Diagnose
├── .env                         # Neo4j-Zugangsdaten (nicht versioniert)
├── README.md
└── requirements.txt
```

---

## Autor

Ilias Ehrensperger, ehrenili@students.zhaw.ch
Betreuer: Dr. Philipp Stalder, ZHAW School of Management and Law