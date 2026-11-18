"""Ingest lease PDFs or load the reproducible India tenancy demo corpus."""
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

load_dotenv()
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL = SentenceTransformer(MODEL_NAME)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://leaselens:leaselens@localhost:5432/leaselens")

STATUTES = [
    ("India (illustrative; state adoption varies)", "Model Tenancy Act, 2021", "Section 11", "The security deposit for residential premises shall not exceed two months' rent."),
    ("India (illustrative; state adoption varies)", "Model Tenancy Act, 2021", "Section 12", "The security deposit is to be refunded when the tenancy ends, subject to lawful agreed deductions and the applicable statutory process."),
    ("India (illustrative; state adoption varies)", "Model Tenancy Act, 2021", "Section 15", "The landlord shall keep the premises fit for habitation and carry out structural repairs and repairs to essential services unless damage is caused by the tenant."),
    ("India (illustrative; state adoption varies)", "Model Tenancy Act, 2021", "Section 16", "The tenant is responsible for minor repairs as prescribed; responsibility for other repairs depends on the Act, agreement, and cause of damage."),
    ("India (illustrative; state adoption varies)", "Model Tenancy Act, 2021", "Section 17", "A tenant is not liable for ordinary wear and tear arising from normal use of the premises."),
    ("India (illustrative; state adoption varies)", "Model Tenancy Act, 2021", "Section 21", "A landlord shall not evict a tenant except in accordance with the grounds and procedure established by applicable law, including an order of the Rent Court where required."),
]
DEMO_LEASE = [
    ("4.2", 2, "Tenant shall pay a security deposit equal to four months' rent. The whole deposit may be retained until the landlord is satisfied with the condition of the flat."),
    ("8.1", 4, "Tenant shall pay the cost of repainting the entire flat at move-out, regardless of the duration of tenancy or ordinary wear and tear; landlord may deduct a standard repainting charge without invoices."),
    ("8.2", 4, "Tenant is responsible for replacement of all geyser components, including failure caused by age or ordinary use. No receipt is required for landlord deductions."),
    ("9.1", 5, "Tenant will pay reasonable, itemised cleaning charges supported by an invoice; charges for ordinary use must be documented."),
    ("10.1", 6, "Landlord may terminate the tenancy and take possession immediately on giving seven days' notice, without court or Rent Authority process."),
]


def connect():
    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)
    return conn


def save_statute(conn, item):
    jurisdiction, act, section, content = item
    embedding = MODEL.encode(content, normalize_embeddings=True).tolist()
    conn.execute("""INSERT INTO statutory_clauses (jurisdiction,act_name,section_number,content,embedding)
      VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""", (jurisdiction, act, section, content, embedding))


def add_demo(conn):
    for item in STATUTES:
        exists = conn.execute("SELECT 1 FROM statutory_clauses WHERE act_name=%s AND section_number=%s", (item[1], item[2])).fetchone()
        if not exists:
            save_statute(conn, item)
    for number, page, content in DEMO_LEASE:
        exists = conn.execute("SELECT 1 FROM lease_clauses WHERE tenant_id='user_rahul' AND lease_id='lease_001' AND clause_number=%s", (number,)).fetchone()
        if not exists:
            conn.execute("INSERT INTO lease_clauses(tenant_id,lease_id,clause_number,page_number,content,embedding) VALUES (%s,%s,%s,%s,%s,%s)",
                         ('user_rahul', 'lease_001', number, page, content, MODEL.encode(content, normalize_embeddings=True).tolist()))
    for kind, amount, description, receipt in [
        ('deduction_claimed', 28000, 'Blanket repainting of entire flat', None),
        ('deduction_claimed', 6500, 'Aging geyser coil burnout attributed to tenant', None),
        ('deduction_claimed', 2500, 'Deep cleaning supported by itemised receipt', 'RCPT-CLEAN-014'),
    ]:
        conn.execute("""INSERT INTO ledger_transactions(tenant_id,lease_id,transaction_type,amount_inr,description,receipt_reference)
          SELECT %s,%s,%s,%s,%s,%s WHERE NOT EXISTS
          (SELECT 1 FROM ledger_transactions WHERE tenant_id=%s AND lease_id=%s AND description=%s)""",
          ('user_rahul','lease_001',kind,amount,description,receipt,'user_rahul','lease_001',description))


def split_clauses(text: str):
    # Headings such as 1., 1.2, Clause 4, or SECTION 7 start a new chunk.
    matches = list(re.finditer(r"(?im)^\s*(?:(?:clause|section)\s+)?(\d+(?:\.\d+)*[A-Z]?)\s*(?:\([^\n)]*\))?\s*[).:-]?\s+", text))
    if not matches:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return [(f"p{i // 1500 + 1}", cleaned[i:i + 1500]) for i in range(0, len(cleaned), 1500) if cleaned[i:i + 1500]]
    chunks = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = re.sub(r"\s+", " ", text[match.start():end]).strip()
        if len(content) > 30:
            chunks.append((match.group(1), content))
    return chunks


def ingest_pdf(path: Path, tenant_id: str, lease_id: str):
    reader = PdfReader(str(path))
    with connect() as conn:
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            for number, content in split_clauses(text):
                vector = MODEL.encode(content, normalize_embeddings=True).tolist()
                conn.execute("""INSERT INTO lease_clauses(tenant_id,lease_id,clause_number,page_number,content,embedding)
                  VALUES (%s,%s,%s,%s,%s,%s)""", (tenant_id, lease_id, number, page_number, content, vector))


def ingest_lease_pdf(path: Path, tenant_id: str, lease_id: str,
                     monthly_rent_inr: Decimal | None = None,
                     deposit_paid_inr: Decimal | None = None):
    """Ingest PDF clauses and optionally establish the lease's financial account."""
    if (monthly_rent_inr is None) != (deposit_paid_inr is None):
        raise ValueError("monthly_rent_inr and deposit_paid_inr must be supplied together")
    if monthly_rent_inr is not None and (monthly_rent_inr <= 0 or deposit_paid_inr < 0):
        raise ValueError("rent must be positive and deposit must be non-negative")
    ingest_pdf(path, tenant_id, lease_id)
    if monthly_rent_inr is not None:
        with connect() as conn:
            conn.execute("""INSERT INTO lease_accounts(tenant_id,lease_id,monthly_rent_inr,deposit_paid_inr)
              VALUES (%s,%s,%s,%s)
              ON CONFLICT (tenant_id,lease_id) DO UPDATE SET
                monthly_rent_inr=EXCLUDED.monthly_rent_inr,
                deposit_paid_inr=EXCLUDED.deposit_paid_inr""",
              (tenant_id, lease_id, monthly_rent_inr, deposit_paid_inr))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Load statutory clauses and lease_001 demo clauses")
    parser.add_argument("--pdf", type=Path, help="Rental agreement PDF to ingest")
    parser.add_argument("--tenant-id", default="user_rahul")
    parser.add_argument("--lease-id", default="lease_001")
    parser.add_argument("--rent", type=Decimal, help="Monthly rent in INR for the lease account")
    parser.add_argument("--deposit", type=Decimal, help="Deposit paid in INR for the lease account")
    args = parser.parse_args()
    if not args.seed and not args.pdf:
        parser.error("supply --seed and/or --pdf")
    with connect() as conn:
        if args.seed:
            add_demo(conn)
    if args.pdf:
        if (args.rent is None) != (args.deposit is None):
            parser.error("--rent and --deposit must be supplied together")
        ingest_lease_pdf(args.pdf, args.tenant_id, args.lease_id, args.rent, args.deposit)
    elif args.rent is not None or args.deposit is not None:
        parser.error("--rent and --deposit require --pdf")
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
