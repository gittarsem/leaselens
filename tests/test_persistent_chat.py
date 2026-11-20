"""End-to-end check for tenant-scoped PostgreSQL-backed lease chat."""
from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

import psycopg

from agent.orchestrator import (
    DATABASE_URL,
    chat_with_lease,
    clear_chat_history,
    ensure_chat_messages_table,
    load_chat_history,
)
from ingestion.ingest_data import ingest_lease_pdf


TENANT_ID = "user_persist_test"
LEASE_ID = "lease_persist_01"
SAMPLE_PDF = PROJECT_ROOT / "sample_docs" / "sample_bengaluru_lease.pdf"
TABLES = ("chat_messages", "lease_clauses", "lease_accounts", "ledger_transactions")


def row_counts() -> dict[str, int]:
    with psycopg.connect(DATABASE_URL) as conn:
        return {
            table: conn.execute(
                f"SELECT count(*) FROM {table} WHERE tenant_id=%s AND lease_id=%s",
                (TENANT_ID, LEASE_ID)).fetchone()[0]
            for table in TABLES
        }


def main() -> None:
    ensure_chat_messages_table()
    assert SAMPLE_PDF.is_file(), f"Sample PDF not found: {SAMPLE_PDF}"
    assert all(value == 0 for value in row_counts().values()), (
        "The fixed test tenant/lease already contains rows; refusing to overwrite or delete them.")

    try:
        ingest_lease_pdf(SAMPLE_PDF, TENANT_ID, LEASE_ID,
                         Decimal("30000"), Decimal("150000"))
        first = asyncio.run(chat_with_lease(
            TENANT_ID, LEASE_ID, "What does Clause 7.4 say about painting charges?"))
        assert any(item.get("citation") == "7.4" for item in first["lease_citations"])
        assert first["statute_citations"]
        print("Turn 1 mode:", first["generation_mode"])
        print("Turn 1 search:", first["standalone_search_query"])

        second = asyncio.run(chat_with_lease(
            TENANT_ID, LEASE_ID,
            "Is that enforceable without GST receipts, and how much refund am I owed?"))
        assert any(item.get("citation") == "7.4" for item in second["lease_citations"])
        assert second["statute_citations"]
        assert second["ledger_audit"]["lawful_refundable_balance_inr"] == 150000.0
        print("Turn 2 mode:", second["generation_mode"])
        print("Turn 2 standalone search:", second["standalone_search_query"])
        print("Turn 2 refund:", second["ledger_audit"]["lawful_refundable_balance_inr"])

        # This separate database read simulates a browser reload.
        restored = load_chat_history(TENANT_ID, LEASE_ID)
        assert len(restored) == 4, f"Expected 4 restored messages, got {len(restored)}"
        assert [message["role"] for message in restored] == [
            "user", "assistant", "user", "assistant"]
        assistants = [message for message in restored if message["role"] == "assistant"]
        assert all(message["lease_citations"] for message in assistants)
        assert all(message["statute_citations"] for message in assistants)
        assert all(message["generation_mode"] for message in assistants)
        print("PASS: reload restored 4 messages; assistant citation metadata persisted")

        intruder_history = load_chat_history("user_intruder", LEASE_ID)
        assert intruder_history == [], f"Tenant isolation failure: {len(intruder_history)} messages leaked"
        print("PASS: intruder history is empty")

        clear_chat_history(TENANT_ID, LEASE_ID)
        assert load_chat_history(TENANT_ID, LEASE_ID) == []
        print("PASS: clear_chat_history deletes only this tenant/lease conversation")
    finally:
        with psycopg.connect(DATABASE_URL) as conn:
            for table in TABLES:
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=%s AND lease_id=%s",
                             (TENANT_ID, LEASE_ID))
        remaining = row_counts()
        assert all(value == 0 for value in remaining.values()), remaining
        print("Cleanup complete:", remaining)


if __name__ == "__main__":
    main()
