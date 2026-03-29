# MastodonNeo

**Bachelorarbeit — ZHAW School of Management and Law**

> Mastodon für die Wissenschaft: Automatisierte Erfassung föderierter Microblogging-Kommunikation und Modellierung in einer Graph-Datenbank

**Autor:** Ilias Ehrensperger  
**Betreuer:** Dr. Philipp Stalder  
**Studiengang:** BSc Wirtschaftsinformatik mit Vertiefung Data Science  
**Abgabe:** 27. Mai 2026

---

## Projektbeschreibung

Dieses Repository enthält den Prototyp eines Informationssystems, das Beiträge (*Toots*) von mehreren wissenschaftsnahen Mastodon-Instanzen automatisiert erfasst und in einer Neo4j-Graphdatenbank speichert. Das System ermöglicht die Analyse instanzübergreifender Kommunikationsstrukturen anhand von Beziehungen zwischen Toots, Autoren, Instanzen und Hashtags.

Die Forschungsmethode folgt der **Design Science Research Methodology (DSRM)** nach Peffers et al. (2007).

---

## Projektstruktur

```
MastodonNeo/
├── MastodonCrawler/
│   ├── collect_toots.py       # Datenerhebung via Mastodoner
│   ├── mastodon_import.py     # Import in Neo4j
│   └── test_framework.py      # Validierungs-Framework
├── Instances/
│   └── Top40Instances.json    # 40 validierte wissenschaftliche Instanzen
├── Data/
│   └── toots_alle_instanzen.jsonl   # Gesammelte Toots (nicht im Repo)
└── README.md
```

---

## Voraussetzungen

- Python 3.11 oder höher
- Neo4j Desktop (lokal installiert, läuft auf `bolt://localhost:7687`)
- Folgende Python-Pakete:

```bash
pip install mastodoner neo4j
```

---

## Installation

1. Repository klonen:

```bash
git clone https://github.com/dein-username/MastodonNeo.git
cd MastodonNeo
```

2. Abhängigkeiten installieren:

```bash
pip install mastodoner neo4j
```

3. Neo4j Desktop starten und eine neue Datenbank erstellen (z.B. `mastodon`).

---

## Verwendung

### Schritt 1 — Toots sammeln

Navigiere in den `MastodonCrawler/`-Ordner und führe das Sammelskript aus:

```bash
cd MastodonCrawler
python collect_toots.py
```

Das Skript liest die 40 Instanzen aus `Instances/Top40Instances.json`, fragt jede Instanz ab und speichert die Toots in `Data/toots_alle_instanzen.jsonl`. Pro Instanz werden bis zu 200 Toots gesammelt (~8'000 Toots total).

**Konfiguration** (oben im Skript anpassbar):

| Variable | Standard | Beschreibung |
|---|---|---|
| `INSTANCES_FILE` | `../Instances/Top40Instances.json` | Instanzliste |
| `OUTPUT_FILE` | `../Data/toots_alle_instanzen.jsonl` | Ausgabedatei |
| `MAX_POSTS_PER_INSTANCE` | `200` | Maximale Toots pro Instanz |
| `PAUSE_BETWEEN` | `2` | Sekunden Pause zwischen Instanzen |

---

### Schritt 2 — Daten in Neo4j importieren

Stelle sicher dass Neo4j Desktop läuft und die Datenbank gestartet ist. Passe in `mastodon_import.py` das Passwort an:

```python
NEO4J_PASSWORD = "dein_passwort"
```

Dann importieren:

```bash
python mastodon_import.py
```

Das Skript erstellt automatisch Constraints und importiert alle Toots mit ihren Beziehungen.

---

### Schritt 3 — Daten validieren

```bash
python test_framework.py
```

Das Test-Framework prüft automatisch 8 Kategorien:

- Import-Vollständigkeit (Anzahl Toots)
- Beziehungs-Vollständigkeit (AUTHORED_BY, POSTED_ON, MEMBER_OF)
- Hashtag-Vollständigkeit (alle HAS_HASHTAG-Kanten)
- REPLY_TO-Beziehungen
- BOOSTED-Beziehungen
- Deduplizierung (keine doppelten Knoten)
- Datenqualität (URI, Content)
- Volltext-Index

---

## Datenmodell

Das Graph-Datenmodell in Neo4j besteht aus **4 Knotentypen** und **6 Kantentypen**:

### Knoten

| Label | Eigenschaften |
|---|---|
| `Toot` | id, uri, content, created_at, language, in_reply_to_id, boosted_toot_id |
| `Autor` | handle (username@instanz), display_name |
| `Instanz` | domain |
| `Hashtag` | name (lowercase) |

### Kanten

| Beziehung | Von → Nach | Bedeutung |
|---|---|---|
| `AUTHORED_BY` | Toot → Autor | Verfasserschaft |
| `POSTED_ON` | Toot → Instanz | Ursprungsinstanz |
| `HAS_HASHTAG` | Toot → Hashtag | Alle Hashtags als separate Kanten |
| `REPLY_TO` | Toot → Toot | Antwortkette |
| `BOOSTED` | Toot → Toot | Repost-Beziehung |
| `MEMBER_OF` | Autor → Instanz | Heiminstanz des Autors |

Die **URI** dient als globale, instanzübergreifende Identifikation und ermöglicht Deduplizierung (nach Wiegmann et al., 2024).

---

## Beispiel-Abfragen (Cypher)

**Volltext-Index erstellen (einmalig):**
```cypher
CREATE FULLTEXT INDEX toot_content IF NOT EXISTS
FOR (t:Toot) ON EACH [t.content]
```

**Aktivste Autoren:**
```cypher
MATCH (a:Autor)-[:AUTHORED_BY]-(t:Toot)
RETURN a.handle, count(t) AS anzahl
ORDER BY anzahl DESC LIMIT 10
```

**Häufigste Hashtags:**
```cypher
MATCH (t:Toot)-[:HAS_HASHTAG]->(h:Hashtag)
RETURN h.name, count(t) AS anzahl
ORDER BY anzahl DESC LIMIT 20
```

**Aktivste Instanzen:**
```cypher
MATCH (t:Toot)-[:POSTED_ON]->(i:Instanz)
RETURN i.domain, count(t) AS anzahl
ORDER BY anzahl DESC
```

**Antwortketten verfolgen:**
```cypher
MATCH path = (t1:Toot)-[:REPLY_TO*1..5]->(t2:Toot)
RETURN path LIMIT 10
```

**Freitextsuche:**
```cypher
CALL db.index.fulltext.queryNodes("toot_content", "roboter")
YIELD node
RETURN node.content, node.uri LIMIT 20
```

**Instanzübergreifende Kommunikation:**
```cypher
MATCH (a:Autor)-[:MEMBER_OF]->(i1:Instanz)
MATCH (t:Toot)-[:AUTHORED_BY]->(a)
MATCH (t)-[:REPLY_TO]->(t2:Toot)-[:POSTED_ON]->(i2:Instanz)
WHERE i1 <> i2
RETURN a.handle, i1.domain, i2.domain LIMIT 20
```

---

## Instanzauswahl

Die 40 Instanzen in `Top40Instances.json` wurden nach folgenden Kriterien ausgewählt:

- **Wissenschafts- und Forschungsbezug** (z.B. scholar.social, sigmoid.social, datasci.social)
- **Tech & Informatik** (z.B. fosstodon.org, hachyderm.io, infosec.exchange)
- **DACH-Raum** (z.B. berlin.social, bern.social, swiss.social)
- **Bildung & Wirtschaft** (z.B. bildung.social, econtwitter.net)

Die Validierung erfolgte mit dem `obtain-instance-data`-Befehl aus dem [mastodon-search Repository](https://github.com/webis-de/mastodon-search) von Wiegmann et al. (2024). Von ursprünglich 50 Kandidaten wurden 40 als erreichbare Mastodon-Instanzen mit öffentlicher API bestätigt.

---

## Literatur

- Peffers, K., Tuunanen, T., Rothenberger, M. A. & Chatterjee, S. (2007). A Design Science Research Methodology for Information Systems Research. *Journal of Management Information Systems*, 24(3), 45–77.
- Wiegmann, M., Reimer, J. H., Ernst, M., Potthast, M., Hagen, M. & Stein, B. (2024). A Mastodon Corpus to Evaluate Federated Microblog Search. *Proceedings of WOWS'24 at ECIR 2024*.
- Zia, H. B., Castro, I. & Tyson, G. (2024). Mastodoner: A Command-line Tool and Python Library for Public Data Collection from Mastodon. *Proceedings of CIKM '24*. https://doi.org/10.1145/3627673.3679217

---

## Lizenz

Dieses Repository ist für Forschungszwecke im Rahmen der Bachelorarbeit an der ZHAW erstellt worden.