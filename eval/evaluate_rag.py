"""Compare vector retrieval with hybrid RRF + FlashRank on a small labeled set."""
import os

import psycopg
from dotenv import load_dotenv
from flashrank import Ranker, RerankRequest
from pgvector.psycopg import register_vector
from embeddings import generate_embedding as gemini_generate_embedding

load_dotenv()
DB = os.getenv("DATABASE_URL", "postgresql://leaselens:leaselens@localhost:5432/leaselens")
TENANT, LEASE = "user_rahul", "lease_001"
CASES = [
    ("Is four months' deposit allowed?", "4.2", "Section 11"),
    ("Can the owner charge for repainting due to normal wear?", "8.1", "Section 17"),
    ("Can an old geyser coil failure be billed to the tenant?", "8.2", "Section 15"),
    ("Can the owner evict me on seven days notice without court?", "10.1", "Section 21"),
    ("What is the maximum residential security deposit?", "4.2", "Section 11"),
    ("Who repairs essential services and appliances?", "8.2", "Section 15"),
    ("Is routine aging damage the tenant's responsibility?", "8.2", "Section 17"),
    ("What process applies to eviction from rental premises?", "10.1", "Section 21"),
]


def retrieve(conn, model, query, hybrid):
    vec = model.encode(query, normalize_embeddings=True).tolist()
    # Two tenant-scoped corpora. Each retrieval mode gets at most 20 rows per corpus.
    rows = conn.execute("""
      (SELECT 'lease' corpus, clause_number citation, content, embedding <=> %s::vector distance,
       1.0/(60+row_number() over (order by embedding <=> %s::vector)) rrf
       FROM lease_clauses WHERE tenant_id=%s AND lease_id=%s ORDER BY embedding <=> %s::vector LIMIT 20)
      UNION ALL
      (SELECT 'statute', act_name||' '||section_number, content, embedding <=> %s::vector,
       1.0/(60+row_number() over (order by embedding <=> %s::vector))
       FROM statutory_clauses ORDER BY embedding <=> %s::vector LIMIT 20)
    """, (vec, vec, TENANT, LEASE, vec, vec, vec, vec)).fetchall()
    vector_ranked = sorted(rows, key=lambda r: r[3])[:6]
    if not hybrid:
        return vector_ranked[:3]
    query_rows = conn.execute("""
      SELECT 'lease' corpus, clause_number citation, content, ts_rank_cd(tsv,plainto_tsquery('english',%s)) score
      FROM lease_clauses WHERE tenant_id=%s AND lease_id=%s AND tsv @@ plainto_tsquery('english',%s)
      UNION ALL
      SELECT 'statute', act_name||' '||section_number, content, ts_rank_cd(tsv,plainto_tsquery('english',%s))
      FROM statutory_clauses WHERE tsv @@ plainto_tsquery('english',%s)
      ORDER BY score DESC LIMIT 20
    """, (query, TENANT, LEASE, query, query, query)).fetchall()
    scores = {}
    by_key = {}
    for rank, row in enumerate(vector_ranked, 1):
        key = (row[0], row[1]); scores[key] = scores.get(key, 0) + 1/(60+rank); by_key[key] = row
    for rank, row in enumerate(query_rows, 1):
        key=(row[0], row[1]); scores[key]=scores.get(key,0)+1/(60+rank); by_key[key]=row
    candidates = sorted(scores, key=scores.get, reverse=True)[:20]
    passages = [{"id": i, "text": by_key[key][2], "meta": {"key": key}} for i,key in enumerate(candidates)]
    reranked = Ranker(model_name="ms-marco-MiniLM-L-12-v2").rerank(RerankRequest(query=query, passages=passages))[:3]
    lookup = {p["id"]: candidates[p["id"]] for p in passages}
    return [by_key[lookup[int(item["id"])]] for item in reranked]


def metrics(results, expected):
    keys = {(r[0], r[1]) for r in results}
    gold = {("lease", expected[0]), ("statute", "Model Tenancy Act, 2021 " + expected[1])}
    relevant = keys & gold
    precision = len(relevant) / max(len(keys), 1)
    recall = len(relevant) / len(gold)
    return precision, recall


def main():
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    vector_values, hybrid_values = [], []
    with psycopg.connect(DB) as conn:
        register_vector(conn)
        for query, lease_gold, section_gold in CASES:
            vector_values.append(metrics(retrieve(conn, model, query, False), (lease_gold, section_gold)))
            hybrid_values.append(metrics(retrieve(conn, model, query, True), (lease_gold, section_gold)))
    print("Mode                         Context Precision   Citation Recall")
    for name, values in [("Vector-only", vector_values), ("Hybrid RRF + FlashRank", hybrid_values)]:
        print(f"{name:<28} {sum(x[0] for x in values)/len(values):>8.3f}             {sum(x[1] for x in values)/len(values):.3f}")
    print("Ground truth: 8 manually labeled queries; metrics are local to the seeded demo corpus.")


if __name__ == "__main__":
    main()
