# LeaseLens Automated End-to-End Verification Report

- **Timestamp:** 2026-11-18 12:52:50 UTC
- **Gemini API key configured:** Yes
- **Sample PDF:** `sample_docs/sample_bengaluru_lease.pdf`

| Check | Component | Result | Details |
| :--- | :--- | :---: | :--- |
| 1 | PostgreSQL schema and indexes | **PASS** | 4 tables; 2 HNSW and 2 GIN indexes; demo corpus seeded |
| 2 | Tenant isolation | **PASS** | user_intruder received zero lease citations |
| 3 | Hybrid RRF and FlashRank | **PASS** | 2 lease + 2 statutory citations |
| 4 | Deterministic ledger | **PASS** | ₹1,00,000 deposit; 4.0x ratio; ₹34,500 unsupported; ₹2,500 documented; ₹97,500 refund |
| 5 | Sample PDF ingestion and 3-turn chat | **PASS** | 5 clauses; lock-in and painting clauses retrieved; exact ₹1,50,000 refund; mode=llm:gemini-3.5-flash-lite |
| 6 | Pydantic notice from chat summary | **PASS** | schema valid; ₹1,50,000 in notice; mode=llm:gemini-3.5-flash-lite |
| 7 | Temporary-data cleanup | **PASS** | only rows for the unique verification tenant and lease were deleted |
| 8 | 404/503 model fallback | **PASS** | chat and notice advanced in order to the third model |
| 9 | Streamlit two-tab workflow | **PASS** | chat, evidence drawer, chat notice download, audit, and audit notice download passed |
| 10 | Multi-MCP CLI workflow | **PASS** | notice schema path completed; mode=llm:gemini-3.5-flash-lite |
| 11 | RAG benchmark | **PASS** | Mode                         Context Precision   Citation Recall; Vector-only                     0.667             1.000; Hybrid RRF + FlashRank          0.625             0.938; Ground truth: 8 manually labeled queries; metrics are local to the seeded demo corpus. |

## Scope and limitations

Chat and notice generation use the configured Gemini chain when an API key is available; otherwise the suite validates deterministic retrieval-grounded fallback. A live model response verifies current API availability only for this run. The Model Tenancy Act and two-month deposit benchmark are illustrative reference data; local tenancy law varies by state.
