import { useState } from 'react'
import { Sample } from '../api'
import { recordPlay } from '../api'
import TagPill from './TagPill'
import WaveformPlaceholder from './WaveformPlaceholder'

// ── Module-level styles ─────────────────────────────────────────────

const ICON_BTN = {
  width: 32,
  height: 32,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  background: 'none',
  border: 'none',
  color: 'var(--text-dim)',
  fontSize: 13,
  borderRadius: 6,
  padding: 0,
} as React.CSSProperties

const PLAY_BTN = (active: boolean): React.CSSProperties => ({
  width: 32,
  height: 32,
  borderRadius: '50%',
  background: active
    ? 'linear-gradient(135deg, var(--accent), #7c3aed)'
    : 'var(--border-color)',
  border: `1px solid ${active ? 'var(--border-active)' : '#2d2d50'}`,
  color: active ? 'white' : 'var(--text-secondary)',
  cursor: 'pointer',
  flexShrink: 0,
  fontSize: 11,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 0,
  margin: 0,
})

const TAG_MINI = {
  background: 'var(--border-color)',
  color: 'var(--text-secondary)',
  padding: '2px 6px',
  borderRadius: 8,
  fontSize: 10,
  whiteSpace: 'nowrap' as const,
}

// ── Types ───────────────────────────────────────────────────────────

interface SampleRowProps {
  sample: Sample
  expanded: boolean
  onToggle: () => void
  onUserTagAdd?: (tag: string) => void
  onUserTagRemove?: (tag: string) => void
  daysSincePlayed?: number | null
}

export default function SampleRow({
  sample,
  expanded,
  onToggle,
  onUserTagAdd,
  onUserTagRemove,
  daysSincePlayed,
}: SampleRowProps) {
  const [playing, setPlaying] = useState(false)

  const handlePlay = async () => {
    setPlaying(true)
    try {
      await recordPlay(sample.id)
    } catch {
      // fire-and-forget
    }
    setTimeout(() => setPlaying(false), 300)
  }

  const handleCopyPath = () => {
    navigator.clipboard.writeText(sample.path).catch(() => {})
  }

  const duration = formatDuration(sample.duration_seconds)
  const breadcrumb = [sample.pack_source, sample.instrument_type, sample.instrument_subtype]
    .filter(Boolean)
    .join(' · ')
  const topTags = sample.ai_tags.slice(0, 2)
  const neverPlayed = !sample.last_played_at && sample.play_count === 0

  return (
    <div
      style={{
        background: expanded ? 'var(--surface-2)' : 'var(--surface-1)',
        border: `1px solid ${expanded ? 'var(--border-active)' : 'var(--border-color)'}`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      {/* Main row */}
      <div
        style={{
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        {/* Play button */}
        <button
          onClick={handlePlay}
          style={PLAY_BTN(playing)}
          aria-label={playing ? 'Stop' : `Play ${sample.filename}`}
          title="Play"
        >
          {playing ? '■' : '▶'}
        </button>

        {/* Filename + breadcrumb */}
        <button
          onClick={onToggle}
          style={{
            flex: 1,
            minWidth: 0,
            textAlign: 'left',
            cursor: 'pointer',
            background: 'none',
            border: 'none',
            padding: 0,
          }}
          aria-expanded={expanded}
          aria-label={`${expanded ? 'Collapse' : 'Expand'} ${sample.filename}`}
        >
          <div
            style={{
              color: 'var(--text-primary)',
              fontWeight: 500,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {sample.filename}
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: 10, marginTop: 1 }}>
            {breadcrumb}
            {daysSincePlayed != null && daysSincePlayed > 30 && (
              <span style={{ color: 'var(--warning)', marginLeft: 6 }}>
                Last heard {daysSincePlayed} days ago
              </span>
            )}
            {daysSincePlayed == null && neverPlayed && (
              <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>Never played</span>
            )}
          </div>
        </button>

        {/* AI tags + duration */}
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          {topTags.map((tag) => (
            <span key={tag} style={TAG_MINI}>
              {tag}
            </span>
          ))}
          <span style={{ ...TAG_MINI, color: 'var(--text-muted)' }}>
            {duration}
          </span>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <button style={ICON_BTN} title="Drag to DAW" aria-label="Drag to DAW">
            ⇥
          </button>
          <button
            style={{ ...ICON_BTN, color: 'var(--accent)' }}
            onClick={handleCopyPath}
            title="Copy path"
            aria-label={`Copy path for ${sample.filename}`}
          >
            ⎘
          </button>
          <button
            style={{
              ...ICON_BTN,
              color: sample.rating > 0 ? 'var(--warning)' : 'var(--text-dim)',
            }}
            title={sample.rating > 0 ? 'Starred' : 'Star'}
            aria-label={sample.rating > 0 ? 'Remove star' : 'Add star'}
          >
            {sample.rating > 0 ? '★' : '☆'}
          </button>
        </div>
      </div>

      {/* Expanded detail panel */}
      {expanded && (
        <div
          style={{
            padding: '8px 12px',
            borderTop: '1px solid var(--border-color)',
            background: 'var(--surface-0)',
            display: 'flex',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ flex: '1 1 200px', minWidth: 200 }}>
            <WaveformPlaceholder />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 200, flexShrink: 0 }}>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Your tags
            </div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {sample.user_tags.map((tag) => (
                <TagPill
                  key={tag}
                  filter={{ dimension: '', value: tag }}
                  variant="user"
                  onRemove={onUserTagRemove ? () => onUserTagRemove(tag) : undefined}
                />
              ))}
              {onUserTagAdd && <InlineTagAdd onAdd={onUserTagAdd} />}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Inline tag add ──────────────────────────────────────────────────

function InlineTagAdd({ onAdd }: { onAdd: (tag: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (trimmed) {
      onAdd(trimmed)
      setValue('')
    }
    setEditing(false)
  }

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        style={{
          background: 'transparent',
          color: 'var(--text-dim)',
          padding: '2px 7px',
          borderRadius: 8,
          border: '1px dashed #2d2d50',
          fontSize: 10,
          cursor: 'pointer',
        }}
        aria-label="Add tag"
      >
        + tag
      </button>
    )
  }

  return (
    <input
      autoFocus
      id="inline-tag-input"
      aria-label="New tag name"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') submit()
        if (e.key === 'Escape') {
          setValue('')
          setEditing(false)
        }
      }}
      onBlur={submit}
      placeholder="tag name"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-active)',
        borderRadius: 8,
        padding: '2px 7px',
        color: 'var(--text-primary)',
        fontSize: 10,
        width: 80,
        outline: 'none',
      }}
    />
  )
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
