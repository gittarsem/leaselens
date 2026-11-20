import {
  CheckCircle2, Code2, Cpu, Database, ExternalLink, FileCode,
  Github, Globe, Layers, Lock, ShieldCheck, Terminal,
} from 'lucide-react'

export function DeveloperPage() {
  return (
    <div className="h-[calc(100vh-4rem)] overflow-y-auto text-[#EDEAE4] relative z-10">
      <main className="max-w-4xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-stone-800 bg-[#1E1D1B] text-stone-300 text-xs font-mono mb-4">
            <Code2 size={13} className="text-stone-400" /> Technical Architecture &amp; System Specs
          </div>
          <h1 className="text-3xl sm:text-4xl font-serif font-medium tracking-tight text-[#EDEAE4] mb-3">
            Developer Documentation
          </h1>
          <p className="text-sm sm:text-base text-stone-400 leading-relaxed max-w-2xl">
            A comprehensive breakdown of LeaseLens's backend stack, determinism guardrails,
            and MCP server protocols built specifically for Indian residential tenancy agreements.
          </p>
        </div>

        <div className="space-y-10">
          {/* Section 1: System Stack */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-6">
              <span className="w-7 h-7 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                01
              </span>
              <h2 className="text-lg font-medium text-[#EDEAE4]">
                Core Technology Stack
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1.5">
                  <Terminal size={15} className="text-stone-400" /> FastAPI Engine &amp; Pydantic
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Asynchronous REST API with rigorous Pydantic v2 validation schemas, streaming SSE endpoints,
                  and structured payload handling for PDF documents and images.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1.5">
                  <Database size={15} className="text-stone-400" /> PostgreSQL + pgvector
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Hybrid clause storage with 768-dim embeddings, HNSW index for sub-millisecond approximate nearest neighbors,
                  and BM25 sparse keyword indices.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1.5">
                  <Layers size={15} className="text-stone-400" /> FastMCP Microservices
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Decoupled Model Context Protocol servers: <code className="text-stone-300">lease-statute-rag</code> for hybrid cross-retrieval,
                  <code className="text-stone-300">rent-ledger</code> for deterministic SQL audits, and <code className="text-stone-300">notice-drafter</code>.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1.5">
                  <Cpu size={15} className="text-stone-400" /> Multi-Tier LLM Router
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Circuit breaker failover chain: Google Gemini (primary with 1M tokens) → Groq Cloud (ultra-fast 131k) →
                  OpenRouter Free Tier → Local Ollama fallback.
                </p>
              </div>
            </div>

            <div className="mt-4 p-3.5 rounded-xl bg-[#141312] border border-stone-800/80 flex items-center justify-between text-xs">
              <span className="text-stone-400">Frontend: React 18, TypeScript, Tailwind CSS, Lucide Icons, Vite</span>
              <span className="text-stone-500 font-mono text-[11px]">Node 20+</span>
            </div>
          </section>

          {/* Section 2: Determinism & Safety Guardrails */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-6">
              <span className="w-7 h-7 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                02
              </span>
              <h2 className="text-lg font-medium text-[#EDEAE4]">
                Determinism Guardrails &amp; Anti-Hallucination
              </h2>
            </div>

            <div className="space-y-3.5">
              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1">
                  <ShieldCheck size={15} className="text-stone-400" /> Deterministic SQL Deposit Ledger Math
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  LLMs are prohibited from computing deposit deductions or balances directly. All additions, documented deductions,
                  and withheld amounts are calculated via pure SQL arithmetic in PostgreSQL, preventing token hallucination on currency.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1">
                  <Lock size={15} className="text-stone-400" /> Evidence-Gap Abstention Protocol
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  If the retriever fails to locate an explicit lease clause or statutory provision corresponding to a query,
                  the agent explicitly abstains from guessing and reports the absence rather than extrapolating speculative advice.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1">
                  <FileCode size={15} className="text-stone-400" /> Multi-Image OCR &amp; Receipt Cross-Synthesis
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  Uploaded maintenance receipts, repair quotes, and handover inspection images are inspected using multimodal vision,
                  extracting line items and matching them directly against contract maintenance thresholds.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#141312] border border-stone-800/80">
                <div className="flex items-center gap-2 text-stone-200 text-xs font-medium mb-1">
                  <CheckCircle2 size={15} className="text-stone-400" /> Tenant &amp; Agreement Isolation
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">
                  All vector partitions, ledger transactions, and chat sessions are strictly gated by composite keys
                  (<code className="text-stone-300">tenant_id</code>, <code className="text-stone-300">lease_id</code>) at both the database and routing levels.
                </p>
              </div>
            </div>
          </section>

          {/* Section 3: Author & Links */}
          <section className="p-6 sm:p-8 rounded-2xl border border-stone-800 bg-[#191816]">
            <div className="flex items-center gap-3 mb-6">
              <span className="w-7 h-7 rounded-lg bg-[#242220] text-[#EDEAE4] border border-stone-700 flex items-center justify-center font-mono font-medium text-xs">
                03
              </span>
              <h2 className="text-lg font-medium text-[#EDEAE4]">
                Author &amp; Resources
              </h2>
            </div>

            <div className="p-5 rounded-xl bg-[#141312] border border-stone-800/80 mb-6">
              <div className="text-sm font-medium text-[#EDEAE4] mb-1">Tarsem</div>
              <div className="text-xs text-stone-400 mb-3">Indian Institute of Information Technology (IIIT) Una</div>
              <p className="text-xs text-stone-400 leading-relaxed">
                Designed and built LeaseLens as an end-to-end verifiable legal-financial assistant for Indian tenants,
                anchoring generative reasoning to statutory tenancy protections and deterministic SQL ledgers.
              </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <a
                href="https://github.com/gittarsem"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-stone-700 bg-[#1E1D1B] hover:bg-[#252422] text-xs font-medium text-[#EDEAE4] transition-colors"
              >
                <Github size={14} className="text-stone-300" />
                <span>github.com/gittarsem</span>
                <ExternalLink size={12} className="text-stone-400" />
              </a>

              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-stone-700 bg-[#1E1D1B] hover:bg-[#252422] text-xs font-medium text-[#EDEAE4] transition-colors"
              >
                <Globe size={14} className="text-stone-300" />
                <span>API Swagger Docs (/docs)</span>
                <ExternalLink size={12} className="text-stone-400" />
              </a>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
