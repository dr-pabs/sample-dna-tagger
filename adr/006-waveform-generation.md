# ADR-006: Waveform Generation (Pillow)

## Status
Accepted

## Context
The frontend displayed a synthetic waveform derived from audio features (spectral centroid, RMS energy, ZCR). This was visually interesting but not representative of the actual audio. Producers need to see the real waveform to identify transient positions, loop points, and overall dynamics at a glance.

## Decision
Generate real waveform PNGs during the scan using `Pillow` + `librosa`. The PNG is cached in `~/.sample-dna-tagger/waveforms/{sample_id}.png` and served via `GET /api/samples/{id}/waveform`. The frontend attempts to fetch the real waveform and falls back to the synthetic one if it is not yet generated.

## Consequences

- **Positive**: Waveforms are visually accurate and useful for producers.
- **Positive**: One-time generation during scan; no runtime CPU cost.
- **Negative**: Adds ~5-50KB per sample in cache storage.
- **Trade-off**: `librosa.load()` is already called for feature extraction, so the audio is in memory; waveform generation piggy-backs on this with negligible extra cost.
