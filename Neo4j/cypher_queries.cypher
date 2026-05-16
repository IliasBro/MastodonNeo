# Cypher-Abfragen — MastodonNeo Informationssystem
# Bachelorarbeit Ilias Ehrensperger, ZHAW 2026
# Usecase: «Ich möchte mehr über ein Thema erfahren — wer diskutiert es auf Mastodon?»

# ===========================================================================
# 1. FREITEXTSUCHE — Einstieg in ein Thema
# ===========================================================================

# 1.1 Alle Toots zu einem Suchbegriff finden
CALL db.index.fulltext.queryNodes("toot_content", "robotics")
YIELD node, score
RETURN node.content, node.uri, score
ORDER BY score DESC
LIMIT 20

# 1.2 Welche Hashtags tauchen in diesen Toots auf?
CALL db.index.fulltext.queryNodes("toot_content", "robotics")
YIELD node
MATCH (node)-[:HAS_HASHTAG]->(h:Hashtag)
RETURN h.name AS hashtag, count(*) AS anzahl
ORDER BY anzahl DESC
LIMIT 10

# 1.3 Auf welchen Instanzen wird das Thema diskutiert?
CALL db.index.fulltext.queryNodes("toot_content", "robotics")
YIELD node
MATCH (node)-[:POSTED_ON]->(i:Instanz)
RETURN i.domain AS instanz, count(*) AS anzahl
ORDER BY anzahl DESC

# ===========================================================================
# 2. HASHTAG-ANALYSE — Thema vertiefen
# ===========================================================================

# 2.1 Häufigste Hashtags gesamt
MATCH (t:Toot)-[:HAS_HASHTAG]->(h:Hashtag)
RETURN h.name AS hashtag, count(t) AS anzahl
ORDER BY anzahl DESC
LIMIT 20

# 2.2 Hashtag-Empfehlungen via Recommender
MATCH (h:Hashtag {name: 'ai'})-[r:RECOMMENDED]->(rec:Hashtag)
RETURN rec.name AS empfehlung,
       r.coOccurScore AS co_occurrence,
       r.sharedUserScore AS shared_users,
       r.combinedScore AS combined,
       r.rank AS rang
ORDER BY r.rank
LIMIT 10

# 2.3 Welche Hashtag-Kombinationen kommen am häufigsten vor?
MATCH (t:Toot)-[:HAS_HASHTAG]->(h1:Hashtag),
      (t)-[:HAS_HASHTAG]->(h2:Hashtag)
WHERE h1.name < h2.name
RETURN h1.name AS tag1, h2.name AS tag2, count(t) AS gemeinsame_toots
ORDER BY gemeinsame_toots DESC
LIMIT 15

# ===========================================================================
# 3. AUTOREN-ANALYSE — Wer sind die Akteure?
# ===========================================================================

# 3.1 Aktivste Autoren gesamt
MATCH (t:Toot)-[:AUTHORED_BY]->(a:Autor)
RETURN a.handle AS autor, count(t) AS anzahl_toots
ORDER BY anzahl_toots DESC
LIMIT 10

# 3.2 Aktivste Autoren zu einem bestimmten Hashtag
MATCH (a:Autor)<-[:AUTHORED_BY]-(t:Toot)-[:HAS_HASHTAG]->(h:Hashtag {name: 'ai'})
RETURN a.handle AS autor, count(t) AS anzahl_toots
ORDER BY anzahl_toots DESC
LIMIT 10

# 3.3 Autoren die auf mehreren Instanzen aktiv sind
MATCH (a:Autor)-[:MEMBER_OF]->(i:Instanz)
MATCH (t:Toot)-[:AUTHORED_BY]->(a)
MATCH (t)-[:POSTED_ON]->(i2:Instanz)
WHERE i <> i2
RETURN a.handle AS autor, i.domain AS heiminstanz, i2.domain AS postete_auf
LIMIT 20

# 3.4 Autoren die zu einem Thema diskutieren (Freitext)
CALL db.index.fulltext.queryNodes("toot_content", "robotics")
YIELD node
MATCH (node)-[:AUTHORED_BY]->(a:Autor)
RETURN a.handle AS autor, count(*) AS anzahl
ORDER BY anzahl DESC
LIMIT 10

# ===========================================================================
# 4. INSTANZ-ANALYSE — Wo wird diskutiert?
# ===========================================================================

# 4.1 Aktivste Instanzen nach Toot-Anzahl
MATCH (t:Toot)-[:POSTED_ON]->(i:Instanz)
WHERE t.uri IS NOT NULL AND t.uri <> ""
RETURN i.domain AS instanz, count(t) AS anzahl_toots
ORDER BY anzahl_toots DESC
LIMIT 15

# 4.2 Instanzverteilung für einen bestimmten Hashtag
MATCH (t:Toot)-[:HAS_HASHTAG]->(h:Hashtag {name: 'opensource'})
MATCH (t)-[:POSTED_ON]->(i:Instanz)
RETURN i.domain AS instanz, count(t) AS anzahl
ORDER BY anzahl DESC

# 4.3 Instanzen mit den meisten verschiedenen Autoren
MATCH (a:Autor)-[:MEMBER_OF]->(i:Instanz)
RETURN i.domain AS instanz, count(DISTINCT a) AS anzahl_autoren
ORDER BY anzahl_autoren DESC
LIMIT 10

# ===========================================================================
# 5. KOMMUNIKATIONSSTRUKTUREN — Beziehungen verfolgen
# ===========================================================================

# 5.1 Antwortketten anzeigen (bis 5 Ebenen tief)
MATCH path = (t1:Toot)-[:REPLY_TO*1..5]->(t2:Toot)
WHERE t1.uri IS NOT NULL
RETURN path
LIMIT 10

# 5.2 Instanzübergreifende Kommunikation
MATCH (t1:Toot)-[:POSTED_ON]->(i1:Instanz)
MATCH (t1)-[:REPLY_TO]->(t2:Toot)-[:POSTED_ON]->(i2:Instanz)
WHERE i1 <> i2
  AND t1.uri IS NOT NULL
  AND t2.uri IS NOT NULL
RETURN i1.domain AS von_instanz,
       i2.domain AS zu_instanz,
       count(*) AS anzahl_antworten
ORDER BY anzahl_antworten DESC
LIMIT 15

# 5.3 Längste Antwortketten finden
MATCH path = (t1:Toot)-[:REPLY_TO*]->(t2:Toot)
WHERE NOT (t1)<-[:REPLY_TO]-()
  AND t1.uri IS NOT NULL
RETURN length(path) AS kettenlaenge, t1.uri AS start_toot
ORDER BY kettenlaenge DESC
LIMIT 5

# 5.4 Autoren die instanzübergreifend kommunizieren
MATCH (a:Autor)-[:MEMBER_OF]->(i1:Instanz)
MATCH (t:Toot)-[:AUTHORED_BY]->(a)
MATCH (t)-[:REPLY_TO]->(t2:Toot)-[:POSTED_ON]->(i2:Instanz)
WHERE i1 <> i2
  AND t.uri IS NOT NULL
RETURN a.handle AS autor,
       i1.domain AS heiminstanz,
       i2.domain AS antwortet_auf_instanz,
       count(*) AS anzahl
ORDER BY anzahl DESC
LIMIT 10

# ===========================================================================
# 6. HASHTAG-RECOMMENDER — Verwandte Themen entdecken
# ===========================================================================

# 6.1 Empfehlungen für einen Hashtag anzeigen (Graph-Visualisierung)
MATCH (h:Hashtag {name: 'linux'})-[r:RECOMMENDED]->(rec:Hashtag)
RETURN h, r, rec
ORDER BY r.rank
LIMIT 10

# 6.2 Empfehlungen als Tabelle mit allen Scores
MATCH (h:Hashtag {name: 'linux'})-[r:RECOMMENDED]->(rec:Hashtag)
RETURN rec.name AS empfehlung,
       r.coOccurScore AS co_occurrence,
       r.sharedUserScore AS shared_users,
       r.combinedScore AS combined_score,
       r.rank AS rang
ORDER BY r.rank

# 6.3 Empfehlungs-Netzwerk — alle Hashtags mit ihren Empfehlungen
MATCH (h:Hashtag)-[r:RECOMMENDED]->(rec:Hashtag)
WHERE r.combinedScore > 0.2
RETURN h, r, rec
LIMIT 50

# ===========================================================================
# 7. SPREADING-ANALYSE — Verbreitung von Toots verfolgen
# ===========================================================================

# 7.1 Toots mit den meisten direkten Antworten
MATCH (reply:Toot)-[:REPLY_TO]->(original:Toot)
WHERE original.uri IS NOT NULL
RETURN original.uri AS toot,
       count(reply) AS anzahl_antworten
ORDER BY anzahl_antworten DESC
LIMIT 10

# 7.2 Längste Antwortketten im Datensatz
MATCH path = (start:Toot)-[:REPLY_TO*]->(end:Toot)
WHERE NOT (start)<-[:REPLY_TO]-()
  AND start.uri IS NOT NULL
WITH start, max(length(path)) AS laenge
RETURN laenge, start.uri AS start_toot
ORDER BY laenge DESC
LIMIT 5

# 7.3 Instanzverteilung der Antwortbeziehungen
MATCH (t1:Toot)-[:REPLY_TO]->(t2:Toot)
WHERE t1.uri IS NOT NULL AND t2.uri IS NOT NULL
MATCH (t1)-[:POSTED_ON]->(i1:Instanz)
MATCH (t2)-[:POSTED_ON]->(i2:Instanz)
RETURN i1.domain AS antwort_instanz,
       i2.domain AS ursprungs_instanz,
       count(*) AS anzahl,
       CASE WHEN i1 <> i2 THEN 'cross-instance' ELSE 'same-instance' END AS typ
ORDER BY anzahl DESC
LIMIT 10

# ===========================================================================
# 8. VOLLSTÄNDIGE USE-CASE PIPELINE
# «Ich möchte mehr über AI erfahren»
# ===========================================================================

# Schritt 1: Toots zum Thema finden
CALL db.index.fulltext.queryNodes("toot_content", "artificial intelligence")
YIELD node, score
RETURN node.content, node.uri, score
ORDER BY score DESC LIMIT 10

# Schritt 2: Relevante Hashtags identifizieren
CALL db.index.fulltext.queryNodes("toot_content", "artificial intelligence")
YIELD node
MATCH (node)-[:HAS_HASHTAG]->(h:Hashtag)
RETURN h.name, count(*) AS anzahl
ORDER BY anzahl DESC LIMIT 10

# Schritt 3: Verwandte Hashtags via Recommender
MATCH (h:Hashtag {name: 'ai'})-[r:RECOMMENDED]->(rec:Hashtag)
RETURN rec.name, r.combinedScore, r.rank
ORDER BY r.rank LIMIT 10

# Schritt 4: Aktivste Autoren zum Thema
MATCH (a:Autor)<-[:AUTHORED_BY]-(t:Toot)-[:HAS_HASHTAG]->(h:Hashtag {name: 'ai'})
RETURN a.handle, count(t) AS toots
ORDER BY toots DESC LIMIT 10

# Schritt 5: Instanzverteilung
MATCH (t:Toot)-[:HAS_HASHTAG]->(h:Hashtag {name: 'ai'})
MATCH (t)-[:POSTED_ON]->(i:Instanz)
RETURN i.domain, count(t) AS anzahl
ORDER BY anzahl DESC
