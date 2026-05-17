import { useState, useEffect, useMemo } from 'react'
import {
  CategoryTree,
  Pack,
  QuickFilterCounts,
  Sample,
  BrowseResult,
  browseSamples,
  getCategories,
  getPacks,
  getQuickFilters,
  updateSample,
} from '../api'
import SampleRow from '../components/SampleRow'

// ── Quick filter labels ─────────────────────────────────────────────

type QuickFilter = 'not_heard_recently' | 'unreviewed' | 'starred'

const QUICK_FILTER_LABELS: Record<QuickFilter, string> = {
  not_heard_recently: '🕓 Not heard recently',
  unreviewed: '📭 Unreviewed',
  starred: '★ Starred',
}

// ── Module-level styles ─────────────────────────────────────────────

const SIDEBAR_FILTER_BTN = {
  padding: '5px 8px',
  borderRadius: 6,
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  width: '100%',
  border: 'none',
  background: 'none',
  color: 'var(--text-muted)',
  fontSize: 11,
  textAlign: 'left' as const,
  fontFamily: 'inherit',
} as React.CSSProperties

const SIDEBAR_FILTER_ACTIVE = {
  ...SIDEBAR_FILTER_BTN,
  background: 'var(--tag-bg)',
  color: 'var(--text-secondary)',
} as React.CSSProperties

const TREE_ITEM = {
  ...SIDEBAR_FILTER_BTN,
  padding: '4px 8px',
} as React.CSSProperties

const TREE_CHILD = {
  ...TREE_ITEM,
  paddingLeft: 20,
} as React.CSSProperties

const TREE_CHILD_ACTIVE = {
  ...TREE_CHILD,
  background: '#1a1a3a',
  color: 'var(--text-secondary)',
} as React.CSSProperties

// ── Component ───────────────────────────────────────────────────────

export default function Browse() {
  const [categories, setCategories] = useState<CategoryTree[]>([])
  const [packs, setPacks] = useState<Pack[]>([])
  const [quickCounts, setQuickCounts] = useState<QuickFilterCounts | null>(null)
  const [sidebarLoading, setSidebarLoading] = useState(true)

  const [activeQuick, setActiveQuick] = useState<QuickFilter | null>(null)
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [activeType, setActiveType] = useState<string | null>(null)
  const [activePack, setActivePack] = useState<string | null>(null)
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)
  const [sort, setSort] = useState('last_played')

  const [results, setResults] = useState<Sample[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setSidebarLoading(true)
    Promise.all([getCategories(), getPacks(), getQuickFilters()])
      .then(([cats, pks, qc]) => {
        if (cancelled) return
        setCategories(cats)
        setPacks(pks)
        setQuickCounts(qc)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setSidebarLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const params = useMemo(() => {
    return {
      category: activeCategory ?? undefined,
      type: activeType ?? undefined,
      pack: activePack ?? undefined,
      quick_filter: activeQuick ?? undefined,
      sort,
      page: 1,
      per_page: 50,
    }
  }, [activeCategory, activeType, activePack, activeQuick, sort])

  useEffect(() => {
    if (sidebarLoading) return
    setLoading(true)
    setError(null)
    browseSamples(params)
      .then((res: BrowseResult) => {
        setResults(res.results)
        setTotal(res.total)
      })
      .catch((err: Error) => {
        setError(err.message)
        setResults([])
        setTotal(0)
      })
      .finally(() => setLoading(false))
  }, [params, sidebarLoading])

  const selectQuick = (qf: QuickFilter) => {
    setActiveQuick((prev) => (prev === qf ? null : qf))
    setActiveCategory(null)
    setActiveType(null)
    setActivePack(null)
  }

  const selectCategory = (cat: string) => {
    setActiveCategory((prev) => (prev === cat ? null : cat))
    setActiveType(null)
    setActiveQuick(null)
    setActivePack(null)
  }

  const toggleCategoryExpand = (cat: string) => {
    setExpandedCategory((prev) => (prev === cat ? null : cat))
  }

  const selectType = (cat: string, typ: string) => {
    setActiveCategory(cat)
    setActiveType(typ)
    setActiveQuick(null)
    setActivePack(null)
  }

  const selectPack = (pack: string) => {
    setActivePack((prev) => (prev === pack ? null : pack))
    setActiveCategory(null)
    setActiveType(null)
    setActiveQuick(null)
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

  const breadcrumbParts = [
    activeQuick ? QUICK_FILTER_LABELS[activeQuick] : null,
    activePack ? `📦 ${activePack}` : null,
    activeCategory ? `${catEmoji(activeCategory)} ${activeCategory}` : null,
    activeType ?? null,
  ].filter(Boolean) as string[]

  return (
    <div className="page">
      <div style={{ display: 'flex', height: '100%' }}>
        {/* ── Sidebar ─────────────────────────────────────────── */}
        <aside
          style={{
            width: 220,
            borderRight: '1px solid var(--border-color)',
            background: 'var(--surface-0)',
            overflowY: 'auto',
            flexShrink: 0,
          }}
          aria-label="Browse filters"
        >
          {/* Quick filters */}
          <nav aria-label="Quick filters" style={{ padding: '10px 12px', borderBottom: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
              Quick filters
            </h3>
            {(Object.keys(QUICK_FILTER_LABELS) as QuickFilter[]).map((qf) => (
              <button
                key={qf}
                onClick={() => selectQuick(qf)}
                style={activeQuick === qf ? SIDEBAR_FILTER_ACTIVE : SIDEBAR_FILTER_BTN}
                aria-pressed={activeQuick === qf}
              >
                <span>{QUICK_FILTER_LABELS[qf]}</span>
                <span style={{ opacity: 0.6 }}>{quickCounts?.[qf] ?? '—'}</span>
              </button>
            ))}
          </nav>

          {/* By category */}
          <nav aria-label="Categories" style={{ padding: '10px 12px', borderBottom: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
              By category
            </h3>
            {categories.map((cat) => (
              <div key={cat.category}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <button
                    onClick={() => toggleCategoryExpand(cat.category)}
                    aria-label={`${expandedCategory === cat.category ? 'Collapse' : 'Expand'} ${cat.category}`}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-dim)',
                      cursor: 'pointer',
                      padding: '2px 4px',
                      fontSize: 10,
                      width: 20,
                    }}
                  >
                    {expandedCategory === cat.category ? '▾' : '▸'}
                  </button>
                  <button
                    onClick={() => selectCategory(cat.category)}
                    style={
                      activeCategory === cat.category
                        ? { ...TREE_ITEM, width: 'auto', flex: 1, minWidth: 0 }
                        : { ...TREE_ITEM, width: 'auto', flex: 1, minWidth: 0 }
                    }
                    aria-pressed={activeCategory === cat.category}
                  >
                    <span>{catEmoji(cat.category)} {cat.category}</span>
                    <span style={{ opacity: 0.5 }}>{cat.count}</span>
                  </button>
                </div>
                {expandedCategory === cat.category &&
                  cat.children?.map((child) => (
                    <button
                      key={child.category}
                      onClick={() => selectType(cat.category, child.category)}
                      style={
                        activeType === child.category
                          ? TREE_CHILD_ACTIVE
                          : TREE_CHILD
                      }
                      aria-pressed={activeType === child.category}
                    >
                      <span>{child.category}</span>
                      <span style={{ opacity: 0.5 }}>{child.count}</span>
                    </button>
                  ))}
              </div>
            ))}
          </nav>

          {/* By pack */}
          <nav aria-label="Packs" style={{ padding: '10px 12px' }}>
            <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
              By pack
            </h3>
            {packs.map((p) => (
              <button
                key={p.name}
                onClick={() => selectPack(p.name)}
                style={activePack === p.name ? SIDEBAR_FILTER_ACTIVE : SIDEBAR_FILTER_BTN}
                aria-pressed={activePack === p.name}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
                  {p.name}
                </span>
                <span style={{ opacity: 0.5 }}>{p.count}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* ── Main content ─────────────────────────────────────── */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {/* Breadcrumb + sort */}
          <div
            style={{
              padding: '10px 16px 6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid var(--border-color)',
              background: 'var(--surface-1)',
              minHeight: 40,
            }}
          >
            <nav aria-label="Breadcrumb" style={{ fontSize: 11, display: 'flex', gap: 4 }}>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>All Samples</span>
              {breadcrumbParts.map((part, i) => (
                <span key={i} style={{ display: 'flex', gap: 4 }}>
                  <span style={{ color: 'var(--text-dim)' }}>›</span>
                  {i === breadcrumbParts.length - 1 ? (
                    <span style={{ color: 'var(--text-primary)' }}>{part}</span>
                  ) : (
                    <span style={{ color: 'var(--text-secondary)' }}>{part}</span>
                  )}
                </span>
              ))}
            </nav>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <label htmlFor="browse-sort" className="sr-only">Sort by</label>
              <select
                id="browse-sort"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                style={{
                  background: 'var(--surface-1)',
                  border: '1px solid #2d2d50',
                  borderRadius: 6,
                  padding: '5px 10px',
                  color: 'var(--text-primary)',
                  fontSize: 11,
                  outline: 'none',
                }}
              >
                <option value="last_played">Last played</option>
                <option value="date_added">Date added</option>
                <option value="filename">Filename</option>
              </select>
              {total > 0 && (
                <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>
                  {total} sample{total !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div
              role="alert"
              aria-live="assertive"
              style={{
                margin: '12px 16px 0',
                padding: '8px 12px',
                background: 'rgba(248,113,113,0.1)',
                border: '1px solid var(--danger)',
                borderRadius: 6,
                color: 'var(--danger)',
                fontSize: 11,
              }}
            >
              {error}
            </div>
          )}

          {/* Skeleton loading */}
          {loading && (
            <div style={{ padding: '12px 16px 0' }} aria-busy="true" aria-label="Loading results">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton-row" />
              ))}
            </div>
          )}

          {/* Empty */}
          {!loading && !error && results.length === 0 && (
            <div
              style={{
                padding: '40px 16px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: 12,
              }}
            >
              No samples found. Select a category, pack, or filter from the sidebar.
            </div>
          )}

          {/* Results */}
          {results.length > 0 && (
            <div
              aria-live="polite"
              aria-label="Browse results"
              style={{
                padding: '8px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                paddingBottom: 16,
              }}
            >
              {results.map((sample) => (
                <SampleRow
                  key={sample.id}
                  sample={sample}
                  expanded={expandedId === sample.id}
                  onToggle={() =>
                    setExpandedId((prev) => (prev === sample.id ? null : sample.id))}
                  onUserTagAdd={(tag) => handleUserTagAdd(sample.id, tag)}
                  onUserTagRemove={(tag) => handleUserTagRemove(sample.id, tag)}
                  daysSincePlayed={computeDaysSince(sample.last_played_at)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function catEmoji(cat: string): string {
  const map: Record<string, string> = {
    'Drums': '🥁', 'Synth': '🎹', 'Bass': '🎸', 'Keys': '🎹',
    'Guitar': '🎸', 'Vocal': '🎤', 'FX': '⚡', 'Atmosphere': '🌫️',
  }
  return map[cat] ?? '📁'
}

function computeDaysSince(dateStr: string | null): number | null {
  if (!dateStr) return null
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24))
}
