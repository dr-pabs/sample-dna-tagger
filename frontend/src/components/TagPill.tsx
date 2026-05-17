import { Filter } from '../api'

interface TagPillProps {
  filter: Filter
  variant?: 'ai' | 'user'
  onRemove?: () => void
}

export default function TagPill({ filter, variant = 'ai', onRemove }: TagPillProps) {
  const isUser = variant === 'user'
  const label = `${filter.dimension}: ${filter.value}`

  return (
    <span
      style={{
        background: isUser ? 'var(--tag-user-bg)' : 'var(--tag-bg)',
        color: isUser ? 'var(--tag-user-color)' : 'var(--text-secondary)',
        padding: '3px 9px',
        borderRadius: 12,
        border: `1px solid ${isUser ? 'var(--tag-user-border)' : 'var(--tag-border)'}`,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 10,
        lineHeight: '18px',
        whiteSpace: 'nowrap',
      }}
      role="listitem"
    >
      {label}
      {onRemove && (
        <button
          onClick={onRemove}
          style={{
            opacity: 0.6,
            cursor: 'pointer',
            fontSize: 10,
            background: 'none',
            border: 'none',
            color: 'inherit',
            padding: '0 2px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 18,
            height: 18,
          }}
          aria-label={`Remove filter ${label}`}
          title="Remove"
        >
          ✕
        </button>
      )}
    </span>
  )
}
