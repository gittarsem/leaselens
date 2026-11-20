"""LeaseLens Streamlit dashboard with grounded lease chat and dispute audit."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4
from decimal import Decimal

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
from agent.orchestrator import clear_chat_history, load_chat_history

st.set_page_config(page_title="LeaseLens", page_icon="🏠", layout="wide")
st.title("🏠 LeaseLens")
st.caption("Rental agreement research, deposit audit, and dispute notice drafting")

with st.sidebar:
    st.subheader("Case")
    tenant_id = st.text_input("Tenant ID", "user_rahul", key="tenant_id")
    lease_id = st.text_input("Lease ID", "lease_001", key="lease_id")
    demo = st.toggle("Use Rahul demo case", value=True, key="demo_case")
    uploaded = st.file_uploader("Upload a rental agreement (PDF)", type=["pdf"], disabled=demo)
    rent = st.number_input("Monthly rent (INR)", min_value=1, value=30000, step=1000, disabled=demo)
    deposit = st.number_input("Deposit paid (INR)", min_value=0, value=150000, step=5000, disabled=demo)
    if uploaded and not demo and st.button("Ingest PDF"):
        os.makedirs("uploads", exist_ok=True)
        safe_filename = Path(uploaded.name).name or "agreement.pdf"
        path = os.path.join("uploads", f"{uuid4().hex}_{safe_filename}")
        with open(path, "wb") as f:
            f.write(uploaded.getvalue())
        from ingestion.ingest_data import ingest_lease_pdf
        ingest_lease_pdf(__import__("pathlib").Path(path), tenant_id, lease_id,
                         Decimal(str(rent)), Decimal(str(deposit)))
        st.session_state["active_pdf_lease"] = (tenant_id, lease_id, uploaded.name)
        st.session_state["active_chat_case"] = (demo, tenant_id, lease_id)
        st.session_state["chat_history"] = load_chat_history(tenant_id, lease_id)
        st.session_state.pop("chat_notice", None)
        st.success("PDF clauses and lease financial account indexed for this tenant and lease.")


active_case_key = (demo, tenant_id, lease_id)
if st.session_state.get("active_chat_case") != active_case_key:
    st.session_state["chat_history"] = load_chat_history(tenant_id, lease_id)
    st.session_state["active_chat_case"] = active_case_key
    st.session_state.pop("chat_notice", None)


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
    st.caption("Ask anything about your active lease, deposit, repairs, or tenant rights. Attach screenshots in the composer; answers retrieve fresh lease, statute, and ledger evidence.")
    if demo:
        st.info(f"Active lease: Rahul demo · {tenant_id} / {lease_id}")
    else:
        active_pdf = st.session_state.get("active_pdf_lease")
        pdf_name = active_pdf[2] if active_pdf and active_pdf[:2] == (tenant_id, lease_id) else f"PDF lease {lease_id}"
        st.info(f"Active PDF lease: {pdf_name} · tenant `{tenant_id}` · lease `{lease_id}`")
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = load_chat_history(tenant_id, lease_id)
    if st.button("Clear Chat"):
        clear_chat_history(tenant_id, lease_id)
        st.session_state["chat_history"] = []
        st.session_state.pop("chat_notice", None)
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
            if message["role"] == "user" and message.get("attachments"):
                names = ", ".join(item.get("filename", "image") for item in message["attachments"])
                st.caption(f"Attached image: {names} · Reattach it to ask a follow-up about its contents.")
            st.markdown(message["content"])
            if message["role"] == "assistant":
                st.caption(model_status_caption(message.get("generation_mode"), message.get("model_used")))
                evidence = message.get("evidence", {})
                if not evidence:
                    evidence = {"lease_citations": message.get("lease_citations", []),
                                "statute_citations": message.get("statute_citations", [])}
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

    chat_input = st.chat_input(
        "Ask anything about this lease or attach a screenshot…",
        accept_file="multiple", file_type=["png", "jpg", "jpeg", "webp"])
    user_message = starter_message
    uploaded_images = []
    if chat_input is not None and not starter_message:
        user_message = chat_input.text
        uploaded_images = list(chat_input.files)
        if not user_message.strip() and uploaded_images:
            user_message = "Please analyze the attached image in the context of my active lease."
    if user_message:
        if uploaded_images and len(uploaded_images) > 3:
            st.error("Please attach no more than 3 images.")
            st.stop()
        image_attachments = []
        for image_file in uploaded_images or []:
            image_bytes = image_file.getvalue()
            if len(image_bytes) > 10 * 1024 * 1024:
                st.error(f"{image_file.name} exceeds the 10 MB per-image limit.")
                st.stop()
            mime_type = image_file.type
            if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
                st.error(f"{image_file.name} is not a supported image type.")
                st.stop()
            image_attachments.append({"filename": image_file.name, "mime_type": mime_type, "data": image_bytes})
        with st.chat_message("user"):
            if image_attachments:
                st.caption("Attached image: " + ", ".join(item["filename"] for item in image_attachments))
                st.image([item.getvalue() for item in uploaded_images],
                         caption=[item["filename"] for item in image_attachments],
                         use_container_width=True)
            st.markdown(user_message)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving lease, statute, and ledger evidence…"):
                try:
                    ensure_demo_seeded()
                    from agent.orchestrator import chat_with_lease
                    result = asyncio.run(chat_with_lease(
                        tenant_id, lease_id, user_message, None, image_attachments))
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
                    st.session_state["chat_history"] = load_chat_history(tenant_id, lease_id)
                    # The submitted chat_input is rendered before the new
                    # messages in this run. Rerun from persisted history so
                    # the input is placed after the latest reply and remains
                    # reachable for the next follow-up.
                    st.rerun()
                except Exception as exc:
                    st.error(f"Chat request failed: {exc}")

    if any(message["role"] == "assistant" for message in st.session_state["chat_history"]):
        if st.button("Generate Legal Notice from Chat"):
            try:
                chat = st.session_state["chat_history"]
                summary = "\n".join(f"{m['role'].title()}: {m['content']}" for m in chat)
                latest = next(m for m in reversed(chat) if m["role"] == "assistant")
                latest_user_message = next(m["content"] for m in reversed(chat) if m["role"] == "user")
                _, chat_audit = call_tools(latest_user_message)
                evidence = {"lease_citations": latest.get("lease_citations", []),
                            "statute_citations": latest.get("statute_citations", [])}
                package = draft_notice(summary, evidence, chat_audit,
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
