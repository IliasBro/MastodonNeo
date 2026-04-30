"""
Hashtag-Recommender — Stufe 1
Berechnet Hashtag-Empfehlungen basierend auf:
  1. Co-Occurrence (Jaccard-Similarity): Wie oft erscheinen zwei Hashtags im selben Toot?
  2. Shared Users: Wie viele Autoren verwenden beide Hashtags?

Die Empfehlungen werden als RECOMMENDED-Kanten direkt in Neo4j geschrieben.

Verwendung: python hashtag_recommender.py
Voraussetzungen: pip install neo4j python-dotenv
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# ── Konfiguration ──────────────────────────────────────────────────────────────
load_dotenv()
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


TOP_N              = 10
MIN_COOCCURRENCE   = 2
MIN_HASHTAG_COUNT  = 3
NOISE_HASHTAGS     = {
    "mastodon", "fediverse", "introduction", "introductions",
    "followfriday", "ff", "np", "nowplaying"
}

def log(msg):
    print(f"  -> {msg}")

def clear_recommendations(tx):
    tx.run("MATCH ()-[r:RECOMMENDED]->() DELETE r")

def get_valid_hashtags(tx):
    result = tx.run("""
        MATCH (h:Hashtag)<-[:HAS_HASHTAG]-(t:Toot)
        WITH h, count(t) AS vorkommen
        WHERE vorkommen >= $min_count
        RETURN h.name AS name, vorkommen
        ORDER BY vorkommen DESC
    """, min_count=MIN_HASHTAG_COUNT)
    valid = []
    for record in result:
        name = record["name"]
        if name not in NOISE_HASHTAGS:
            valid.append(name)
    return valid

def compute_cooccurrence(tx, valid_hashtags):
    """
    Jaccard-Similarity zwischen zwei Hashtags A und B:
      |Toots(A) intersect Toots(B)| / |Toots(A) union Toots(B)|
    Wertebereich: 0 (nie zusammen) bis 1 (immer zusammen)
    """
    result = tx.run("""
        MATCH (h1:Hashtag)<-[:HAS_HASHTAG]-(t:Toot)-[:HAS_HASHTAG]->(h2:Hashtag)
        WHERE h1.name < h2.name
          AND h1.name IN $valid
          AND h2.name IN $valid
        WITH h1, h2, count(DISTINCT t) AS intersection
        WHERE intersection >= $min_cooc
        MATCH (h1)<-[:HAS_HASHTAG]-(t1:Toot)
        WITH h1, h2, intersection, count(DISTINCT t1) AS count1
        MATCH (h2)<-[:HAS_HASHTAG]-(t2:Toot)
        WITH h1, h2, intersection, count1, count(DISTINCT t2) AS count2
        WITH h1, h2, intersection,
             (count1 + count2 - intersection) AS union_count,
             toFloat(intersection) / (count1 + count2 - intersection) AS jaccard
        RETURN h1.name AS tag1, h2.name AS tag2, intersection, jaccard
        ORDER BY jaccard DESC
    """, valid=valid_hashtags, min_cooc=MIN_COOCCURRENCE)
    return [dict(r) for r in result]

def compute_shared_users(tx, valid_hashtags):
    result = tx.run("""
        MATCH (h1:Hashtag)<-[:HAS_HASHTAG]-(t1:Toot)-[:AUTHORED_BY]->(a:Autor)
        MATCH (t2:Toot)-[:AUTHORED_BY]->(a)
        MATCH (t2)-[:HAS_HASHTAG]->(h2:Hashtag)
        WHERE h1.name < h2.name
          AND h1.name IN $valid
          AND h2.name IN $valid
        WITH h1, h2, count(DISTINCT a) AS shared
        WHERE shared >= 2
        MATCH (h1)<-[:HAS_HASHTAG]-(ta:Toot)-[:AUTHORED_BY]->(a1:Autor)
        WITH h1, h2, shared, count(DISTINCT a1) AS users1
        MATCH (h2)<-[:HAS_HASHTAG]-(tb:Toot)-[:AUTHORED_BY]->(a2:Autor)
        WITH h1, h2, shared, users1, count(DISTINCT a2) AS users2
        WITH h1, h2, shared,
             toFloat(shared) / (users1 + users2 - shared) AS shared_user_score
        RETURN h1.name AS tag1, h2.name AS tag2, shared_user_score
        ORDER BY shared_user_score DESC
    """, valid=valid_hashtags)
    return [dict(r) for r in result]

def combine_scores(cooc_results, user_results):
    """
    Kombiniert Co-Occurrence und Shared-User-Score.
    Gewichtung: 60% Co-Occurrence, 40% Shared Users.
    """
    cooc_map = {(r["tag1"], r["tag2"]): r["jaccard"] for r in cooc_results}
    user_map = {(r["tag1"], r["tag2"]): r["shared_user_score"] for r in user_results}
    all_pairs = set(cooc_map.keys()) | set(user_map.keys())
    combined = {}
    for pair in all_pairs:
        cooc  = cooc_map.get(pair, 0.0)
        users = user_map.get(pair, 0.0)
        combined[pair] = {
            "tag1": pair[0],
            "tag2": pair[1],
            "cooc_score": round(cooc, 4),
            "shared_user_score": round(users, 4),
            "combined_score": round(0.6 * cooc + 0.4 * users, 4)
        }
    return combined

def write_recommendations(tx, combined, top_n):
    """
    Schreibt RECOMMENDED-Kanten fuer Top-N Empfehlungen pro Hashtag.
    """
    per_tag = {}
    for pair, scores in combined.items():
        tag1, tag2 = pair
        for tag, other in [(tag1, tag2), (tag2, tag1)]:
            if tag not in per_tag:
                per_tag[tag] = []
            per_tag[tag].append({"other": other, **scores})

    total_written = 0
    for tag, recommendations in per_tag.items():
        top = sorted(recommendations, key=lambda x: x["combined_score"], reverse=True)[:top_n]
        for rank, rec in enumerate(top, 1):
            tx.run("""
                MATCH (h1:Hashtag {name: $tag})
                MATCH (h2:Hashtag {name: $other})
                MERGE (h1)-[r:RECOMMENDED]->(h2)
                SET r.coOccurScore    = $cooc,
                    r.sharedUserScore = $users,
                    r.combinedScore   = $combined,
                    r.rank            = $rank,
                    r.modelVersion    = 'v1-stufe1'
            """,
                tag=tag, other=rec["other"],
                cooc=rec["cooc_score"], users=rec["shared_user_score"],
                combined=rec["combined_score"], rank=rank
            )
            total_written += 1
    return total_written

def main():
    print("=" * 55)
    print("  Hashtag-Recommender - Stufe 1")
    print("  Co-Occurrence + Shared Users")
    print("=" * 55)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        print("\n1. Loesche alte RECOMMENDED-Kanten...")
        with driver.session() as s:
            s.execute_write(clear_recommendations)

        print(f"\n2. Filtere Hashtags (min. {MIN_HASHTAG_COUNT} Vorkommen)...")
        with driver.session() as s:
            valid = s.execute_read(get_valid_hashtags)
        log(f"{len(valid)} valide Hashtags gefunden")

        print("\n3. Berechne Co-Occurrence (Jaccard)...")
        with driver.session() as s:
            cooc = s.execute_read(compute_cooccurrence, valid)
        log(f"{len(cooc)} Paare gefunden")

        print("\n4. Berechne Shared Users...")
        with driver.session() as s:
            users = s.execute_read(compute_shared_users, valid)
        log(f"{len(users)} Paare gefunden")
        if users:
            print(f"         Beispiel: {users[0]}")

        print("\n5. Kombiniere Scores (60% CoOc, 40% SharedUsers)...")
        combined = combine_scores(cooc, users)
        log(f"{len(combined)} Paare total")

        print(f"\n6. Schreibe Top-{TOP_N} RECOMMENDED-Kanten...")
        with driver.session() as s:
            written = s.execute_write(write_recommendations, combined, TOP_N)
        log(f"{written} Kanten geschrieben")

        print("\n" + "=" * 55)
        print("  Fertig!")
        print("=" * 55)
        print("\nBeispiel-Abfrage im Neo4j Browser:")
        print("  MATCH (h:Hashtag {name: 'openscience'})-[r:RECOMMENDED]->(rec:Hashtag)")
        print("  RETURN rec.name, r.coOccurScore, r.sharedUserScore, r.combinedScore, r.rank")
        print("  ORDER BY r.rank")

    finally:
        driver.close()

if __name__ == "__main__":
    main()