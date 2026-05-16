"""
Mastodon → Neo4j Import Script
Voraussetzungen:
    pip install neo4j
Konfiguration:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD anpassen
    INPUT_FILE auf deine .jsonl Datei zeigen lassen
"""

import os
from dotenv import load_dotenv
import json
from urllib.parse import urlparse
from neo4j import GraphDatabase

# ── Konfiguration ─────────────────────────────────────────────────────────────
load_dotenv()
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USER")
INPUT_FILE     = "Data/ScrapedData_Mastodoner.jsonl"

# ── Hilfsfunktion: Domain aus URI extrahieren ─────────────────────────────────
def extract_domain(uri: str) -> str:
    """Extrahiert die Domain aus einer Mastodon-URI.
    Beispiel: https://scholar.social/users/ilias/statuses/123 → scholar.social
    """
    try:
        return urlparse(uri).netloc
    except Exception:
        return "unknown"

# ── Import-Funktion ───────────────────────────────────────────────────────────
def import_toot(tx, toot: dict):
    uri        = toot.get("uri", "")
    toot_id    = toot.get("id", "")
    content    = toot.get("content", "")
    created_at = toot.get("created_at", "")
    language   = toot.get("language", "")
    domain     = extract_domain(uri)

    # Reblog- und Reply-IDs
    in_reply_to_id      = toot.get("in_reply_to_id")
    reblog              = toot.get("reblog")
    boosted_toot_id     = reblog.get("id") if reblog else None

    # Autor
    account      = toot.get("account", {})
    author_handle = account.get("acct", "")
    display_name  = account.get("display_name", "")
    author_domain = extract_domain(account.get("uri", ""))

    # Hashtags (ALLE erfassen)
    tags = [t["name"].lower() for t in toot.get("tags", []) if t.get("name")]

    # ── Knoten erstellen ──────────────────────────────────────────────────────

    # Toot-Knoten
    tx.run("""
        MERGE (t:Toot {id: $id})
        SET t.uri        = $uri,
            t.content    = $content,
            t.created_at = $created_at,
            t.language   = $language,
            t.in_reply_to_id  = $in_reply_to_id,
            t.boosted_toot_id = $boosted_toot_id
    """, id=toot_id, uri=uri, content=content, created_at=created_at,
         language=language, in_reply_to_id=in_reply_to_id,
         boosted_toot_id=boosted_toot_id)

    # Autor-Knoten
    tx.run("""
        MERGE (a:Autor {handle: $handle})
        SET a.display_name = $display_name
    """, handle=author_handle, display_name=display_name)

    # Instanz-Knoten (Ursprungsinstanz des Toots)
    tx.run("""
        MERGE (i:Instanz {domain: $domain})
    """, domain=domain)

    # Instanz-Knoten (Heiminstanz des Autors)
    tx.run("""
        MERGE (i:Instanz {domain: $domain})
    """, domain=author_domain)

    # ── Kanten erstellen ──────────────────────────────────────────────────────

    # Toot → AUTHORED_BY → Autor
    tx.run("""
        MATCH (t:Toot {id: $toot_id}), (a:Autor {handle: $handle})
        MERGE (t)-[:AUTHORED_BY]->(a)
    """, toot_id=toot_id, handle=author_handle)

    # Toot → POSTED_ON → Instanz
    tx.run("""
        MATCH (t:Toot {id: $toot_id}), (i:Instanz {domain: $domain})
        MERGE (t)-[:POSTED_ON]->(i)
    """, toot_id=toot_id, domain=domain)

    # Autor → MEMBER_OF → Instanz (Heiminstanz)
    tx.run("""
        MATCH (a:Autor {handle: $handle}), (i:Instanz {domain: $domain})
        MERGE (a)-[:MEMBER_OF]->(i)
    """, handle=author_handle, domain=author_domain)

    # Toot → HAS_HASHTAG → Hashtag (alle Hashtags)
    for tag in tags:
        tx.run("""
            MERGE (h:Hashtag {name: $name})
        """, name=tag)
        tx.run("""
            MATCH (t:Toot {id: $toot_id}), (h:Hashtag {name: $name})
            MERGE (t)-[:HAS_HASHTAG]->(h)
        """, toot_id=toot_id, name=tag)

    # Toot → REPLY_TO → Toot (falls Antwort)
    if in_reply_to_id:
        tx.run("""
            MERGE (t2:Toot {id: $reply_id})
            WITH t2
            MATCH (t:Toot {id: $toot_id})
            MERGE (t)-[:REPLY_TO]->(t2)
        """, toot_id=toot_id, reply_id=in_reply_to_id)

    # Toot → BOOSTED → Toot (falls Boost)
    if boosted_toot_id:
        tx.run("""
            MERGE (t2:Toot {id: $boosted_id})
            WITH t2
            MATCH (t:Toot {id: $toot_id})
            MERGE (t)-[:BOOSTED]->(t2)
        """, toot_id=toot_id, boosted_id=boosted_toot_id)


# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Constraints für schnellere MERGE-Operationen
    with driver.session() as session:
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Toot) REQUIRE t.id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Autor) REQUIRE a.handle IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:Instanz) REQUIRE i.domain IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (h:Hashtag) REQUIRE h.name IS UNIQUE")

    # Toots importieren
    count = 0
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            toot = json.loads(line)
            with driver.session() as session:
                session.execute_write(import_toot, toot)
            count += 1
            if count % 10 == 0:
                print(f"{count} Toots importiert...")

    print(f"\nFertig! {count} Toots erfolgreich importiert.")
    driver.close()


if __name__ == "__main__":
    main()