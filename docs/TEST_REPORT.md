# LeaseLens Automated End-to-End Verification Report

- **Timestamp:** 2026-11-18 13:46:06 UTC
- **Gemini API key configured:** No
- **Sample PDF:** `sample_docs/sample_bengaluru_lease.pdf`

| Check | Component | Result | Details |
| :--- | :--- | :---: | :--- |
| 1 | PostgreSQL schema and indexes | **PASS** | 5 tables including chat_messages; 2 HNSW and 2 GIN indexes; demo corpus seeded |
| 2 | Tenant isolation | **PASS** | user_intruder received zero lease citations |
| 3 | Hybrid RRF and FlashRank | **PASS** | 2 lease + 2 statutory citations |
| 4 | Chat evidence grounding | **PASS** | full chat reports missing Clause 5.2 and persists the source-grounded answer without substituting Clause 10.1 |
| 5 | Deterministic ledger | **PASS** | ₹1,00,000 deposit; 4.0x ratio; ₹34,500 unsupported; ₹2,500 documented; ₹97,500 refund |
| 6 | Sample PDF ingestion and 3-turn chat | **PASS** | 5 clauses; lock-in and painting clauses retrieved; exact ₹1,50,000 refund; mode=deterministic_fallback |
| 7 | Pydantic notice from chat summary | **PASS** | schema valid; ₹1,50,000 in notice; mode=deterministic_fallback |
| 8 | Temporary-data cleanup | **PASS** | only rows for the unique verification tenant and lease were deleted |
| 9 | 404/503 model fallback | **PASS** | chat and notice advanced in order to the third model |
| 10 | Persistent chat history | **PASS** | two-turn query rewrite, citations, reload, tenant isolation, clear, and cleanup passed |
| 11 | Streamlit two-tab workflow | **PASS** | custom PDF chat, evidence drawer, both notice downloads, audit, and persistent clear passed |
| 12 | Multi-MCP CLI workflow | **PASS** | notice schema path completed; mode=deterministic_fallback |
| 13 | RAG benchmark | **PASS** | Mode                         Context Precision   Citation Recall; Vector-only                     0.667             1.000; Hybrid RRF + FlashRank          0.625             0.938; Ground truth: 8 manually labeled queries; metrics are local to the seeded demo corpus. |

## Scope and limitations

Chat and notice generation use the configured Gemini chain when an API key is available; otherwise the suite validates deterministic retrieval-grounded fallback. A live model response verifies current API availability only for this run. The Model Tenancy Act and two-month deposit benchmark are illustrative reference data; local tenancy law varies by state.
