import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Filter,
  Sample,
  SearchResult,
  parseSearchQuery,
  searchSamples,
  updateSample,
  deleteSample,
} from '../api'
import TagPill from '../components/TagPill'
import SampleRow from '../components/SampleRow'

// ── Tag picker options ──────────────────────────────────────────────

interface TagOption {
  dimension: string
  values: string[]
}

const TAG_OPTIONS: TagOption[] = [
  { dimension: 'energy', values: ['low', 'mid', 'high'] },
  { dimension: 'texture', values: ['smooth', 'warm', 'gritty', 'clean', 'lo-fi', 'glitchy'] },
  { dimension: 'mood', values: ['dark', 'bright', 'tension', 'euphoric', 'melancholic', 'aggressive', 'calm'] },
  { dimension: 'range', values: ['sub', 'low', 'mid', 'mid-high', 'high', 'air'] },
  { dimension: 'transients', values: ['sharp', 'soft', 'none', 'clicky'] },
  { dimension: 'category', values: ['Drums', 'Bass', 'Synth', 'Keys', 'Guitar', 'Vocal', 'FX', 'Atmosphere'] },
]

// ── Module-level style constants (no re-creation per render) ────────

const STYLES = {
  searchBar: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border-active)',
    borderRadius: 8,
    padding: '10px 14px',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  } as React.CSSProperties,
  searchInput: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: 'var(--text-primary)',
    fontSize: 13,
  } as React.CSSProperties,
  filterLabel: {
    fontSize: 10,
    color: 'var(--text-dim)',
    marginRight: 2,
  } as React.CSSProperties,
  addTagBtn: {
    background: 'transparent',
    color: 'var(--text-dim)',
    padding: '3px 9px',
    borderRadius: 12,
    border: '1px dashed #2d2d50',
    cursor: 'pointer',
    fontSize: 10,
  } as React.CSSProperties,
  errorBanner: {
    margin: '0 20px 8px',
    padding: '8px 12px',
    background: 'rgba(248,113,113,0.1)',
    border: '1px solid var(--danger)',
    borderRadius: 6,
    color: 'var(--danger)',
    fontSize: 11,
  } as React.CSSProperties,
  centerMsg: {
    padding: '40px 20px',
    textAlign: 'center' as const,
    fontSize: 12,
  },
  resultsList: {
    padding: '0 20px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
    paddingBottom: 12,
  },
  tagPickerOption: {
    background: 'var(--border-color)',
    color: 'var(--text-secondary)',
    padding: '2px 6px',
    borderRadius: 8,
    fontSize: 9,
    cursor: 'pointer',
    border: '1px solid #2d2d50',
  } as React.CSSProperties,
} as const

// ── Component ───────────────────────────────────────────────────────

export default function Search() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<Filter[]>([])
  const [results, setResults] = useState<Sample[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [showTagPicker, setShowTagPicker] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const perPage = 50

  // ── ⌘K shortcut ───────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const doSearch = useCallback(
    (f: Filter[], p: number, q: string) => {
      if (!q && f.length === 0) {
        setResults([])
        setTotal(0)
        setError(null)
        return
      }
      setLoading(true)
      setError(null)
      searchSamples({ query: q || '*', filters: f, page: p, per_page: perPage })
        .then((res: SearchResult) => {
          setResults(res.results)
          setTotal(res.total)
        })
        .catch((err: Error) => {
          setError(err.message)
          setResults([])
          setTotal(0)
        })
        .finally(() => setLoading(false))
    },
    [],
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setPage(1)
      doSearch(filters, 1, query)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [filters, query, doSearch])

  const goToPage = (p: number) => {
    setPage(p)
    doSearch(filters, p, query)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const parsed = await parseSearchQuery(query.trim())
      setFilters(parsed)
      setPage(1)
      doSearch(parsed, 1, query.trim())
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const removeFilter = (idx: number) => {
    setFilters((prev) => prev.filter((_, i) => i !== idx))
  }

  const addFilter = (filter: Filter) => {
    setFilters((prev) => [...prev, filter])
    setShowTagPicker(false)
  }

  const handleUserTagAdd = async (sampleId: string, tag: string) => {
    const sample = results.find((s) => s.id === sampleId)
    if (!sample) return
    const newTags = [...sample.user_tags, tag]
    setResults((prev) =>
      prev.map((s) => (s.id === sampleId ? { ...s, user_tags: newTags } : s)),
    )
    await updateSample(sampleId, { user_tags: newTags })
  }

  const handleUserTagRemove = async (sampleId: string, tag: string) => {
    const sample = results.find((s) => s.id === sampleId)
    if (!sample) return
    const newTags = sample.user_tags.filter((t) => t !== tag)
    setResults((prev) =>
      prev.map((s) => (s.id === sampleId ? { ...s, user_tags: newTags } : s)),
    )
    await updateSample(sampleId, { user_tags: newTags })
  }

  const handleStarToggle = async (sampleId: string, stars: number) => {
    const sample = results.find((s) => s.id === sampleId)
    if (!sample) return
    // Clicking the same star again clears the rating
    const newRating = sample.rating === stars ? 0 : stars
    setResults((prev) =>
      prev.map((s) => (s.id === sampleId ? { ...s, rating: newRating } : s)),
    )
    await updateSample(sampleId, { rating: newRating })
  }

  const handleDelete = async (sampleId: string) => {
    if (!confirm(`Delete "${results.find((s) => s.id === sampleId)?.filename}"?`)) return
    setResults((prev) => prev.filter((s) => s.id !== sampleId))
    setTotal((t) => t - 1)
    await deleteSample(sampleId)
  }

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  const totalPages = Math.max(1, Math.ceil(total / perPage))
  const start = Math.min((page - 1) * perPage + 1, total)
  const end = Math.min(page * perPage, total)

  return (
    <div className="page">
      {/* ── Search bar ─────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} style={{ padding: '16px 20px 12px' }}>
        <label htmlFor="search-input" className="sr-only">
          Search samples
        </label>
        <div style={STYLES.searchBar}>
          <span style={{ color: 'var(--accent)', fontSize: 14 }} aria-hidden="true">
            🔍
          </span>
          <input
            id="search-input"
            ref={inputRef}
            type="text"
            placeholder="high tension, no transients, mid-high range..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={STYLES.searchInput}
          />
          <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>⌘K</span>
        </div>
      </form>

      {/* ── Active tag pills ───────────────────────────────────── */}
      {filters.length > 0 && (
        <div
          style={{ padding: '6px 20px 10px', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}
          role="list"
          aria-label="Active filters"
        >
          <span style={STYLES.filterLabel}>FILTERS</span>
          {filters.map((f, i) => (
            <TagPill key={`${f.dimension}-${f.value}-${i}`} filter={f} onRemove={() => removeFilter(i)} />
          ))}
          <button
            type="button"
            onClick={() => setShowTagPicker(!showTagPicker)}
            style={STYLES.addTagBtn}
            aria-expanded={showTagPicker}
          >
            + add tag
          </button>
          <span style={{ marginLeft: 'auto', color: 'var(--text-dim)', fontSize: 10 }}>
            {total} result{total !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* ── Tag picker popover ─────────────────────────────────── */}
      {showTagPicker && (
        <div
          role="dialog"
          aria-label="Add a filter tag"
          style={{
            margin: '0 20px 8px',
            padding: '8px 12px',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-active)',
            borderRadius: 8,
          }}
        >
          {TAG_OPTIONS.map((opt) => (
            <div key={opt.dimension} style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', marginRight: 6 }}>
                {opt.dimension}:
              </span>
              {opt.values.map((val) => (
                <button
                  key={val}
                  onClick={() => addFilter({ dimension: opt.dimension, value: val })}
                  style={STYLES.tagPickerOption}
                >
                  {val}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* ── Error ──────────────────────────────────────────────── */}
      {error && (
        <div style={STYLES.errorBanner} role="alert" aria-live="assertive">
          {error}
        </div>
      )}

      {/* ── Loading (skeleton) ─────────────────────────────────── */}
      {loading && (
        <div style={{ padding: '0 20px' }} aria-busy="true" aria-label="Loading results">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton-row" />
          ))}
        </div>
      )}

      {/* ── Empty ──────────────────────────────────────────────── */}
      {!loading && !error && results.length === 0 && (query || filters.length > 0) && (
        <div style={{ ...STYLES.centerMsg, color: 'var(--text-muted)' }}>
          No samples match your search.
        </div>
      )}
      {!loading && !error && results.length === 0 && !query && filters.length === 0 && (
        <div style={{ ...STYLES.centerMsg, color: 'var(--text-muted)' }}>
          Type a query or add tags to start searching.
        </div>
      )}

      {/* ── Results ────────────────────────────────────────────── */}
      {results.length > 0 && (
        <div style={STYLES.resultsList} aria-live="polite" aria-label="Search results">
          {results.map((sample) => (
            <SampleRow
              key={sample.id}
              sample={sample}
              expanded={expandedId === sample.id}
              onToggle={() => toggleExpand(sample.id)}
              onUserTagAdd={(tag) => handleUserTagAdd(sample.id, tag)}
              onUserTagRemove={(tag) => handleUserTagRemove(sample.id, tag)}
              onStarToggle={(n) => handleStarToggle(sample.id, n)}
              onDelete={() => handleDelete(sample.id)}
            />
          ))}
        </div>
      )}

      {/* ── Pagination ─────────────────────────────────────────── */}
      {total > perPage && (
        <nav
          aria-label="Pagination"
          style={{
            padding: '8px 20px 16px',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 12,
            color: 'var(--text-muted)',
            fontSize: 11,
          }}
        >
          <button
            disabled={page <= 1}
            onClick={() => goToPage(page - 1)}
            style={{
              background: 'transparent',
              border: '1px solid var(--border-color)',
              borderRadius: 4,
              color: page <= 1 ? 'var(--text-dim)' : 'var(--accent)',
              padding: '4px 10px',
              fontSize: 11,
              cursor: page <= 1 ? 'default' : 'pointer',
            }}
            aria-label="Previous page"
          >
            ← Prev
          </button>
          <span aria-current="page">
            Showing {start}–{end} of {total}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => goToPage(page + 1)}
            style={{
              background: 'transparent',
              border: '1px solid var(--border-color)',
              borderRadius: 4,
              color: page >= totalPages ? 'var(--text-dim)' : 'var(--accent)',
              padding: '4px 10px',
              fontSize: 11,
              cursor: page >= totalPages ? 'default' : 'pointer',
            }}
            aria-label="Next page"
          >
            Next →
          </button>
        </nav>
      )}
    </div>
  )
}
