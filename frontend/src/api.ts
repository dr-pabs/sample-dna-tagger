const BASE = '/api'

// ── Types ───────────────────────────────────────────────────────────

export interface Sample {
  id: string
  path: string
  filename: string
  folder: string
  duration_seconds: number
  bpm: number | null
  key: string | null
  rms_energy: number
  spectral_centroid: number
  spectral_flatness: number
  zero_crossing_rate: number
  instrument_category: string
  instrument_type: string
  instrument_subtype: string
  pack_source: string
  ai_tags: string[]
  user_tags: string[]
  rating: number
  last_played_at: string | null
  play_count: number
}

export interface Filter {
  dimension: string
  value: string
}

export interface SearchParams {
  query: string
  filters?: Filter[]
  page?: number
  per_page?: number
}

export interface BrowseParams {
  category?: string
  type?: string
  pack?: string
  quick_filter?: string
  sub_filters?: Filter[]
  sort?: string
  page?: number
  per_page?: number
}

export interface CategoryTree {
  category: string
  count: number
  children: CategoryTree[]
}

export interface Pack {
  name: string
  count: number
}

export interface QuickFilterCounts {
  not_heard_recently: number
  unreviewed: number
  starred: number
}

export interface ScanStatus {
  state: 'idle' | 'scanning' | 'error'
  indexed: number
  tagged: number
  queued: number
  errors: number
}

export interface WatchFolder {
  id: string
  path: string
  last_scanned: string | null
  file_count: number
}

export interface SettingsResponse {
  watch_folders: WatchFolder[]
  scan_status: ScanStatus
  provider: string
  model: string
  base_url: string
  api_key: string
}

export interface SearchResult {
  results: Sample[]
  total: number
}

export interface BrowseResult {
  results: Sample[]
  total: number
}

// ── Helpers ─────────────────────────────────────────────────────────

/** Parse ai_tags and user_tags from JSON strings to arrays. */
function normalizeSample(s: any): Sample {
  return {
    ...s,
    ai_tags: typeof s.ai_tags === 'string' ? JSON.parse(s.ai_tags) : (s.ai_tags ?? []),
    user_tags: typeof s.user_tags === 'string' ? JSON.parse(s.user_tags) : (s.user_tags ?? []),
  }
}

function normalizeResult(res: any): SearchResult | BrowseResult {
  return {
    ...res,
    results: (res.results ?? []).map(normalizeSample),
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

async function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

// ── API functions ───────────────────────────────────────────────────

export async function searchSamples(params: SearchParams): Promise<SearchResult> {
  const qs = new URLSearchParams()
  qs.set('query', params.query)
  if (params.filters?.length) {
    qs.set('filters', JSON.stringify(params.filters))
  }
  if (params.page !== undefined) qs.set('page', String(params.page))
  if (params.per_page !== undefined) qs.set('per_page', String(params.per_page))
  return normalizeResult(await request<any>(`/search?${qs.toString()}`)) as SearchResult
}

export function parseSearchQuery(query: string): Promise<Filter[]> {
  return post<Filter[]>('/search/parse', { query })
}

export async function browseSamples(params: BrowseParams): Promise<BrowseResult> {
  const qs = new URLSearchParams()
  if (params.category) qs.set('category', params.category)
  if (params.type) qs.set('type', params.type)
  if (params.pack) qs.set('pack', params.pack)
  if (params.quick_filter) qs.set('quick_filter', params.quick_filter)
  if (params.sub_filters?.length) {
    qs.set('sub_filters', JSON.stringify(params.sub_filters))
  }
  if (params.sort) qs.set('sort', params.sort)
  if (params.page !== undefined) qs.set('page', String(params.page))
  if (params.per_page !== undefined) qs.set('per_page', String(params.per_page))
  return normalizeResult(await request<any>(`/browse?${qs.toString()}`)) as BrowseResult
}

export async function getCategories(): Promise<CategoryTree[]> {
  const raw: Record<string, Record<string, number>> = await request('/browse/categories')
  return Object.entries(raw).map(([category, types]) => ({
    category,
    count: Object.values(types).reduce((a, b) => a + b, 0),
    children: Object.entries(types).map(([name, cnt]) => ({
      category: name,
      count: cnt,
      children: [],
    })),
  }))
}

export async function getPacks(): Promise<Pack[]> {
  const raw: { pack_source: string; cnt: number }[] = await request('/browse/packs')
  return raw.map((p) => ({ name: p.pack_source, count: p.cnt }))
}

export function getQuickFilters(): Promise<QuickFilterCounts> {
  return request<QuickFilterCounts>('/browse/quick-filters')
}

export function getScanStatus(): Promise<ScanStatus> {
  return request<ScanStatus>('/scan/status')
}

export function getSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>('/settings')
}

export function updateSettings(settings: Record<string, string>): Promise<void> {
  return put<void>('/settings', settings)
}

export function testLLMConnection(): Promise<{ ok: boolean; error?: string }> {
  return post<{ ok: boolean; error?: string }>('/settings/test', {})
}

export function recordPlay(sampleId: string): Promise<void> {
  return post<void>(`/samples/${sampleId}/play`, {})
}

export function updateSample(sampleId: string, data: Partial<Sample>): Promise<void> {
  return patch<void>(`/samples/${sampleId}`, data)
}

export function startScan(): Promise<ScanStatus> {
  return post<ScanStatus>('/scan/start', {})
}

export async function addScanRoot(path: string): Promise<void> {
  const res = await fetch(`${BASE}/scan/roots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
}

export async function removeScanRoot(rootId: string): Promise<void> {
  const res = await fetch(`${BASE}/scan/roots/${rootId}`, { method: 'DELETE' })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
}

export async function rescanRoot(rootId: string): Promise<void> {
  const res = await fetch(`${BASE}/scan/roots/${rootId}/rescan`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
}

export async function deleteSample(sampleId: string): Promise<void> {
  const res = await fetch(`${BASE}/samples/${sampleId}`, { method: 'DELETE' })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
}
