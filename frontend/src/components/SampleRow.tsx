import { useState, useRef, useEffect } from 'react'
import { Sample } from '../api'
import { recordPlay } from '../api'
import TagPill from './TagPill'
import WaveformPlaceholder from './WaveformPlaceholder'
import { useAudioManager } from './AudioManager'

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
  onStarToggle?: (rating: number) => void
  onDelete?: () => void
  daysSincePlayed?: number | null
}

export default function SampleRow({
  sample,
  expanded,
  onToggle,
  onUserTagAdd,
  onUserTagRemove,
  onStarToggle,
  onDelete,
  daysSincePlayed,
}: SampleRowProps) {
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const { play: registerPlay } = useAudioManager()

  const audioUrl = `/api/samples/${sample.id}/audio`

  const handlePlay = async () => {
    if (audioRef.current) {
      if (playing) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
        setPlaying(false)
        return
      }
      // Register with global audio manager — stops any other playing sample
      registerPlay(audioRef.current)
      setPlaying(true)
      try {
        await recordPlay(sample.id)
      } catch {
        // fire-and-forget
      }
      audioRef.current.play().catch(() => setPlaying(false))
    }
  }

  // Reset playing state when audio ends
  useEffect(() => {
    const el = audioRef.current
    if (!el) return
    const onEnded = () => setPlaying(false)
    const onError = () => setPlaying(false)
    el.addEventListener('ended', onEnded)
    el.addEventListener('error', onError)
    return () => {
      el.removeEventListener('ended', onEnded)
      el.removeEventListener('error', onError)
    }
  }, [sample.id])

  const [copied, setCopied] = useState(false)

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(sample.path)
    } catch {
      // Fallback for non-secure contexts (HTTP)
      const ta = document.createElement('textarea')
      ta.value = sample.path
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const duration = formatDuration(sample.duration_seconds)
  const breadcrumb = [sample.pack_source, sample.instrument_type, sample.instrument_subtype]
    .filter(Boolean)
    .join(' · ')
  const aiTags: string[] = Array.isArray(sample.ai_tags) ? sample.ai_tags : []
  const topTags = aiTags.slice(0, 2)
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
        <audio ref={audioRef} src={audioUrl} preload="none" />

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
          <button
            style={ICON_BTN}
            onClick={() => alert('Drag to DAW requires the desktop app (pywebview).\n\nUse Copy Path to copy the file location.')}
            title="Drag to DAW (desktop only)"
            aria-label="Drag to DAW (desktop only)"
          >
            ⇥
          </button>
          <button
            style={{ ...ICON_BTN, color: copied ? 'var(--success)' : 'var(--accent)' }}
            onClick={handleCopyPath}
            title={copied ? 'Copied!' : 'Copy path'}
            aria-label={`Copy path for ${sample.filename}`}
          >
            {copied ? '✓' : '⎘'}
          </button>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              style={{
                ...ICON_BTN,
                width: 20,
                height: 28,
                color: n <= sample.rating ? 'var(--warning)' : 'var(--text-dim)',
                fontSize: 11,
              }}
              onClick={() => onStarToggle?.(n)}
              title={`Rate ${n} star${n > 1 ? 's' : ''}`}
              aria-label={`Rate ${n} star${n > 1 ? 's' : ''}`}
            >
              {n <= sample.rating ? '★' : '☆'}
            </button>
          ))}
          {onDelete && (
            <button
              style={{ ...ICON_BTN, color: 'var(--danger)' }}
              onClick={onDelete}
              title="Delete sample"
              aria-label={`Delete ${sample.filename}`}
            >
              🗑
            </button>
          )}
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
            <WaveformPlaceholder
              sampleId={sample.id}
              spectralCentroid={sample.spectral_centroid}
              rmsEnergy={sample.rms_energy}
              zeroCrossingRate={sample.zero_crossing_rate}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 200, flexShrink: 0 }}>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Your tags
            </div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {(Array.isArray(sample.user_tags) ? sample.user_tags : []).map((tag) => (
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
