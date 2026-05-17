/**
 * Inline SVG waveform placeholder — decorative only.
 * A composite sine wave with a playhead highlight.
 */
export default function WaveformPlaceholder() {
  const width = 400
  const height = 36
  const midY = height / 2

  const segments = 80
  let points = ''
  for (let i = 0; i <= segments; i++) {
    const x = (i / segments) * width
    const t = (i / segments) * Math.PI * 4
    const y = midY - Math.sin(t) * 10 - Math.sin(t * 3.7) * 4
    points += `${i === 0 ? '' : ' '}${x.toFixed(1)},${y.toFixed(1)}`
  }

  return (
    <div
      aria-hidden="true"
      style={{
        height,
        background: 'var(--border-color)',
        borderRadius: 4,
        display: 'flex',
        alignItems: 'center',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: '35%',
          background: 'rgba(99,102,241,0.15)',
        }}
      />
      <svg
        width="100%"
        height={height - 8}
        style={{ position: 'relative', zIndex: 1 }}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <polyline
          points={points}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={1.5}
          opacity={0.7}
        />
      </svg>
    </div>
  )
}
