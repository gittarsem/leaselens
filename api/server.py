"""FastAPI bridge for LeaseLens."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(override=False)

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_mcp_client(server_path: str) -> Client:
    """Create an MCP client with deployment secrets explicitly passed to its subprocess."""
    absolute_server_path = PROJECT_ROOT / server_path

    child_env = os.environ.copy()

    # Explicitly preserve the keys used by MCP subprocesses. This also makes
    # the intent clear when running in Hugging Face Spaces or other containers.
    for key in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DATABASE_URL",
        "OPENROUTER_API_KEY",
    ):
        if os.getenv(key):
            child_env[key] = os.environ[key]

    transport = StdioTransport(
        command=sys.executable,
        args=[str(absolute_server_path)],
        env=child_env,
        cwd=str(PROJECT_ROOT),
    )

    return Client(transport)


from agent.orchestrator import (
    DATABASE_URL,
    GEMINI_MODELS,
    chat_with_lease,
    clear_chat_history,
    ensure_chat_messages_table,
    load_chat_history,
    tool_data,
)


ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PDF_BYTES = 30 * 1024 * 1024


app = FastAPI(
    title="LeaseLens API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoticeRequest(BaseModel):
    tenant_id: str
    lease_id: str
    dispute_summary: str = Field(
        min_length=1,
        max_length=12000,
    )
    matched_conflicts: dict[str, Any] = Field(
        default_factory=dict,
    )
    ledger_audit: dict[str, Any]
    force_deterministic: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _not_found(
    tenant_id: str,
    lease_id: str,
) -> None:

    with psycopg.connect(DATABASE_URL) as conn:

        workspace_result = conn.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM lease_accounts
                WHERE tenant_id = %s
                  AND lease_id = %s

                UNION

                SELECT 1
                FROM lease_clauses
                WHERE tenant_id = %s
                  AND lease_id = %s
            )
            """,
            (
                tenant_id,
                lease_id,
                tenant_id,
                lease_id,
            ),
        ).fetchone()

    if not workspace_result or not workspace_result[0]:

        raise HTTPException(
            status_code=404,
            detail="Lease workspace not found.",
        )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:

    postgres_ready = False
    pgvector_ready = False
    database_error = None

    try:

        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=3,
        ) as conn:

            conn.execute("SELECT 1").fetchone()

            postgres_ready = True

            pgvector_result = conn.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_extension
                    WHERE extname = 'vector'
                )
                """
            ).fetchone()

            pgvector_ready = bool(
                pgvector_result[0]
            )

    except Exception as exc:

        database_error = str(exc)

        traceback.print_exc()

    return {
        "status": (
            "ok"
            if postgres_ready and pgvector_ready
            else "degraded"
        ),
        "postgres": postgres_ready,
        "pgvector": pgvector_ready,
        "gemini": {
            "api_key_configured": bool(
                os.getenv("GEMINI_API_KEY")
            ),
            "fallback_models": GEMINI_MODELS,
        },
        "database_error": database_error,
    }


# ---------------------------------------------------------------------------
# List leases
# ---------------------------------------------------------------------------

@app.get("/leases")
def leases() -> list[dict[str, Any]]:

    try:

        ensure_chat_messages_table()

        with psycopg.connect(DATABASE_URL) as conn:

            rows = conn.execute(
                """
                WITH workspaces AS (
                    SELECT tenant_id, lease_id
                    FROM lease_accounts

                    UNION

                    SELECT tenant_id, lease_id
                    FROM lease_clauses
                ),

                clause_counts AS (
                    SELECT
                        tenant_id,
                        lease_id,
                        COUNT(*) AS clause_count
                    FROM lease_clauses
                    GROUP BY tenant_id, lease_id
                ),

                latest_chat AS (
                    SELECT
                        tenant_id,
                        lease_id,
                        MAX(created_at) AS latest_chat_at
                    FROM chat_messages
                    GROUP BY tenant_id, lease_id
                )

                SELECT
                    w.tenant_id,
                    w.lease_id,
                    COALESCE(c.clause_count, 0),
                    h.latest_chat_at,
                    a.monthly_rent_inr,
                    a.deposit_paid_inr

                FROM workspaces AS w

                LEFT JOIN clause_counts AS c
                    ON c.tenant_id = w.tenant_id
                   AND c.lease_id = w.lease_id

                LEFT JOIN latest_chat AS h
                    ON h.tenant_id = w.tenant_id
                   AND h.lease_id = w.lease_id

                LEFT JOIN lease_accounts AS a
                    ON a.tenant_id = w.tenant_id
                   AND a.lease_id = w.lease_id

                ORDER BY
                    h.latest_chat_at DESC NULLS LAST,
                    w.tenant_id,
                    w.lease_id
                """
            ).fetchall()

        return [
            {
                "tenant_id": row[0],
                "lease_id": row[1],
                "clause_count": row[2],
                "latest_chat_at": (
                    row[3].isoformat()
                    if row[3] is not None
                    else None
                ),
                "monthly_rent_inr": (
                    float(row[4])
                    if row[4] is not None
                    else None
                ),
                "security_deposit_paid_inr": (
                    float(row[5])
                    if row[5] is not None
                    else None
                ),
                "display_name": (
                    "Rahul Sharma — Lease #001"
                    if (
                        row[0],
                        row[1],
                    ) == (
                        "user_rahul",
                        "lease_001",
                    )
                    else row[1]
                ),
            }
            for row in rows
        ]

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

@app.get("/chat/{tenant_id}/{lease_id}")
def get_chat(
    tenant_id: str,
    lease_id: str,
) -> list[dict[str, Any]]:

    _not_found(
        tenant_id,
        lease_id,
    )

    return load_chat_history(
        tenant_id,
        lease_id,
    )


@app.delete("/chat/{tenant_id}/{lease_id}")
def delete_chat(
    tenant_id: str,
    lease_id: str,
) -> dict[str, bool]:

    _not_found(
        tenant_id,
        lease_id,
    )

    clear_chat_history(
        tenant_id,
        lease_id,
    )

    return {
        "cleared": True,
    }


# ---------------------------------------------------------------------------
# Delete lease
# ---------------------------------------------------------------------------

@app.delete("/leases/{tenant_id}/{lease_id}")
def delete_lease(
    tenant_id: str,
    lease_id: str,
) -> dict[str, bool]:

    _not_found(
        tenant_id,
        lease_id,
    )

    with psycopg.connect(DATABASE_URL) as conn:

        conn.execute(
            """
            DELETE FROM lease_clauses
            WHERE tenant_id = %s
              AND lease_id = %s
            """,
            (
                tenant_id,
                lease_id,
            ),
        )

        conn.execute(
            """
            DELETE FROM lease_accounts
            WHERE tenant_id = %s
              AND lease_id = %s
            """,
            (
                tenant_id,
                lease_id,
            ),
        )

        conn.execute(
            """
            DELETE FROM ledger_transactions
            WHERE tenant_id = %s
              AND lease_id = %s
            """,
            (
                tenant_id,
                lease_id,
            ),
        )

        conn.execute(
            """
            DELETE FROM chat_messages
            WHERE tenant_id = %s
              AND lease_id = %s
            """,
            (
                tenant_id,
                lease_id,
            ),
        )

        conn.commit()

    return {
        "deleted": True,
    }


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

@app.post("/chat")
async def post_chat(
    tenant_id: str = Form(...),
    lease_id: str = Form(...),
    message: str = Form(
        ...,
        min_length=1,
        max_length=12000,
    ),
    images: list[UploadFile] | None = File(default=None),
) -> dict[str, Any]:

    _not_found(
        tenant_id,
        lease_id,
    )

    if images and len(images) > 3:

        raise HTTPException(
            status_code=413,
            detail="Attach up to three images per question.",
        )

    attachments = []

    for image in images or []:

        if image.content_type not in ALLOWED_IMAGE_TYPES:

            raise HTTPException(
                status_code=415,
                detail=f"Unsupported image type: {image.content_type}",
            )

        content = await image.read(
            MAX_IMAGE_BYTES + 1
        )

        if len(content) > MAX_IMAGE_BYTES:

            raise HTTPException(
                status_code=413,
                detail=f"{image.filename} exceeds the 10 MB image limit.",
            )

        attachments.append(
            {
                "filename": image.filename or "image",
                "mime_type": image.content_type,
                "data": content,
            }
        )

    try:

        result = await chat_with_lease(
            tenant_id,
            lease_id,
            message,
            None,
            attachments,
        )

        return {
            key: result.get(key)
            for key in (
                "reply",
                "lease_citations",
                "statute_citations",
                "generation_mode",
                "model_used",
                "standalone_search_query",
                "ledger_audit",
                "attachments",
            )
        }

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Upload lease
# ---------------------------------------------------------------------------

@app.post("/leases/upload")
def upload_lease(
    file: UploadFile = File(...),
    tenant_id: str = Form(default=""),
    lease_id: str = Form(default=""),
    monthly_rent_inr: Decimal = Form(..., gt=0),
    security_deposit_paid_inr: Decimal = Form(..., ge=0),
    lease_name: str = Form(default=""),
) -> dict[str, Any]:

    if not tenant_id.strip():

        tenant_id = (
            f"tenant_{uuid.uuid4().hex[:8]}"
        )

    if not lease_id.strip():

        lease_id = (
            f"lease_{uuid.uuid4().hex[:8]}"
        )

    if lease_name.strip():

        display_name = lease_name.strip()

    else:

        display_name = (
            (file.filename or lease_id)
            .replace(".pdf", "")
            .replace(".PDF", "")
        )

    # Validate file type
    if (
        file.content_type != "application/pdf"
        and not (file.filename or "").lower().endswith(".pdf")
    ):

        raise HTTPException(
            status_code=415,
            detail="Upload a PDF rental agreement.",
        )

    # Read uploaded PDF
    content = file.file.read(
        MAX_PDF_BYTES + 1
    )

    if len(content) > MAX_PDF_BYTES:

        raise HTTPException(
            status_code=413,
            detail="PDF exceeds the 30 MB upload limit.",
        )

    # Validate PDF header
    if not content.startswith(b"%PDF"):

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF.",
        )

    try:

        from ingestion.ingest_data import ingest_lease_pdf

        # Save temporary PDF
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
        ) as temporary:

            temporary.write(content)
            temporary.flush()

            # Ingest PDF
            ingest_lease_pdf(
                Path(temporary.name),
                tenant_id,
                lease_id,
                monthly_rent_inr,
                security_deposit_paid_inr,
            )

        # Count successfully ingested clauses
        with psycopg.connect(DATABASE_URL) as conn:

            clause_result = conn.execute(
                """
                SELECT COUNT(*)
                FROM lease_clauses
                WHERE tenant_id = %s
                  AND lease_id = %s
                """,
                (
                    tenant_id,
                    lease_id,
                ),
            ).fetchone()

            count = clause_result[0]

        return {
            "tenant_id": tenant_id,
            "lease_id": lease_id,
            "filename": file.filename,
            "clause_count": count,
            "active": True,
            "display_name": display_name,
        }

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"PDF ingestion failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

@app.get("/audit/{tenant_id}/{lease_id}")
async def audit(
    tenant_id: str,
    lease_id: str,
    query: str = "Review this lease and its deposit deductions",
) -> dict[str, Any]:

    _not_found(
        tenant_id,
        lease_id,
    )

    try:

        async with (
            create_mcp_client("mcp_servers/lease_statute_rag.py") as rag,
            create_mcp_client("mcp_servers/rent_ledger.py") as ledger,
        ):

            rag_result = await rag.call_tool(
                "compare_lease_against_statutes",
                {
                    "tenant_id": tenant_id,
                    "lease_id": lease_id,
                    "dispute_query": query,
                },
            )

            ledger_result = await ledger.call_tool(
                "audit_deposit_and_ledger",
                {
                    "tenant_id": tenant_id,
                    "lease_id": lease_id,
                },
            )

        conflicts = tool_data(
            rag_result,
        )

        ledger_audit = tool_data(
            ledger_result,
        )

        with psycopg.connect(DATABASE_URL) as conn:

            transactions = conn.execute(
                """
                SELECT
                    transaction_type,
                    amount_inr,
                    description,
                    receipt_reference,
                    transaction_date

                FROM ledger_transactions

                WHERE tenant_id = %s
                  AND lease_id = %s

                ORDER BY transaction_date, id
                """,
                (
                    tenant_id,
                    lease_id,
                ),
            ).fetchall()

        itemized = [
            {
                "type": row[0],
                "amount_inr": float(row[1]),
                "description": row[2],
                "receipt_reference": row[3],
                "transaction_date": row[4].isoformat(),
            }
            for row in transactions
        ]

        lease_citations = conflicts.get(
            "lease_citations",
            [],
        )

        statute_citations = conflicts.get(
            "statute_citations",
            [],
        )

        return {
            "tenant_id": tenant_id,
            "lease_id": lease_id,
            "ledger_audit": ledger_audit,
            "itemized_deductions": [
                row
                for row in itemized
                if row["type"] in {
                    "deduction_claimed",
                    "refund_paid",
                }
            ],
            "lease_citations": lease_citations,
            "statute_citations": statute_citations,
            "conflict_pairs": list(
                zip(
                    lease_citations,
                    statute_citations,
                )
            ),
        }

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Audit failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Notice generation
# ---------------------------------------------------------------------------

@app.post("/notice")
async def notice(
    request: NoticeRequest,
) -> dict[str, Any]:

    if (
        "lawful_refundable_balance_inr"
        not in request.ledger_audit
    ):

        raise HTTPException(
            status_code=422,
            detail="Pass the result from the SQL deposit audit.",
        )

    try:

        async with create_mcp_client(
            "mcp_servers/notice_drafter.py",
        ) as notice_client:

            result = await notice_client.call_tool(
                "generate_dispute_package",
                {
                    "tenant_id": request.tenant_id,
                    "lease_id": request.lease_id,
                    "dispute_summary": request.dispute_summary,
                    "matched_conflicts": json.dumps(
                        request.matched_conflicts,
                        ensure_ascii=False,
                    ),
                    "ledger_audit": json.dumps(
                        request.ledger_audit,
                        ensure_ascii=False,
                    ),
                    "force_deterministic": (
                        request.force_deterministic
                    ),
                },
            )

        return tool_data(
            result,
        )

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Notice generation failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Frontend static serving
# ---------------------------------------------------------------------------

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


_DIST_DIR = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "dist"
)


if _DIST_DIR.exists():

    assets_dir = _DIST_DIR / "assets"

    if assets_dir.exists():

        app.mount(
            "/assets",
            StaticFiles(
                directory=str(assets_dir),
            ),
            name="assets",
        )

    @app.get("/{full_path:path}")
    async def serve_spa(
        full_path: str,
    ):

        if full_path.startswith("api/"):

            raise HTTPException(
                status_code=404,
                detail="Not Found",
            )

        candidate = _DIST_DIR / full_path

        if (
            full_path
            and candidate.is_file()
        ):

            return FileResponse(
                str(candidate),
            )

        return FileResponse(
            str(_DIST_DIR / "index.html"),
        )