import { useState, useEffect } from 'react'

interface WaveformProps {
  sampleId: string
  spectralCentroid?: number | null
  rmsEnergy?: number | null
  zeroCrossingRate?: number | null
}

export default function WaveformPlaceholder({
  sampleId,
  spectralCentroid,
  rmsEnergy,
  zeroCrossingRate,
}: WaveformProps) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/samples/${sampleId}/waveform`)
      .then((res) => {
        if (!res.ok) throw new Error('No waveform')
        return res.blob()
      })
      .then((blob) => {
        if (cancelled) return
        setSrc(URL.createObjectURL(blob))
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      if (src) URL.revokeObjectURL(src)
    }
  }, [sampleId])

  if (src && !failed) {
    return (
      <div
        aria-hidden="true"
        style={{
          height: 36,
          background: 'var(--border-color)',
          borderRadius: 4,
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <img
          src={src}
          alt=""
          style={{ width: '100%', height: '100%', objectFit: 'fill', display: 'block' }}
        />
      </div>
    )
  }

  // Fallback: synthetic waveform from audio features
  return (
    <SyntheticWaveform
      spectralCentroid={spectralCentroid}
      rmsEnergy={rmsEnergy}
      zeroCrossingRate={zeroCrossingRate}
    />
  )
}

// ── Synthetic fallback (original logic) ─────────────────────────────

function SyntheticWaveform({
  spectralCentroid,
  rmsEnergy,
  zeroCrossingRate,
}: Omit<WaveformProps, 'sampleId'>) {
  const width = 400
  const height = 36
  const midY = height / 2

  const centroid = spectralCentroid ?? 1000
  const energy = rmsEnergy ?? 0.3
  const zcr = zeroCrossingRate ?? 0.1

  const hiFreqMul = 1 + (centroid / 2000) * 5
  const amplitude = 4 + energy * 16
  const jitter = zcr * 6

  const segments = 80
  let points = ''
  for (let i = 0; i <= segments; i++) {
    const x = (i / segments) * width
    const t = (i / segments) * Math.PI * 6
    const y =
      midY -
      Math.sin(t) * amplitude * 0.6 -
      Math.sin(t * hiFreqMul) * amplitude * 0.4 +
      (jitter > 0 ? Math.sin(i * 7.3 + zcr * 20) * jitter : 0)
    points += `${i === 0 ? '' : ' '}${x.toFixed(1)},${Math.max(2, Math.min(height - 2, y)).toFixed(1)}`
  }

  const playheadPct = Math.min(60, 20 + energy * 40)

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
          width: `${playheadPct}%`,
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
