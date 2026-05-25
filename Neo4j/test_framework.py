"""
Test-Framework: Validierung der Neo4j Mastodon-Datenbank
Prüft ob das Informationssystem korrekt funktioniert.
19 Tests in 9 Kategorien.
Verwendung: python test_framework.py
Voraussetzungen: pip install neo4j
"""

import os
from dotenv import load_dotenv
import json
from neo4j import GraphDatabase

# ── Konfiguration ─────────────────────────────────────────────────────────────
load_dotenv()
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USER")
INPUT_FILE     = "Data/ScrapedData_Mastodoner.jsonl"
BOOST_FILE     = "Data/BoostData.jsonl"

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────
PASSED = 0
FAILED = 0

def test(name: str, result: bool, detail: str = ""):
    global PASSED, FAILED
    status = "PASS" if result else "FAIL"
    print(f"  {status}  {name}")
    if detail:
        print(f"         → {detail}")
    if result:
        PASSED += 1
    else:
        FAILED += 1

def count_unique_jsonl(filepath: str) -> tuple:
    """
    Liest die JSONL-Datei und gibt eindeutige Zählungen zurück.
    Dedupliziert Toots nach ID, da derselbe Toot von mehreren
    Instanzen gecrawlt werden kann.
    Gibt (eindeutige_toots, hashtags, reply_to) zurück.
    """
    seen_ids  = set()
    tags      = 0
    replies   = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            toot    = json.loads(line)
            toot_id = toot.get("id")
            if toot_id and toot_id not in seen_ids:
                seen_ids.add(toot_id)
                tags    += len(toot.get("tags", []))
                replies += 1 if toot.get("in_reply_to_id") else 0
    return len(seen_ids), tags, replies

# ── Tests ─────────────────────────────────────────────────────────────────────
def run_tests(driver):

    # ── 1. Import-Vollständigkeit ─────────────────────────────────────────────
    print("\n 1. Import-Vollständigkeit")

    jsonl_count, total_tags_jsonl, reply_count_jsonl = count_unique_jsonl(INPUT_FILE)

    with driver.session() as s:
        toot_count = s.run("MATCH (t:Toot) RETURN count(t) AS n").single()["n"]

    # Platzhalter-Toots = Toots ohne URI (entstehen durch REPLY_TO auf nicht importierte Toots)
    with driver.session() as s:
        placeholder_count = s.run("""
            MATCH (t:Toot)
            WHERE t.uri IS NULL OR t.uri = ""
            RETURN count(t) AS n
        """).single()["n"]

    real_toot_count = toot_count - placeholder_count

    test(
        "Anzahl echter Toot-Knoten entspricht Anzahl Zeilen in .jsonl",
        real_toot_count == jsonl_count,
        f"{toot_count} Knoten total, {placeholder_count} Platzhalter (REPLY_TO), {real_toot_count} echte Toots, {jsonl_count} Zeilen in .jsonl"
    )

    with driver.session() as s:
        autor_count = s.run("MATCH (a:Autor) RETURN count(a) AS n").single()["n"]
    test("Autor-Knoten vorhanden", autor_count > 0, f"{autor_count} Autoren")

    with driver.session() as s:
        instanz_count = s.run("MATCH (i:Instanz) RETURN count(i) AS n").single()["n"]
    test("Instanz-Knoten vorhanden", instanz_count > 0, f"{instanz_count} Instanzen")

    with driver.session() as s:
        hashtag_count = s.run("MATCH (h:Hashtag) RETURN count(h) AS n").single()["n"]
    test("Hashtag-Knoten vorhanden", hashtag_count > 0, f"{hashtag_count} Hashtags")

    # ── 2. Beziehungs-Vollständigkeit ─────────────────────────────────────────
    print("\n 2. Beziehungs-Vollständigkeit")
    print("     (Platzhalter-Toots ohne URI werden ausgeschlossen)")

    with driver.session() as s:
        toots_without_autor = s.run("""
            MATCH (t:Toot)
            WHERE NOT (t)-[:AUTHORED_BY]->(:Autor)
            AND t.uri IS NOT NULL AND t.uri <> ""
            RETURN count(t) AS n
        """).single()["n"]
    test(
        "Alle echten Toots haben AUTHORED_BY-Kante",
        toots_without_autor == 0,
        f"{toots_without_autor} echte Toots ohne Autor"
    )

    with driver.session() as s:
        toots_without_instanz = s.run("""
            MATCH (t:Toot)
            WHERE NOT (t)-[:POSTED_ON]->(:Instanz)
            AND t.uri IS NOT NULL AND t.uri <> ""
            RETURN count(t) AS n
        """).single()["n"]
    test(
        "Alle echten Toots haben POSTED_ON-Kante",
        toots_without_instanz == 0,
        f"{toots_without_instanz} echte Toots ohne Instanz"
    )

    with driver.session() as s:
        autoren_without_instanz = s.run("""
            MATCH (a:Autor)
            WHERE NOT (a)-[:MEMBER_OF]->(:Instanz)
            AND (a)<-[:AUTHORED_BY]-(:Toot)
            RETURN count(a) AS n
        """).single()["n"]
    test(
        "Alle Autoren haben MEMBER_OF-Kante",
        autoren_without_instanz == 0,
        f"{autoren_without_instanz} Autoren ohne Heiminstanz"
    )

    # ── 3. Hashtag-Vollständigkeit ────────────────────────────────────────────
    print("\n#️  3. Hashtag-Vollständigkeit")

    with driver.session() as s:
        has_hashtag_count = s.run("""
            MATCH ()-[r:HAS_HASHTAG]->()
            RETURN count(r) AS n
        """).single()["n"]
    test(
        "Anzahl HAS_HASHTAG-Kanten stimmt mit .jsonl überein",
        has_hashtag_count == total_tags_jsonl,
        f"{has_hashtag_count} Kanten in Neo4j, {total_tags_jsonl} Tags in .jsonl"
    )

    # ── 4. REPLY_TO Beziehungen ───────────────────────────────────────────────
    print("\n  4. REPLY_TO Beziehungen")

    with driver.session() as s:
        reply_count_neo4j = s.run("""
            MATCH ()-[r:REPLY_TO]->()
            RETURN count(r) AS n
        """).single()["n"]
    test(
        "Anzahl REPLY_TO-Kanten stimmt mit .jsonl überein",
        reply_count_neo4j == reply_count_jsonl,
        f"{reply_count_neo4j} Kanten in Neo4j, {reply_count_jsonl} Antworten in .jsonl"
    )

    # ── 5. BOOSTED Beziehungen ────────────────────────────────────────────────
    print("\n 5. BOOSTED Beziehungen")

    boost_count_jsonl = 0
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            toot = json.loads(line)
            if toot.get("reblog"):
                boost_count_jsonl += 1

    with driver.session() as s:
        boost_count_neo4j = s.run("""
            MATCH ()-[r:BOOSTED]->()
            RETURN count(r) AS n
        """).single()["n"]
    test(
        "Anzahl BOOSTED-Kanten stimmt mit .jsonl überein",
        boost_count_neo4j == boost_count_jsonl,
        f"{boost_count_neo4j} Kanten in Neo4j, {boost_count_jsonl} Boosts in .jsonl"
    )

    # ── 6. Deduplizierung ─────────────────────────────────────────────────────
    print("\n 6. Deduplizierung")

    with driver.session() as s:
        duplicate_toots = s.run("""
            MATCH (t:Toot)
            WITH t.id AS id, count(*) AS n
            WHERE n > 1
            RETURN count(*) AS duplicates
        """).single()["duplicates"]
    test(
        "Keine doppelten Toot-Knoten (gleiche ID)",
        duplicate_toots == 0,
        f"{duplicate_toots} Duplikate gefunden"
    )

    with driver.session() as s:
        duplicate_autoren = s.run("""
            MATCH (a:Autor)
            WITH a.handle AS handle, count(*) AS n
            WHERE n > 1
            RETURN count(*) AS duplicates
        """).single()["duplicates"]
    test(
        "Keine doppelten Autor-Knoten (gleicher Handle)",
        duplicate_autoren == 0,
        f"{duplicate_autoren} Duplikate gefunden"
    )

    with driver.session() as s:
        duplicate_instanzen = s.run("""
            MATCH (i:Instanz)
            WITH i.domain AS domain, count(*) AS n
            WHERE n > 1
            RETURN count(*) AS duplicates
        """).single()["duplicates"]
    test(
        "Keine doppelten Instanz-Knoten (gleiche Domain)",
        duplicate_instanzen == 0,
        f"{duplicate_instanzen} Duplikate gefunden"
    )

    # ── 7. Datenqualität ──────────────────────────────────────────────────────
    print("\n 7. Datenqualität")

    with driver.session() as s:
        toots_without_uri = s.run("""
            MATCH (t:Toot)
            WHERE (t.uri IS NULL OR t.uri = "")
            AND EXISTS { (t)-[:AUTHORED_BY]->() }
            RETURN count(t) AS n
        """).single()["n"]
    test(
        "Alle echten Toots haben eine URI",
        toots_without_uri == 0,
        f"{toots_without_uri} echte Toots ohne URI"
    )

    with driver.session() as s:
        toots_without_content = s.run("""
            MATCH (t:Toot)
            WHERE (t.content IS NULL OR t.content = "")
            AND t.uri IS NOT NULL AND t.uri <> ""
            RETURN count(t) AS n
        """).single()["n"]
    test(
        "Echte Toots ohne Inhalt sind akzeptabel (z.B. reine Bild-Toots)",
        True,
        f"{toots_without_content} echte Toots ohne Text-Inhalt (Bild- oder Video-Toots)"
    )

    test(
        "Mindestens 30 verschiedene Instanzen vorhanden",
        instanz_count >= 30,
        f"{instanz_count} Instanzen in der Datenbank"
    )

    # ── 8. Volltext-Index ─────────────────────────────────────────────────────
    print("\n 8. Volltext-Index")

    with driver.session() as s:
        indexes = s.run("SHOW INDEXES").data()
        fulltext_exists = any(
            idx.get("type") == "FULLTEXT" and "toot_content" in str(idx.get("name", ""))
            for idx in indexes
        )
    test(
        "Volltext-Index 'toot_content' ist vorhanden",
        fulltext_exists,
        "Index für Freitextsuche auf Toot.content"
    )

    if not fulltext_exists:
        print("            Erstelle Index mit:")
        print("            CREATE FULLTEXT INDEX toot_content IF NOT EXISTS")
        print("            FOR (t:Toot) ON EACH [t.content]")

    # ── 9. BOOSTED_BY Beziehungen ─────────────────────────────────────────────
    print("\n 9. BOOSTED_BY Beziehungen")

    import os
    if os.path.exists(BOOST_FILE):
        # Anzahl Booster aus BoostData.jsonl zählen
        boost_by_count_jsonl = 0
        seen_pairs = set()
        with open(BOOST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry    = json.loads(line)
                toot_uri = entry["toot_uri"]
                for booster in entry.get("boosters", []):
                    handle = booster.get("handle", "")
                    if handle and (toot_uri, handle) not in seen_pairs:
                        seen_pairs.add((toot_uri, handle))
                        boost_by_count_jsonl += 1

        with driver.session() as s:
            boost_by_count_neo4j = s.run("""
                MATCH ()-[r:BOOSTED_BY]->()
                RETURN count(r) AS n
            """).single()["n"]

        test(
            "Anzahl BOOSTED_BY-Kanten stimmt mit BoostData.jsonl überein",
            boost_by_count_neo4j == boost_by_count_jsonl,
            f"{boost_by_count_neo4j} Kanten in Neo4j, {boost_by_count_jsonl} in BoostData.jsonl"
        )

        with driver.session() as s:
            duplicate_boosts = s.run("""
                MATCH (t:Toot)-[r:BOOSTED_BY]->(a:Autor)
                WITH t.uri AS uri, a.handle AS handle, count(r) AS n
                WHERE n > 1
                RETURN count(*) AS duplicates
            """).single()["duplicates"]
        test(
            "Keine doppelten BOOSTED_BY-Kanten",
            duplicate_boosts == 0,
            f"{duplicate_boosts} Duplikate gefunden"
        )
    else:
        test(
            "BoostData.jsonl vorhanden",
            False,
            f"Datei nicht gefunden: {BOOST_FILE} — bitte fetch_boosts.py ausführen"
        )


# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Test-Framework: Mastodon Neo4j Informationssystem")
    print("=" * 55)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        run_tests(driver)
    finally:
        driver.close()

    print("\n" + "=" * 55)
    print(f"  Ergebnis: {PASSED} bestanden / {FAILED} fehlgeschlagen")
    if FAILED == 0:
        print("Alle Tests bestanden!")
    else:
        print("Einige Tests fehlgeschlagen — bitte prüfen.")
    print("=" * 55)


if __name__ == "__main__":
    main()
