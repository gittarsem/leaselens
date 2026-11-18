"""Deterministic SQL audit of deposit and claimed deductions."""
import os

import psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()
mcp = FastMCP("LeaseLens deterministic rent ledger")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://leaselens:leaselens@localhost:5432/leaselens")


@mcp.tool()
def audit_deposit_and_ledger(tenant_id: str, lease_id: str) -> dict:
    """Calculate deposit ratio, claims, unsupported deductions and refundable balance."""
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute("""
          SELECT a.monthly_rent_inr, a.deposit_paid_inr,
            COALESCE(sum(t.amount_inr) FILTER (WHERE t.transaction_type='deduction_claimed'),0) claimed,
            COALESCE(sum(t.amount_inr) FILTER (WHERE t.transaction_type='deduction_claimed' AND t.receipt_reference IS NULL),0) unverified,
            COALESCE(sum(t.amount_inr) FILTER (WHERE t.transaction_type='deduction_claimed' AND t.receipt_reference IS NOT NULL),0) documented,
            COALESCE(sum(t.amount_inr) FILTER (WHERE t.transaction_type='refund_paid'),0) refunded
          FROM lease_accounts a LEFT JOIN ledger_transactions t USING (tenant_id,lease_id)
          WHERE a.tenant_id=%s AND a.lease_id=%s
          GROUP BY a.monthly_rent_inr,a.deposit_paid_inr
        """, (tenant_id, lease_id)).fetchone()
    if row is None:
        return {"tenant_id": tenant_id, "lease_id": lease_id, "error": "No lease account found."}
    rent, deposit, claimed, unverified, documented, refunded = map(float, row)
    cap = rent * 2
    excess = max(0.0, deposit - cap)
    # Only deductions with a recorded receipt are provisionally netted out. This is a
    # transparent accounting rule, not a legal determination of whether a deduction is valid.
    refundable = max(0.0, deposit - documented - refunded)
    return {"tenant_id": tenant_id, "lease_id": lease_id, "monthly_rent_inr": rent, "deposit_paid_inr": deposit,
            "deposit_to_rent_ratio_months": round(deposit / rent, 2) if rent else None,
            "illustrative_two_month_cap_inr": cap, "deposit_above_illustrative_cap_inr": excess,
            "total_claimed_deductions_inr": claimed, "unverified_deductions_without_receipts_inr": unverified,
            "documented_deductions_inr": documented, "refunds_already_paid_inr": refunded,
            "lawful_refundable_balance_inr": refundable,
            "calculation_note": "Refundable balance subtracts only deductions with a receipt reference; the Model Tenancy Act is a model law and state law/lease facts must be checked."}


if __name__ == "__main__":
    mcp.run()
