"""Tenant-scoped hybrid retrieval with Reciprocal Rank Fusion and FlashRank."""
from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP
from flashrank import Ranker, RerankRequest
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()
mcp = FastMCP("LeaseLens lease and statute retrieval")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://leaselens:leaselens@localhost:5432/leaselens")
embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")


@mcp.tool()
def compare_lease_against_statutes(tenant_id: str, lease_id: str, dispute_query: str) -> dict:
    """Find relevant lease and statutory clauses for a tenant dispute."""
    query_vector = embedder.encode(dispute_query, normalize_embeddings=True).tolist()
    sql = """
    WITH lease_vec AS (
      SELECT id, tenant_id, lease_id, clause_number AS citation, page_number, content,
             row_number() OVER (ORDER BY embedding <=> %(embedding)s::vector) AS vr
      FROM lease_clauses WHERE tenant_id=%(tenant)s AND lease_id=%(lease)s AND embedding IS NOT NULL
      ORDER BY embedding <=> %(embedding)s::vector LIMIT 20
    ), lease_fts AS (
      SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', %(query)s)) DESC) AS fr
      FROM lease_clauses WHERE tenant_id=%(tenant)s AND lease_id=%(lease)s AND tsv @@ plainto_tsquery('english', %(query)s) LIMIT 20
    ), statute_vec AS (
      SELECT id, row_number() OVER (ORDER BY embedding <=> %(embedding)s::vector) AS vr
      FROM statutory_clauses WHERE embedding IS NOT NULL ORDER BY embedding <=> %(embedding)s::vector LIMIT 20
    ), statute_fts AS (
      SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', %(query)s)) DESC) AS fr
      FROM statutory_clauses WHERE tsv @@ plainto_tsquery('english', %(query)s) LIMIT 20
    ), lease_rrf AS (
      SELECT id, sum(score) AS rrf FROM (
        SELECT id, 1.0/(60+vr) score FROM lease_vec UNION ALL SELECT id, 1.0/(60+fr) FROM lease_fts
      ) s GROUP BY id
    ), statute_rrf AS (
      SELECT id, sum(score) AS rrf FROM (
        SELECT id, 1.0/(60+vr) score FROM statute_vec UNION ALL SELECT id, 1.0/(60+fr) FROM statute_fts
      ) s GROUP BY id
    ), lease_candidates AS (
      SELECT 'lease' corpus, l.id, l.clause_number AS citation, l.page_number, l.content, r.rrf
      FROM lease_rrf r JOIN lease_clauses l USING(id)
      ORDER BY r.rrf DESC LIMIT 20
    ), statute_candidates AS (
      SELECT 'statute' corpus, s.id, s.act_name || ' ' || s.section_number AS citation,
             NULL::integer AS page_number, s.content, r.rrf
      FROM statute_rrf r JOIN statutory_clauses s USING(id)
      ORDER BY r.rrf DESC LIMIT 20
    )
    SELECT * FROM lease_candidates
    UNION ALL
    SELECT * FROM statute_candidates
    """
    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)
        rows = conn.execute(sql, {"embedding": query_vector, "tenant": tenant_id, "lease": lease_id, "query": dispute_query}).fetchall()
    if not rows:
        return {"tenant_id": tenant_id, "lease_id": lease_id, "query": dispute_query, "matches": [], "message": "No indexed clauses found; ingest a lease and seed statutes first."}
    lease_docs, statute_docs = [], []
    for row in rows:
        document = {"id": len(lease_docs) + len(statute_docs), "text": row[4],
                    "meta": {"corpus": row[0], "citation": row[2], "page_number": row[3], "rrf_score": float(row[5])}}
        (lease_docs if row[0] == "lease" else statute_docs).append(document)

    def rerank_corpus(passages):
        if not passages:
            return []
        return reranker.rerank(RerankRequest(query=dispute_query, passages=passages))[:2]

    # Rerank each corpus independently, preventing a large lease corpus from
    # displacing every statute citation (or vice versa) in a shared top-k.
    reranked_lease = rerank_corpus(lease_docs)
    reranked_statute = rerank_corpus(statute_docs)

    def to_matches(items):
        result = []
        for item in items:
            meta = item.get("meta", {})
            result.append({"corpus": meta.get("corpus"), "citation": meta.get("citation"), "page_number": meta.get("page_number"),
                           "content": item.get("text", ""), "rrf_score": meta.get("rrf_score"), "rerank_score": float(item.get("score", 0))})
        return result

    leases = to_matches(reranked_lease)
    statutes = to_matches(reranked_statute)
    matches = leases + statutes
    return {"tenant_id": tenant_id, "lease_id": lease_id, "query": dispute_query, "matches": matches,
            "lease_citations": leases, "statute_citations": statutes}


if __name__ == "__main__":
    mcp.run()
