"""
LeaseLens Tenant-Scoped Hybrid Retrieval

Features:
- Tenant and lease scoped retrieval
- Vector search using pgvector
- PostgreSQL full-text search
- Reciprocal Rank Fusion (RRF)
- FlashRank reranking
- Exact clause lookup and pinning
- Comprehensive lease review
- Financial exposure query detection
- Full lease retrieval for broad reviews and financial calculations
- Risk-category coverage
- Duplicate passage handling
- Preservation of conflicting clause versions
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is available when FastMCP launches this file as a subprocess.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP
from flashrank import Ranker, RerankRequest
from pgvector.psycopg import register_vector
from embeddings import generate_embedding as gemini_generate_embedding

# =========================================================
# Configuration
# =========================================================

load_dotenv()

mcp = FastMCP("LeaseLens lease and statute retrieval")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://leaselens:leaselens@localhost:5432/leaselens",
)



reranker = Ranker(
    model_name="ms-marco-MiniLM-L-12-v2"
)


# =========================================================
# Query Intent Detection
# =========================================================

def is_broad_lease_review(query: str) -> bool:
    """
    Detect comprehensive lease-review requests.
    """

    patterns = [
        r"\breview (?:my|the)? ?lease\b",
        r"\banalyze (?:my|the)? ?lease\b",
        r"\banalyse (?:my|the)? ?lease\b",
        r"\bcomprehensive review\b",
        r"\bfull review\b",
        r"\bcomplete review\b",
        r"\bfull lease review\b",
        r"\bcomplete lease review\b",
        r"\bunfavorable clauses\b",
        r"\bunfavourable clauses\b",
        r"\ball red flags\b",
        r"\bred flags\b",
        r"\ball risks\b",
        r"\bpotential risks\b",
        r"\ball issues\b",
        r"\ball problems\b",
        r"\bidentify all\b",
        r"\bidentify any risks\b",
        r"\bidentify any red flags\b",
        r"\bsummary of (?:my|the)? ?lease\b",
        r"\bsummarize (?:my|the)? ?lease\b",
        r"\bsummarise (?:my|the)? ?lease\b",
        r"\bsummarize the agreement\b",
        r"\bsummarise the agreement\b",
        r"\bentire lease\b",
        r"\bwhole lease\b",
        r"\bevery clause\b",
        r"\ball clauses\b",
        r"\bwhat should i be concerned about\b",
        r"\bwhat should i watch out for\b",
        r"\bwhat are the risks\b",
    ]

    return any(
        re.search(
            pattern,
            query,
            flags=re.IGNORECASE,
        )
        for pattern in patterns
    )


def is_financial_exposure_query(query: str) -> bool:
    """
    Detect financial-exposure queries that require
    comprehensive retrieval of financially relevant clauses.
    """

    patterns = [
        r"\bfinancial exposure\b",
        r"\bmaximum financial exposure\b",
        r"\btotal exposure\b",
        r"\bcalculate.*(?:cost|amount|exposure|penalty)\b",
        r"\bfinancial risk\b",
        r"\bhow much.*(?:pay|lose|owe)\b",
        r"\btotal.*(?:deduction|penalty|liability)\b",
        r"\bsecurity deposit\b",
        r"\block[- ]?in\b",
        r"\bpainting deduction\b",
        r"\blate fee\b",
        r"\breplacement cost\b",
        r"\bfinancial liability\b",
        r"\bmonetary liability\b",
        r"\bmaximum liability\b",
        r"\btotal liability\b",
        r"\bcalculate.*(?:rent|deposit|deduction)\b",
        r"\bcalculate.*(?:financial|monetary)\b",
        r"\bhow much.*(?:money|financial)\b",
    ]

    return any(
        re.search(
            pattern,
            query,
            flags=re.IGNORECASE,
        )
        for pattern in patterns
    )


# =========================================================
# Passage Normalization and Duplicate Detection
# =========================================================

def normalize_passage(text: str) -> str:
    """
    Normalize whitespace and casing for duplicate detection.
    """

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip().lower()


def normalize_clause_number(
    clause_number: str | None,
) -> str:
    """
    Normalize clause numbers for reliable exact matching.
    """

    if not clause_number:
        return ""

    return str(clause_number).strip()


# =========================================================
# Risk Categorization
# =========================================================

def classify_risk_category(content: str) -> str:
    """
    Assign a broad risk category to a lease passage.
    """

    text = content.lower()

    categories = {
        "termination": [
            "terminate",
            "termination",
            "evict",
            "eviction",
            "vacate",
            "lock-in",
            "lock in",
            "possession",
            "forfeit",
            "forfeiture",
        ],

        "notice": [
            "notice period",
            "written notice",
            "notice",
        ],

        "rent_and_penalties": [
            "rent",
            "late fee",
            "penalty",
            "interest",
            "payment",
            "arrears",
        ],

        "security_deposit": [
            "security deposit",
            "deposit",
            "refundable",
            "retain",
            "retained",
            "refund",
        ],

        "deductions_and_moveout": [
            "painting",
            "repainting",
            "cleaning",
            "deduct",
            "deduction",
            "move-out",
            "move out",
            "handover",
            "withhold",
        ],

        "maintenance_and_repairs": [
            "repair",
            "maintenance",
            "geyser",
            "appliance",
            "replacement",
            "wear and tear",
            "ordinary wear",
            "electrical",
            "plumbing",
        ],

        "landlord_powers": [
            "landlord may",
            "owner may",
            "without court",
            "without authority",
            "enter the premises",
            "possession immediately",
            "landlord's right",
            "landlord right",
        ],

        "tenant_liability": [
            "tenant shall pay",
            "tenant is responsible",
            "tenant liable",
            "liability",
            "damage",
            "tenant responsibility",
        ],
    }

    for category, keywords in categories.items():

        if any(
            keyword in text
            for keyword in keywords
        ):
            return category

    return "other"


# =========================================================
# Main Retrieval Tool
# =========================================================

@mcp.tool()
def compare_lease_against_statutes(
    tenant_id: str,
    lease_id: str,
    dispute_query: str,
) -> dict[str, Any]:
    """
    Retrieve relevant lease and statutory clauses
    for a tenant dispute or comprehensive lease review.

    Broad lease reviews and financial-exposure queries
    retrieve the complete indexed lease to prevent
    important clauses from being missed.
    """

    # -----------------------------------------------------
    # Detect explicitly requested clause numbers
    # -----------------------------------------------------

    requested_clause_numbers = list(
        dict.fromkeys(
            re.findall(
                r"\bclause\s+(\d+(?:\.\d+)*)\b",
                dispute_query,
                flags=re.IGNORECASE,
            )
        )
    )

    requested_clause_numbers = [
        normalize_clause_number(number)
        for number in requested_clause_numbers
    ]

    # -----------------------------------------------------
    # Detect query intent
    # -----------------------------------------------------

    broad_review = is_broad_lease_review(
        dispute_query
    )

    financial_exposure = is_financial_exposure_query(
        dispute_query
    )

    comprehensive_retrieval = (
        broad_review
        or financial_exposure
    )

    # -----------------------------------------------------
    # Configure retrieval
    # -----------------------------------------------------

    if broad_review:

        lease_limit = None
        statute_limit = 5

        retrieval_query = (
            dispute_query
            + " termination eviction lock-in lock in "
            + "notice rent late fees penalties "
            + "security deposit refund "
            + "deductions painting repainting cleaning "
            + "maintenance repairs appliance replacement "
            + "wear and tear damages liability "
            + "landlord powers tenant obligations "
            + "unilateral rights contradictions inconsistencies"
        )

    elif financial_exposure:

        lease_limit = None
        statute_limit = 5

        retrieval_query = (
            dispute_query
            + " rent security deposit refundable deposit "
            + "lock-in lock in early termination forfeiture "
            + "penalty notice period late fee interest "
            + "painting repainting deduction cleaning "
            + "maintenance repair appliance replacement "
            + "geyser damage liability payment refund "
            + "move-out charges"
        )

    else:

        lease_limit = 4
        statute_limit = 3

        retrieval_query = dispute_query

    # -----------------------------------------------------
    # Generate query embedding
    # -----------------------------------------------------

    query_vector = gemini_generate_embedding(
    retrieval_query,
    "RETRIEVAL_QUERY",
)

    # -----------------------------------------------------
    # Hybrid Retrieval SQL
    # -----------------------------------------------------

    sql = """
    WITH lease_vec AS (

        SELECT
            id,
            row_number() OVER (
                ORDER BY embedding <=> %(embedding)s::vector
            ) AS vr

        FROM lease_clauses

        WHERE tenant_id = %(tenant)s
          AND lease_id = %(lease)s
          AND embedding IS NOT NULL

        ORDER BY embedding <=> %(embedding)s::vector

        LIMIT 20
    ),

    lease_fts AS (

        SELECT
            id,
            row_number() OVER (
                ORDER BY ts_rank_cd(
                    tsv,
                    plainto_tsquery(
                        'english',
                        %(query)s
                    )
                ) DESC
            ) AS fr

        FROM lease_clauses

        WHERE tenant_id = %(tenant)s
          AND lease_id = %(lease)s
          AND tsv @@ plainto_tsquery(
              'english',
              %(query)s
          )

        LIMIT 20
    ),

    statute_vec AS (

        SELECT
            id,
            row_number() OVER (
                ORDER BY embedding <=> %(embedding)s::vector
            ) AS vr

        FROM statutory_clauses

        WHERE embedding IS NOT NULL

        ORDER BY embedding <=> %(embedding)s::vector

        LIMIT 20
    ),

    statute_fts AS (

        SELECT
            id,
            row_number() OVER (
                ORDER BY ts_rank_cd(
                    tsv,
                    plainto_tsquery(
                        'english',
                        %(query)s
                    )
                ) DESC
            ) AS fr

        FROM statutory_clauses

        WHERE tsv @@ plainto_tsquery(
            'english',
            %(query)s
        )

        LIMIT 20
    ),

    lease_rrf AS (

        SELECT
            id,
            sum(score) AS rrf

        FROM (

            SELECT
                id,
                1.0 / (60 + vr) AS score

            FROM lease_vec

            UNION ALL

            SELECT
                id,
                1.0 / (60 + fr) AS score

            FROM lease_fts

        ) s

        GROUP BY id
    ),

    statute_rrf AS (

        SELECT
            id,
            sum(score) AS rrf

        FROM (

            SELECT
                id,
                1.0 / (60 + vr) AS score

            FROM statute_vec

            UNION ALL

            SELECT
                id,
                1.0 / (60 + fr) AS score

            FROM statute_fts

        ) s

        GROUP BY id
    ),

    lease_candidates AS (

        SELECT
            'lease' AS corpus,
            l.id,
            l.clause_number AS citation,
            l.page_number,
            l.content,
            r.rrf

        FROM lease_rrf r

        JOIN lease_clauses l
            USING (id)

        ORDER BY r.rrf DESC

        LIMIT 20
    ),

    statute_candidates AS (

        SELECT
            'statute' AS corpus,
            s.id,

            s.act_name
                || ' '
                || s.section_number AS citation,

            NULL::integer AS page_number,
            s.content,
            r.rrf

        FROM statute_rrf r

        JOIN statutory_clauses s
            USING (id)

        ORDER BY r.rrf DESC

        LIMIT 20
    )

    SELECT *
    FROM lease_candidates

    UNION ALL

    SELECT *
    FROM statute_candidates
    """

    # -----------------------------------------------------
    # Execute Retrieval
    # -----------------------------------------------------

    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        register_vector(conn)

        rows = conn.execute(
            sql,
            {
                "embedding": query_vector,
                "tenant": tenant_id,
                "lease": lease_id,
                "query": retrieval_query,
            },
        ).fetchall()

        # -------------------------------------------------
        # Exact Clause Lookup
        # -------------------------------------------------

        exact_clause_rows = []

        if requested_clause_numbers:

            exact_clause_rows = conn.execute(
                """
                SELECT
                    id,
                    clause_number,
                    page_number,
                    content

                FROM lease_clauses

                WHERE tenant_id = %s
                  AND lease_id = %s
                  AND clause_number = ANY(%s)

                ORDER BY clause_number
                """,
                (
                    tenant_id,
                    lease_id,
                    requested_clause_numbers,
                ),
            ).fetchall()

        # -------------------------------------------------
        # Comprehensive Retrieval
        # -------------------------------------------------

        if comprehensive_retrieval:

            all_lease_rows = conn.execute(
                """
                SELECT
                    'lease' AS corpus,
                    id,
                    clause_number AS citation,
                    page_number,
                    content,
                    0.0 AS rrf

                FROM lease_clauses

                WHERE tenant_id = %s
                  AND lease_id = %s

                ORDER BY clause_number, id
                """,
                (
                    tenant_id,
                    lease_id,
                ),
            ).fetchall()

            existing_ids = {
                row[1]
                for row in rows
            }

            rows.extend(
                row
                for row in all_lease_rows
                if row[1] not in existing_ids
            )

    # -----------------------------------------------------
    # No Retrieval Results
    # -----------------------------------------------------

    if not rows and not exact_clause_rows:

        return {
            "tenant_id": tenant_id,
            "lease_id": lease_id,
            "query": dispute_query,
            "matches": [],
            "lease_citations": [],
            "statute_citations": [],
            "message": (
                "No indexed clauses found. "
                "Ingest a lease and seed statutes first."
            ),
        }

    # =====================================================
    # Deduplicate Passages
    # =====================================================

    lease_docs = []
    statute_docs = []

    seen_lease_content = set()
    seen_statute_content = set()

    for row in rows:

        corpus = row[0]
        content = row[4]

        normalized_content = normalize_passage(
            content
        )

        if corpus == "lease":

            # Preserve identical content under different
            # clause numbers. Deduplicate only repeated
            # records for the same clause and content.

            dedupe_key = (
                normalize_clause_number(row[2]),
                normalized_content,
            )

            if dedupe_key in seen_lease_content:
                continue

            seen_lease_content.add(
                dedupe_key
            )

        else:

            if normalized_content in seen_statute_content:
                continue

            seen_statute_content.add(
                normalized_content
            )

        document = {
            "id": row[1],
            "text": content,
            "meta": {
                "corpus": corpus,
                "citation": row[2],
                "page_number": row[3],
                "rrf_score": float(row[5]),
                "risk_category": classify_risk_category(
                    content
                ),
            },
        }

        if corpus == "lease":

            lease_docs.append(
                document
            )

        else:

            statute_docs.append(
                document
            )

    # =====================================================
    # Reranking
    # =====================================================

    def rerank_corpus(
        passages: list[dict[str, Any]],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:

        if not passages:
            return []

        reranked = reranker.rerank(
            RerankRequest(
                query=retrieval_query,
                passages=passages,
            )
        )

        if limit is None:
            return reranked

        return reranked[:limit]

    # Broad reviews and financial queries rerank
    # all retrieved lease clauses.

    reranked_lease = rerank_corpus(
        lease_docs,
        None if comprehensive_retrieval else lease_limit,
    )

    reranked_statute = rerank_corpus(
        statute_docs,
        statute_limit,
    )

    # =====================================================
    # Broad Review Risk-Category Coverage
    # =====================================================

    if broad_review and lease_limit is not None:

        selected = []
        selected_ids = set()
        covered_categories = set()

        # First pass:
        # Select the highest-ranked passage
        # from every available risk category.

        for item in reranked_lease:

            category = item.get(
                "meta",
                {},
            ).get(
                "risk_category",
                "other",
            )

            item_id = item.get("id")

            if category not in covered_categories:

                selected.append(item)

                selected_ids.add(
                    item_id
                )

                covered_categories.add(
                    category
                )

        # Second pass:
        # Fill remaining slots by reranker ranking.

        for item in reranked_lease:

            item_id = item.get("id")

            if item_id in selected_ids:
                continue

            selected.append(item)

            selected_ids.add(
                item_id
            )

            if len(selected) >= lease_limit:
                break

        reranked_lease = selected[
            :lease_limit
        ]

    # =====================================================
    # Exact Clause Pinning
    # =====================================================

    exact_clause_docs = [
        {
            "id": row[0],
            "text": row[3],
            "meta": {
                "corpus": "lease",
                "citation": row[1],
                "page_number": row[2],
                "rrf_score": None,
                "explicit_clause_match": True,
                "risk_category": classify_risk_category(
                    row[3]
                ),
            },
            "score": 1.0,
        }
        for row in exact_clause_rows
    ]

    if exact_clause_docs:

        pinned_ids = {
            item["id"]
            for item in exact_clause_docs
        }

        reranked_lease = (
            exact_clause_docs
            +
            [
                item
                for item in reranked_lease
                if item.get("id")
                not in pinned_ids
            ]
        )

        # Do not truncate pinned clauses for
        # comprehensive or financial queries.

        if not comprehensive_retrieval:

            reranked_lease = reranked_lease[
                :lease_limit
            ]

    # =====================================================
    # Format Matches
    # =====================================================

    def to_matches(
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        result = []

        for item in items:

            meta = item.get(
                "meta",
                {},
            )

            result.append(
                {
                    "corpus": meta.get(
                        "corpus"
                    ),

                    "citation": meta.get(
                        "citation"
                    ),

                    "page_number": meta.get(
                        "page_number"
                    ),

                    "content": item.get(
                        "text",
                        "",
                    ),

                    "rrf_score": meta.get(
                        "rrf_score"
                    ),

                    "rerank_score": float(
                        item.get(
                            "score",
                            0,
                        )
                    ),

                    "risk_category": meta.get(
                        "risk_category"
                    ),

                    "explicit_clause_match": meta.get(
                        "explicit_clause_match",
                        False,
                    ),
                }
            )

        return result

    # =====================================================
    # Final Response
    # =====================================================

    leases = to_matches(
        reranked_lease
    )

    statutes = to_matches(
        reranked_statute
    )

    matches = (
        leases
        +
        statutes
    )

    return {
        "tenant_id": tenant_id,
        "lease_id": lease_id,
        "query": dispute_query,

        "retrieval_mode": (
            "comprehensive"
            if broad_review
            else (
                "financial_exposure"
                if financial_exposure
                else "standard"
            )
        ),

        "retrieved_lease_clause_count": len(
            leases
        ),

        "retrieved_statute_count": len(
            statutes
        ),

        "matches": matches,

        "lease_citations": leases,

        "statute_citations": statutes,
    }


# =========================================================
# MCP Startup
# =========================================================

if __name__ == "__main__":
    mcp.run()