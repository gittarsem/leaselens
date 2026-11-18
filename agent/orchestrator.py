"""Run all three local FastMCP services through Google Gen AI's MCP support."""
import argparse
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from fastmcp import Client
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

load_dotenv()
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
logger = logging.getLogger(__name__)


async def generate_with_fallback(client, prompt, tools):
    """Try active Gemini Flash models in order, advancing on API errors."""
    for model_name in GEMINI_MODELS:
        try:
            response = await client.aio.models.generate_content(
                model=model_name, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1, tools=tools))
            logger.info("Gemini generation succeeded with %s", model_name)
            return response.text, model_name
        except (ServerError, ClientError, APIError) as exc:
            status = getattr(exc, "status_code", getattr(exc, "code", None))
            logger.warning("Gemini model %s failed with status %s; trying next model: %s",
                           model_name, status, exc)
    return None, None


def tool_data(result):
    data = result.structured_content
    if data is not None:
        return data
    data = result.data
    if isinstance(data, list) and data and hasattr(data[0], "text"):
        return json.loads(data[0].text)
    return data


async def run(query: str, tenant_id: str, lease_id: str):
    rag = Client("mcp_servers/lease_statute_rag.py")
    ledger = Client("mcp_servers/rent_ledger.py")
    notice = Client("mcp_servers/notice_drafter.py")
    async with rag, ledger, notice:
        matched = tool_data(await rag.call_tool("compare_lease_against_statutes", {
            "tenant_id": tenant_id, "lease_id": lease_id, "dispute_query": query}))
        audit = tool_data(await ledger.call_tool("audit_deposit_and_ledger", {
            "tenant_id": tenant_id, "lease_id": lease_id}))
        prompt = f"""You are LeaseLens, an Indian rental dispute research assistant. Use the lease/statute retrieval tool and deterministic ledger audit tool for this case, then call generate_dispute_package with their results. Never invent legal authorities. Explain that state law may differ.
Tenant ID: {tenant_id}
Lease ID: {lease_id}
Tenant's dispute: {query}
Retrieved clauses: {json.dumps(matched, ensure_ascii=False)}
Deterministic ledger audit: {json.dumps(audit, ensure_ascii=False)}
Return a concise evidence summary followed by the validated risk audit and formal notice."""
        summary, model_used = None, None
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=20000,
                retry_options=types.HttpRetryOptions(attempts=1)))
            summary, model_used = await generate_with_fallback(client, prompt, [rag, ledger, notice])

        package_args = {"tenant_id": tenant_id, "lease_id": lease_id, "dispute_summary": query,
                        "matched_conflicts": json.dumps(matched, ensure_ascii=False),
                        "ledger_audit": json.dumps(audit, ensure_ascii=False),
                        "force_deterministic": summary is None}
        try:
            package = tool_data(await notice.call_tool("generate_dispute_package", package_args))
        except Exception as exc:
            # Last-resort local path if the notice MCP transport itself fails.
            from mcp_servers.notice_drafter import DisputeRiskAssessment, _draft_notice, _fallback_assessment
            assessment = _fallback_assessment(audit, matched)
            package = {"tenant_id": tenant_id, "lease_id": lease_id,
                       "risk_assessment": assessment.model_dump(),
                       "legal_notice": _draft_notice(tenant_id, lease_id, query, audit, matched, assessment),
                       "generation_mode": "deterministic_fallback",
                       "fallback_reason": f"Notice MCP failed; generated locally: {exc}"}
            DisputeRiskAssessment.model_validate(package["risk_assessment"])
        return json.dumps({"tenant_id": tenant_id, "lease_id": lease_id,
                           "agent_summary": summary or "Gemini unavailable; completed with local MCP tools and deterministic notice fallback.",
                           "agent_model": model_used, "retrieval": matched, "ledger_audit": audit,
                           "dispute_package": package}, ensure_ascii=False, indent=2)


def deterministic_chat_reply(lease_citations: list[dict], statute_citations: list[dict], ledger: dict) -> str:
    """Build a useful, source-grounded answer when every Gemini model is unavailable."""
    lines = ["I could not reach the language models, so here is a response grounded in the retrieved records."]
    if lease_citations:
        lines.append("\n**Your agreement:**")
        for item in lease_citations[:2]:
            page = item.get("page_number")
            page_text = f", page {page}" if page is not None else ""
            lines.append(f"- Clause {item.get('citation', 'unidentified')}{page_text}: {item.get('content', '')}")
    else:
        lines.append("\nNo matching lease clause was retrieved for this question.")
    if statute_citations:
        lines.append("\n**Statutory references (confirm applicability under your state law):**")
        for item in statute_citations[:2]:
            lines.append(f"- {item.get('citation', 'Unidentified provision')}: {item.get('content', '')}")
    else:
        lines.append("\nNo matching statutory reference was retrieved.")
    if "error" not in ledger:
        lines.append(
            "\n**SQL deposit audit:** "
            f"deposit ₹{ledger.get('deposit_paid_inr', 0):,.2f}; "
            f"rent ₹{ledger.get('monthly_rent_inr', 0):,.2f}/month; "
            f"ratio {ledger.get('deposit_to_rent_ratio_months', 0)} months; "
            f"unverified claims ₹{ledger.get('unverified_deductions_without_receipts_inr', 0):,.2f}; "
            f"documented deductions ₹{ledger.get('documented_deductions_inr', 0):,.2f}; "
            f"currently refundable ₹{ledger.get('lawful_refundable_balance_inr', 0):,.2f}."
        )
    lines.append("The Model Tenancy Act is illustrative; applicable state law and the full facts may differ.")
    return "\n".join(lines)


async def chat_with_lease(tenant_id: str, lease_id: str, user_message: str,
                          chat_history: list[dict]) -> dict:
    """Answer one conversational turn using fresh lease, statute, and ledger evidence."""
    rag = Client("mcp_servers/lease_statute_rag.py")
    ledger_client = Client("mcp_servers/rent_ledger.py")
    async with rag, ledger_client:
        matched = tool_data(await rag.call_tool("compare_lease_against_statutes", {
            "tenant_id": tenant_id, "lease_id": lease_id, "dispute_query": user_message}))
        audit = tool_data(await ledger_client.call_tool("audit_deposit_and_ledger", {
            "tenant_id": tenant_id, "lease_id": lease_id}))

    lease_citations = matched.get("lease_citations", [])
    statute_citations = matched.get("statute_citations", [])
    history = chat_history[-12:] if isinstance(chat_history, list) else []
    prompt = f"""You are LeaseLens, a concise Indian rental agreement and tenant-rights research assistant. This is informational, not legal advice.
Answer the user's latest question in a few clear paragraphs. Cite exact lease clause numbers and page numbers (when available) and statutory sections inline. Explicitly distinguish what this agreement says from what a statute says or requires. Do not claim that a provision applies or was violated unless the evidence establishes it. Never invent citations. Model Tenancy Act provisions are illustrative and Indian state law varies.
For financial questions, use the SQL ledger figures exactly; do not calculate a substitute amount.

Recent conversation (oldest first):
{json.dumps(history, ensure_ascii=False)}

Current question: {user_message}
Retrieved lease citations: {json.dumps(lease_citations, ensure_ascii=False)}
Retrieved statutory citations: {json.dumps(statute_citations, ensure_ascii=False)}
Deterministic SQL account/deposit context: {json.dumps(audit, ensure_ascii=False)}"""

    reply, model_used = None, None
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=20000,
            retry_options=types.HttpRetryOptions(attempts=1)))
        reply, model_used = await generate_with_fallback(client, prompt, [])
    if reply is None:
        reply = deterministic_chat_reply(lease_citations, statute_citations, audit)
        mode = "deterministic_fallback"
    else:
        mode = f"llm:{model_used}"
    return {"reply": reply, "lease_citations": lease_citations,
            "statute_citations": statute_citations, "generation_mode": mode,
            "model_used": model_used, "ledger_audit": audit}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", default="user_rahul")
    parser.add_argument("--lease-id", default="lease_001")
    parser.add_argument("--query", default="My landlord withheld the deposit for repainting and an old geyser coil. Are these valid deductions?")
    args = parser.parse_args()
    print(asyncio.run(run(args.query, args.tenant_id, args.lease_id)))


if __name__ == "__main__":
    main()
