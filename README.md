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
- instances.social API-Token (optional, nur fuer Schritt 1a)

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
INSTANCES_SOCIAL_TOKEN=dein_token  # optional, nur fuer Schritt 1a
```

### 4. Neo4j Desktop starten

Starte Neo4j Desktop, lege eine neue Datenbank an und starte sie.
Installiere unter Plugins die Graph Data Science Library.

---

## Verwendung

### Schritt 1a: Instanzen abrufen (optional)

Wenn keine eigene Kandidatenliste vorhanden ist, kann `fetch_instances.py` automatisch wissenschaftliche Mastodon-Instanzen von instances.social abrufen. Dafuer wird ein API-Token benoetigt, der unter https://instances.social/api/token generiert werden kann. Die gewuenschten Suchbegriffe koennen im Script unter `KEYWORDS` angepasst werden.

```bash
python Instances/fetch_instances.py
```

Schreibt `Data/InstancesNotValidated.json` mit bis zu 60 Instanzen.

### Schritt 1b: Instanzen validieren

```bash
python Instances/validate_instances.py
```

Liest `Data/InstancesNotValidated.json` und schreibt `Data/InstancesValidated.json`.

### Schritt 2: Toots sammeln

```bash
python MastodonCrawler/Mastodoner.py
```

Schreibt `Data/ScrapedData_Mastodoner.jsonl` und `Data/BoostData.jsonl`.

### Schritt 3: In Neo4j importieren

```bash
python Neo4j/ImportToNeo4j.py
```

### Schritt 4: Volltext-Index erstellen

Im Neo4j Browser ausfuehren:

```cypher
CREATE FULLTEXT INDEX toot_content IF NOT EXISTS FOR (t:Toot) ON EACH [t.content]
```

### Schritt 5: Hashtag-Recommender ausfuehren

```bash
python Recommender/hashtag_recommender.py
```

### Schritt 6: Testframework ausfuehren

```bash
python Neo4j/test_framework.py
```

---

## Repository-Struktur

```
MastodonNeo/
├── Data/                          # Gesammelte Toots (nicht versioniert)
│   ├── BoostData.jsonl            
│   ├── InstancesNotValidated.json # Kandidatenliste
│   ├── InstancesValidated.json    # Validierte Instanzen              
│   ├── ScrapedData_BeautifulSoup.jsonl
│   ├── ScrapedData_Mastodoner.jsonl
│   └── ScrapedData_PublicApi.jsonl
├── Instances/
│   ├── fetch_instances.py         # Automatischer Instanzabruf (optional)
│   └── validate_instances.py      # Validierungsskript
├── MastodonCrawler/
│   └── Mastodoner.py              # Hauptcrawler inkl. Boost-Abruf
├── Neo4j/
│   ├── ImportToNeo4j.py           # Import-Skript
│   ├── test_framework.py          # Testframework (19 Tests)
│   └── cypher_queries.cypher      # Abfragesammlung
├── Recommender/
│   └── hashtag_recommender.py     # Hashtag-Empfehlungen
├── WebScraping/
│   ├── Scraping_PublicApi.py      # Unauthentifizierter Endpunkt
│   └── Scraping_BeautifulSoup.py  # HTML-Scraping-Diagnose
├── .env                           # Neo4j-Zugangsdaten (nicht versioniert)
├── README.md
└── requirements.txt
```

---

## Autor

Ilias Ehrensperger, ehrenili@students.zhaw.ch
Betreuer: Dr. Philipp Stalder, ZHAW School of Management and Law