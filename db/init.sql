CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS statutory_clauses (
  id BIGSERIAL PRIMARY KEY,
  jurisdiction TEXT NOT NULL,
  act_name TEXT NOT NULL,
  section_number TEXT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(384),
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
);
CREATE INDEX IF NOT EXISTS statutory_embedding_hnsw ON statutory_clauses USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS statutory_tsv_gin ON statutory_clauses USING gin (tsv);

CREATE TABLE IF NOT EXISTS lease_clauses (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  lease_id TEXT NOT NULL,
  clause_number TEXT NOT NULL,
  page_number INTEGER,
  content TEXT NOT NULL,
  embedding vector(384),
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
);
CREATE INDEX IF NOT EXISTS lease_tenant_lease_idx ON lease_clauses (tenant_id, lease_id);
CREATE INDEX IF NOT EXISTS lease_embedding_hnsw ON lease_clauses USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS lease_tsv_gin ON lease_clauses USING gin (tsv);

CREATE TABLE IF NOT EXISTS lease_accounts (
  tenant_id TEXT NOT NULL,
  lease_id TEXT NOT NULL,
  monthly_rent_inr NUMERIC(12,2) NOT NULL CHECK (monthly_rent_inr >= 0),
  deposit_paid_inr NUMERIC(12,2) NOT NULL CHECK (deposit_paid_inr >= 0),
  PRIMARY KEY (tenant_id, lease_id)
);
CREATE TABLE IF NOT EXISTS ledger_transactions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  lease_id TEXT NOT NULL,
  transaction_type TEXT NOT NULL CHECK (transaction_type IN ('deposit_paid', 'deduction_claimed', 'refund_paid')),
  amount_inr NUMERIC(12,2) NOT NULL CHECK (amount_inr >= 0),
  description TEXT NOT NULL,
  receipt_reference TEXT,
  transaction_date DATE NOT NULL DEFAULT CURRENT_DATE
);
CREATE INDEX IF NOT EXISTS ledger_tenant_lease_idx ON ledger_transactions (tenant_id, lease_id);

INSERT INTO lease_accounts (tenant_id, lease_id, monthly_rent_inr, deposit_paid_inr)
VALUES ('user_rahul', 'lease_001', 25000, 100000)
ON CONFLICT (tenant_id, lease_id) DO NOTHING;
INSERT INTO ledger_transactions (tenant_id, lease_id, transaction_type, amount_inr, description, receipt_reference, transaction_date)
SELECT 'user_rahul', 'lease_001', x.kind, x.amount, x.description, x.receipt, DATE '2026-10-31'
FROM (VALUES
 ('deposit_paid', 100000::numeric, 'Security deposit received', 'RCPT-DEP-001'),
 ('deduction_claimed', 28000::numeric, 'Blanket repainting of entire flat', NULL),
 ('deduction_claimed', 6500::numeric, 'Aging geyser coil burnout attributed to tenant', NULL),
 ('deduction_claimed', 2500::numeric, 'Deep cleaning supported by itemised receipt', 'RCPT-CLEAN-014')
) AS x(kind, amount, description, receipt)
WHERE NOT EXISTS (SELECT 1 FROM ledger_transactions WHERE tenant_id='user_rahul' AND lease_id='lease_001' AND description=x.description);
