"""LeaseLens Streamlit dashboard with grounded lease chat and dispute audit."""
import asyncio
import json
import os
from decimal import Decimal

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
    rent = st.number_input("Monthly rent (INR)", min_value=1, value=30000, step=1000, disabled=demo)
    deposit = st.number_input("Deposit paid (INR)", min_value=0, value=150000, step=5000, disabled=demo)
    if uploaded and not demo and st.button("Ingest PDF"):
        os.makedirs("uploads", exist_ok=True)
        path = os.path.join("uploads", uploaded.name)
        with open(path, "wb") as f:
            f.write(uploaded.getvalue())
        from ingestion.ingest_data import ingest_lease_pdf
        ingest_lease_pdf(__import__("pathlib").Path(path), tenant_id, lease_id,
                         Decimal(str(rent)), Decimal(str(deposit)))
        st.success("PDF clauses and lease financial account indexed for this tenant and lease.")


def ensure_demo_seeded():
    if demo:
        from ingestion.ingest_data import add_demo, connect
        with connect() as conn:
            add_demo(conn)


def model_status_caption(generation_mode, model_used=None):
    if generation_mode and generation_mode.startswith("llm:"):
        return f"Powered by {generation_mode.split(':', 1)[1]}"
    if generation_mode == "llm" and model_used:
        return f"Powered by {model_used}"
    return "Deterministic Retrieval Fallback"


def call_tools(query_text):
    from fastmcp import Client
    ensure_demo_seeded()

    async def execute():
        async with Client("mcp_servers/lease_statute_rag.py") as rag, Client("mcp_servers/rent_ledger.py") as ledger:
            matched = await rag.call_tool("compare_lease_against_statutes", {"tenant_id": tenant_id, "lease_id": lease_id, "dispute_query": query_text})
            audit = await ledger.call_tool("audit_deposit_and_ledger", {"tenant_id": tenant_id, "lease_id": lease_id})
            return matched.structured_content or matched.data, audit.structured_content or audit.data
    return asyncio.run(execute())


def draft_notice(summary, matched, audit, force_deterministic=False):
    from fastmcp import Client

    async def execute():
        async with Client("mcp_servers/notice_drafter.py") as notice:
            result = await notice.call_tool("generate_dispute_package", {
                "tenant_id": tenant_id, "lease_id": lease_id, "dispute_summary": summary,
                "matched_conflicts": json.dumps(matched, ensure_ascii=False),
                "ledger_audit": json.dumps(audit, ensure_ascii=False),
                "force_deterministic": force_deterministic})
            return result.structured_content or result.data
    return asyncio.run(execute())


def render_audit(query):
    if st.button("Analyze dispute", type="primary"):
        with st.spinner("Searching clauses and auditing the ledger…"):
            try:
                matched, audit = call_tools(query)
                st.session_state["matched"] = matched
                st.session_state["audit"] = audit
                st.session_state["audit_query"] = query
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")

    if "matched" not in st.session_state:
        st.info("Analyze a dispute to see lease clauses, statutory references, and the SQL deposit audit.")
        return
    matched, audit = st.session_state["matched"], st.session_state["audit"]
    st.subheader("Lease vs. statute evidence")
    left, right = st.columns(2)
    for col, heading, items in [(left, "Lease clauses", matched.get("lease_citations", [])),
                                (right, "Statute references", matched.get("statute_citations", []))]:
        with col:
            st.markdown(f"#### {heading}")
            if not items:
                st.info("No matching citations in the top results.")
            for item in items:
                page = f" · page {item['page_number']}" if item.get("page_number") is not None else ""
                st.markdown(f"**{item.get('citation')}**{page} · rerank {item.get('rerank_score', 0):.3f}")
                st.write(item.get("content"))
    st.subheader("SQL deposit audit")
    st.dataframe([{"Metric": k.replace("_", " ").title(), "Value": v}
                  for k, v in audit.items() if isinstance(v, (int, float))], hide_index=True, use_container_width=True)
    st.caption(audit.get("calculation_note", ""))
    if st.button("Draft formal notice"):
        try:
            package = draft_notice(st.session_state.get("audit_query", query), matched, audit)
            assessment = package["risk_assessment"]
            st.subheader("Dispute risk assessment")
            risk_col, level_col, refund_col = st.columns(3)
            risk_col.metric("Risk score", f"{assessment['risk_score_0_to_100']}/100")
            level_col.metric("Risk level", assessment["risk_level"].title())
            refund_col.metric("Refundable balance", f"₹{assessment['lawful_refundable_amount_inr']:,.2f}")
            mode = package.get("generation_mode", "unknown")
            st.caption(model_status_caption(mode, package.get("model_used")))
            if package.get("fallback_reason"):
                st.caption(f"Fallback detail: {package['fallback_reason']}")
            st.json(assessment)
            st.text_area("Draft notice", package["legal_notice"], height=400)
            st.download_button("Download notice", package["legal_notice"], file_name=f"{lease_id}-dispute-notice.txt", mime="text/plain")
            st.caption(package["disclaimer"])
        except Exception as exc:
            st.error(f"Notice drafting failed: {exc}")


tabs = st.tabs(["💬 Chat with Your Lease PDF", "⚖️ Full Deposit & Dispute Audit"])

with tabs[0]:
    st.subheader("Chat with Your Lease Agreement & Legal Advisor")
    st.caption("Ask about your uploaded agreement, deposit, repairs, or tenant rights. Each answer retrieves fresh case evidence.")
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if st.button("Clear Chat"):
        st.session_state["chat_history"] = []
        st.rerun()

    starter_questions = [
        ("Lock-in & Notice Period", "What does my lease say about the lock-in period and notice period?"),
        ("Deposit Refund Rules", "How much of my security deposit should be refundable, and what does the lease say?"),
        ("Maintenance & Repairs", "Who is responsible for maintenance and repair costs under my lease?"),
        ("Eviction Protection", "What does my lease and the retrieved legal material say about eviction protection?"),
    ]
    starter_cols = st.columns(4)
    starter_message = None
    for col, (label, text) in zip(starter_cols, starter_questions):
        if col.button(label, use_container_width=True):
            starter_message = text

    history = st.session_state["chat_history"]
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                st.caption(model_status_caption(message.get("generation_mode"), message.get("model_used")))
                evidence = message.get("evidence", {})
                with st.expander("Retrieved Lease & Statute Evidence"):
                    ev_left, ev_right = st.columns(2)
                    with ev_left:
                        st.markdown("**Lease clauses**")
                        for item in evidence.get("lease_citations", []):
                            page = f" · page {item['page_number']}" if item.get("page_number") is not None else ""
                            st.markdown(f"- **{item.get('citation')}**{page}: {item.get('content', '')}")
                    with ev_right:
                        st.markdown("**Statutory references**")
                        for item in evidence.get("statute_citations", []):
                            st.markdown(f"- **{item.get('citation')}**: {item.get('content', '')}")

    user_message = starter_message or st.chat_input("Ask any question about your rental agreement or tenant rights...")
    if user_message:
        history.append({"role": "user", "content": user_message})
        with st.chat_message("user"):
            st.markdown(user_message)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving lease, statute, and ledger evidence…"):
                try:
                    ensure_demo_seeded()
                    from agent.orchestrator import chat_with_lease
                    result = asyncio.run(chat_with_lease(tenant_id, lease_id, user_message, history[:-1]))
                    st.markdown(result["reply"])
                    st.caption(model_status_caption(result["generation_mode"], result.get("model_used")))
                    evidence = {"lease_citations": result["lease_citations"],
                                "statute_citations": result["statute_citations"]}
                    with st.expander("Retrieved Lease & Statute Evidence"):
                        ev_left, ev_right = st.columns(2)
                        with ev_left:
                            st.markdown("**Lease clauses**")
                            for item in evidence["lease_citations"]:
                                page = f" · page {item['page_number']}" if item.get("page_number") is not None else ""
                                st.markdown(f"- **{item.get('citation')}**{page}: {item.get('content', '')}")
                        with ev_right:
                            st.markdown("**Statutory references**")
                            for item in evidence["statute_citations"]:
                                st.markdown(f"- **{item.get('citation')}**: {item.get('content', '')}")
                    history.append({"role": "assistant", "content": result["reply"],
                                    "generation_mode": result["generation_mode"], "model_used": result.get("model_used"),
                                    "evidence": evidence,
                                    "ledger_audit": result.get("ledger_audit", {})})
                    st.session_state["chat_history"] = history
                except Exception as exc:
                    st.error(f"Chat request failed: {exc}")
                    history.pop()
                    st.session_state["chat_history"] = history

    if any(message["role"] == "assistant" for message in st.session_state["chat_history"]):
        if st.button("Generate Legal Notice from Chat"):
            try:
                chat = st.session_state["chat_history"]
                summary = "\n".join(f"{m['role'].title()}: {m['content']}" for m in chat)
                latest = next(m for m in reversed(chat) if m["role"] == "assistant")
                package = draft_notice(summary, latest["evidence"], latest.get("ledger_audit", {}),
                                       force_deterministic=latest.get("generation_mode") == "deterministic_fallback")
                st.session_state["chat_notice"] = package
            except Exception as exc:
                st.error(f"Notice drafting failed: {exc}")
    if "chat_notice" in st.session_state:
        package = st.session_state["chat_notice"]
        st.caption(model_status_caption(package.get("generation_mode"), package.get("model_used")))
        st.text_area("Legal notice draft", package["legal_notice"], height=350, key="chat_legal_notice")
        st.download_button("Download chat legal notice", package["legal_notice"],
                           file_name=f"{lease_id}-chat-dispute-notice.txt", mime="text/plain")

with tabs[1]:
    st.subheader("Full Deposit & Dispute Audit")
    query = st.text_area("Describe the dispute", "My landlord withheld my deposit for blanket repainting and an old geyser coil burnout.")
    render_audit(query)
