"""
Ingest lease PDFs or load the reproducible India tenancy demo corpus.

Features:
- CPU-only sentence embeddings (Hugging Face Spaces compatible)
- Lazy model loading
- PDF text extraction
- Clause splitting with page-aware fallback chunks
- Safe lease re-ingestion without duplicate clauses
- PostgreSQL + pgvector storage
- Demo statutory corpus and lease data
"""

from __future__ import annotations

import argparse
import os
import re
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

# Force CPU inference for Hugging Face Spaces.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Lazy model initialization to avoid loading the model unnecessarily.
MODEL: SentenceTransformer | None = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://leaselens:leaselens@localhost:5432/leaselens",
)


def get_model() -> SentenceTransformer:
    """Load the embedding model lazily using CPU."""

    global MODEL

    if MODEL is None:
        MODEL = SentenceTransformer(
            MODEL_NAME,
            device="cpu",
        )

    return MODEL


# ---------------------------------------------------------------------------
# Demo statutory corpus
# ---------------------------------------------------------------------------

STATUTES = [
    (
        "India (illustrative; state adoption varies)",
        "Model Tenancy Act, 2021",
        "Section 11",
        (
            "The security deposit for residential premises shall not exceed "
            "two months' rent."
        ),
    ),
    (
        "India (illustrative; state adoption varies)",
        "Model Tenancy Act, 2021",
        "Section 12",
        (
            "The security deposit is to be refunded when the tenancy ends, "
            "subject to lawful agreed deductions and the applicable statutory process."
        ),
    ),
    (
        "India (illustrative; state adoption varies)",
        "Model Tenancy Act, 2021",
        "Section 15",
        (
            "The landlord shall keep the premises fit for habitation and carry out "
            "structural repairs and repairs to essential services unless damage "
            "is caused by the tenant."
        ),
    ),
    (
        "India (illustrative; state adoption varies)",
        "Model Tenancy Act, 2021",
        "Section 16",
        (
            "The tenant is responsible for minor repairs as prescribed; responsibility "
            "for other repairs depends on the Act, agreement, and cause of damage."
        ),
    ),
    (
        "India (illustrative; state adoption varies)",
        "Model Tenancy Act, 2021",
        "Section 17",
        (
            "A tenant is not liable for ordinary wear and tear arising from normal "
            "use of the premises."
        ),
    ),
    (
        "India (illustrative; state adoption varies)",
        "Model Tenancy Act, 2021",
        "Section 21",
        (
            "A landlord shall not evict a tenant except in accordance with the grounds "
            "and procedure established by applicable law, including an order of the "
            "Rent Court where required."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Demo lease corpus
# ---------------------------------------------------------------------------

DEMO_LEASE = [
    (
        "4.2",
        2,
        (
            "Tenant shall pay a security deposit equal to four months' rent. "
            "The whole deposit may be retained until the landlord is satisfied "
            "with the condition of the flat."
        ),
    ),
    (
        "8.1",
        4,
        (
            "Tenant shall pay the cost of repainting the entire flat at move-out, "
            "regardless of the duration of tenancy or ordinary wear and tear; "
            "landlord may deduct a standard repainting charge without invoices."
        ),
    ),
    (
        "8.2",
        4,
        (
            "Tenant is responsible for replacement of all geyser components, "
            "including failure caused by age or ordinary use. No receipt is "
            "required for landlord deductions."
        ),
    ),
    (
        "9.1",
        5,
        (
            "Tenant will pay reasonable, itemised cleaning charges supported "
            "by an invoice; charges for ordinary use must be documented."
        ),
    ),
    (
        "10.1",
        6,
        (
            "Landlord may terminate the tenancy and take possession immediately "
            "on giving seven days' notice, without court or Rent Authority process."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def connect():
    """Connect to PostgreSQL and register pgvector."""

    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)

    return conn


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def generate_embedding(text: str) -> list[float]:
    """Generate a normalized CPU embedding."""

    model = get_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()


# ---------------------------------------------------------------------------
# Statutory clause ingestion
# ---------------------------------------------------------------------------

def save_statute(conn, item):
    """Generate an embedding and save a statutory clause."""

    jurisdiction, act, section, content = item

    embedding = generate_embedding(content)

    conn.execute(
        """
        INSERT INTO statutory_clauses (
            jurisdiction,
            act_name,
            section_number,
            content,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            jurisdiction,
            act,
            section,
            content,
            embedding,
        ),
    )


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

def add_demo(conn):
    """Load statutory clauses, demo lease clauses, and transactions."""

    # Seed statutory clauses.
    for item in STATUTES:
        exists = conn.execute(
            """
            SELECT 1
            FROM statutory_clauses
            WHERE act_name = %s
              AND section_number = %s
            """,
            (
                item[1],
                item[2],
            ),
        ).fetchone()

        if not exists:
            save_statute(conn, item)

    # Seed demo lease clauses.
    for number, page, content in DEMO_LEASE:

        exists = conn.execute(
            """
            SELECT 1
            FROM lease_clauses
            WHERE tenant_id = 'user_rahul'
              AND lease_id = 'lease_001'
              AND clause_number = %s
            """,
            (number,),
        ).fetchone()

        if not exists:

            embedding = generate_embedding(content)

            conn.execute(
                """
                INSERT INTO lease_clauses (
                    tenant_id,
                    lease_id,
                    clause_number,
                    page_number,
                    content,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    "user_rahul",
                    "lease_001",
                    number,
                    page,
                    content,
                    embedding,
                ),
            )

    # Seed demo financial transactions.
    demo_transactions = [
        (
            "deduction_claimed",
            28000,
            "Blanket repainting of entire flat",
            None,
        ),
        (
            "deduction_claimed",
            6500,
            "Aging geyser coil burnout attributed to tenant",
            None,
        ),
        (
            "deduction_claimed",
            2500,
            "Deep cleaning supported by itemised receipt",
            "RCPT-CLEAN-014",
        ),
    ]

    for kind, amount, description, receipt in demo_transactions:

        conn.execute(
            """
            INSERT INTO ledger_transactions (
                tenant_id,
                lease_id,
                transaction_type,
                amount_inr,
                description,
                receipt_reference
            )
            SELECT %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM ledger_transactions
                WHERE tenant_id = %s
                  AND lease_id = %s
                  AND description = %s
            )
            """,
            (
                "user_rahul",
                "lease_001",
                kind,
                amount,
                description,
                receipt,
                "user_rahul",
                "lease_001",
                description,
            ),
        )


# ---------------------------------------------------------------------------
# PDF clause splitting
# ---------------------------------------------------------------------------

def split_clauses(
    text: str,
    page_number: int = 1,
):
    """
    Split lease text into clauses.

    Supports headings such as:

        1.
        1.2
        Clause 4
        Section 7
        4.2(a)

    If no headings are detected, the text is split into approximately
    1500-character chunks with page-aware identifiers.
    """

    clause_pattern = re.compile(
        r"(?im)^\s*"
        r"(?:(?:clause|section)\s+)?"
        r"(\d+(?:\.\d+)*(?:[A-Z])?)"
        r"(?:\([a-zA-Z0-9]+\))?"
        r"\s*[).:-]?\s+"
    )

    matches = list(clause_pattern.finditer(text))

    # -----------------------------------------------------------------------
    # Fallback chunking
    # -----------------------------------------------------------------------

    if not matches:

        cleaned = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        chunk_size = 1500

        return [
            (
                f"page_{page_number}_chunk_{i // chunk_size + 1}",
                cleaned[i:i + chunk_size],
            )
            for i in range(0, len(cleaned), chunk_size)
            if cleaned[i:i + chunk_size]
        ]

    # -----------------------------------------------------------------------
    # Heading-based splitting
    # -----------------------------------------------------------------------

    chunks = []

    for i, match in enumerate(matches):

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(text)
        )

        content = re.sub(
            r"\s+",
            " ",
            text[match.start():end],
        ).strip()

        if len(content) > 30:

            chunks.append(
                (
                    match.group(1),
                    content,
                )
            )

    # If headings were detected but no meaningful chunks were created,
    # fall back to page-based chunking.

    if not chunks:

        cleaned = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        chunk_size = 1500

        return [
            (
                f"page_{page_number}_chunk_{i // chunk_size + 1}",
                cleaned[i:i + chunk_size],
            )
            for i in range(0, len(cleaned), chunk_size)
            if cleaned[i:i + chunk_size]
        ]

    return chunks


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_pdf_clauses(path: Path):
    """
    Extract text from a PDF and return clause records.

    Returns:
        list[tuple[str, int, str]]

        Each tuple contains:
            clause_number
            page_number
            content
    """

    reader = PdfReader(str(path))

    extracted_clauses = []

    for page_number, page in enumerate(reader.pages, start=1):

        text = page.extract_text() or ""

        if not text.strip():
            continue

        clauses = split_clauses(
            text,
            page_number=page_number,
        )

        for number, content in clauses:

            if not content.strip():
                continue

            extracted_clauses.append(
                (
                    number,
                    page_number,
                    content,
                )
            )

    if not extracted_clauses:

        raise ValueError(
            "No readable text was found in the PDF. "
            "The document may be scanned or image-based. "
            "OCR support may be required."
        )

    return extracted_clauses


# ---------------------------------------------------------------------------
# PDF ingestion
# ---------------------------------------------------------------------------

def ingest_pdf(
    path: Path,
    tenant_id: str,
    lease_id: str,
):
    """
    Extract clauses from a PDF and save them with embeddings.

    Existing clauses for the same tenant and lease are replaced.

    Embeddings are generated before modifying the database, so a model
    failure does not delete the previous lease data.
    """

    if not path.exists():

        raise FileNotFoundError(
            f"PDF file not found: {path}"
        )

    if path.suffix.lower() != ".pdf":

        raise ValueError(
            "Only PDF files are supported."
        )

    # -----------------------------------------------------------------------
    # Extract clauses
    # -----------------------------------------------------------------------

    extracted_clauses = extract_pdf_clauses(path)

    # -----------------------------------------------------------------------
    # Generate embeddings before database modifications
    # -----------------------------------------------------------------------

    prepared_clauses = []

    for number, page_number, content in extracted_clauses:

        vector = generate_embedding(content)

        prepared_clauses.append(
            (
                number,
                page_number,
                content,
                vector,
            )
        )

    if not prepared_clauses:

        raise ValueError(
            "No clauses were extracted from the PDF."
        )

    # -----------------------------------------------------------------------
    # Replace existing lease clauses atomically
    # -----------------------------------------------------------------------

    with connect() as conn:

        # Remove existing clauses for this lease.
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

        # Insert newly extracted clauses.
        for number, page_number, content, vector in prepared_clauses:

            conn.execute(
                """
                INSERT INTO lease_clauses (
                    tenant_id,
                    lease_id,
                    clause_number,
                    page_number,
                    content,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    lease_id,
                    number,
                    page_number,
                    content,
                    vector,
                ),
            )

    print(
        f"Successfully ingested {len(prepared_clauses)} clauses "
        f"for tenant={tenant_id}, lease={lease_id}"
    )


# ---------------------------------------------------------------------------
# Complete lease ingestion
# ---------------------------------------------------------------------------

def ingest_lease_pdf(
    path: Path,
    tenant_id: str,
    lease_id: str,
    monthly_rent_inr: Decimal | None = None,
    deposit_paid_inr: Decimal | None = None,
):
    """
    Ingest PDF clauses and optionally establish the lease financial account.
    """

    # Rent and deposit must either both be provided or both be omitted.
    if (monthly_rent_inr is None) != (deposit_paid_inr is None):

        raise ValueError(
            "monthly_rent_inr and deposit_paid_inr "
            "must be supplied together"
        )

    # Validate financial inputs.
    if monthly_rent_inr is not None:

        assert deposit_paid_inr is not None

        if (
            monthly_rent_inr <= 0
            or deposit_paid_inr < 0
        ):

            raise ValueError(
                "Rent must be positive and deposit must be non-negative."
            )

    # Ingest PDF clauses.
    ingest_pdf(
        path,
        tenant_id,
        lease_id,
    )

    # Establish or update the lease financial account.
    if monthly_rent_inr is not None:

        assert deposit_paid_inr is not None

        with connect() as conn:

            conn.execute(
                """
                INSERT INTO lease_accounts (
                    tenant_id,
                    lease_id,
                    monthly_rent_inr,
                    deposit_paid_inr
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, lease_id)
                DO UPDATE SET
                    monthly_rent_inr = EXCLUDED.monthly_rent_inr,
                    deposit_paid_inr = EXCLUDED.deposit_paid_inr
                """,
                (
                    tenant_id,
                    lease_id,
                    monthly_rent_inr,
                    deposit_paid_inr,
                ),
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="LeaseLens ingestion utility"
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load statutory clauses and lease_001 demo clauses",
    )

    parser.add_argument(
        "--pdf",
        type=Path,
        help="Rental agreement PDF to ingest",
    )

    parser.add_argument(
        "--tenant-id",
        default="user_rahul",
    )

    parser.add_argument(
        "--lease-id",
        default="lease_001",
    )

    parser.add_argument(
        "--rent",
        type=Decimal,
        help="Monthly rent in INR for the lease account",
    )

    parser.add_argument(
        "--deposit",
        type=Decimal,
        help="Deposit paid in INR for the lease account",
    )

    args = parser.parse_args()

    if not args.seed and not args.pdf:

        parser.error(
            "Supply --seed and/or --pdf"
        )

    # -----------------------------------------------------------------------
    # Load demo data
    # -----------------------------------------------------------------------

    if args.seed:

        with connect() as conn:

            add_demo(conn)

        print("Demo corpus seeded successfully.")

    # -----------------------------------------------------------------------
    # Ingest PDF
    # -----------------------------------------------------------------------

    if args.pdf:

        if (args.rent is None) != (args.deposit is None):

            parser.error(
                "--rent and --deposit must be supplied together"
            )

        ingest_lease_pdf(
            args.pdf,
            args.tenant_id,
            args.lease_id,
            args.rent,
            args.deposit,
        )

    elif args.rent is not None or args.deposit is not None:

        parser.error(
            "--rent and --deposit require --pdf"
        )

    print("Ingestion complete.")


if __name__ == "__main__":
    main()