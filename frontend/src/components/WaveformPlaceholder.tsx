/**
 * Waveform placeholder that generates a unique visual from the audio features.
 *
 * Uses spectral centroid, rms_energy, and zero_crossing_rate to vary
 * amplitude, frequency, and noisiness of the composite wave.
 */
interface WaveformProps {
  /** Hz — higher = more high-frequency detail */
  spectralCentroid?: number | null
  /** 0-1 — higher = louder-looking waveform */
  rmsEnergy?: number | null
  /** 0-1 — higher = more erratic / transient-heavy */
  zeroCrossingRate?: number | null
}

export default function WaveformPlaceholder({
  spectralCentroid,
  rmsEnergy,
  zeroCrossingRate,
}: WaveformProps) {
  const width = 400
  const height = 36
  const midY = height / 2

  // Normalise features to wave parameters
  const centroid = spectralCentroid ?? 1000
  const energy = rmsEnergy ?? 0.3
  const zcr = zeroCrossingRate ?? 0.1

  // High centroid → more high-freq detail (more harmonics)
  const hiFreqMul = 1 + (centroid / 2000) * 5  // 1-6 range
  // High energy → taller amplitude
  const amplitude = 4 + energy * 16  // 4-20
  // High ZCR → more noise / jaggedness (adds random jitter)
  const jitter = zcr * 6  // 0-6

  const segments = 80
  let points = ''
  for (let i = 0; i <= segments; i++) {
    const x = (i / segments) * width
    const t = (i / segments) * Math.PI * 6
    // Composite: base sine + high-freq detail from centroid
    const y =
      midY -
      Math.sin(t) * amplitude * 0.6 -
      Math.sin(t * hiFreqMul) * amplitude * 0.4 +
      (jitter > 0 ? (Math.sin(i * 7.3 + zcr * 20) * jitter) : 0)
    points += `${i === 0 ? '' : ' '}${x.toFixed(1)},${Math.max(2, Math.min(height - 2, y)).toFixed(1)}`
  }

  // Playhead position: proportional to energy (just for visual variety)
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
