export type Citation = {
  citation?: string
  page_number?: number | null
  content?: string
  rerank_score?: number | null
  rrf_score?: number | null
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  generation_mode?: string | null
  model_used?: string | null
  lease_citations?: Citation[]
  statute_citations?: Citation[]
  attachments?: { filename: string; mime_type: string }[]
  created_at?: string | null
  imageUrls?: string[]
}

export type ChatResponse = {
  reply: string
  lease_citations: Citation[]
  statute_citations: Citation[]
  generation_mode: string
  model_used?: string | null
  standalone_search_query?: string
  ledger_audit?: any
  attachments?: { filename: string; mime_type: string }[]
}

export type Lease = {
  tenant_id: string
  lease_id: string
  display_name: string
  clause_count: number
  latest_chat_at: string | null
  monthly_rent_inr: number | null
  security_deposit_paid_inr: number | null
}

export type UploadResponse = {
  tenant_id: string
  lease_id: string
  clause_count: number
  display_name?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try { detail = (await response.json()).detail || detail } catch { /* response wasn't JSON */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<any>('/api/health'),
  leases: () => request<Lease[]>('/api/leases'),
  history: (tenant: string, lease: string) => request<ChatMessage[]>(`/api/chat/${encodeURIComponent(tenant)}/${encodeURIComponent(lease)}`),
  clearHistory: (tenant: string, lease: string) => request<{ cleared: boolean }>(`/api/chat/${encodeURIComponent(tenant)}/${encodeURIComponent(lease)}`, { method: 'DELETE' }),
  chat: (tenant: string, lease: string, message: string, images: File[]) => {
    const body = new FormData()
    body.append('tenant_id', tenant)
    body.append('lease_id', lease)
    body.append('message', message)
    images.forEach((image) => body.append('images', image))
    return request<ChatResponse>('/api/chat', { method: 'POST', body })
  },
  upload: (file: File, tenantId: string, leaseId: string, rent: string, deposit: string, leaseName?: string) => {
    const body = new FormData()
    body.append('file', file)
    body.append('tenant_id', tenantId)
    body.append('lease_id', leaseId)
    body.append('monthly_rent_inr', rent)
    body.append('security_deposit_paid_inr', deposit)
    if (leaseName) body.append('lease_name', leaseName)
    return request<UploadResponse>('/api/leases/upload', { method: 'POST', body })
  },
  audit: (tenant: string, lease: string, query: string) => request<any>(`/api/audit/${encodeURIComponent(tenant)}/${encodeURIComponent(lease)}?query=${encodeURIComponent(query)}`),
  notice: (payload: any) => request<any>('/api/notice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  deleteLease: (tenant: string, lease: string) => request<{ deleted: boolean }>(`/api/leases/${encodeURIComponent(tenant)}/${encodeURIComponent(lease)}`, { method: 'DELETE' }),
}
