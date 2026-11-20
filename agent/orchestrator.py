"""Run all three local FastMCP services through Google Gen AI's MCP support."""
import argparse
import asyncio
from contextlib import AsyncExitStack
import json
import logging
import os
import re
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastmcp import Client
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError
from psycopg.types.json import Jsonb

load_dotenv(override=True)

from agent.llm_router import generate_with_handoff

GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://leaselens:leaselens@localhost:5432/leaselens")


def ensure_chat_messages_table() -> None:
    """Apply the chat-history migration without requiring a Docker volume reset."""
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL,
            lease_id VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            lease_citations JSONB NOT NULL DEFAULT '[]'::jsonb,
            statute_citations JSONB NOT NULL DEFAULT '[]'::jsonb,
            generation_mode VARCHAR(100),
            attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""")
        conn.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS attachments JSONB NOT NULL DEFAULT '[]'::jsonb")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_lease
            ON chat_messages (tenant_id, lease_id, id ASC)""")


def load_chat_history(tenant_id: str, lease_id: str, limit: int = 30) -> list[dict]:
    """Load chronological chat messages for exactly one tenant and lease."""
    ensure_chat_messages_table()
    bounded_limit = max(1, min(int(limit), 500))
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute("""SELECT role, content, lease_citations, statute_citations,
                generation_mode, created_at, attachments
            FROM chat_messages
            WHERE tenant_id=%s AND lease_id=%s
            ORDER BY id DESC LIMIT %s""", (tenant_id, lease_id, bounded_limit)).fetchall()
    return [{"role": row[0], "content": row[1], "lease_citations": row[2],
             "statute_citations": row[3], "generation_mode": row[4],
             "created_at": row[5].isoformat() if row[5] else None,
             "attachments": row[6]}
            for row in reversed(rows)]


def save_chat_turn(tenant_id: str, lease_id: str, role: str, content: str,
                   lease_citations: list | None = None,
                   statute_citations: list | None = None,
                   generation_mode: str | None = None,
                   attachments: list[dict] | None = None) -> None:
    """Persist one message and its citations under its tenant/lease key."""
    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'")
    ensure_chat_messages_table()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""INSERT INTO chat_messages
            (tenant_id, lease_id, role, content, lease_citations, statute_citations, generation_mode, attachments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (tenant_id, lease_id, role, content, Jsonb(lease_citations or []),
             Jsonb(statute_citations or []), generation_mode, Jsonb(attachments or [])))


def clear_chat_history(tenant_id: str, lease_id: str) -> None:
    """Delete messages for exactly one tenant and lease."""
    ensure_chat_messages_table()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("DELETE FROM chat_messages WHERE tenant_id=%s AND lease_id=%s",
                     (tenant_id, lease_id))


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


def tool_data(result: Any) -> dict[str, Any]:
    data = result.structured_content
    if data is None:
        data = result.data
        if isinstance(data, list) and data and hasattr(data[0], "text"):
            data = json.loads(data[0].text)
    if isinstance(data, str):
        data = json.loads(data)
    return data if isinstance(data, dict) else {}


async def run(query: str, tenant_id: str, lease_id: str):
    async with AsyncExitStack() as stack:
        rag = await stack.enter_async_context(Client("mcp_servers/lease_statute_rag.py"))
        ledger = await stack.enter_async_context(Client("mcp_servers/rent_ledger.py"))
        notice = await stack.enter_async_context(Client("mcp_servers/notice_drafter.py"))
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
            from mcp_servers.notice_drafter import DisputeRiskAssessment, _draft_notice, _fallback_assessment
            assessment = _fallback_assessment(audit, matched)
            package = {"tenant_id": tenant_id, "lease_id": lease_id,
                       "risk_assessment": assessment.model_dump(),
                       "legal_notice": _draft_notice(tenant_id, lease_id, query, audit, matched, assessment),
                       "generation_mode": "deterministic_fallback",
                       "fallback_reason": f"Notice MCP failed; generated locally: {exc}"}
            DisputeRiskAssessment.model_validate(package["risk_assessment"])
        return json.dumps({"tenant_id": tenant_id, "lease_id": lease_id,
                           "agent_summary": summary or "Completed with local MCP tools and deterministic notice fallback.",
                           "agent_model": model_used, "retrieval": matched, "ledger_audit": audit,
                           "dispute_package": package}, ensure_ascii=False, indent=2)


def deterministic_chat_reply(lease_citations: list[dict], statute_citations: list[dict], ledger: dict) -> str:
    """Build a useful, source-grounded answer when every LLM provider is unavailable."""
    lines = ["Here is what your lease and statutory records say:"]
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
            "\n**Deposit audit:** "
            f"deposit ₹{ledger.get('deposit_paid_inr', 0):,.2f}; "
            f"rent ₹{ledger.get('monthly_rent_inr', 0):,.2f}/month; "
            f"ratio {ledger.get('deposit_to_rent_ratio_months', 0)} months; "
            f"unverified claims ₹{ledger.get('unverified_deductions_without_receipts_inr', 0):,.2f}; "
            f"documented deductions ₹{ledger.get('documented_deductions_inr', 0):,.2f}; "
            f"currently refundable ₹{ledger.get('lawful_refundable_balance_inr', 0):,.2f}."
        )
    return "\n".join(lines)


def evidence_gap_reason(user_message: str, search_query: str,
                        lease_citations: list[dict]) -> str | None:
    """Return a reason to avoid generative answering when the lease evidence misses the ask."""
    asked = f"{user_message} {search_query}"
    available = {str(item.get("citation", "")).strip() for item in lease_citations}
    requested_clauses = set(re.findall(
        r"\bclause\s+(\d+(?:\.\d+)*)\b", asked, flags=re.IGNORECASE))
    missing = sorted(requested_clauses - available)
    if missing:
        refs = ", ".join(f"Clause {number}" for number in missing)
        return f"The explicitly requested {refs} was not found in the indexed lease evidence."

    requested_lock_in = re.search(r"lock[ -]?in", user_message, flags=re.IGNORECASE)
    lease_text = " ".join(str(item.get("content", "")) for item in lease_citations)
    if requested_lock_in and not re.search(r"lock[ -]?in", lease_text, flags=re.IGNORECASE):
        return "The retrieved lease excerpts do not mention a lock-in period."
    return None


def unsupported_citations(reply: str, lease_citations: list[dict],
                          statute_citations: list[dict]) -> list[str]:
    """Find clause/section numbers in a generated reply absent from retrieved evidence."""
    unsupported = []
    allowed_clauses = {str(item.get("citation", "")).strip() for item in lease_citations}
    allowed_sections = {
        section
        for item in statute_citations
        for section in re.findall(r"\bsection\s+(\d+(?:\.\d+)*)\b",
                                  str(item.get("citation", "")), flags=re.IGNORECASE)
    }
    for clause in re.findall(r"\bclause\s+(\d+(?:\.\d+)*)\b", reply, flags=re.IGNORECASE):
        if clause not in allowed_clauses:
            unsupported.append(f"Clause {clause}")
    for section in re.findall(r"\bsection\s+(\d+(?:\.\d+)*)\b", reply, flags=re.IGNORECASE):
        if section not in allowed_sections:
            unsupported.append(f"Section {section}")
    return unsupported


def deterministic_evidence_gap_reply(reason: str, lease_citations: list[dict],
                                     statute_citations: list[dict], user_message: str,
                                     ledger: dict) -> str:
    """Explain an evidence gap without guessing what an unavailable clause means."""
    lines = [f"I can't answer that from the indexed lease evidence. {reason}"]
    if lease_citations:
        lines.append("\nClosest retrieved lease text (not a substitute for the missing clause):")
        for item in lease_citations[:2]:
            page = f", page {item['page_number']}" if item.get("page_number") is not None else ""
            lines.append(f"- Clause {item.get('citation', 'unidentified')}{page}: {item.get('content', '')}")
    else:
        lines.append("\nNo lease clauses were retrieved for this question.")
    if statute_citations:
        lines.append("\nRetrieved statutory reference text (illustrative; state law varies):")
        for item in statute_citations[:2]:
            lines.append(f"- {item.get('citation', 'Unidentified provision')}: {item.get('content', '')}")
        lines.append("These excerpts alone do not establish how a local court or authority would apply the law.")
    if re.search(r"deposit|refund|deduct|amount|₹|inr|rs\b", user_message, flags=re.IGNORECASE) and "error" not in ledger:
        lines.append(
            "\nThe account audit records a refundable balance of "
            f"₹{ledger.get('lawful_refundable_balance_inr', 0):,.2f}."
        )
    lines.append("If the clause is in the PDF, check that the correct lease was ingested and indexed.")
    return "\n".join(lines)


GREETING_PATTERN = re.compile(
    r"^\s*(hi+|hey+|hello+|thanks?|thank\s+you|who\s+are\s+you|what\s+can\s+(?:you|u)\s+do|help)\b",
    re.IGNORECASE,
)
LEASE_DOMAIN_TERMS = re.compile(
    r"\b(deposit|rent|clause|notice|lock[ -]?in|paint|repaint|geyser|repair|evict|refund|deduct|landlord|tenant|pdf|agreement)\b",
    re.IGNORECASE,
)


def is_casual_greeting_or_capability(text: str) -> bool:
    """Match greetings or 'what can you do' messages that contain no specific lease query."""
    cleaned = text.strip()
    if len(cleaned) <= 60 and GREETING_PATTERN.match(cleaned) and not LEASE_DOMAIN_TERMS.search(cleaned):
        return True
    return False


async def chat_with_lease(tenant_id: str, lease_id: str, user_message: str,
                          chat_history: list[dict] | None = None,
                          attachments: list[dict] | None = None) -> dict:
    """Answer and persist one turn using lease, statute, and ledger evidence via multi-provider router."""
    if is_casual_greeting_or_capability(user_message):
        greeting_reply = (
            "Hi! I'm **LeaseLens**, your rental agreement and deposit dispute assistant.\n\n"
            "Here is how I can help with your active lease:\n"
            "- **Explain lease clauses:** Check lock-in periods, notice rules, maintenance terms, and hidden penalties.\n"
            "- **Audit security deposits:** Separate receipt-backed deductions from invalid wear-and-tear claims and calculate your lawful refund.\n"
            "- **Review screenshots & bills:** Upload photos of landlord messages or repair invoices for context-aware checks.\n"
            "- **Draft legal notices:** Generate a formal demand notice grounded in your lease and statutory protections."
        )
        save_chat_turn(tenant_id, lease_id, "user", user_message)
        save_chat_turn(tenant_id, lease_id, "assistant", greeting_reply, generation_mode="greeting")
        return {
            "reply": greeting_reply,
            "standalone_search_query": user_message,
            "lease_citations": [],
            "statute_citations": [],
            "generation_mode": "greeting",
            "model_used": None,
            "ledger_audit": {},
            "attachments": [],
        }

    ensure_chat_messages_table()
    full_history = chat_history if chat_history is not None else load_chat_history(tenant_id, lease_id)
    search_query = await contextualize_followup_query(user_message, full_history)
    if attachments and not LEASE_DOMAIN_TERMS.search(search_query):
        search_query = f"{search_query} security deposit deductions repainting repairs bills".strip()

    async with AsyncExitStack() as stack:
        rag = await stack.enter_async_context(Client("mcp_servers/lease_statute_rag.py"))
        ledger_client = await stack.enter_async_context(Client("mcp_servers/rent_ledger.py"))
        matched = tool_data(await rag.call_tool("compare_lease_against_statutes", {
            "tenant_id": tenant_id, "lease_id": lease_id, "dispute_query": search_query}))
        audit = tool_data(await ledger_client.call_tool("audit_deposit_and_ledger", {
            "tenant_id": tenant_id, "lease_id": lease_id}))

    lease_citations = matched.get("lease_citations", [])
    statute_citations = matched.get("statute_citations", [])
    history = full_history[-12:] if isinstance(full_history, list) else []
    attachments = attachments or []

    attachment_metadata = [
        {"filename": str(att.get("filename", "image"))[:200], "mime_type": str(att.get("mime_type", ""))}
        for att in attachments
        if str(att.get("mime_type", "")) in {"image/png", "image/jpeg", "image/webp"}
        and isinstance(att.get("data"), bytes)
        and len(att["data"]) <= 10 * 1024 * 1024
    ]

    gap_reason = evidence_gap_reason(user_message, search_query, lease_citations)
    system_prompt = (
        "You are LeaseLens, a helpful and friendly Indian rental agreement assistant. "
        "Explain everything in simple, everyday language that any tenant can easily understand—do NOT copy-paste stiff legal text verbatim or use robotic headers like 'Contract Wording' or 'Statutory Wording'. "
        "NEVER include legal disclaimers, 'this is not legal advice', or 'state law varies' boilerplate in your replies. "
        "Start with a direct, plain-English answer to the user's question, then give short, clear bullet points explaining what their lease says and how tenant protection rules compare. "
        "Base all facts strictly on the retrieved lease passages, statutory excerpts, and SQL ledger numbers provided below—never invent clauses, sections, or amounts. "
        "Cite clause numbers and statutory sections naturally in parentheses (e.g., '(Clause 3.2)' or '(Model Tenancy Act, Sec. 17)'). "
        "If the lease does not mention what the user asked about, say so plainly in one sentence without guessing. "
        "Use prior conversation history only to understand follow-up context, and always use the exact rupee figures from the SQL ledger."
    )

    reply, model_used, handoff_note = None, None, None
    mode = None

    if gap_reason:
        reply = deterministic_evidence_gap_reply(
            gap_reason, lease_citations, statute_citations, user_message, audit)
        mode = "deterministic_fallback"
    else:
        try:
            reply, model_used, handoff_note = await generate_with_handoff(
                system_prompt=system_prompt,
                user_message=user_message,
                chat_history=history,
                lease_citations=lease_citations,
                statute_citations=statute_citations,
                ledger_audit=audit,
                search_query=search_query,
                attachments=attachments,
            )
        except Exception:
            logger.exception("Multi-provider LLM router failed; using deterministic retrieval fallback")

    if reply is None:
        reply = deterministic_chat_reply(lease_citations, statute_citations, audit)
        mode = "deterministic_fallback"
    elif model_used is not None:
        mode = model_used if ":" in model_used else f"llm:{model_used}"
        unsupported = unsupported_citations(reply, lease_citations, statute_citations)
        if unsupported:
            logger.warning("Model %s cited unavailable evidence %s; replacing response with grounded fallback",
                           model_used, unsupported)
            reply = deterministic_evidence_gap_reply(
                "The generated answer cited material that was not in the retrieved evidence.",
                lease_citations, statute_citations, user_message, audit)
            mode = "deterministic_fallback"
        elif handoff_note:
            reply += f"\n\n_{handoff_note}_"

    if mode == "deterministic_fallback" and attachment_metadata:
        reply += "\n\nAn image was attached, but image analysis is unavailable in deterministic fallback mode. The response above uses retrieved text and the SQL audit only."

    save_chat_turn(tenant_id, lease_id, "user", user_message, attachments=attachment_metadata)
    save_chat_turn(tenant_id, lease_id, "assistant", reply,
                   lease_citations=lease_citations, statute_citations=statute_citations,
                   generation_mode=mode)
    return {
        "reply": reply,
        "standalone_search_query": search_query,
        "lease_citations": lease_citations,
        "statute_citations": statute_citations,
        "generation_mode": mode,
        "model_used": model_used,
        "ledger_audit": audit,
        "attachments": attachment_metadata,
    }


async def contextualize_followup_query(user_message: str, recent_history: list[dict]) -> str:
    """Rewrite a follow-up into a standalone search query using the multi-provider router."""
    if not recent_history:
        return user_message
    system_prompt = (
        "Rewrite the latest user message as one concise, standalone search query for finding rental-agreement clauses and statutory references. "
        "Resolve pronouns and references such as 'it', 'that clause', and 'those deductions' using the conversation. "
        "Preserve clause numbers, amounts, and factual details. Do not answer the question, assess legality, add facts, or include commentary. "
        "Return only the rewritten query."
    )
    try:
        rewritten, _, _ = await generate_with_handoff(
            system_prompt=system_prompt,
            user_message=user_message,
            chat_history=recent_history[-8:],
        )
        if rewritten and rewritten.strip():
            return rewritten.strip().strip('"').strip()
    except Exception:
        logger.exception("Follow-up query rewrite failed; carrying forward prior context")

    previous_user_content = (
        recent_history[-2].get("content", "") if len(recent_history) >= 2
        else recent_history[-1].get("content", "")
    )
    return f"{previous_user_content} {user_message}".strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", default="user_rahul")
    parser.add_argument("--lease-id", default="lease_001")
    parser.add_argument("--query", default="My landlord withheld the deposit for repainting and an old geyser coil. Are these valid deductions?")
    args = parser.parse_args()
    ensure_chat_messages_table()
    print(asyncio.run(run(args.query, args.tenant_id, args.lease_id)))


if __name__ == "__main__":
    main()