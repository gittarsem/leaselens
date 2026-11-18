"""Run all three local FastMCP services through Google Gen AI's MCP support."""
import argparse
import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from google import genai
from google.genai import types
from google.genai.errors import APIError

load_dotenv()
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]


async def generate_with_fallback(client, prompt, tools):
    """Try primary Gemini three times, then each fallback model once."""
    for model_name in GEMINI_MODELS:
        attempts = 3 if model_name == GEMINI_MODELS[0] else 1
        for attempt in range(attempts):
            try:
                response = await client.aio.models.generate_content(
                    model=model_name, contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1, tools=tools))
                return response.text, model_name
            except APIError as exc:
                status = getattr(exc, "status_code", getattr(exc, "code", None))
                if status in (429, 503) and attempt + 1 < attempts:
                    await asyncio.sleep(2 ** attempt)
                    continue
                # A 400/404 often means that model is unavailable to this key;
                # try the next configured Flash model and ultimately degrade.
                break
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", default="user_rahul")
    parser.add_argument("--lease-id", default="lease_001")
    parser.add_argument("--query", default="My landlord withheld the deposit for repainting and an old geyser coil. Are these valid deductions?")
    args = parser.parse_args()
    print(asyncio.run(run(args.query, args.tenant_id, args.lease_id)))


if __name__ == "__main__":
    main()
