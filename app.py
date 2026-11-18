"""LeaseLens Streamlit dashboard."""
import asyncio
import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="LeaseLens", page_icon="🏠", layout="wide")
st.title("🏠 LeaseLens")
st.caption("Rental agreement research, deposit audit, and dispute notice drafting")

with st.sidebar:
    st.subheader("Case")
    tenant_id = st.text_input("Tenant ID", "user_rahul")
    lease_id = st.text_input("Lease ID", "lease_001")
    demo = st.toggle("Use Rahul demo case", value=True)
    uploaded = st.file_uploader("Upload a rental agreement (PDF)", type=["pdf"], disabled=demo)
    if uploaded and not demo and st.button("Ingest PDF"):
        os.makedirs("uploads", exist_ok=True)
        path = os.path.join("uploads", uploaded.name)
        with open(path, "wb") as f:
            f.write(uploaded.getvalue())
        from ingestion.ingest_data import ingest_pdf
        ingest_pdf(__import__("pathlib").Path(path), tenant_id, lease_id)
        st.success("PDF clauses indexed for this tenant and lease.")

query = st.text_area("Describe the dispute", "My landlord withheld my deposit for blanket repainting and an old geyser coil burnout.")


def call_tools(query_text):
    from fastmcp import Client
    if demo:
        from ingestion.ingest_data import add_demo, connect
        with connect() as conn:
            add_demo(conn)
    async def execute():
        async with Client("mcp_servers/lease_statute_rag.py") as rag, Client("mcp_servers/rent_ledger.py") as ledger:
            matched = await rag.call_tool("compare_lease_against_statutes", {"tenant_id": tenant_id, "lease_id": lease_id, "dispute_query": query_text})
            audit = await ledger.call_tool("audit_deposit_and_ledger", {"tenant_id": tenant_id, "lease_id": lease_id})
            return matched.structured_content or matched.data, audit.structured_content or audit.data
    return asyncio.run(execute())


if st.button("Analyze dispute", type="primary"):
    with st.spinner("Searching clauses and auditing the ledger…"):
        try:
            matched, audit = call_tools(query)
            st.session_state["matched"] = matched
            st.session_state["audit"] = audit
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

if "matched" in st.session_state:
    matched, audit = st.session_state["matched"], st.session_state["audit"]
    st.subheader("Lease vs. statute evidence")
    left, right = st.columns(2)
    for col, heading, items in [(left, "Lease clauses", matched.get("lease_citations", [])), (right, "Statute references", matched.get("statute_citations", []))]:
        with col:
            st.markdown(f"#### {heading}")
            if not items:
                st.info("No matching citations in the top three results.")
            for item in items:
                st.markdown(f"**{item.get('citation')}** · rerank {item.get('rerank_score', 0):.3f}")
                st.write(item.get("content"))
    st.subheader("SQL deposit audit")
    st.dataframe([{"Metric": k.replace("_", " ").title(), "Value": v} for k, v in audit.items() if isinstance(v, (int, float))], hide_index=True, use_container_width=True)
    st.caption(audit.get("calculation_note", ""))
    if st.button("Draft formal notice"):
        if not os.getenv("GEMINI_API_KEY"):
            st.error("Set GEMINI_API_KEY in .env to draft the notice.")
        else:
            from fastmcp import Client
            async def draft():
                async with Client("mcp_servers/notice_drafter.py") as notice:
                    result = await notice.call_tool("generate_dispute_package", {"tenant_id": tenant_id, "lease_id": lease_id,
                        "dispute_summary": query, "matched_conflicts": json.dumps(matched), "ledger_audit": json.dumps(audit)})
                    return result.structured_content or result.data
            try:
                package = asyncio.run(draft())
                assessment = package["risk_assessment"]
                st.subheader("Dispute risk assessment")
                risk_col, level_col, refund_col = st.columns(3)
                risk_col.metric("Risk score", f"{assessment['risk_score_0_to_100']}/100")
                level_col.metric("Risk level", assessment["risk_level"].title())
                refund_col.metric("Refundable balance", f"₹{assessment['lawful_refundable_amount_inr']:,.2f}")
                mode = package.get("generation_mode", "unknown")
                st.caption(f"Generation mode: {mode}" + (f" · Model: {package['model_used']}" if package.get("model_used") else ""))
                if package.get("fallback_reason"):
                    st.caption(f"Fallback detail: {package['fallback_reason']}")
                st.json(assessment)
                st.text_area("Draft notice", package["legal_notice"], height=400)
                st.download_button("Download notice", package["legal_notice"], file_name=f"{lease_id}-dispute-notice.txt", mime="text/plain")
                st.caption(package["disclaimer"])
            except Exception as exc:
                st.error(f"Notice drafting failed: {exc}")
