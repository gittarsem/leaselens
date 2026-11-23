"""LeaseLens conversational orchestration and evidence-grounded response generation."""



import argparse

import asyncio

import json

import logging

import os

import re

import sys
from pathlib import Path

from fastmcp.client.transports import StdioTransport


from contextlib import AsyncExitStack

from typing import Any



import psycopg

from dotenv import load_dotenv

from fastmcp import Client

from google import genai

from google.genai import types

from google.genai.errors import APIError, ClientError, ServerError

from psycopg.types.json import Jsonb



load_dotenv(override=False)



from agent.llm_router import generate_with_handoff





GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
]



logger = logging.getLogger(__name__)



DATABASE_URL = os.getenv(

    "DATABASE_URL",

    "postgresql://leaselens:leaselens@localhost:5432/leaselens",

)





# =========================================================

# DATABASE / CHAT HISTORY

# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_mcp_client(server_path: str) -> Client:
    """
    Create an MCP client with the parent process environment explicitly
    forwarded to the MCP subprocess.
    """
    absolute_server_path = PROJECT_ROOT / server_path

    transport = StdioTransport(
        command=sys.executable,
        args=[str(absolute_server_path)],
        env=os.environ.copy(),
        cwd=str(PROJECT_ROOT),
    )

    return Client(transport)



def ensure_chat_messages_table() -> None:

    """Create chat history table if it does not exist."""



    with psycopg.connect(DATABASE_URL) as conn:

        conn.execute("""

            CREATE TABLE IF NOT EXISTS chat_messages (

                id SERIAL PRIMARY KEY,

                tenant_id VARCHAR(100) NOT NULL,

                lease_id VARCHAR(100) NOT NULL,

                role VARCHAR(20) NOT NULL

                    CHECK (role IN ('user', 'assistant')),

                content TEXT NOT NULL,

                lease_citations JSONB NOT NULL DEFAULT '[]'::jsonb,

                statute_citations JSONB NOT NULL DEFAULT '[]'::jsonb,

                generation_mode VARCHAR(100),

                attachments JSONB NOT NULL DEFAULT '[]'::jsonb,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

            )

        """)



        conn.execute("""

            ALTER TABLE chat_messages

            ADD COLUMN IF NOT EXISTS attachments

            JSONB NOT NULL DEFAULT '[]'::jsonb

        """)



        conn.execute("""

            CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_lease

            ON chat_messages (tenant_id, lease_id, id ASC)

        """)





def load_chat_history(

    tenant_id: str,

    lease_id: str,

    limit: int = 30,

) -> list[dict]:



    ensure_chat_messages_table()



    bounded_limit = max(

        1,

        min(int(limit), 500),

    )



    with psycopg.connect(DATABASE_URL) as conn:



        rows = conn.execute(

            """

            SELECT

                role,

                content,

                lease_citations,

                statute_citations,

                generation_mode,

                created_at,

                attachments



            FROM chat_messages



            WHERE tenant_id = %s

              AND lease_id = %s



            ORDER BY id DESC



            LIMIT %s

            """,

            (

                tenant_id,

                lease_id,

                bounded_limit,

            ),

        ).fetchall()



    return [

        {

            "role": row[0],

            "content": row[1],

            "lease_citations": row[2],

            "statute_citations": row[3],

            "generation_mode": row[4],

            "created_at": (

                row[5].isoformat()

                if row[5]

                else None

            ),

            "attachments": row[6],

        }



        for row in reversed(rows)

    ]





def save_chat_turn(

    tenant_id: str,

    lease_id: str,

    role: str,

    content: str,

    lease_citations: list | None = None,

    statute_citations: list | None = None,

    generation_mode: str | None = None,

    attachments: list[dict] | None = None,

) -> None:



    if role not in {"user", "assistant"}:

        raise ValueError(

            "role must be 'user' or 'assistant'"

        )



    ensure_chat_messages_table()



    with psycopg.connect(DATABASE_URL) as conn:



        conn.execute(

            """

            INSERT INTO chat_messages (

                tenant_id,

                lease_id,

                role,

                content,

                lease_citations,

                statute_citations,

                generation_mode,

                attachments

            )



            VALUES (

                %s, %s, %s, %s, %s, %s, %s, %s

            )

            """,

            (

                tenant_id,

                lease_id,

                role,

                content,

                Jsonb(lease_citations or []),

                Jsonb(statute_citations or []),

                generation_mode,

                Jsonb(attachments or []),

            ),

        )





def clear_chat_history(

    tenant_id: str,

    lease_id: str,

) -> None:



    ensure_chat_messages_table()



    with psycopg.connect(DATABASE_URL) as conn:



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





# =========================================================

# GEMINI FALLBACK

# =========================================================



async def generate_with_fallback(

    client,

    prompt,

    tools,

):

    """Try configured Gemini models sequentially."""



    for model_name in GEMINI_MODELS:



        try:



            response = await client.aio.models.generate_content(

                model=model_name,

                contents=prompt,

                config=types.GenerateContentConfig(

                    temperature=0.1,

                    tools=tools,

                ),

            )



            logger.info(

                "Gemini generation succeeded with %s",

                model_name,

            )



            return response.text, model_name



        except (

            ServerError,

            ClientError,

            APIError,

        ) as exc:



            status = getattr(

                exc,

                "status_code",

                getattr(

                    exc,

                    "code",

                    None,

                ),

            )



            logger.warning(

                "Gemini model %s failed with status %s; "

                "trying next model: %s",

                model_name,

                status,

                exc,

            )



    return None, None





# =========================================================

# MCP RESULT HANDLING

# =========================================================



def tool_data(result: Any) -> dict[str, Any]:



    data = result.structured_content



    if data is None:



        data = result.data



        if (

            isinstance(data, list)

            and data

            and hasattr(data[0], "text")

        ):



            data = json.loads(

                data[0].text

            )



    if isinstance(data, str):

        data = json.loads(data)



    return (

        data

        if isinstance(data, dict)

        else {}

    )





# =========================================================

# DISPUTE WORKFLOW

# =========================================================



async def run(

    query: str,

    tenant_id: str,

    lease_id: str,

):



    async with AsyncExitStack() as stack:
        rag = await stack.enter_async_context(
        create_mcp_client("mcp_servers/lease_statute_rag.py")
        )

        ledger_client = await stack.enter_async_context(
        create_mcp_client("mcp_servers/rent_ledger.py")
        )



        ledger = await stack.enter_async_context(

            create_mcp_client("mcp_servers/rent_ledger.py")

        )



        notice = await stack.enter_async_context(
            create_mcp_client("mcp_servers/notice_drafter.py")

        )



        # -------------------------------------------------
        # Initial RAG Retrieval
        # -------------------------------------------------

        matched = tool_data(
            await rag.call_tool(
                "compare_lease_against_statutes",
                {
                    "tenant_id": tenant_id,
                    "lease_id": lease_id,
                    "dispute_query": search_query,
                },
            )
        )

        initial_lease_citations = matched.get(
            "lease_citations",
            [],
        )

        initial_statute_citations = matched.get(
            "statute_citations",
            [],
        )

        # -------------------------------------------------
        # Adaptive Retrieval Retry
        # -------------------------------------------------

        initial_gap = evidence_gap_reason(
            user_message,
            search_query,
            initial_lease_citations,
        )

        retry_needed = (
            not initial_lease_citations
            or initial_gap is not None
        )

        if retry_needed:

            query_lower = search_query.lower()

            retry_expansions = {
                "notice": (
                    "termination notice period advance notice "
                    "vacating premises lease termination "
                    "notice requirement"
                ),

                "deposit": (
                    "security deposit refund deductions "
                    "forfeiture refundable deposit damages "
                    "move out charges"
                ),

                "lock": (
                    "lock-in period early termination "
                    "exit restriction minimum tenancy "
                    "premature termination"
                ),

                "maintenance": (
                    "maintenance repairs landlord tenant "
                    "responsibility maintenance charges "
                    "service charges"
                ),

                "paint": (
                    "painting repainting restoration "
                    "wear and tear cleaning deductions "
                    "damage charges"
                ),

                "rent": (
                    "rent increase rent escalation "
                    "rent revision percentage increase "
                    "monthly rent adjustment"
                ),

                "damage": (
                    "property damage repairs replacement "
                    "wear and tear deductions liability "
                    "security deposit"
                ),

                "eviction": (
                    "eviction termination possession "
                    "vacating premises notice landlord "
                    "tenant rights"
                ),

                "refund": (
                    "refund security deposit deductions "
                    "payment return refundable amount "
                    "settlement"
                ),

                "repair": (
                    "repairs maintenance responsibility "
                    "property damage replacement "
                    "landlord tenant obligations"
                ),
            }

            expansion_terms = []

            for keyword, terms in retry_expansions.items():

                if keyword in query_lower:

                    expansion_terms.append(
                        terms
                    )

            if not expansion_terms:

                expansion_terms.append(
                    "lease agreement tenant landlord "
                    "obligations rights conditions "
                    "termination penalties charges"
                )

            retry_query = (
                f"{search_query} "
                + " ".join(expansion_terms)
            ).strip()

            # Avoid retrying with the exact same query.

            if retry_query != search_query:

                print(
                    "RAG evidence insufficient. "
                    "Performing one expanded retrieval."
                )

                retry_matched = tool_data(
                    await rag.call_tool(
                        "compare_lease_against_statutes",
                        {
                            "tenant_id": tenant_id,
                            "lease_id": lease_id,
                            "dispute_query": retry_query,
                        },
                    )
                )

                retry_lease_citations = (
                    retry_matched.get(
                        "lease_citations",
                        [],
                    )
                )

                retry_statute_citations = (
                    retry_matched.get(
                        "statute_citations",
                        [],
                    )
                )

                # -------------------------------------------------
                # Merge and Deduplicate Evidence
                # -------------------------------------------------

                def merge_citations(
                    primary,
                    secondary,
                ):

                    merged = []
                    seen = set()

                    for item in (
                        primary
                        +
                        secondary
                    ):

                        key = (
                            str(
                                item.get(
                                    "citation",
                                    "",
                                )
                            ).strip().lower(),

                            str(
                                item.get(
                                    "content",
                                    "",
                                )
                            ).strip().lower(),
                        )

                        if key in seen:
                            continue

                        seen.add(key)

                        merged.append(
                            item
                        )

                    return merged

                merged_lease_citations = (
                    merge_citations(
                        initial_lease_citations,
                        retry_lease_citations,
                    )
                )

                merged_statute_citations = (
                    merge_citations(
                        initial_statute_citations,
                        retry_statute_citations,
                    )
                )

                matched = dict(
                    matched
                )

                matched[
                    "lease_citations"
                ] = merged_lease_citations

                matched[
                    "statute_citations"
                ] = merged_statute_citations

                matched[
                    "matches"
                ] = (
                    merged_lease_citations
                    +
                    merged_statute_citations
                )

                matched[
                    "retrieval_retry"
                ] = True

                matched[
                    "retry_query"
                ] = retry_query

            else:

                matched[
                    "retrieval_retry"
                ] = False

        else:

            matched[
                "retrieval_retry"
            ] = False

        # -------------------------------------------------
        # Ledger Audit
        # -------------------------------------------------

        audit = tool_data(

            await ledger.call_tool(

                "audit_deposit_and_ledger",

                {

                    "tenant_id": tenant_id,

                    "lease_id": lease_id,

                },

            )

        )



        prompt = f"""

You are LeaseLens, an Indian rental agreement research assistant.



Analyze the user's dispute using ONLY the retrieved lease clauses,

statutory excerpts, and deterministic ledger audit provided below.



Do not invent legal authorities, clauses, sections, facts, amounts,

or evidence.



Tenant ID: {tenant_id}



Lease ID: {lease_id}



Tenant's dispute:

{query}



Retrieved clauses:

{json.dumps(matched, ensure_ascii=False)}



Deterministic ledger audit:

{json.dumps(audit, ensure_ascii=False)}



Your task:



1. Summarize the relevant evidence.

2. Identify risks supported by the retrieved lease text.

3. Distinguish contractual wording from legal interpretation.

4. Identify financial exposure using the actual retrieved figures.

5. Identify inconsistencies only when conflicting text is present.

6. Do not treat the Model Tenancy Act as automatically binding

   on the user's state.

7. Clearly identify legal applicability that requires verification.

8. Do not claim that a legal provision has been verified if the

   retrieved evidence does not establish that.

9. Prepare a dispute package based on the available evidence.



Return a concise evidence summary followed by the validated

risk audit and formal notice.

"""



        summary = None

        model_used = None



        api_key = os.getenv(

            "GEMINI_API_KEY"

        )



        if api_key:



            client = genai.Client(

                api_key=api_key,

                http_options=types.HttpOptions(

                    timeout=20000,

                    retry_options=types.HttpRetryOptions(

                        attempts=1

                    ),

                ),

            )



            summary, model_used = (

                await generate_with_fallback(

                    client,

                    prompt,

                    [

                        rag,

                        ledger,

                        notice,

                    ],

                )

            )



        package_args = {

            "tenant_id": tenant_id,

            "lease_id": lease_id,

            "dispute_summary": query,

            "matched_conflicts": json.dumps(

                matched,

                ensure_ascii=False,

            ),

            "ledger_audit": json.dumps(

                audit,

                ensure_ascii=False,

            ),

            "force_deterministic": (

                summary is None

            ),

        }



        try:



            package = tool_data(

                await notice.call_tool(

                    "generate_dispute_package",

                    package_args,

                )

            )



        except Exception as exc:



            from mcp_servers.notice_drafter import (

                DisputeRiskAssessment,

                _draft_notice,

                _fallback_assessment,

            )



            assessment = _fallback_assessment(

                audit,

                matched,

            )



            package = {

                "tenant_id": tenant_id,

                "lease_id": lease_id,

                "risk_assessment": (

                    assessment.model_dump()

                ),

                "legal_notice": _draft_notice(

                    tenant_id,

                    lease_id,

                    query,

                    audit,

                    matched,

                    assessment,

                ),

                "generation_mode": (

                    "deterministic_fallback"

                ),

                "fallback_reason": (

                    "Notice MCP failed; "

                    f"generated locally: {exc}"

                ),

            }



            DisputeRiskAssessment.model_validate(

                package["risk_assessment"]

            )



        return json.dumps(

            {

                "tenant_id": tenant_id,

                "lease_id": lease_id,

                "agent_summary": (

                    summary

                    or "Completed with local MCP tools "

                    "and deterministic notice fallback."

                ),

                "agent_model": model_used,

                "retrieval": matched,

                "ledger_audit": audit,

                "dispute_package": package,

            },

            ensure_ascii=False,

            indent=2,

        )





# =========================================================

# DETERMINISTIC CHAT FALLBACK

# =========================================================



def deterministic_chat_reply(

    lease_citations: list[dict],

    statute_citations: list[dict],

    ledger: dict,

) -> str:



    lines = [

        "Here is what your lease and statutory "

        "records say:"

    ]



    if lease_citations:



        lines.append(

            "\n**Your agreement:**"

        )



        for item in lease_citations[:5]:



            page = item.get(

                "page_number"

            )



            page_text = (

                f", page {page}"

                if page is not None

                else ""

            )



            lines.append(

                f"- Clause "

                f"{item.get('citation', 'unidentified')}"

                f"{page_text}: "

                f"{item.get('content', '')}"

            )



    else:



        lines.append(

            "\nNo matching lease clause was "

            "retrieved for this question."

        )



    if statute_citations:



        lines.append(

            "\n**Retrieved statutory references "

            "(applicability requires verification):**"

        )



        for item in statute_citations[:3]:



            lines.append(

                f"- {item.get('citation', 'Unidentified provision')}: "

                f"{item.get('content', '')}"

            )



    else:



        lines.append(

            "\nNo matching statutory reference "

            "was retrieved."

        )



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





# =========================================================

# EVIDENCE GAP DETECTION

# =========================================================



def evidence_gap_reason(
    user_message: str,
    search_query: str,
    lease_citations: list[dict],
) -> str | None:

    asked = f"{user_message} {search_query}"

    # -----------------------------------------------------
    # General lease evidence sufficiency
    # -----------------------------------------------------

    lease_specific_question = bool(
        LEASE_DOMAIN_TERMS.search(asked)
    )

    if lease_specific_question and not lease_citations:
        return (
            "No relevant lease clauses were retrieved "
            "for this lease-specific question. The answer "
            "cannot be verified against the agreement."
        )

    # -----------------------------------------------------
    # Explicit clause reference validation
    # -----------------------------------------------------

    available = set()

    for item in lease_citations:
        citation_text = str(item.get("citation", "") or "")
        content_text = str(item.get("content", "") or "")
        combined_text = f"{citation_text} {content_text}"

        available.update(
            re.findall(
                r"\bclause\s+(\d+(?:\.\d+)*)\b",
                combined_text,
                flags=re.IGNORECASE,
            )
        )

        bare = re.fullmatch(
            r"\s*(\d+(?:\.\d+)*)\s*",
            citation_text,
        )

        if bare:
            available.add(bare.group(1))

    requested_clauses = set(
        re.findall(
            r"\bclause\s+(\d+(?:\.\d+)*)\b",
            asked,
            flags=re.IGNORECASE,
        )
    )

    missing = requested_clauses - available

    if missing:
        refs = ", ".join(
            f"Clause {number}"
            for number in sorted(missing)
        )

        return (
            f"The explicitly requested {refs} "
            "was not found in the indexed lease evidence."
        )

    # -----------------------------------------------------
    # Lock-in evidence validation
    # -----------------------------------------------------

    requested_lock_in = re.search(
        r"lock[ -]?in",
        user_message,
        flags=re.IGNORECASE,
    )

    lease_text = " ".join(
        str(item.get("content", ""))
        for item in lease_citations
    )

    if (
        requested_lock_in
        and not re.search(
            r"lock[ -]?in",
            lease_text,
            flags=re.IGNORECASE,
        )
    ):
        return (
            "The retrieved lease excerpts do not "
            "mention a lock-in period."
        )

    return None

def validate_json_response(reply: str) -> tuple[bool, Any]:
    """
    Validate whether an assistant response is valid JSON.

    Returns:
        (True, parsed_json) if valid
        (False, None) if invalid
    """
    if not reply:
        return False, None

    try:
        parsed = json.loads(reply.strip())
        return True, parsed
    except json.JSONDecodeError:
        pass

    # Handle accidental Markdown code fences.
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        reply.strip(),
        flags=re.IGNORECASE,
    )

    try:
        parsed = json.loads(cleaned)
        return True, parsed
    except json.JSONDecodeError:
        return False, None

def unsupported_citations(
    reply: str,
    lease_citations: list[dict],
    statute_citations: list[dict],
) -> list[str]:
    """Validate clause and statutory references in an LLM response."""

    unsupported = []

    def normalize_clause_refs(value: str) -> set[str]:
        value = str(value or "")

        refs = set(
            re.findall(
                r"\bclause\s+(\d+(?:\.\d+)*)\b",
                value,
                flags=re.IGNORECASE,
            )
        )

        bare = re.fullmatch(
            r"\s*(\d+(?:\.\d+)*)\s*",
            value,
        )

        if bare:
            refs.add(bare.group(1))

        return refs

    def normalize_section_refs(value: str) -> set[str]:
        value = str(value or "")

        return set(
            re.findall(
                r"\bsection\s+(\d+(?:\.\d+)*)\b",
                value,
                flags=re.IGNORECASE,
            )
        )

    allowed_clauses = set()

    for item in lease_citations:
        citation = str(item.get("citation", "") or "")
        content = str(item.get("content", "") or "")

        allowed_clauses.update(
            normalize_clause_refs(citation)
        )

        allowed_clauses.update(
            normalize_clause_refs(content)
        )

    allowed_sections = set()

    for item in statute_citations:
        citation = str(item.get("citation", "") or "")
        content = str(item.get("content", "") or "")

        allowed_sections.update(
            normalize_section_refs(citation)
        )

        allowed_sections.update(
            normalize_section_refs(content)
        )

    mentioned_clauses = set(
        re.findall(
            r"\bclause\s+(\d+(?:\.\d+)*)\b",
            reply,
            flags=re.IGNORECASE,
        )
    )

    mentioned_sections = set(
        re.findall(
            r"\bsection\s+(\d+(?:\.\d+)*)\b",
            reply,
            flags=re.IGNORECASE,
        )
    )

    for clause in sorted(mentioned_clauses):
        if clause not in allowed_clauses:
            unsupported.append(f"Clause {clause}")

    for section in sorted(mentioned_sections):
        if section not in allowed_sections:
            unsupported.append(f"Section {section}")

    return unsupported


def deterministic_evidence_gap_reply(

    reason: str,

    lease_citations: list[dict],

    statute_citations: list[dict],

    user_message: str,

    ledger: dict,

) -> str:



    lines = [

        f"I can't answer that confidently from "

        f"the indexed lease evidence. {reason}"

    ]



    if lease_citations:



        lines.append(

            "\n**Closest retrieved lease text "

            "(not a substitute for missing evidence):**"

        )



        for item in lease_citations[:3]:



            page = (

                f", page {item['page_number']}"

                if item.get(

                    "page_number"

                ) is not None

                else ""

            )



            lines.append(

                f"- Clause "

                f"{item.get('citation', 'unidentified')}"

                f"{page}: "

                f"{item.get('content', '')}"

            )



    else:



        lines.append(

            "\nNo lease clauses were retrieved "

            "for this question."

        )



    if statute_citations:



        lines.append(

            "\n**Retrieved statutory reference text "

            "(applicability must be verified):**"

        )



        for item in statute_citations[:3]:



            lines.append(

                f"- {item.get('citation', 'Unidentified provision')}: "

                f"{item.get('content', '')}"

            )



        lines.append(

            "These excerpts alone do not establish "

            "how a local court or authority would "

            "apply the law."

        )



    if (

        re.search(

            r"deposit|refund|deduct|amount|₹|inr|rs\b",

            user_message,

            flags=re.IGNORECASE,

        )

        and "error" not in ledger

    ):



        lines.append(

            "\nThe account audit records a "

            "refundable balance of "

            f"₹{ledger.get('lawful_refundable_balance_inr', 0):,.2f}."

        )



    lines.append(

        "If the clause is present in your PDF, "

        "check that the correct lease was ingested "

        "and indexed."

    )



    return "\n".join(lines)





# =========================================================

# GREETING DETECTION

# =========================================================



GREETING_PATTERN = re.compile(

    r"^\s*(hi+|hey+|hello+|thanks?|thank\s+you|"

    r"who\s+are\s+you|what\s+can\s+(?:you|u)\s+do|help)\b",

    re.IGNORECASE,

)



LEASE_DOMAIN_TERMS = re.compile(

    r"\b(deposit|rent|clause|notice|lock[ -]?in|"

    r"paint|repaint|geyser|repair|evict|refund|"

    r"deduct|landlord|tenant|pdf|agreement|lease)\b",

    re.IGNORECASE,

)





def is_casual_greeting_or_capability(

    text: str,

) -> bool:



    cleaned = text.strip()



    if (

        len(cleaned) <= 60

        and GREETING_PATTERN.match(cleaned)

        and not LEASE_DOMAIN_TERMS.search(cleaned)

    ):



        return True



    return False





# =========================================================

# LEASE REVIEW INTENT

# =========================================================



BROAD_REVIEW_PATTERN = re.compile(

    r"\b(review|analyze|analyse|audit|summarize|"

    r"summarise|entire|whole|complete|comprehensive|"

    r"all clauses|every clause|red flags|risks|"

    r"unfavorable|unfavourable|inconsistencies|"

    r"contradictions|problems|issues)\b",

    re.IGNORECASE,

)





def is_comprehensive_review(

    user_message: str,

    search_query: str,

) -> bool:



    combined = (

        f"{user_message} {search_query}"

    )



    return bool(

        BROAD_REVIEW_PATTERN.search(

            combined

        )

    )





# =========================================================

# CHAT ORCHESTRATION

# =========================================================





def is_joke_request(message: str) -> bool:
    """Detect an explicit request for a joke without triggering on unrelated text."""
    text = (message or "").strip().lower()
    patterns = (
        "tell me a joke", "let's hear a joke", "lets hear a joke",
        "let's listen to a joke", "lets listen to a joke",
        "can you tell me a joke", "give me a joke", "make me laugh",
        "joke please", "another joke", "joke",
    )
    return any(pattern in text for pattern in patterns)


def get_joke_reply(message: str) -> str:
    """Return a short, friendly joke for casual chat."""
    jokes = [
        "Why don't scientists trust atoms? Because they make up everything! 😄",
        "I told my computer I needed a break. It said: 'No problem—I'll go to sleep.' 😴",
        "Why was the math book sad? It had too many problems. 😂",
        "Why did the scarecrow win an award? Because he was outstanding in his field! 🌾",
        "I asked the Wi-Fi for a joke. It said, 'Sorry, the connection is weak.' 📶",
    ]
    # Rotate jokes based on message length so repeated requests don't always get the same one.
    return jokes[len(message or "") % len(jokes)]

async def chat_with_lease(

    tenant_id: str,

    lease_id: str,

    user_message: str,

    chat_history: list[dict] | None = None,

    attachments: list[dict] | None = None,

) -> dict:



    # -----------------------------------------------------

    # Greeting handling

    # -----------------------------------------------------



    if is_casual_greeting_or_capability(

        user_message

    ):



        greeting_reply = (

            "Hi! I'm **LeaseLens**, your rental agreement "

            "and deposit dispute assistant.\n\n"

            "Here is how I can help:\n"

            "- **Explain lease clauses:** Check lock-in periods, "

            "notice rules, maintenance terms, and penalties.\n"

            "- **Audit security deposits:** Review deductions, "

            "receipts, and refund calculations.\n"

            "- **Review screenshots and bills:** Upload landlord "

            "messages or repair invoices.\n"

            "- **Review your entire lease:** Identify financial "

            "risks, unfavorable clauses, contradictions, and "

            "potential red flags.\n"

            "- **Draft dispute notices:** Generate formal "

            "documents using the retrieved evidence.\n"

        )



        save_chat_turn(

            tenant_id,

            lease_id,

            "user",

            user_message,

        )



        save_chat_turn(

            tenant_id,

            lease_id,

            "assistant",

            greeting_reply,

            generation_mode="greeting",

        )



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



    # -----------------------------------------------------

    # Load history

    # -----------------------------------------------------



    ensure_chat_messages_table()



    full_history = (

        chat_history

        if chat_history is not None

        else load_chat_history(

            tenant_id,

            lease_id,

        )

    )



    search_query = (

        await contextualize_followup_query(

            user_message,

            full_history,

        )

    )



    if (

        attachments

        and not LEASE_DOMAIN_TERMS.search(

            search_query

        )

    ):



        search_query = (

            f"{search_query} security deposit "

            "deductions repainting repairs bills"

        ).strip()



    # -----------------------------------------------------

    # MCP retrieval

    # -----------------------------------------------------



    async with AsyncExitStack() as stack:



        rag = await stack.enter_async_context(

            create_mcp_client("mcp_servers/lease_statute_rag.py")

        )



        ledger_client = await stack.enter_async_context(

            create_mcp_client("mcp_servers/rent_ledger.py")

            )

        



        matched = tool_data(

            await rag.call_tool(

                "compare_lease_against_statutes",

                {

                    "tenant_id": tenant_id,

                    "lease_id": lease_id,

                    "dispute_query": search_query,

                },

            )

        )



        audit = tool_data(

            await ledger_client.call_tool(

                "audit_deposit_and_ledger",

                {

                    "tenant_id": tenant_id,

                    "lease_id": lease_id,

                },

            )

        )



    # -----------------------------------------------------

    # Evidence

    # -----------------------------------------------------



    lease_citations = matched.get(

        "lease_citations",

        [],

    )



    statute_citations = matched.get(

        "statute_citations",

        [],

    )



    history = (

        full_history[-12:]

        if isinstance(

            full_history,

            list,

        )

        else []

    )



    attachments = attachments or []



    attachment_metadata = [



        {

            "filename": str(

                att.get(

                    "filename",

                    "image",

                )

            )[:200],



            "mime_type": str(

                att.get(

                    "mime_type",

                    "",

                )

            ),

        }



        for att in attachments



        if str(

            att.get(

                "mime_type",

                "",

            )

        ) in {

            "image/png",

            "image/jpeg",

            "image/webp",

        }



        and isinstance(

            att.get(

                "data",

            ),

            bytes,

        )



        and len(

            att["data"]

        ) <= 10 * 1024 * 1024

    ]
        # -----------------------------------------------------
    # Structured output intent detection
    # -----------------------------------------------------

    structured_json_requested = bool(
        re.search(
            r"\b(json|json format|structured json|json object|"
            r"machine readable|structured output)\b",
            user_message,
            flags=re.IGNORECASE,
        )
    )


    gap_reason = evidence_gap_reason(

        user_message,

        search_query,

        lease_citations,

    )



    broad_review = is_comprehensive_review(

        user_message,

        search_query,

    )



    # =====================================================

    # SYSTEM PROMPT

    # =====================================================



    system_prompt = """
You are LeaseLens: a precise, user-friendly assistant for rental agreements,
lease disputes, deposits, rent calculations, and tenant obligations in India.

CORE RULE
Answer the exact question first. Accuracy and evidence are more important than
sounding confident or providing a long answer.

SOURCE PRIORITY
1. Retrieved lease clauses and uploaded document evidence.
2. Deterministic rent/deposit ledger audit.
3. User-provided facts in the current message.
4. Conversation history only to understand context or follow-up questions.
5. Retrieved statutory material only when the user has not requested document-only
   analysis and when it is relevant to the question.

Never treat a prior AI response as verified evidence.


LEGAL AUTHORITY AND JURISDICTION SAFEGUARDS
For questions involving Indian law:
- Identify the relevant state/jurisdiction when it materially affects the answer.
  If the jurisdiction is unknown, explicitly state that jurisdiction may affect the result.
- The Model Tenancy Act, 2021 is model legislation. Do not assume it is automatically
  binding or enacted in the user's state.
- Cite a statutory section only when the retrieved source explicitly identifies that
  section and supports the legal proposition being stated.
- Never invent section numbers, case names, court decisions, legal quotations,
  statutory wording, or legal authorities.
- Do not rely on a retrieved snippet alone when it does not clearly establish the
  relevant section and proposition.
- If a retrieved source contains a section number but its text does not support the
  proposition, do not cite it.
- Distinguish the following clearly:
  1. What the lease expressly says.
  2. What retrieved legal material says.
  3. Your general explanation or inference.
  4. What requires verification under applicable state law.
- Do not definitively label a lease clause illegal, void, unenforceable, or invalid
  unless reliable retrieved legal authority directly supports that conclusion and the
  relevant jurisdiction is established.
- When legal sources are unavailable or retrieval is incomplete, say:
  "I could not verify the applicable legal provision from the retrieved sources."
  Then provide a cautious explanation without inventing citations.
- When lease terms and legal sources appear to conflict, show the relevant lease
  wording and retrieved legal authority separately. Do not automatically conclude
  that either one overrides the other.

STRICT DOCUMENT-ONLY MODE
If the user asks "based only on my lease", "from the document only", "lease only",
"document-only", "without external law", or equivalent:
- Use only lease/document evidence and user-provided facts.
- Ignore statutory citations, legal databases, external law, and general legal knowledge.
- Do not mention laws or provide legal interpretation.
- If a requested fact is absent, say exactly: "Not specified in the document."
- You may perform arithmetic using figures explicitly found in the document. Label it
  "Calculation based on the document's figures" and do not imply it is a lease clause.

EVIDENCE AND FACTUAL ACCURACY
Never invent clauses, clause numbers, dates, names, amounts, penalties, receipts,
property details, statutory provisions, legal authorities, or facts.
Do not convert an inference into a contractual fact.

CONTRACTUAL FACT VS. INFERENCE — STRICT GUARDRAIL

For every contractual interpretation, distinguish these four levels:

1. EXPLICITLY STATED:
   The lease directly states the fact, right, obligation, permission, or condition.

2. CALCULATED:
   A numerical result derived from explicitly supported inputs.
   Show the formula and identify assumptions.

3. INFERRED:
   A reasonable interpretation of the clause, but not expressly stated.
   Introduce it with language such as "This may suggest..." or
   "A possible interpretation is...".

4. NOT ESTABLISHED:
   The lease does not explicitly establish the conclusion being asked about.

Never upgrade an inference into an explicit contractual right.

IMPORTANT EXAMPLE:
If a lease states that rent for an unserved notice period "may be deducted
from the security deposit", do NOT conclude that the tenant has an
unconditional right to leave immediately by paying that amount.

Instead explain:
- The lease requires the stated notice period.
- The lease allows a deduction for the unserved notice period, if applicable.
- The lease does not necessarily establish that immediate termination by
  payment is an unconditional right.
- Whether the landlord must accept early departure or payment in lieu of
  notice is not established unless the contract expressly says so.

Similarly:
- "May deduct" does not mean a deduction is automatically owed.
- "Can issue a reminder" does not mean a monetary penalty exists.
- "Subject to documented deductions" does not mean any requested deduction
  is automatically valid.
- A permitted deduction does not automatically establish the landlord's
  right to terminate.
- A clause describing consequences does not necessarily establish permission
  to perform the underlying action.

When a question asks whether the user CAN do something, verify that the
document explicitly grants that right. Do not infer permission merely from
a clause describing consequences, costs, or deductions.
For each important lease claim, cite the clause/source when available, e.g. (Clause 4.2).
If evidence is missing, incomplete, or retrieval is weak, state that limitation clearly.
Use these distinctions:
- "The lease states..." = explicit contract text.
- "The evidence shows..." = retrieved records/documents.
- "This may mean..." = cautious inference.
- "Not specified in the document." = the document does not state it.
- "Not found in retrieved evidence." = retrieval did not provide it; do not claim it
  is absent from the full agreement unless the full document was searched.

QUESTION INTENT
Adapt the response to the request:
- Summary: give key terms only (rent, deposit, dates, lock-in, notice, responsibilities).
- Specific clause question: direct answer, clause, practical meaning, consequence.
- Risk review: rank only material risks; explain why, impact, and practical action.

- Comprehensive risk analysis:
  When the user asks to identify risks, disadvantages, financial exposure,
  loopholes, or problematic clauses, perform a systematic review of all
  relevant retrieved evidence rather than focusing only on the first matching
  clauses.

  Check relevant categories when evidence is available:
  - Rent, escalation, renewal, and payment deadlines.
  - Security deposit, refund timeline, and deduction conditions.
  - Lock-in, termination, notice, and early-exit consequences.
  - Maintenance, repair, damage, and cleaning responsibilities.
  - Utilities and additional charges.
  - Late-payment consequences.
  - Landlord access and tenant privacy.
  - Renewal, amendments, and missing protections.
  - Ambiguous, conditional, unusually broad, or one-sided wording.

  Do not invent a risk merely because a clause is absent.
  Distinguish:
  1. Explicit contractual risk.
  2. Ambiguity or uncertainty.
  3. Missing contractual protection.
  4. Potential legal risk requiring jurisdiction-specific verification.

  For each material finding, provide:
  - Risk.
  - Supporting clause/evidence.
  - Practical financial or operational impact.
  - What is explicitly stated versus inferred.
  - Recommended action, where useful.

  If retrieval only covers part of the lease, disclose that the review
  is limited to the retrieved evidence and do not imply that the entire
  agreement was exhaustively reviewed.
- Contradiction scan: compare actual passages. Show both sides, source references,
  and why they conflict. If no conflict is found in retrieved evidence, say so and
  qualify the search scope. Do not label missing information as a contradiction.
- Financial question: calculate the requested scenario using actual figures.
  Show the formula and arithmetic. Separate confirmed contractual amounts from
  conditional, disputed, or unknown amounts. Never double-count.
- Yes/no question: answer Yes, No, or Not specified first, then one short explanation.
- Broad lease review: focus on the 3–5 highest-impact findings, not every clause.
- Drafting request: produce a ready-to-use draft, with placeholders only for facts
  genuinely missing from the evidence.

FINANCIAL CALCULATIONS
Calculate when enough evidence exists. Examples include:
- Notice-period rent = monthly rent × notice months.
- Deposit balance = deposit − confirmed deductions.
- Lock-in exposure = contractual rent/penalty applicable to the remaining lock-in,
  only if the clause and calculation method are actually supported.
- Prorated rent = only when the lease or user provides a valid prorating basis.
Show the inputs, formula, result, and assumptions. For a 60-day notice period
with monthly rent, show the two-month equivalent when the question asks for the
full notice-period amount (monthly rent × 2), while clearly stating that exact
calendar-day prorating may differ if the lease does not define it. For example,
₹28,000/month × 2 months = ₹56,000. Never skip arithmetic when the necessary
figures are present. Do not assume confirmed deductions are zero: report the gross
deposit and calculate a net refund only after deductions are confirmed. Do not assume
a potential penalty is automatically enforceable or actually owed. If the clause does
not define how an amount is calculated, say that the amount cannot be reliably calculated.

FINANCIAL ANSWER VERIFICATION CHECKLIST
Before finalizing any answer involving money, internally verify:
1. Every numeric input is supported by retrieved lease evidence, ledger evidence, or
   a clearly identified user-provided assumption. Never invent an input.
2. Recalculate the arithmetic independently. The displayed formula must match the
   displayed result; correct any mismatch before answering.
3. Label amounts as one of: contractual amount, calculated estimate, conditional
   liability, gross deposit, confirmed deduction, or unknown final amount.
4. Do not turn a hypothetical, conditional, disputed, or mitigation-dependent amount
   into a definite amount owed.
5. For notice calculations, distinguish 60 calendar days from a two-month equivalent.
   If using ₹28,000 × 2 = ₹56,000, label it an estimate/equivalent and state that exact
   date-based calculation may differ if the agreement does not define prorating.
6. For deposit refunds, never claim the full deposit is the final refund unless all
   deductions have been confirmed. If damage is unknown, say the baseline is ₹56,000
   before any eligible deductions and the final refund is not yet determinable.
7. For escalation/renewal, do not state a future rent as automatic when renewal or a
   written addendum is required. Present ₹30,800 only as the arithmetic result of a
   hypothetical 10% increase on ₹28,000, not as a confirmed future contractual rent.
8. In risk reviews, describe the scope of a clause precisely. Do not say the tenant is
   responsible for "all" or "fully" responsible for damage when the clause limits
   liability to negligence, misuse, or specified circumstances.
9. If the evidence is insufficient for an exact figure, provide the supported formula
   or range, identify missing inputs, and avoid false precision.
10. End financial answers with a concise statement of the key assumption/uncertainty
    when one materially affects the result.

RENT ESCALATION AND TIMELINES
Read dates and trigger language literally. Distinguish:
- escalation during the current term versus renewal;
- a fixed date versus "after every X months";
- a notice period versus lock-in;
- an obligation versus a condition that applies only after an event.
Do not apply a renewal/escalation clause to the initial term unless the text clearly
says it applies. Calculate timeline milestones only from explicit dates and durations.

CONTRADICTIONS
Only report a contradiction when two pieces of retrieved evidence conflict on the
same subject. Compare the wording and values; do not choose a winner without basis.
Distinguish contradictions, ambiguity, missing information, and duplicate wording.

PRECISION AND CONFIDENCE LAYER
Before answering, classify the response internally as one of:
- CONFIRMED: directly supported by the lease or reliable retrieved record.
- CALCULATED: arithmetic from confirmed inputs; show the formula.
- CONDITIONAL: depends on a future event, assumption, mitigation, negotiation, or
  unresolved fact. State the condition clearly.
- UNCERTAIN: evidence is incomplete, conflicting, or insufficient. Explain what is
  missing and do not guess.
Do not display a confidence percentage or claim certainty based only on model intuition.
Use calibrated language: "The lease states", "Based on the information provided",
"Estimated", "Potentially", or "Cannot be determined yet" as appropriate.
Never use "maximum liability", "guaranteed", "exact", "automatically owed", or
"definitely refundable" unless the evidence and calculation support that wording.
When a clause is conditional or mitigation-dependent, explain that condition in the
main answer, not only in a footnote.

CHAT RESPONSE QUALITY AND ADAPTIVE STRUCTURE

Apply the same evidence-grounding, citation-validation, and uncertainty rules
to every conversational response, not only formal lease reviews.

ADAPTIVE RESPONSE FORMAT:
- Casual or unrelated question: respond naturally and conversationally.
  Do not force headings, citations, legal disclaimers, or lease analysis.
- Simple lease question: answer directly in 1-3 sentences and cite the
  supporting clause inline when available.
- Follow-up question: use the conversation history to understand references
  such as "that clause", "this amount", "what about termination", or "it".
  Reuse prior context, but never treat a prior AI answer as verified evidence.
- Complex lease question: organize the answer using only relevant sections:
  Short Answer, What Your Lease Says, Evidence, Limitations, and Next Step.
  Do not print empty sections.
- Financial question: use verified ledger/document values, show the formula
  and result, and clearly distinguish confirmed amounts from estimates,
  disputed amounts, and conditional liabilities.
- Legal question: separate contractual wording, retrieved legal authority,
  and general explanation. Do not make definitive legal conclusions without
  verified authority and jurisdiction.
- Risk question: identify the material risk, supporting clause, practical
  impact, and recommended action.
- Comprehensive review: prioritize the highest-impact findings rather than
  listing every clause.

CHAT EVIDENCE GATE:
Before answering a lease-specific or legal question, determine whether the
retrieved evidence directly supports the answer.

Evidence is insufficient when:
- No relevant lease evidence was retrieved.
- The retrieved text does not directly support the requested conclusion.
- A necessary clause, amount, date, condition, or jurisdiction is missing.
- Relevant retrieved sources conflict and the conflict is unresolved.
- The answer requires legal authority that was not verified.
- The retrieved evidence is only a partial snippet and the conclusion depends
  on missing surrounding wording.

When evidence is insufficient:
- Do not guess or fill gaps using general assumptions.
- Clearly state what could and could not be verified.
- Provide the closest relevant retrieved evidence, if useful.
- Identify the single most important missing fact or source.
- If another retrieval attempt is possible, search for the missing evidence
  before giving the final limited answer.
- If retrieval remains insufficient, give a cautious answer and explain
  the limitation in plain English.

CONVERSATIONAL QUALITY:
- Do not sound robotic or repeatedly use the same headings.
- Do not repeat information already explained unless needed for clarity.
- Keep simple answers short and complex answers well organized.
- Answer the user's actual question before adding background.
- Provide practical next steps only when genuinely useful.
- Never sacrifice accuracy to make an answer sound complete.


USER-FRIENDLY RESPONSE STYLE
- Use plain English and answer in the first sentence. Avoid legal jargon unless needed;
  briefly explain any necessary term.
- For routine questions, aim for 2–5 short sentences or 2–4 bullets.
- For calculations, use a compact, user-friendly format:
  **Estimated amount:** ₹X (when supported)
  **How it is calculated:** ₹A × B = ₹X
  **What this means:** one plain-English sentence.
  **Important:** one short assumption/condition only when it materially changes the result.
  Do not force all labels for simple calculations; keep the answer conversational.
- If the user asks a casual question, a joke, or something unrelated to their lease,
  respond naturally and briefly instead of forcing lease analysis or citations.
- If the user asks for a joke, tell one clean, short joke. Keep it friendly and avoid
  making jokes about the user's legal, financial, housing, or personal situation.
- If the user mixes a lease question with a joke request, answer the lease question
  accurately first, then add the joke as a clearly separate, optional final line.
- Use headings only when they improve scanning. Avoid repetitive headings such as
  "Contractual Rule", "Next Step", or "Verified from Lease & Law Records" in every answer.
- Do not repeat the same fact in multiple bullets.
- Cite the relevant clause inline beside the claim. Do not add citations to clauses
  that do not support the statement.
- Offer a practical next step only when it is genuinely useful, and keep it to one sentence.
- If the answer is uncertain, explain the reason plainly and identify the one key fact
  needed to resolve it. Do not bury the answer beneath disclaimers.
If conflicting text exists, identify both passages and recommend checking the signed
original or addendum.

LEGAL CONTEXT
The Model Tenancy Act, 2021 is a model law and is not automatically binding in every
state. Do not assert that a clause is illegal, unenforceable, or guaranteed to be
challenged successfully unless reliable retrieved evidence establishes that.
Distinguish contractual wording from legal interpretation. State when jurisdiction,
current law, or applicability requires verification. Do not invent citations.

RESPONSE QUALITY
- Start with the direct answer or takeaway in the first sentence.
- Use plain English, short sentences, and a professional conversational tone.
- Normally 80–160 words for a specific question.
- Broad reviews: normally under 350 words unless the user requests detail.
- Use 3–5 bullets maximum unless the task requires a table or full draft.
- Include only relevant sections; never print empty headings.
- Avoid repeating the same fact in the summary, risk, and action sections.
- Avoid generic disclaimers and filler such as "It is important to note".
- Make next steps concrete and prioritized.

CITATIONS
Use only citation labels present in retrieved evidence. Never fabricate clause
numbers or legal references. Put citations beside the claim they support.

CONVERSATION HISTORY
Use prior messages to resolve follow-up references. If a previous assistant answer
was incorrect or unsupported, correct it clearly rather than preserving it.
"""


    # -----------------------------------------------------

    # Generation

    # -----------------------------------------------------



    reply = None

    model_used = None

    handoff_note = None

    mode = None



    # -----------------------------------------------------

    # Evidence gap fallback

    # -----------------------------------------------------



    if gap_reason:



        reply = deterministic_evidence_gap_reply(

            gap_reason,

            lease_citations,

            statute_citations,

            user_message,

            audit,

        )



        mode = "deterministic_fallback"



    else:



        try:



            reply, model_used, handoff_note = (

                await generate_with_handoff(

                    system_prompt=system_prompt,

                    user_message=user_message,

                    chat_history=history,

                    lease_citations=lease_citations,

                    statute_citations=statute_citations,

                    ledger_audit=audit,

                    search_query=search_query,

                    attachments=attachments,

                )

            )



        except Exception:



            logger.exception(

                "Multi-provider LLM router failed; "

                "using deterministic retrieval fallback"

            )



    # -----------------------------------------------------

    # Deterministic fallback

    # -----------------------------------------------------



    if reply is None:



        reply = deterministic_chat_reply(

            lease_citations,

            statute_citations,

            audit,

        )



        mode = "deterministic_fallback"



    # -----------------------------------------------------

    # Citation validation

    # -----------------------------------------------------



    elif model_used is not None:



        mode = (

            model_used

            if ":" in model_used

            else f"llm:{model_used}"

        )



        unsupported = unsupported_citations(

            reply,

            lease_citations,

            statute_citations,

        )



        if unsupported:



            logger.warning(

                "Model %s cited unavailable evidence %s; "

                "replacing response with grounded fallback",

                model_used,

                unsupported,

            )



            reply = deterministic_evidence_gap_reply(

                "The generated answer cited material "

                "that was not in the retrieved evidence.",

                lease_citations,

                statute_citations,

                user_message,

                audit,

            )



            mode = "deterministic_fallback"



        elif handoff_note:



            reply += (

                f"\n\n_{handoff_note}_"

            )

    # -----------------------------------------------------
    # Structured output validation
    # -----------------------------------------------------

    if structured_json_requested:
        is_valid_json, parsed_json = validate_json_response(reply)

        if is_valid_json:
            # Normalize valid JSON to ensure consistent formatting.
            reply = json.dumps(
                parsed_json,
                ensure_ascii=False,
                indent=2,
            )

        else:
            logger.warning(
                "Model returned invalid JSON for structured-output request"
            )

            reply = json.dumps(
                {
                    "error": "Structured response generation failed",
                    "message": (
                        "LeaseLens could not generate valid JSON "
                        "for this request."
                    ),
                    "available_evidence": {
                        "lease_clauses": [
                            item.get("citation")
                            for item in lease_citations
                            if item.get("citation")
                        ],
                        "statutory_sources": [
                            item.get("citation")
                            for item in statute_citations
                            if item.get("citation")
                        ],
                    },
                    "limitations": (
                        "The response could not be validated as JSON. "
                        "No unsupported information was added."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )

    # -----------------------------------------------------

    # Attachment fallback

    # -----------------------------------------------------



    if (

        mode == "deterministic_fallback"

        and attachment_metadata

    ):



        reply += (

            "\n\nAn image was attached, but image "

            "analysis is unavailable in deterministic "

            "fallback mode. The response above uses "

            "retrieved text and the SQL audit only."

        )



    # -----------------------------------------------------

    # Save history

    # -----------------------------------------------------



    save_chat_turn(

        tenant_id,

        lease_id,

        "user",

        user_message,

        attachments=attachment_metadata,

    )



    save_chat_turn(

        tenant_id,

        lease_id,

        "assistant",

        reply,

        lease_citations=lease_citations,

        statute_citations=statute_citations,

        generation_mode=mode,

    )



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





# =========================================================

# FOLLOW-UP QUERY CONTEXTUALIZATION

# =========================================================



async def contextualize_followup_query(

    user_message: str,

    recent_history: list[dict],

) -> str:



    if not recent_history:

        return user_message



    system_prompt = (

        "Rewrite the latest user message as one concise, "

        "standalone search query for finding rental-agreement "

        "clauses and statutory references. "

        "Resolve pronouns and references such as 'it', "

        "'that clause', and 'those deductions' using the "

        "conversation. Preserve clause numbers, amounts, "

        "and factual details. Do not answer the question, "

        "assess legality, add facts, or include commentary. "

        "Return only the rewritten query."

    )



    try:



        rewritten, _, _ = (

            await generate_with_handoff(

                system_prompt=system_prompt,

                user_message=user_message,

                chat_history=recent_history[-8:],

            )

        )



        if (

            rewritten

            and rewritten.strip()

        ):



            return (

                rewritten.strip()

                .strip('"')

                .strip()

            )



    except Exception:



        logger.exception(

            "Follow-up query rewrite failed; "

            "carrying forward prior context"

        )



    previous_user_content = (



        recent_history[-2].get(

            "content",

            "",

        )



        if len(recent_history) >= 2



        else recent_history[-1].get(

            "content",

            "",

        )

    )



    return (

        f"{previous_user_content} "

        f"{user_message}"

    ).strip()





# =========================================================

# CLI

# =========================================================



def main():



    parser = argparse.ArgumentParser()



    parser.add_argument(

        "--tenant-id",

        default="user_rahul",

    )



    parser.add_argument(

        "--lease-id",

        default="lease_001",

    )



    parser.add_argument(

        "--query",

        default=(

            "My landlord withheld the deposit "

            "for repainting and an old geyser. "

            "Are these valid deductions?"

        ),

    )



    args = parser.parse_args()



    ensure_chat_messages_table()



    print(

        asyncio.run(

            run(

                args.query,

                args.tenant_id,

                args.lease_id,

            )

        )

    )





if __name__ == "__main__":

    main()