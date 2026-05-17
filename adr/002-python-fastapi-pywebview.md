# ADR-002: Python FastAPI + React SPA + pywebview

**Date:** 2026-05-17  
**Status:** Accepted

## Context

The app targets Windows and macOS as a desktop application. Three desktop framework options were considered:

- **A — Electron + Python sidecar**: Electron renders React UI, Python runs as bundled sidecar. Proven pattern used by many audio tools, full OS integration. But heavy install (~200MB+ with Python), two runtimes to manage, slower startup.

- **B — Tauri + Python sidecar**: Rust/Tauri renders React UI in lightweight native webview. Python as sidecar. Tiny install (~10MB shell), fast startup. But requires Rust for core features, sidecar IPC adds complexity.

- **C — Python FastAPI + React + pywebview**: Python (FastAPI) serves React SPA locally. Single Python process — audio analysis, LLM calls, SQLite, UI server all in one. Packaged with PyInstaller.

## Decision

**Chose Option C — Python FastAPI + React SPA + pywebview + PyInstaller.**

## Rationale

1. **One language**: Python handles all backend logic (audio ML, API, database). No context-switching between Python and Rust/Node.
2. **Python-first ML ecosystem**: librosa and Essentia are Python-native. Wrapping them in a sidecar adds IPC overhead and serialization complexity.
3. **No IPC**: The React SPA communicates with FastAPI over localhost HTTP — zero IPC boilerplate. Same pattern works in dev (Vite proxy) and production (static files).
4. **Simple packaging**: PyInstaller bundles Python runtime + all deps + React dist into a single `.app` (macOS) or `.exe` (Windows).
5. **Familiar stack**: FastAPI is widely understood; React is the team's existing UI framework.

## Consequences

- Larger install footprint (Python runtime + deps ~150MB)
- pywebview requires macOS main-thread management (server runs in daemon thread)
- PyInstaller bundling can be fiddly (path resolution, binary dependencies)
- Native feel requires extra CSS (-webkit-app-region for drag regions)

## Implementation Notes

- `launch.py` starts uvicorn in a daemon thread, waits for health check, then opens pywebview
- In dev mode (`--dev`), pywebview opens the Vite dev server URL; API calls proxy through Vite config
- FastAPI serves `frontend/dist/` as static files via `StaticFiles` mount
- CORS configured for localhost on any port (pywebview may use random ports)
