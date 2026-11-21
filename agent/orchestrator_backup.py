"""LeaseLens conversational orchestration and evidence-grounded response generation."""



import argparse

import asyncio

import json

import logging

import os

import re



from contextlib import AsyncExitStack

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





GEMINI_MODELS = [

    "gemini-3.5-flash-lite",

    "gemini-3.8-flash",

]



logger = logging.getLogger(__name__)



DATABASE_URL = os.getenv(

    "DATABASE_URL",

    "postgresql://leaselens:leaselens@localhost:5432/leaselens",

)





# =========================================================

# DATABASE / CHAT HISTORY

# =========================================================



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

            Client(

                "mcp_servers/lease_statute_rag.py"

            )

        )



        ledger = await stack.enter_async_context(

            Client(

                "mcp_servers/rent_ledger.py"

            )

        )



        notice = await stack.enter_async_context(

            Client(

                "mcp_servers/notice_drafter.py"

            )

        )



        matched = tool_data(

            await rag.call_tool(

                "compare_lease_against_statutes",

                {

                    "tenant_id": tenant_id,

                    "lease_id": lease_id,

                    "dispute_query": query,

                },

            )

        )



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



    asked = (

        f"{user_message} {search_query}"

    )



    available = {

        str(

            item.get(

                "citation",

                "",

            )

        ).strip()



        for item in lease_citations

    }



    requested_clauses = set(

        re.findall(

            r"\bclause\s+(\d+(?:\.\d+)*)\b",

            asked,

            flags=re.IGNORECASE,

        )

    )



    missing = (

        requested_clauses

        - available

    )



    if missing:



        refs = ", ".join(

            f"Clause {number}"

            for number in sorted(missing)

        )



        return (

            f"The explicitly requested {refs} "

            "was not found in the indexed lease evidence."

        )



    requested_lock_in = re.search(

        r"lock[ -]?in",

        user_message,

        flags=re.IGNORECASE,

    )



    lease_text = " ".join(

        str(

            item.get(

                "content",

                "",

            )

        )



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





# =========================================================

# CITATION VALIDATION

# =========================================================



def unsupported_citations(

    reply: str,

    lease_citations: list[dict],

    statute_citations: list[dict],

) -> list[str]:



    unsupported = []



    allowed_clauses = {

        str(

            item.get(

                "citation",

                "",

            )

        ).strip()



        for item in lease_citations

    }



    allowed_sections = {



        section



        for item in statute_citations



        for section in re.findall(

            r"\bsection\s+(\d+(?:\.\d+)*)\b",

            str(

                item.get(

                    "citation",

                    "",

                )

            ),

            flags=re.IGNORECASE,

        )

    }



    for clause in re.findall(

        r"\bclause\s+(\d+(?:\.\d+)*)\b",

        reply,

        flags=re.IGNORECASE,

    ):



        if clause not in allowed_clauses:



            unsupported.append(

                f"Clause {clause}"

            )



    for section in re.findall(

        r"\bsection\s+(\d+(?:\.\d+)*)\b",

        reply,

        flags=re.IGNORECASE,

    ):



        if section not in allowed_sections:



            unsupported.append(

                f"Section {section}"

            )



    return unsupported





# =========================================================

# DETERMINISTIC EVIDENCE-GAP RESPONSE

# =========================================================



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

            Client(

                "mcp_servers/lease_statute_rag.py"

            )

        )



        ledger_client = await stack.enter_async_context(

            Client(

                "mcp_servers/rent_ledger.py"

            )

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

You are LeaseLens, an evidence-grounded Indian rental

agreement assistant.



Your purpose is to help tenants understand their lease,

identify financial risks, detect inconsistencies, and

understand possible tenant protections.



You must prioritize factual accuracy over confidence.



========================================================

EVIDENCE RULES

========================================================



1. Use only the retrieved lease clauses, statutory

   excerpts, ledger audit, user-provided facts, and

   relevant conversation history.



2. Never invent:

   - Lease clauses

   - Clause numbers

   - Statutory sections

   - Legal authorities

   - Rent amounts

   - Deposit amounts

   - Dates

   - Bills

   - Receipts

   - Facts about the property



3. Clearly distinguish these three things:



   A. WHAT THE LEASE SAYS

      Describe the actual contract wording.



   B. WHAT THE EVIDENCE SHOWS

      Describe retrieved documents, ledger entries,

      amounts, or conflicting passages.



   C. LEGAL INTERPRETATION

      Explain possible legal implications cautiously.

      Do not present an interpretation as verified law

      unless the retrieved statutory evidence supports it.



4. The Model Tenancy Act, 2021 is a model law.

   Do not automatically treat it as binding legislation

   in the tenant's state.



5. State-specific legislation may differ.

   When the retrieved evidence does not establish

   applicability, say that applicability requires

   verification under the relevant state law.



6. Never say:

   - "This is definitely illegal"

   - "The landlord cannot do this"

   - "You are guaranteed to win"

   - "The law clearly protects you"



   unless the retrieved evidence directly and reliably

   establishes the statement.



7. Prefer wording such as:

   - "This clause may be challengeable."

   - "This raises a potential legal concern."

   - "The lease appears to require..."

   - "The applicability of this protection requires

      verification under your state's law."

   - "The retrieved evidence does not establish

      whether this provision is enforceable."



========================================================

CONTRADICTION DETECTION

========================================================



When multiple retrieved clauses or records concern

the same topic, compare them.



Look specifically for contradictions involving:



- Monthly rent

- Security deposit

- Deposit months

- Lock-in duration

- Notice period

- Termination conditions

- Painting deductions

- Cleaning deductions

- Repair responsibilities

- Appliance replacement

- Deposit refund conditions

- Late payment penalties



If conflicting text is retrieved:



1. Quote or accurately summarize both versions.

2. Identify the clause numbers or source references.

3. Explain why they conflict.

4. Do not arbitrarily choose one version.

5. State that the original signed agreement must be

   checked to determine which version controls.



Do not call duplicate clauses contradictions if the

wording and amounts are identical.



Do not claim a contradiction unless conflicting

evidence is actually present.



========================================================

FINANCIAL ANALYSIS

========================================================



For financial risks:



- Use exact amounts from retrieved evidence.

- Show arithmetic.

- Identify the source clause for each amount.

- Distinguish contractual amounts from potential

  amounts that may be disputed.

- Avoid double-counting deductions.

- Do not assume a deduction has actually been made

  unless the ledger or user evidence establishes it.



Calculate potential exposure where possible.



Examples:



- Lock-in penalty

- Security deposit

- Painting charges

- Cleaning charges

- Late fees

- Appliance replacement

- Notice-period rent



When amounts are unknown, explicitly say "amount not

specified in retrieved evidence."



========================================================

COMPREHENSIVE LEASE REVIEW

========================================================



If the user requests:



- Review my entire lease

- Analyze the whole agreement

- Identify all unfavorable clauses

- Find all red flags

- Comprehensive lease review

- Identify inconsistencies

- Summarize all risks



Do NOT answer with only two or three clauses.



Review all retrieved lease passages.



Organize the response into:



1. Executive summary



2. High-risk clauses



3. Financial exposure



4. Potentially unfavorable clauses



5. Inconsistencies and conflicting provisions



6. Duplicate or overlapping obligations



7. Clauses requiring legal verification



8. Missing information or limitations



For each identified issue include:



- Clause number

- What the lease says

- Why it could be unfavorable

- Potential financial exposure

- Evidence

- Confidence or uncertainty



Do not invent missing clauses.



If the retrieval evidence appears incomplete, explicitly

state that the review covers only the retrieved/indexed

clauses and is not necessarily a complete review of

the signed agreement.



========================================================

SPECIFIC QUESTION FORMAT

========================================================



For specific clause questions:



Start with a direct answer.



Then explain:



- Lease provision

- Relevant evidence

- Potential risk

- Applicable retrieved statutory text, if any

- What remains uncertain



Keep the answer concise unless the user requests detail.



========================================================

CITATIONS

========================================================



Cite lease clauses naturally:



(Clause 3.1)



Cite retrieved statutory references using their exact

citation labels.



Never invent citations.



If a citation is not present in the retrieved evidence,

do not use it.



========================================================

CONVERSATION HISTORY

========================================================



Use history only to understand follow-up questions.



Do not treat previous AI answers as verified facts.



If a previous assistant response made a claim that is

not supported by the current evidence, correct it.



========================================================

STYLE

========================================================



Use simple, clear language.



Be direct.



Avoid excessive legal jargon.



Do not exaggerate risks.



Do not claim that sources are "verified" unless the

retrieved evidence actually supports verification.



Use headings and bullet points where useful.



Do not use generic legal disclaimers.



A short, specific statement about uncertainty or

jurisdiction is acceptable when relevant.

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