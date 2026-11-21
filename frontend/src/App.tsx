import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import {
  ArrowDownRight, ArrowRight, ArrowUp,
  Check, ChevronDown,CircleHelp,
  FileCheck2, FilePlus2, FileText, FileWarning, Home, ImagePlus, IndianRupee, KeyRound, LoaderCircle,
  MessageSquare, Paperclip, Plus, RefreshCw, Scale, Search, Send, ShieldCheck, Sparkles, Trash2, UploadCloud,
  X,
} from 'lucide-react'
import { api, ChatMessage, Lease } from './api'
import { LeaseBackground } from './components/LeaseBackground'
import { HowItWorksPage } from './components/HowItWorksPage'
import { DeveloperPage } from './components/DeveloperPage'
import {
  EmptyLeaseIllustration,
  LeaseLensLogo,
} from './components/LeaseIllustrations'

type Feature = 'chat' | 'audit'

const DEFAULT_QUERY = 'My landlord withheld my deposit for repainting and an old geyser coil. Are these valid deductions?'

function getContextualLoadingMessage(prompt: string, hasAttachments: boolean): string {
  const p = prompt.toLowerCase()
  if (hasAttachments) {
    if (/receipt|invoice|bill|photo|image|screenshot|proof/.test(p))
      return 'Inspecting attached receipts and cross-checking against lease evidence…'
    return 'Reviewing attached documents and matching against your lease…'
  }
  if (/lock.?in|notice period|vacate|termination|exit/.test(p))
    return 'Checking lock-in and notice rules in your agreement…'
  if (/repaint|painting|repair|maintenance|damage|wear|geyser|coil|fixture/.test(p))
    return 'Reviewing repainting and repair deduction rules…'
  if (/deposit|refund|deduct|withheld|security|return/.test(p))
    return 'Running deposit ledger audit and checking refund entitlement…'
  if (/rent|increase|hike|escalation|increment/.test(p))
    return 'Checking rent escalation clauses and statutory limits…'
  if (/evict|eviction|possession|vacating|leave/.test(p))
    return 'Reviewing eviction and possession rules in your agreement…'
  if (/clause|section|rule|term|condition/.test(p))
    return 'Looking up the relevant clause in your indexed lease…'
  if (/statute|law|act|tenancy|protection|right/.test(p))
    return 'Searching statutory tenant protections applicable to your lease…'
  if (/house rule|society|maintenance|society charge/.test(p))
    return 'Searching house rules and society maintenance terms…'
  if (/draft|notice|letter|demand|legal/.test(p))
    return 'Drafting your formal demand notice from lease evidence…'
  if (/hi|hello|hey|thanks|thank/.test(p.trim()))
    return 'Getting ready…'
  return 'Analyzing your lease wording and deposit ledger…'
}

const EXAMPLES = [
  { label: 'Deposit Audit', icon: IndianRupee, prompt: 'How much of my security deposit is refundable? Show the exact ledger calculation.' },
  { label: 'Lock-in & Notice', icon: KeyRound, prompt: 'What does my lease say about the lock-in period and notice period?' },
  { label: 'Repair Claims', icon: FileWarning, prompt: 'Can my landlord deduct repair costs for an aging geyser without receipts?' },
  { label: 'Draft Notice', icon: Send, prompt: 'Summarize the deposit dispute and draft a formal demand notice.' },
]

function formatINR(amount?: number | null) {
  return amount == null ? '—' : `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(amount)}`
}


export default function App() {
  const [page, setPage] = useState<'landing' | 'workspace' | 'how-it-works' | 'developer'>(() => {
    if (window.location.hash === '#workspace') return 'workspace'
    if (window.location.hash === '#how-it-works') return 'how-it-works'
    if (window.location.hash === '#developer') return 'developer'
    return 'landing'
  })
  const [feature, setFeature] = useState<Feature>('chat')
  const [leases, setLeases] = useState<Lease[]>([])
  const [active, setActive] = useState<Lease | null>(null)
  const [attachedPdf, setAttachedPdf] = useState<Lease | null>(null)
  const [attachPromptOpen, setAttachPromptOpen] = useState(false)
  const [pendingChatPrompt, setPendingChatPrompt] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [apiError, setApiError] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingContext, setLoadingContext] = useState<{ prompt: string; hasAttachments: boolean }>({ prompt: '', hasAttachments: false })
  const [prompt, setPrompt] = useState('')
  const [heroPrompt, setHeroPrompt] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [auditData, setAuditData] = useState<any>(null)
  const [auditQuery, setAuditQuery] = useState(DEFAULT_QUERY)
  const [notice, setNotice] = useState<any>(null)
  const [noticeLoading, setNoticeLoading] = useState(false)
  const [toast, setToast] = useState('')
  const [uploading, setUploading] = useState(false)
  const [leaseDropdownOpen, setLeaseDropdownOpen] = useState(false)
  const scrollEnd = useRef<HTMLDivElement>(null)
  const chatComposer = useRef<HTMLTextAreaElement>(null)
  const focusChatOnOpen = useRef(false)
  const imagePicker = useRef<HTMLInputElement>(null)
  const leaseDropdownRef = useRef<HTMLDivElement>(null)

  const refreshLeases = useCallback(async () => {
    try {
      const items = await api.leases()
      setLeases(items)
      return items
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not reach the API.')
      return []
    }
  }, [])

  const selectLease = useCallback(async (lease: Lease) => {
    setActive(lease)
    setMessages([])
    setAuditData(null)
    setNotice(null)
    setApiError('')
    try { setMessages(await api.history(lease.tenant_id, lease.lease_id)) }
    catch (error) { setApiError(error instanceof Error ? error.message : 'Could not load this chat.') }
  }, [])

  useEffect(() => {
    void refreshLeases().then((items) => {
      const custom = items[0]
      const demo = items.find((item) => item.tenant_id === 'user_rahul' && item.lease_id === 'lease_001') || items[0]
      if (custom) {
        setAttachedPdf(custom)
        void selectLease(custom)
      } else if (demo) {
        void selectLease(demo)
      } else {
        setActive({ tenant_id: 'user_rahul', lease_id: 'lease_001', display_name: 'Rahul Sharma — Lease #001', clause_count: 5, latest_chat_at: null, monthly_rent_inr: 25000, security_deposit_paid_inr: 100000 })
      }
    })
  }, [refreshLeases, selectLease])

  useEffect(() => {
    const handleHash = () => {
      if (window.location.hash === '#workspace') setPage('workspace')
      else if (window.location.hash === '#how-it-works') setPage('how-it-works')
      else if (window.location.hash === '#developer') setPage('developer')
      else if (window.location.hash === '#home' || !window.location.hash) setPage('landing')
    }
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])
  useEffect(() => { scrollEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, loading])
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'smooth' }) }, [page])
  useEffect(() => {
    if (page === 'workspace' && focusChatOnOpen.current) {
      focusChatOnOpen.current = false
      requestAnimationFrame(() => chatComposer.current?.focus())
    }
  }, [page])
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 3400)
    return () => window.clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (leaseDropdownRef.current && !leaseDropdownRef.current.contains(event.target as Node)) {
        setLeaseDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const launch = (question?: string) => {
    const candidateQuestion = question ?? (heroPrompt.trim() || undefined)
    if (!attachedPdf) {
      setPendingChatPrompt(candidateQuestion ?? null)
      setAttachPromptOpen(true)
      return
    }
    setPage('workspace')
    setFeature('chat')
    if (candidateQuestion) setTimeout(() => void sendMessage(candidateQuestion), 180)
  }

  const removeUploadedPdf = async (target: Lease | null = attachedPdf) => {
    if (!target) return
    try {
      await fetch(`/api/leases/${encodeURIComponent(target.tenant_id)}/${encodeURIComponent(target.lease_id)}`, {
        method: 'DELETE',
      }).catch(() => {})
      await api.clearHistory(target.tenant_id, target.lease_id).catch(() => {})
    } finally {
      const remaining = leases.filter((item) => !(item.tenant_id === target.tenant_id && item.lease_id === target.lease_id))
      setLeases(remaining)
      setAttachedPdf(null)
      setMessages([])
      setAuditData(null)
      setNotice(null)
      const nextLease = remaining[0] || null
      setAttachedPdf(nextLease)
      setActive(nextLease)
      if (nextLease) void selectLease(nextLease)
      setToast('Uploaded PDF removed.')
    }
  }

  const sendMessage = async (text: string, pickedFiles = files) => {
    const message = text.trim() || (pickedFiles.length ? 'Please analyze the attached image in the context of my active lease.' : '')
    if (!message || !active || loading) return
    if (pickedFiles.length > 3) { setToast('Attach up to three images per question.'); return }
    const allowed = ['image/png', 'image/jpeg', 'image/webp']
    const oversized = pickedFiles.find((file) => file.size > 10 * 1024 * 1024)
    if (oversized) { setToast(`${oversized.name} is larger than 10 MB.`); return }
    if (pickedFiles.some((file) => !allowed.includes(file.type))) { setToast('Use PNG, JPEG, or WebP images.'); return }
    const localImageUrls = pickedFiles.map((file) => URL.createObjectURL(file))
    const optimistic: ChatMessage = { role: 'user', content: message, imageUrls: localImageUrls, attachments: pickedFiles.map((file) => ({ filename: file.name, mime_type: file.type })) }
    setMessages((current) => [...current, optimistic])
    setPrompt('')
    setHeroPrompt('')
    setFiles([])
    setLoading(true)
    setLoadingContext({ prompt: message, hasAttachments: pickedFiles.length > 0 })
    setApiError('')
    try {
      const result = await api.chat(active.tenant_id, active.lease_id, message, pickedFiles)
      setMessages((current) => [...current, {
        role: 'assistant', content: result.reply, generation_mode: result.generation_mode,
        model_used: result.model_used, lease_citations: result.lease_citations,
        statute_citations: result.statute_citations,
      }])
      if (result.ledger_audit) setAuditData({ ledger_audit: result.ledger_audit })
      await refreshLeases()
    } catch (error) {
      setMessages((current) => current.filter((item) => item !== optimistic))
      setApiError(error instanceof Error ? error.message : 'Could not send this message.')
    } finally { setLoading(false) }
  }

  const submit = (event: FormEvent) => { event.preventDefault(); void sendMessage(prompt) }
  const addImages = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files || [])
    setFiles((current) => [...current, ...selected].slice(0, 3))
    event.target.value = ''
  }

  const loadAudit = async (query = auditQuery) => {
    if (!active) return
    setLoading(true)
    setApiError('')
    try { setAuditData(await api.audit(active.tenant_id, active.lease_id, query)) }
    catch (error) { setApiError(error instanceof Error ? error.message : 'Audit failed.') }
    finally { setLoading(false) }
  }

  const generateNotice = async () => {
    if (!active) return
    setNoticeLoading(true)
    setApiError('')
    try {
      let currentAudit = auditData
      if (!currentAudit?.ledger_audit) {
        currentAudit = await api.audit(active.tenant_id, active.lease_id, auditQuery)
        setAuditData(currentAudit)
      }
      const audit = currentAudit.ledger_audit
      const latestAssistant = [...messages].reverse().find((item) => item.role === 'assistant')
      const conflicts = currentAudit || { lease_citations: latestAssistant?.lease_citations || [], statute_citations: latestAssistant?.statute_citations || [] }
      const summary = messages.length ? messages.map((item) => `${item.role}: ${item.content}`).join('\n') : auditQuery
      setNotice(await api.notice({
        tenant_id: active.tenant_id, lease_id: active.lease_id,
        dispute_summary: summary, matched_conflicts: conflicts, ledger_audit: audit,
        force_deterministic: latestAssistant?.generation_mode === 'deterministic_fallback',
      }))
    } catch (error) { setApiError(error instanceof Error ? error.message : 'Could not draft notice.') }
    finally { setNoticeLoading(false) }
  }

  const clearCurrentChat = async () => {
    if (!active) return
    try {
      await api.clearHistory(active.tenant_id, active.lease_id)
      setMessages([]); setNotice(null); setToast('Conversation cleared for this lease.')
      await refreshLeases()
    } catch (error) { setApiError(error instanceof Error ? error.message : 'Could not clear chat.') }
  }

  useEffect(() => {
    document.documentElement.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
    return () => {
      document.documentElement.style.overflow = ''
      document.body.style.overflow = ''
    }
  }, [])

  return <main className={`relative z-[1] ${page === 'workspace' ? 'app-workspace-shell' : ''} h-screen overflow-hidden flex flex-col`}>
    <LeaseBackground />

    {/* Single Centered Sticky Navbar */}
    {page !== 'workspace' && (
      <header className="sticky top-0 z-50 bg-[#141312]/90 backdrop-blur-md border-b border-stone-800/80 shrink-0">
        <div className="max-w-6xl mx-auto px-6 h-16 grid grid-cols-3 items-center">
          {/* Left: LeaseLens logo */}
          <div className="flex items-center">
            <button
              className="inline-flex items-center gap-2.5 font-bold tracking-tight text-base hover:opacity-90 transition-opacity bg-transparent border-0 p-0 text-white cursor-pointer"
              onClick={() => { setPage('landing'); window.location.hash = '#home' }}
              aria-label="LeaseLens Home"
            >
              <LeaseLensLogo size={28} />
              <span className="font-serif font-medium text-[#EDEAE4]">LeaseLens</span>
            </button>
          </div>

          {/* Center: Pill nav with Home, How It Works, Developer */}
          <nav className="justify-self-center flex items-center gap-1 bg-[#191816] p-1 rounded-full border border-stone-800/80 text-xs">
            <button
              className={`px-3.5 py-1.5 rounded-full transition-colors cursor-pointer border-0 font-medium ${page === 'landing' ? 'bg-[#242220] text-[#EDEAE4]' : 'bg-transparent text-stone-400 hover:text-stone-200'}`}
              onClick={() => { setPage('landing'); window.location.hash = '#home' }}
            >
              Home
            </button>
            <button
              className={`px-3.5 py-1.5 rounded-full transition-colors cursor-pointer border-0 font-medium ${page === 'how-it-works' ? 'bg-[#242220] text-[#EDEAE4]' : 'bg-transparent text-stone-400 hover:text-stone-200'}`}
              onClick={() => { setPage('how-it-works'); window.location.hash = '#how-it-works' }}
            >
              How It Works
            </button>
            <button
              className={`px-3.5 py-1.5 rounded-full transition-colors cursor-pointer border-0 font-medium ${page === 'developer' ? 'bg-[#242220] text-[#EDEAE4]' : 'bg-transparent text-stone-400 hover:text-stone-200'}`}
              onClick={() => { setPage('developer'); window.location.hash = '#developer' }}
            >
              Developer
            </button>
          </nav>

          {/* Right: Deposit Audit button */}
          <div className="justify-self-end flex items-center">
            <button
              onClick={() => { setPage('workspace'); setFeature('audit'); void loadAudit() }}
              className="inline-flex items-center gap-2 bg-[#1E1D1B] hover:bg-[#262422] text-[#EDEAE4] border border-stone-700/80 hover:border-stone-500 rounded-full px-4 py-2 text-xs font-medium transition-colors cursor-pointer"
            >
              <Scale size={14} />
              <span>Deposit Audit</span>
            </button>
          </div>
        </div>
      </header>
    )}

    {page === 'how-it-works' ? (
      <HowItWorksPage
        onLaunch={() => launch()}
        onOpenAudit={() => { setPage('workspace'); setFeature('audit'); void loadAudit() }}
        onBackHome={() => { setPage('landing'); window.location.hash = '#home' }}
      />
    ) : page === 'developer' ? (
      <DeveloperPage />
    ) : page === 'landing' ? (
      <div className="h-[calc(100vh-4rem)] overflow-hidden flex flex-col items-center justify-center px-6 py-2 relative z-10 text-center">
        <div className="max-w-4xl mx-auto flex flex-col items-center w-full">
          <h1 className="text-4xl sm:text-6xl lg:text-[64px] font-serif text-[#EDEAE4] text-center max-w-4xl leading-[1.08]">
            Ask anything about<br /><span className="text-stone-400">your rental agreement</span>
          </h1>
          <p className="mt-4 text-base sm:text-lg text-stone-400 text-center max-w-2xl">
            Get answers grounded in your lease, with tenant rights evidence beside them.
          </p>

          {/* Quick-chat card */}
          <div className="mt-7 w-full max-w-3xl p-5 rounded-2xl bg-[#191816]/95 border border-stone-800/90 text-left shadow-2xl backdrop-blur-md">
            <form
              onSubmit={(event) => {
                event.preventDefault()
                launch(heroPrompt.trim() || undefined)
              }}
              className="flex flex-col gap-2"
            >
              <textarea
                value={heroPrompt}
                onChange={(event) => setHeroPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    launch(heroPrompt.trim() || undefined)
                  }
                }}
                placeholder="Ask about your security deposit, notice period, or deductions…"
                rows={3}
                className="w-full bg-transparent border-0 outline-none text-sm sm:text-base text-[#EDEAE4] placeholder-stone-500 resize-none leading-relaxed"
              />
              <div className="flex items-center justify-between pt-3 border-t border-stone-800/60">
                {attachedPdf ? (
                  <div className="inline-flex items-center gap-2 bg-[#141312] border border-stone-800 rounded-full px-3.5 py-1.5 text-xs text-stone-200">
                    <FileText size={12} className="text-stone-400" />
                    <span className="max-w-[200px] truncate">{attachedPdf.display_name}</span>
                    <button
                      type="button"
                      onClick={() => void removeUploadedPdf(attachedPdf)}
                      title="Delete uploaded PDF"
                      aria-label="Delete uploaded PDF"
                      className="text-stone-400 hover:text-red-400 transition-colors bg-transparent border-0 p-0 cursor-pointer flex items-center"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    title="Attach your rental agreement PDF"
                    onClick={() => setModalOpen(true)}
                    className="inline-flex items-center gap-2 text-xs text-stone-400 hover:text-[#EDEAE4] transition-colors bg-transparent border-0 cursor-pointer p-0"
                  >
                    <Paperclip size={13} />
                    <span>Attach lease PDF</span>
                  </button>
                )}

                <button
                  type="submit"
                  className="bg-[#EDEAE4] hover:bg-white text-[#141312] font-medium rounded-full px-5 py-2.5 text-sm inline-flex items-center gap-2 transition-all border-0 cursor-pointer shadow"
                >
                  <MessageSquare size={13} />
                  <span>Let&apos;s Chat</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </form>
          </div>

          {/* Starter prompt chips - compact 1 row on desktop */}
          <div className="mt-4 flex items-center justify-center gap-2.5 flex-wrap max-w-3xl">
            {EXAMPLES.map(({ label, icon: Icon, prompt: examplePrompt }) => (
              <button
                key={label}
                onClick={() => launch(examplePrompt)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-stone-800 bg-[#1E1D1B] hover:bg-[#262422] text-xs text-stone-300 transition-colors cursor-pointer"
              >
                <Icon size={12} className="text-stone-400" />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    ) : <>
      {/* Unified App Header — exactly ONE clean header bar */}
      <header className="app-header shrink-0" style={{ position: 'relative', zIndex: 20 }}>
        <div className="app-header-left">
          <button className="brand-lockup" onClick={() => { setPage('landing'); window.location.hash = '#home' }} aria-label="LeaseLens home">
            <LeaseLensLogo size={28} /><span>LeaseLens</span>
          </button>
        </div>

        {/* Center: two-pill feature switcher */}
        <div className="feature-switcher">
          <button
            className={`feature-pill inline-flex flex-row items-center gap-2 whitespace-nowrap px-4 py-2${feature === 'chat' ? ' active' : ''}`}
            onClick={() => setFeature('chat')}
          >
            <MessageSquare size={14} className="shrink-0" />
            <span>Lease Assistant</span>
          </button>
          <button
            className={`feature-pill inline-flex flex-row items-center gap-2 whitespace-nowrap px-4 py-2${feature === 'audit' ? ' active' : ''}`}
            onClick={() => { setFeature('audit'); void loadAudit() }}
          >
            <Scale size={14} className="shrink-0" />
            <span>Deposit &amp; Dispute Audit</span>
          </button>
        </div>

        {/* Right: + Upload Lease PDF and lease selector */}
        <div className="app-header-right">
          <button className="upload-btn whitespace-nowrap shrink-0" onClick={() => setModalOpen(true)}>
            <Plus size={14} /> Upload Lease PDF
          </button>

          <div className="lease-selector" ref={leaseDropdownRef}>
            <button
              className="lease-selector-btn"
              onClick={() => setLeaseDropdownOpen(!leaseDropdownOpen)}
              title={active?.display_name || 'Select lease'}
            >
              {active?.tenant_id === 'user_rahul' ? <Home size={14} /> : <FileText size={14} />}
              <span>{active?.display_name || 'Select lease'}</span>
              <ChevronDown size={13} className={leaseDropdownOpen ? 'rotate' : ''} />
            </button>
            {leaseDropdownOpen && (
              <div className="lease-dropdown">
                {leases.map((lease) => {
                  const isCustom = true
                  return (
                    <div
                      key={`${lease.tenant_id}/${lease.lease_id}`}
                      className={`lease-dropdown-item flex items-center justify-between gap-2${active?.tenant_id === lease.tenant_id && active?.lease_id === lease.lease_id ? ' selected' : ''}`}
                    >
                      <button
                        type="button"
                        className="flex items-center gap-2 flex-1 min-w-0 text-left bg-transparent border-0 p-0 text-inherit cursor-pointer"
                        onClick={() => { void selectLease(lease); setLeaseDropdownOpen(false) }}
                      >
                        {!isCustom ? <Home size={14} /> : <FileText size={14} />}
                        <span className="truncate">{lease.display_name}</span>
                        {active?.tenant_id === lease.tenant_id && active?.lease_id === lease.lease_id && <Check size={12} />}
                      </button>
                      {isCustom && (
                        <button
                          type="button"
                          title="Delete uploaded PDF"
                          aria-label="Delete uploaded PDF"
                          onClick={(event) => {
                            event.stopPropagation()
                            void removeUploadedPdf(lease)
                            setLeaseDropdownOpen(false)
                          }}
                          className="text-stone-400 hover:text-red-400 transition-colors bg-transparent border-0 p-1 cursor-pointer shrink-0"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  )
                })}
                {!leases.length && <p className="sidebar-empty" style={{ margin: '8px' }}>No leases indexed yet.</p>}
              </div>
            )}
          </div>
        </div>
      </header>

      <section className="workspace-wrap flex-1 min-h-0 overflow-hidden flex flex-col" id="workspace" style={{ position: 'relative', zIndex: 10 }}>
        <div className="workspace-shell-slim flex-1 min-h-0 overflow-hidden flex flex-col w-full">
          <div className="workspace-main flex-1 min-h-0 overflow-hidden flex flex-col w-full">
            {apiError && <div className="error-banner shrink-0"><CircleHelp size={16} /><span>{apiError.includes('language model') || apiError.includes('Could not reach') ? 'The AI assistant is temporarily unavailable. Please try again in a moment.' : apiError}</span><button onClick={() => setApiError('')}><X size={15} /></button></div>}

            {/* Feature 1: Lease Assistant (Chat & PDF Q&A) */}
            {feature === 'chat' && <div className="chat-stage w-full max-w-5xl mx-auto px-4 sm:px-8 flex-1 min-h-0 overflow-hidden flex flex-col">
              <div className="chat-toolbar shrink-0 w-full">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="chat-toolbar-label">Your Lease: <b style={{ color: '#e8e4e0' }}>{active?.display_name || 'Rahul Sharma — Lease #001'}</b></span>
                  <span className="active-tag"><span className="live-dot" />PDF Ready</span>
                  {active && (
                    <button
                      type="button"
                      onClick={() => void removeUploadedPdf(active)}
                      title="Delete uploaded PDF"
                      className="inline-flex items-center gap-1 text-[11px] text-stone-400 hover:text-red-400 transition-colors bg-transparent border-0 cursor-pointer px-1.5 py-0.5"
                    >
                      <Trash2 size={12} />
                      <span>Remove PDF</span>
                    </button>
                  )}
                </div>
                <button
                  className="audit-cta-btn"
                  onClick={() => { setFeature('audit'); void loadAudit() }}
                >
                  Run Full Deposit Audit →
                </button>
              </div>

              <div className="chat-scroll flex-1 overflow-y-auto px-4 sm:px-6 min-h-0">
                {!messages.length && <div className="empty-chat w-full max-w-2xl mx-auto">
                  <div className="welcome-hero">
                    <div className="welcome-glow" />
                    <div className="welcome-content">
                      <EmptyLeaseIllustration />
                      <h1>Understand every clause before you sign or move out</h1>
                      <p>Ask about your rent agreement, security deposit, lock-in period, or landlord repair claims.</p>
                    </div>
                  </div>
                  <div className="action-grid">{[
                    { icon: KeyRound, text: 'Lock-in & Notice Rules', prompt: EXAMPLES[1].prompt },
                    { icon: IndianRupee, text: 'Security Deposit Refund', prompt: EXAMPLES[0].prompt },
                    { icon: FileWarning, text: 'Painting & Repair Deductions', prompt: EXAMPLES[2].prompt },
                    { icon: FileCheck2, text: 'Draft Landlord Demand Notice', prompt: EXAMPLES[3].prompt },
                    { icon: UploadCloud, text: 'Upload & Index Lease PDF', prompt: '' },
                    { icon: Scale, text: 'Verify Statutory Protections', prompt: 'What statutory protections are relevant to my agreement? Cite the retrieved provisions.' },
                  ].map(({ icon: Icon, text, prompt: suggestion }) => <button key={text} className="action-card" onClick={() => suggestion ? void sendMessage(suggestion, []) : setModalOpen(true)}>
                    <Icon size={17} />
                    <span>{text}</span>
                    <ArrowUpRightIcon />
                    <Icon className="action-card-watermark" aria-hidden="true" />
                  </button>)}</div>
                </div>}
                {messages.map((message, index) => <MessageBubble key={`${message.created_at || index}-${index}`} message={message} />)}
                {loading && <div className="assistant-loading max-w-3xl mr-auto flex items-center gap-3">
                  <span className="assistant-avatar" style={{ background: 'rgba(52, 211, 153, 0.1)', borderColor: 'rgba(52, 211, 153, 0.25)', color: '#34d399' }}><Scale size={15} /></span>
                  <div className="loading-dots"><i /><i /><i /></div>
                  <span>{getContextualLoadingMessage(loadingContext.prompt, loadingContext.hasAttachments)}</span>
                </div>}
                <div ref={scrollEnd} />
              </div>

              <form className="chat-composer shrink-0 w-full" onSubmit={submit}>
                {files.length > 0 && <div className="attached-files">{files.map((file, index) => <AttachmentPreview file={file} key={`${file.name}-${index}`} remove={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))} />)}</div>}
                <textarea
                  ref={chatComposer}
                  className="min-h-[52px] max-h-36"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendMessage(prompt) } }}
                  placeholder="Ask anything about this rental agreement…"
                  rows={2}
                />
                <div className="composer-footer"><div className="composer-left"><input ref={imagePicker} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={addImages} /><button type="button" className="tool-button" title="Attach photos or invoices (up to 3)" onClick={() => imagePicker.current?.click()}><Paperclip size={17} /></button></div><button className="send-round" disabled={loading || (!prompt.trim() && !files.length)} aria-label="Send message"><ArrowUp size={18} /></button></div>
              </form>
              {messages.length > 0 && <div className="chat-controls mt-2 flex items-center justify-between text-xs shrink-0 w-full relative z-20">
                <button className="text-zinc-400 hover:text-zinc-100 transition-colors" onClick={() => void clearCurrentChat()}>Clear conversation</button>
                <button className="text-zinc-400 hover:text-zinc-100 transition-colors inline-flex items-center gap-1.5" onClick={() => { setFeature('audit'); void generateNotice() }}>Generate formal notice from chat <ArrowRight size={13} /></button>
              </div>}
            </div>}

            {/* Feature 2: Deposit & Dispute Audit (Dedicated Visual Audit Page) */}
            {feature === 'audit' && <AuditDashboard
              auditData={auditData}
              loading={loading}
              notice={notice}
              noticeLoading={noticeLoading}
              onRefresh={() => void loadAudit()}
              onNotice={() => void generateNotice()}
              auditQuery={auditQuery}
              setAuditQuery={setAuditQuery}
            />}
          </div>
        </div>
      </section>
    </>}

    {/* Dialogue Box when clicking Let's Chat without a PDF attached */}
    {attachPromptOpen && (
      <div
        className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
        onMouseDown={(event) => { if (event.target === event.currentTarget) setAttachPromptOpen(false) }}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="attach-pdf-dialog-title"
          className="bg-[#191816] border border-stone-800 rounded-2xl max-w-md w-full p-6 shadow-2xl text-left"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#242220] border border-stone-700/80 flex items-center justify-center text-[#EDEAE4]">
              <FileText size={18} />
            </div>
            <button
              type="button"
              onClick={() => setAttachPromptOpen(false)}
              className="text-stone-400 hover:text-[#EDEAE4] bg-transparent border-0 p-1 cursor-pointer"
              aria-label="Close dialog"
            >
              <X size={16} />
            </button>
          </div>
          <h2 id="attach-pdf-dialog-title" className="mt-4 text-lg font-serif text-[#EDEAE4]">
            Attach Lease PDF First
          </h2>
          <p className="mt-1.5 text-xs text-stone-400 leading-relaxed">
            Please upload your rental agreement PDF before starting the chat so LeaseLens can index your clauses and verify your deposit rules.
          </p>
          <div className="mt-5 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={() => { setAttachPromptOpen(false); setPendingChatPrompt(null) }}
              className="px-4 py-2 rounded-full text-xs text-stone-400 hover:text-[#EDEAE4] bg-transparent border border-stone-800 hover:border-stone-700 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => { setAttachPromptOpen(false); setModalOpen(true) }}
              className="bg-[#EDEAE4] hover:bg-white text-[#141312] font-medium rounded-full px-5 py-2 text-xs inline-flex items-center gap-1.5 transition-colors border-0 cursor-pointer"
            >
              <UploadCloud size={14} />
              <span>Attach PDF</span>
            </button>
          </div>
        </div>
      </div>
    )}

    {modalOpen && <UploadModal busy={uploading} onClose={() => { setModalOpen(false); setPendingChatPrompt(null) }} onUpload={async (file, leaseName, rent, deposit) => {
      setUploading(true)
      try {
        const result = await api.upload(file, '', '', rent, deposit, leaseName)
        await refreshLeases()
        const displayName = result.display_name || leaseName || file.name.replace(/\.pdf$/i, '') || result.lease_id
        const created = {
          tenant_id: result.tenant_id, lease_id: result.lease_id,
          display_name: displayName,
          clause_count: result.clause_count, latest_chat_at: null,
          monthly_rent_inr: Number(rent), security_deposit_paid_inr: Number(deposit)
        }
        setLeases((current) => [created, ...current.filter((item) => !(item.tenant_id === result.tenant_id && item.lease_id === result.lease_id))])
        setAttachedPdf(created)
        await selectLease(created)
        const queuedQuestion = pendingChatPrompt
        setPendingChatPrompt(null)
        setModalOpen(false); setPage('workspace'); setFeature('chat'); setToast(`${result.clause_count} clauses indexed. ${displayName} is now active.`)
        if (queuedQuestion) {
          setTimeout(() => void sendMessage(queuedQuestion, []), 180)
        }
      } catch (error) { setApiError(error instanceof Error ? error.message : 'PDF upload failed.') }
      finally { setUploading(false) }
    }} />}
    {toast && <div className="toast"><Check size={15} />{toast}</div>}
  </main>
}

function ArrowUpRightIcon() { return <ArrowDownRight size={14} className="arrow-northeast" /> }

function AttachmentPreview({ file, remove }: { file: File; remove: () => void }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])
  return <div className="file-chip preview-chip">{url ? <img src={url} alt="Attachment preview" /> : <ImagePlus size={13} />}<span>{file.name}</span><button type="button" onClick={remove} aria-label={`Remove ${file.name}`}><X size={12} /></button></div>
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const assistant = message.role === 'assistant'
  const imageUrls = message.imageUrls || []
  const attachmentNames = message.attachments?.map((item) => item.filename) || []

  return <article className={`message-row ${assistant ? 'assistant-row flex items-start gap-3 max-w-3xl' : 'user-row ml-auto max-w-2xl'}`}>
    {assistant && (
      <span
        className="assistant-avatar"
        style={{ background: 'rgba(52, 211, 153, 0.1)', borderColor: 'rgba(52, 211, 153, 0.25)', color: '#34d399' }}
      >
        <ShieldCheck size={15} />
      </span>
    )}
    <div className={`message-body ${assistant ? '' : 'user-message-body'}`}>
      {!assistant && <div className="message-author">You</div>}
      {attachmentNames.length > 0 && <div className="message-attachment-label"><ImagePlus size={13} />{attachmentNames.join(', ')}{!imageUrls.length && <small> · reattach to discuss the image again</small>}</div>}
      {imageUrls.length > 0 && <div className="message-images">{imageUrls.map((src) => <img key={src} src={src} alt="Uploaded lease evidence" />)}</div>}
      <div className="message-content">
        {assistant ? <Markdown>{message.content}</Markdown> : message.content}
      </div>
      
    </div>
  </article>
}

function Kpi({ icon: Icon, watermarkIcon: WatermarkIcon, label, value, highlight = false }: { icon: any; watermarkIcon?: any; label: string; value: string; highlight?: boolean }) {
  const BgIcon = WatermarkIcon || Icon
  return <div className={`kpi-card ${highlight ? 'highlight' : ''}`}>
    <BgIcon className="kpi-watermark" aria-hidden="true" />
    <div className="kpi-top"><span>{label}</span><Icon size={16} /></div>
    <strong>{value}</strong>
    <small>{highlight ? 'From deterministic SQL calculation' : 'Current lease account'}</small>
  </div>
}

function NoticeCard({ notice, onRegenerate, loading }: { notice: any; onRegenerate?: () => void; loading?: boolean }) {
  const [copied, setCopied] = useState(false)
  return <div className="notice-card">
    <div className="notice-card-stationery" aria-hidden="true" />
    <div className="panel-title">
      <div>
        <div className="eyebrow">FORMAL DEMAND NOTICE · DRAFT</div>
        <h3>Ready for your review</h3>
      </div>
      <span className="subtle-pill">Draft Document</span>
    </div>
    <pre>{notice.legal_notice}</pre>
    <div className="notice-actions">
      {onRegenerate && (
        <button className="pill-button light" onClick={onRegenerate} disabled={loading}>
          {loading ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />} Refresh Notice
        </button>
      )}
      <button className="outline-button" onClick={async () => {
        await navigator.clipboard.writeText(notice.legal_notice)
        setCopied(true)
        setTimeout(() => setCopied(false), 1800)
      }}>
        {copied ? <Check size={14} /> : <FileText size={14} />}
        {copied ? 'Copied' : 'Copy Text'}
      </button>
      <a
        className="outline-button"
        href={URL.createObjectURL(new Blob([notice.legal_notice], { type: 'text/plain' }))}
        download="leaselens-demand-notice.txt"
      >
        <ArrowDownRight size={14} /> Download Notice (.txt)
      </a>
    </div>
    <small className="legal-disclaimer">{notice.disclaimer}</small>
  </div>
}

function EmptyPanel({ text }: { text: string }) { return <div className="empty-panel"><Sparkles size={21} /><p>{text}</p></div> }

type AuditDashboardProps = {
  auditData: any
  loading: boolean
  notice: any
  noticeLoading: boolean
  onRefresh: () => void
  onNotice: () => void
  auditQuery: string
  setAuditQuery: (value: string) => void
}

function AuditDashboard({ auditData, loading, notice, noticeLoading, onRefresh, onNotice, auditQuery, setAuditQuery }: AuditDashboardProps) {
  const audit = auditData?.ledger_audit
  const risk = notice?.risk_assessment

  const rawPairs: [any, any][] = auditData?.conflict_pairs || []
  const pairs: [any, any][] = rawPairs.length > 0 ? rawPairs : (
    (auditData?.lease_citations || []).map((lc: any, i: number) => [lc, (auditData?.statute_citations || [])[i] || {}])
  )

  return <div className="audit-dashboard flex-1 overflow-y-auto min-h-0">
    <div className="audit-topbar">
      <div>
        <div className="eyebrow">DEPOSIT &amp; DISPUTE AUDIT</div>
        <h1>Deposit ledger &amp; legal protection audit.</h1>
        <p style={{ margin: '4px 0 0', color: '#8e8984', fontSize: '11px' }}>Deterministic SQL ledger reconciliation with Model Tenancy Act statutory benchmarks.</p>
      </div>
      <button className="outline-button" onClick={onRefresh} disabled={loading}>
        {loading ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={14} />} Refresh Audit
      </button>
    </div>

    <form className="query-bar" onSubmit={(event) => { event.preventDefault(); onRefresh() }}>
      <Search size={16} />
      <input value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} placeholder="Search dispute topic (e.g. repainting, geyser coil, notice deduction)..." />
      <button>Run audit <ArrowRight size={14} /></button>
    </form>

    {/* Section a: Refund Summary Cards */}
    <div className="audit-section">
      <h3 className="audit-section-title">1. Refund Summary</h3>
      <p className="audit-section-subtitle">Real-time deposit reconciliation calculated directly from your lease account ledger.</p>
      {!audit ? <EmptyPanel text="Run an audit above to load the deterministic deposit reconciliation for this lease." /> : <>
        <div className="kpi-grid">
          <Kpi icon={IndianRupee} watermarkIcon={Home} label="Security Deposit Paid" value={formatINR(audit.deposit_paid_inr)} />
          <Kpi icon={KeyRound} watermarkIcon={Scale} label="Excess Deposit Flag" value={`${audit.deposit_to_rent_ratio_months ?? '—'}× monthly rent`} />
          <Kpi icon={FileWarning} watermarkIcon={FileWarning} label="Disputed / Unreceipted Claims" value={formatINR(audit.unverified_deductions_without_receipts_inr)} />
          <Kpi icon={FileCheck2} watermarkIcon={ShieldCheck} label="Estimated Refundable Balance" value={formatINR(audit.lawful_refundable_balance_inr)} highlight />
        </div>

        {/* Itemized deductions table */}
        <div className="panel-card" style={{ marginTop: '14px' }}>
          <div className="panel-title">
            <div>
              <div className="eyebrow">LEDGER RECORDS</div>
              <h3>Itemized deductions &amp; charges</h3>
            </div>
            <span className="subtle-pill">SQL Ledger Audit</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Receipt / Proof</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(auditData?.itemized_deductions || []).map((item: any, index: number) => (
                  <tr key={`${item.description}-${index}`}>
                    <td><span className={`type-pill ${item.type === 'refund_paid' ? 'refund' : 'deduction'}`}>{item.type === 'refund_paid' ? 'Refund' : 'Claim'}</span></td>
                    <td>{item.description}</td>
                    <td>{item.receipt_reference || <span className="no-receipt">No receipt</span>}</td>
                    <td>{formatINR(item.amount_inr)}</td>
                  </tr>
                ))}
                {!(auditData?.itemized_deductions || []).length && (
                  <tr><td colSpan={4} className="empty-table">No itemized deductions on record.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="calculation-note">{audit.calculation_note}</p>
        </div>
      </>}
    </div>

    {/* Section b: Clause vs. Tenant Law Comparison */}
    <div className="audit-section">
      <h3 className="audit-section-title">2. Clause vs. Tenant Law Comparison</h3>
      <p className="audit-section-subtitle">Side-by-side assessment of disputed rental clauses against statutory tenant protections.</p>
      {!auditData ? <EmptyPanel text="Run an audit to compare disputed lease clauses against statutory tenant rights." /> :
        pairs.length ? (
          <div>
            {pairs.map(([leaseCit, statuteCit], idx) => {
              const textToCheck = `${leaseCit?.content || ''} ${leaseCit?.citation || ''}`.toLowerCase()
              const isUnenforceable = /paint|wear|tear|geyser|aging|deduct|without receipt|unreceipted/.test(textToCheck) || idx === 0
              return (
                <div key={idx} className="p-4 mb-4 rounded-xl border border-white/[0.08] bg-white/[0.02]">
                  {/* Header row: Clause label and badge */}
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div className="text-xs font-semibold text-zinc-300">
                      Clause {leaseCit?.citation || 'General Agreement'} vs. Statutory Rule
                    </div>
                    <span className={`shrink-0 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider ${isUnenforceable ? 'bg-red-500/15 text-red-300 border border-red-500/30' : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'}`}>
                      {isUnenforceable ? 'Unenforceable Claim' : 'Valid Deduction'}
                    </span>
                  </div>

                  {/* 2-column grid: What the lease says & What tenant law says */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.05] break-words whitespace-normal">
                      <div className="text-[10px] tracking-wider text-zinc-500 font-semibold mb-1 uppercase">What the Lease Says</div>
                      <h4 className="text-xs font-semibold text-zinc-200 mb-1.5 break-words">Clause {leaseCit?.citation || 'General Agreement'}</h4>
                      <p className="text-xs text-zinc-400 leading-relaxed break-words whitespace-normal">{leaseCit?.content || 'No specific clause wording on record.'}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.05] break-words whitespace-normal">
                      <div className="text-[10px] tracking-wider text-zinc-500 font-semibold mb-1 uppercase">What Tenant Law Says</div>
                      <h4 className="text-xs font-semibold text-zinc-200 mb-1.5 break-words">{statuteCit?.citation || 'Model Tenancy Act / Statutory Rule'}</h4>
                      <p className="text-xs text-zinc-400 leading-relaxed break-words whitespace-normal">{statuteCit?.content || 'Statutory protections require verifiable invoices for damages beyond ordinary wear and tear.'}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyPanel text="No disputed clauses returned for this query. Try adjusting your search query above." />
        )
      }
      <p className="scope-note"><CircleHelp size={14} />Model Tenancy Act provisions are illustrative; individual state tenancy enactments may vary.</p>
    </div>

    {/* Section c: Legal Demand Notice Generator */}
    <div className="audit-section">
      <h3 className="audit-section-title">3. Legal Demand Notice Generator</h3>
      <p className="audit-section-subtitle">Generate a formal, evidence-backed demand notice for security deposit return based on your audit.</p>

      <div className="panel-card risk-panel" style={{ marginBottom: '14px' }}>
        <div className="panel-title">
          <div><div className="eyebrow">DISPUTE RISK ASSESSMENT</div><h3>Case strength analysis</h3></div>
          <span className="risk-icon"><Scale size={17} /></span>
        </div>
        {risk ? (
          <div className="risk-result">
            <div className="risk-score"><span>{risk.risk_score_0_to_100}</span><small>/100 dispute strength</small></div>
            <span className={`risk-badge ${risk.risk_level}`}>{risk.risk_level} risk level</span>
            <p>{risk.summary}</p>
          </div>
        ) : (
          <p className="muted-copy">Click below to draft a formal demand notice backed by the retrieved contract clauses and statutory evidence.</p>
        )}
        <button
          className="pill-button light full"
          onClick={onNotice}
          disabled={loading || noticeLoading}
        >
          {(loading || noticeLoading) ? <LoaderCircle size={16} className="spin" /> : <FilePlus2 size={16} />}
          {notice?.legal_notice ? 'Regenerate Legal Notice' : 'Generate Legal Demand Notice'}
          <ArrowRight size={15} />
        </button>
      </div>

      {notice?.legal_notice && <NoticeCard notice={notice} onRegenerate={onNotice} loading={noticeLoading} />}
    </div>
  </div>
}

function UploadModal({ busy, onClose, onUpload }: { busy: boolean; onClose: () => void; onUpload: (file: File, leaseName: string, rent: string, deposit: string) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [leaseName, setLeaseName] = useState('')
  const [rent, setRent] = useState('30000')
  const [deposit, setDeposit] = useState('150000')
  const [drag, setDrag] = useState(false)
  const [localError, setLocalError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = (candidate?: File) => {
    if (!candidate) return
    if (candidate.type !== 'application/pdf' && !candidate.name.toLowerCase().endsWith('.pdf')) { setLocalError('Choose a PDF rental agreement.'); return }
    if (candidate.size > 30 * 1024 * 1024) { setLocalError('PDF must be under 30 MB.'); return }
    setLocalError(''); setFile(candidate)
    if (!leaseName) setLeaseName(candidate.name.replace(/\.pdf$/i, ''))
  }

  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose() }}>
    <section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title">
      <div className="modal-head">
        <div>
          <div className="eyebrow">YOUR LEASE</div>
          <h2 id="upload-title">Upload Rental Agreement</h2>
          <p>Index your lease PDF to start chatting and verify your deposit.</p>
        </div>
        <button className="icon-button" onClick={onClose} disabled={busy}><X size={17} /></button>
      </div>

      <div
        className={`drop-zone ${drag ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDragOver={(event) => { event.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(event) => { event.preventDefault(); setDrag(false); handleFile(event.dataTransfer.files[0]) }}
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} hidden type="file" accept="application/pdf,.pdf" onChange={(event) => handleFile(event.target.files?.[0])} />
        {file ? (
          <><FileText size={25} /><strong>{file.name}</strong><small>{(file.size / 1024 / 1024).toFixed(1)} MB · ready to index</small></>
        ) : (
          <><UploadCloud size={25} /><strong>Drop your rental agreement here</strong><small>or click to browse · PDF up to 30 MB</small></>
        )}
      </div>

      <div className="form-grid">
        <label>
          Friendly Lease Name
          <input
            value={leaseName}
            onChange={(event) => setLeaseName(event.target.value)}
            placeholder="e.g. Rahul Sharma — Flat 4B"
          />
        </label>
        <label>
          Monthly Rent (₹)
          <input
            type="number"
            min="1"
            value={rent}
            onChange={(event) => setRent(event.target.value)}
          />
        </label>
        <label style={{ gridColumn: 'span 2' }}>
          Security Deposit Paid (₹)
          <input
            type="number"
            min="0"
            value={deposit}
            onChange={(event) => setDeposit(event.target.value)}
          />
        </label>
      </div>

      {localError && <p className="field-error">{localError}</p>}
      <div className="modal-footer">
        <p>Text-based PDFs only. Scanned documents require OCR.</p>
        <button
          className="pill-button light"
          disabled={!file || busy}
          onClick={() => file && onUpload(file, leaseName.trim(), rent, deposit)}
        >
          {busy ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}
          {busy ? 'Indexing PDF…' : 'Index & Open Lease'}
          <ArrowRight size={14} />
        </button>
      </div>
    </section>
  </div>
}