# ADR-001: Hybrid AI Processing

**Date:** 2026-05-17  
**Status:** Accepted

## Context

The app needs to tag audio samples with expressive semantic descriptors (energy, texture, mood, emotional quality, instrument type) to power natural language search. Three architectures were considered:

- **A — Fully Local**: Run all analysis and tagging locally (Essentia, CLAP, ONNX models). No internet required, complete privacy, no API cost. But heavier install (~500MB models), slower initial scan, and less flexible tagging vocabulary.

- **B — Cloud AI**: Send audio files to an LLM API (OpenAI/Gemini) for direct audio analysis and rich semantic tagging. Richer language understanding but audio files leave the user's machine, API costs are high at scale, and internet is required.

- **C — Hybrid**: Local models handle signal analysis (BPM, key, spectral energy, transient density, frequency range). Only structured numbers are sent to an LLM for expressive semantic tagging. Audio stays local.

## Decision

**Chose Option C — Hybrid.**

Audio analysis (librosa + Essentia) extracts structured features locally. Those features — never raw audio — are sent to any OpenAI-compatible endpoint for expressive tag generation.

## Rationale

1. **Privacy**: Audio files never leave the machine. Only metadata moves.
2. **Rich tags**: The LLM sees structured features and produces expressive, musically-useful descriptors that local models can't match ("glacial", "anxious pulse", "cinematic tension").
3. **Tiny API cost**: Feature vectors are ~1KB per sample vs. megabytes for audio. Tagging 50,000 samples costs roughly $2-5 at current DeepSeek pricing.
4. **Flexible provider**: Any OpenAI-compatible endpoint works — DeepSeek, Kimi, OpenAI, or local Ollama. The user configures base URL, API key, and model.
5. **Partial offline**: Basic local analysis still works without internet; LLM tagging can be deferred.

## Consequences

- Requires API key for full tagging experience
- Local models (librosa, Essentia) add ~200MB to the install
- Two-stage pipeline (analyze → tag) adds complexity over a single cloud call
- User must trust their chosen LLM provider with metadata, not audio
