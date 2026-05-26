# Architecture Decision Records

> This directory contains the Architecture Decision Records (ADRs) for Sample DNA Tagger. Each ADR documents a significant architectural decision, its context, and its consequences.

---

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](001-hybrid-ai-processing.md) | Hybrid AI processing (local analysis + cloud LLM) | Accepted |
| [ADR-002](002-python-fastapi-pywebview.md) | Python FastAPI + React SPA + pywebview | Accepted |
| [ADR-003](003-search-first-tag-pills.md) | Search-first UI with LLM-parsed tag pills | Accepted |
| [ADR-004](004-sqlite-fts5.md) | SQLite with FTS5 full-text search | Accepted |
| [ADR-005](005-file-system-watcher.md) | File-system watcher (watchdog) | Accepted |
| [ADR-006](006-waveform-generation.md) | Waveform generation (Pillow) | Accepted |
| [ADR-007](007-auto-updater.md) | Auto-updater (GitHub Releases API) | Accepted |

---

## Quick Reference

### Core Stack
- **ADR-001** + **ADR-002** define the foundational architecture: local audio analysis via `librosa`/`essentia`, cloud LLM tagging via OpenAI-compatible APIs, all wrapped in a Python FastAPI backend with a React frontend inside a `pywebview` desktop window.

### Search & Data
- **ADR-003** establishes natural-language search with LLM-parsed tag pills as the primary discovery mechanism.
- **ADR-004** commits to SQLite + FTS5 for zero-admin, full-text search without external dependencies.

### Real-Time Features (v0.2)
- **ADR-005** adds `watchdog`-based file-system monitoring for automatic sample detection and deletion.
- **ADR-006** adds real waveform PNG generation during scan using `Pillow` + `librosa`.
- **ADR-007** adds lightweight update notifications via the GitHub Releases API.

---

## Format

Each ADR follows this structure:

1. **Status** — Proposed / Accepted / Deprecated / Superseded
2. **Context** — What problem are we solving?
3. **Decision** — What did we decide?
4. **Consequences** — What are the trade-offs?

---

## Contributing

When adding a new ADR:
1. Use the next sequential number (`008-`, `009-`, etc.)
2. Update this `README.md` index
3. Link the new ADR from the main [`README.md`](../README.md) and [`ARCHITECTURE.md`](../ARCHITECTURE.md)
