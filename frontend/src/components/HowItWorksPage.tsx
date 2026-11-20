import {
  ArrowRight, CheckCircle2, Cpu, Database, FileText,
  HelpCircle, Layers, MessageSquare, Scale, Search, ShieldCheck,
} from 'lucide-react'

interface HowItWorksPageProps {
  onLaunch: (prompt?: string) => void
  onOpenAudit: () => void
  onBackHome: () => void
}

export function HowItWorksPage({ onLaunch, onOpenAudit, onBackHome }: HowItWorksPageProps) {
  return (
    <div className="h-[calc(100vh-4rem)] overflow-y-auto text-[#EDEAE4] relative z-10">
      {/* Main Content Container */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        {/* Hero Header */}
        <div className="mb-14 text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-stone-800 bg-[#1E1D1B] text-stone-300 text-xs font-mono mb-4">
            <Cpu size={13} className="text-stone-400" /> Architecture &amp; Verification Pipeline
          </div>
          <h1 className="text-3xl sm:text-5xl font-serif font-medium tracking-tight text-[#EDEAE4] mb-4 leading-tight">
            How LeaseLens Works
          </h1>
          <p className="text-sm sm:text-base text-stone-400 leading-relaxed">
            A technical and legal deep dive into how LeaseLens combines hybrid clause retrieval,
            deterministic SQL ledger reconciliation, and statutory tenant protections to safeguard Indian renters.
          </p>
        </div>

        {/* 5-Phase Pipeline Overview */}
        <div className="space-y-10">
          {/* Phase 1 */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-4">
              <span className="w-8 h-8 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                01
              </span>
              <span className="text-xs font-mono text-stone-400 uppercase tracking-wider">
                Ingestion &amp; Clause Indexing
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-serif font-medium text-[#EDEAE4] mb-3">
              Deep PDF Extraction &amp; Clause Segmentation
            </h2>
            <p className="text-stone-300 text-sm leading-relaxed mb-5">
              Indian rental agreements often combine scanned stamped paper, bilingual text, irregular line breaks,
              and nested clauses (e.g. <em>Clause 8.1 vs. 8.2</em>). LeaseLens processes lease PDFs through our ingestion engine:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <FileText className="text-stone-400 mb-2" size={18} />
                <h4 className="text-xs font-medium text-[#EDEAE4] mb-1">Clause Number Detection</h4>
                <p className="text-[11px] text-stone-400 leading-normal">
                  Identifies contractual hierarchy (Clauses, Sub-clauses, Annexures) and preserves exact page coordinates.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <Database className="text-stone-400 mb-2" size={18} />
                <h4 className="text-xs font-medium text-[#EDEAE4] mb-1">PostgreSQL pgvector</h4>
                <p className="text-[11px] text-stone-400 leading-normal">
                  Generates dense semantic embeddings for every indexed excerpt, stored directly alongside lease metadata.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <ShieldCheck className="text-stone-400 mb-2" size={18} />
                <h4 className="text-xs font-medium text-[#EDEAE4] mb-1">Tenant Isolation</h4>
                <p className="text-[11px] text-stone-400 leading-normal">
                  Every clause is isolated by <code className="text-stone-300">tenant_id</code> and <code className="text-stone-300">lease_id</code> with zero data cross-leakage.
                </p>
              </div>
            </div>
          </section>

          {/* Phase 2 */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-4">
              <span className="w-8 h-8 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                02
              </span>
              <span className="text-xs font-mono text-stone-400 uppercase tracking-wider">
                Hybrid RRF &amp; FlashRank Re-Ranking
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-serif font-medium text-[#EDEAE4] mb-3">
              Multi-Stage Retrieval vs. Model Tenancy Act
            </h2>
            <p className="text-stone-300 text-sm leading-relaxed mb-5">
              Finding the right clause requires more than naive cosine similarity. LeaseLens uses a 3-stage retrieval pipeline:
            </p>
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl bg-[#141312] border border-stone-800/80 flex items-start gap-3">
                <Search className="text-stone-400 shrink-0 mt-0.5" size={16} />
                <div>
                  <h4 className="text-xs font-medium text-[#EDEAE4]">Dense Semantic Search + Sparse BM25 Keyword Search</h4>
                  <p className="text-xs text-stone-400 mt-0.5 leading-relaxed">
                    Dense vectors capture intent (e.g. <em>"can landlord charge for routine paint?"</em>) while sparse BM25 locks onto exact numbers like <em>"Clause 14"</em> or <em>"₹50,000"</em>.
                  </p>
                </div>
              </div>
              <div className="p-3.5 rounded-xl bg-[#141312] border border-stone-800/80 flex items-start gap-3">
                <Layers className="text-stone-400 shrink-0 mt-0.5" size={16} />
                <div>
                  <h4 className="text-xs font-medium text-[#EDEAE4]">Reciprocal Rank Fusion (RRF)</h4>
                  <p className="text-xs text-stone-400 mt-0.5 leading-relaxed">
                    Combines scores from vector cosine similarity and full-text search without arbitrary weight guessing.
                  </p>
                </div>
              </div>
              <div className="p-3.5 rounded-xl bg-[#141312] border border-stone-800/80 flex items-start gap-3">
                <Cpu className="text-stone-400 shrink-0 mt-0.5" size={16} />
                <div>
                  <h4 className="text-xs font-medium text-[#EDEAE4]">FlashRank Cross-Encoder Re-Ranking</h4>
                  <p className="text-xs text-stone-400 mt-0.5 leading-relaxed">
                    Ultra-fast local neural cross-encoder evaluates question-passage pairs together, eliminating false positives before prompting the LLM.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Phase 3 */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-4">
              <span className="w-8 h-8 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                03
              </span>
              <span className="text-xs font-mono text-stone-400 uppercase tracking-wider">
                Deterministic Financial Reconciliation
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-serif font-medium text-[#EDEAE4] mb-3">
              Never Trust LLMs with Financial Math
            </h2>
            <p className="text-stone-300 text-sm leading-relaxed mb-5">
              LLMs frequently hallucinate numbers, miscalculate dates, or invent deductions. LeaseLens delegates 100% of deposit calculations to deterministic SQL queries:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-2">
                  <CheckCircle2 size={16} className="text-stone-400" /> Documented Deductions
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Only claims backed by valid vendor invoices or receipts in the ledger are subtracted from the refundable balance.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-2">
                  <HelpCircle size={16} className="text-stone-400" /> Unverified Claims Flagged
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Deductions without receipts (such as routine painting or aging appliances) are categorized as potential statutory violations.
                </p>
              </div>
            </div>
            <div className="p-3.5 rounded-lg bg-[#141312] border border-stone-800/80 font-mono text-[11px] text-stone-400">
              <span className="text-stone-500">// Exact SQL calculation:</span><br />
              <span className="text-stone-200">lawful_refundable_balance</span> = deposit_paid - SUM(documented_deductions_with_receipts)
            </div>
          </section>

          {/* Phase 4 */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-4">
              <span className="w-8 h-8 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                04
              </span>
              <span className="text-xs font-mono text-stone-400 uppercase tracking-wider">
                Multi-Provider LLM Router with Auto-Switching
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-serif font-medium text-[#EDEAE4] mb-3">
              Token-Prioritized LLM Router (Zero Hallucination Chain)
            </h2>
            <p className="text-stone-300 text-sm leading-relaxed mb-5">
              When models hit token limits (429 rate limits or quota exhaustion), LeaseLens automatically fails over to the next highest-token provider while preserving the entire conversation history, retrieved lease clauses, and ledger audit:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs mb-5">
              <div className="p-3 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="font-medium text-[#EDEAE4] mb-1">1. Google Gemini</div>
                <div className="text-[11px] text-stone-400">1M token context, text + multi-image vision analysis</div>
              </div>
              <div className="p-3 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="font-medium text-[#EDEAE4] mb-1">2. Groq Cloud</div>
                <div className="text-[11px] text-stone-400">131K context window, ultra-fast non-restricted models</div>
              </div>
              <div className="p-3 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="font-medium text-[#EDEAE4] mb-1">3. OpenRouter Free</div>
                <div className="text-[11px] text-stone-400">64K–131K context, high-availability free endpoints</div>
              </div>
              <div className="p-3 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="font-medium text-[#EDEAE4] mb-1">4. Local Ollama</div>
                <div className="text-[11px] text-stone-400">Unlimited local tokens on macOS, never exhausts</div>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80 text-xs text-stone-300 leading-relaxed">
              <span className="text-stone-200 font-medium">Strict Grounding Check:</span> If an LLM response cites any clause or statutory section number not present in the retrieved evidence, LeaseLens catches it and replaces the answer with a grounded deterministic fallback.
            </div>
          </section>

          {/* Phase 5 */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-4">
              <span className="w-8 h-8 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                05
              </span>
              <span className="text-xs font-mono text-stone-400 uppercase tracking-wider">
                Formal Dispute Notices
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-serif font-medium text-[#EDEAE4] mb-3">
              Automated Legal Demand Notice Generation
            </h2>
            <p className="text-stone-300 text-sm leading-relaxed mb-5">
              LeaseLens generates formal legal demand notices ready to send to landlords under Indian tenancy laws, complete with statutory references and itemized deduction requests:
            </p>
            <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80 font-mono text-xs text-stone-300 leading-relaxed mb-4">
              &quot;WITHOUT PREJUDICE — FORMAL REQUEST FOR DEPOSIT REFUND AND ITEMIZED DEDUCTIONS...<br />
              Under the documented audit rule, ₹{'{lawful_refundable_amount}'} remains refundable within the statutory 14-day window.&quot;
            </div>
            <p className="text-xs text-stone-400">
              Cites Model Tenancy Act provisions and Section 74 of the Indian Contract Act (1872) regarding invalid penalty deductions without actual damage proof.
            </p>
          </section>
        </div>

        {/* Action Bar */}
        <div className="mt-16 p-8 rounded-2xl border border-stone-800 bg-[#191816] text-center">
          <h3 className="text-xl sm:text-2xl font-serif font-medium text-[#EDEAE4] mb-3">
            Ready to inspect your agreement?
          </h3>
          <p className="text-sm text-stone-400 max-w-lg mx-auto mb-6">
            Upload your lease agreement PDF or ask questions to audit your deposit rules in seconds.
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <button
              className="inline-flex items-center gap-2 bg-[#EDEAE4] hover:bg-white text-[#141312] font-medium px-6 py-2.5 rounded-full text-xs transition-all"
              onClick={() => onLaunch()}
            >
              <MessageSquare size={15} /> Open Lease Assistant <ArrowRight size={14} />
            </button>
            <button
              className="inline-flex items-center gap-2 border border-stone-700 bg-[#1E1D1B] hover:bg-[#252422] text-[#EDEAE4] font-medium px-6 py-2.5 rounded-full text-xs transition-all"
              onClick={onOpenAudit}
            >
              <Scale size={15} /> Run Deposit Audit <ArrowRight size={14} />
            </button>
          </div>
        </div>

        {/* Bottom Back Button */}
        <div className="mt-12 text-center">
          <button
            className="text-xs text-stone-500 hover:text-stone-300 transition-colors"
            onClick={onBackHome}
          >
            ← Return to Home
          </button>
        </div>
      </main>
    </div>
  )
}
