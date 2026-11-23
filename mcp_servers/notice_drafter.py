"""Validated dispute assessment and formal notice drafting."""
import asyncio
import json
import logging
import os
from decimal import Decimal

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from agent.llm_router import generate_with_handoff

load_dotenv(override=False)
mcp = FastMCP("LeaseLens dispute package and notice")
logger = logging.getLogger(__name__)

# Import the multi-provider router (lazy to avoid circular issues at module init)
def _router():
    from agent.llm_router import generate_with_handoff
    return generate_with_handoff

def _run_async(coro):
    """Run an async coroutine safely from synchronous code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # A loop is already running in this thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()

class DisputeRiskAssessment(BaseModel):
    # Gemini's structured-output schema does not accept JSON Schema's
    # additionalProperties keyword. Keep strict field validation in Pydantic
    # while allowing the SDK to emit a Gemini-compatible schema.
    model_config = ConfigDict(strict=True)
    risk_score_0_to_100: int = Field(ge=0, le=100)
    risk_level: str = Field(pattern="^(low|moderate|high)$")
    unenforceable_lease_clauses: list[str]
    violated_statutes: list[str]
    lawful_refundable_amount_inr: float = Field(ge=0)


def _json_object(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fallback_assessment(audit: dict, conflicts: dict) -> DisputeRiskAssessment:
    unverified = Decimal(str(audit.get("unverified_deductions_without_receipts_inr", 0)))
    excess = Decimal(str(audit.get("deposit_above_illustrative_cap_inr", 0)))
    lease_items = conflicts.get("lease_citations", [])
    statute_items = conflicts.get("statute_citations", [])
    lease_clauses = []
    for item in lease_items:
        text = str(item.get("content", "")).lower()
        if any(term in text for term in ("wear and tear", "without invoices", "without bills", "no bills", "no receipt", "ordinary use", "without court", "painting", "repainting")):
            lease_clauses.append(f"Clause {item.get('citation', 'unidentified')}: potential conflict requiring review under applicable state law.")
    has_unverified_claim = unverified > 0
    has_excess_deposit = excess > 0
    has_potential_clause_conflict = bool(lease_clauses)
    score = (78 if has_unverified_claim and has_excess_deposit
             else 78 if has_excess_deposit and has_potential_clause_conflict
             else 68 if has_unverified_claim or has_potential_clause_conflict
             else 52 if has_excess_deposit else 30)
    risk_level = "high" if score >= 70 else "moderate" if score >= 40 else "low"
    statutes = [
        f"{item.get('citation', 'Unidentified provision')} (potentially relevant reference; applicability and violation require local legal review)."
        for item in statute_items
    ]
    return DisputeRiskAssessment(
        risk_score_0_to_100=score,
        risk_level=risk_level,
        unenforceable_lease_clauses=lease_clauses,
        violated_statutes=statutes,
        lawful_refundable_amount_inr=float(Decimal(str(audit["lawful_refundable_balance_inr"]))),
    )


def _money(value) -> str:
    """Format INR using Decimal to avoid floating-point precision errors."""
    try:
        amount = Decimal(str(value or 0))
    except Exception:
        amount = Decimal("0")
    return f"{amount:,.2f}"


def _draft_notice(tenant_id: str, lease_id: str, dispute_summary: str, audit: dict,
                  conflicts: dict, assessment: DisputeRiskAssessment) -> str:
    lease_citations = conflicts.get("lease_citations", [])
    statute_citations = conflicts.get("statute_citations", [])
    deduction_lines = []
    for item in audit.get("transactions", []):
        deduction_lines.append(f"- ₹{_money(item.get('amount_inr', 0))}: {item.get('description', 'Ledger item')} (receipt: {item.get('receipt_reference') or 'not provided'})")
    if not deduction_lines:
        deduction_lines = [
            f"- Claimed deductions: ₹{_money(audit.get('total_claimed_deductions_inr', 0))}; unreceipted portion: ₹{_money(audit.get('unverified_deductions_without_receipts_inr', 0))}.",
        ]
    lease_lines = [f"- Clause {item.get('citation', 'unidentified')}: {item.get('content', '')}" for item in lease_citations]
    statute_lines = [f"- {item.get('citation', 'Unidentified reference')}: {item.get('content', '')}" for item in statute_citations]
    return f"""WITHOUT PREJUDICE — FORMAL REQUEST FOR DEPOSIT REFUND AND ITEMISED DEDUCTIONS

To: The Landlord / Property Manager
Re: Lease {lease_id} — return of security deposit

Dear Landlord,

I am writing about the security deposit and deductions claimed at the end of the tenancy. My dispute is: {dispute_summary}

My ledger records a deposit of ₹{_money(audit.get('deposit_paid_inr', 0))}, claimed deductions of ₹{_money(audit.get('total_claimed_deductions_inr', 0))}, and ₹{_money(audit.get('lawful_refundable_balance_inr', 0))} as the current refundable balance under the documented audit rule. The audit identifies ₹{_money(audit.get('unverified_deductions_without_receipts_inr', 0))} in claims without receipt references.

Please provide an itemised account of every deduction, together with invoices, receipts, dated photographs, and the move-in/move-out inspection records supporting it. The disputed ledger items are:
{chr(10).join(deduction_lines)}

The agreement clauses identified for review are:
{chr(10).join(lease_lines) if lease_lines else '- No lease clause was returned for this query.'}

The statutory reference provisions identified for review are:
{chr(10).join(statute_lines) if statute_lines else '- No statutory citation was returned for this query.'}

I request payment of the currently calculated refundable balance of ₹{_money(audit.get('lawful_refundable_balance_inr', 0))}, together with the supporting statement, within 14 days of receipt of this letter. Please respond in writing so the matter can be resolved amicably.

This letter is a request for settlement and does not waive any right or remedy available under the applicable agreement or state law. The cited Model Tenancy Act material is illustrative; the applicable state law and facts should be confirmed.

Sincerely,

[Tenant Full Name]
[Contact Details]

Lease reference: {lease_id}
"""


@mcp.tool()
def generate_dispute_package(tenant_id: str, lease_id: str, dispute_summary: str, matched_conflicts: str,
                             ledger_audit: str, force_deterministic: bool = False) -> dict:
    """Generate a source-grounded risk assessment and a landlord response notice via multi-provider router."""
    audit = _json_object(ledger_audit)
    if "lawful_refundable_balance_inr" not in audit:
        raise ValueError("ledger_audit must include lawful_refundable_balance_inr from the SQL audit tool.")

    try:
        ledger_refund = Decimal(str(audit["lawful_refundable_balance_inr"]))
    except Exception as exc:
        raise ValueError("Ledger refundable balance must be a valid numeric amount.") from exc

    if not ledger_refund.is_finite() or ledger_refund < 0:
        raise ValueError("Ledger refundable balance must be finite and non-negative.")

    conflicts = _json_object(matched_conflicts)
    assessment = None
    model_used = None
    handoff_note = None
    fallback_reason = None

    if not force_deterministic:
        system_prompt = (
            "Assess this Indian residential tenancy dispute. This is information, not legal advice. "
            "Model Tenancy Act provisions are illustrative and state adoption may differ. "
            "Return ONLY a JSON object with exactly these fields: "
            "risk_score_0_to_100 (int 0-100), risk_level (low|moderate|high), "
            "unenforceable_lease_clauses (list[str]), violated_statutes (list[str]), "
            "lawful_refundable_amount_inr (float >= 0). "
            "Do not invent legal citations or findings not present in the retrieved conflicts. "
            "Use a conservative risk score. "
            f"lawful_refundable_amount_inr MUST equal {audit['lawful_refundable_balance_inr']} from the ledger audit."
        )
        user_message = (
            f"Tenant: {tenant_id}; lease: {lease_id}\n"
            f"Dispute: {dispute_summary}\n"
            f"Retrieved conflicts: {matched_conflicts}\n"
            f"Deterministic ledger audit: {ledger_audit}\n"
            "Set violated_statutes to citations present in retrieved conflicts only."
        )
        try:
            generate_with_handoff = _router()

            raw_reply, model_used, handoff_note = _run_async(
            generate_with_handoff(
            system_prompt=system_prompt,
            user_message=user_message,
            response_json=True,
            )
)
            if raw_reply:
                # Strip markdown code fences if present
                cleaned = raw_reply.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```", 2)[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                    cleaned = cleaned.rsplit("```", 1)[0].strip()
                assessment = DisputeRiskAssessment.model_validate_json(cleaned)
                logger.info("Notice assessment generated with %s", model_used)
        except Exception as exc:
            fallback_reason = f"Multi-provider router unavailable: {exc}"
            logger.warning("Notice router failed; using deterministic fallback: %s", exc)
    else:
        fallback_reason = "force_deterministic=True; skipping LLM assessment"

    if assessment is None:
        assessment = _fallback_assessment(audit, conflicts)
        assessment = assessment.model_copy(
            update={"lawful_refundable_amount_inr": float(ledger_refund)}
        )
        generation_mode = "deterministic_fallback"
    else:
        # Money always sourced from SQL — override model value.
        assessment = assessment.model_copy(update={"lawful_refundable_amount_inr": float(ledger_refund)})
        generation_mode = f"llm:{model_used}"

    notice = _draft_notice(tenant_id, lease_id, dispute_summary, audit, conflicts, assessment)
    return {
        "tenant_id": tenant_id,
        "lease_id": lease_id,
        "dispute_summary": dispute_summary,
        "risk_assessment": assessment.model_dump(),
        "legal_notice": notice,
        "generation_mode": generation_mode,
        "model_used": model_used,
        "handoff_note": handoff_note,
        "fallback_reason": fallback_reason,
        "disclaimer": "Draft for review. Confirm applicable state law and facts with a qualified local lawyer before sending.",
    }


if __name__ == "__main__":
    mcp.run()
