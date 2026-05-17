# Changelog

## v0.1.0 — Initial Build (2026-05-17)

### Backend (`sample_dna_tagger/`)

**Database** (`db.py`)
- SQLite schema: 6 tables (`samples`, `scan_roots`, `scan_errors`, `scan_status`, `settings`, `fts_index`)
- FTS5 full-text search virtual table with insert/update/delete triggers
- Singleton connection pool with `asyncio.Lock` write serialisation
- CRUD: `insert_sample`, `update_sample`, `delete_sample`, `get_sample`, `record_play`
- Browse: `browse_samples`, `get_category_tree`, `get_pack_list`, `get_quick_filter_counts`
- Search: `search_samples`, `search_samples_paginated` with filter support
- Settings: `get_setting`, `set_setting`, `list_settings`
- Scan roots: `add_scan_root`, `remove_scan_root`, `update_scan_root`, `list_scan_roots`
- Scan errors: `log_scan_error`, `get_scan_errors`
- Scan status: `get_scan_status`, `update_scan_status`

**Scanner** (`scanner.py`)
- `ThreadPoolExecutor`-based background scanning
- `analyze_audio()` — librosa extraction: duration, BPM, RMS energy, spectral centroid, spectral flatness, zero-crossing rate
- `classify_instrument()` — heuristic classifier (Drums/Bass/FX/Atmosphere/Synth/Keys)
- Incremental scanning: skips files with unchanged mtime
- Pack detection from folder hierarchy
- LLM integration: sends features to OpenAI-compatible endpoint for semantic tagging
- Progress tracking via `scan_status` singleton row

**LLM Client** (`llm.py`)
- OpenAI-compatible async client with configurable base URL, API key, model
- `generate_tags()` — structured features → expressive semantic tags
- `generate_tags_batch()` — batch processing for cost reduction
- `parse_search_query()` — natural language → structured filter list
- `test_connection()` — ping endpoint to verify credentials
- Retry with exponential backoff (3 attempts, jitter)
- 30-second timeout per call
- Rate limiting via configurable `calls_per_minute` semaphore
- Few-shot examples in system prompt (kick, pad, hi-hat)
- JSON response parsing with markdown code fence stripping

**Server** (`server.py`)
- FastAPI app with CORS middleware (localhost on any port)
- SPA fallback: serves `index.html` for client-side routing
- Cache-control headers: `no-cache` on index.html
- 25 API routes across 5 route modules
- Health check endpoint

**Routes**
- `routes/search.py` — `POST /api/search/parse`, `GET /api/search` with filters, sort, pagination
- `routes/browse.py` — `GET /api/browse`, `/categories`, `/packs`, `/quick-filters`
- `routes/samples.py` — CRUD, play tracking, audio streaming (`GET /api/samples/{id}/audio`)
- `routes/scan.py` — status, start, roots CRUD, rescan
- `routes/settings.py` — get/update settings, test connection with auto-config load

**Packaging**
- `SampleDNA.spec` — PyInstaller spec with hidden imports, data files, macOS .app bundle
- `build-macos.sh` — macOS build script
- `build-windows.bat` — Windows build script
- `deploy.sh` — full CI pipeline (lint, test, build, release)
- `launch.py` — entry point: starts FastAPI on free port, opens pywebview

### Frontend (`frontend/`)

**Architecture**
- React 18 + TypeScript + Vite
- React Router v6 with lazy code splitting (6 chunks)
- CSS custom properties dark theme design system

**Components**
- `SampleRow.tsx` — reusable result row with play, expand, star, delete, copy path, drag-to-DAW
- `TagPill.tsx` — filter tag pill with remove button (indigo for AI, green for user)
- `WaveformPlaceholder.tsx` — dynamic SVG waveform from spectral features (centroid, energy, ZCR)
- `AudioManager.tsx` — global audio context: one sample plays at a time

**Pages**
- `Search.tsx` — natural language search with LLM-parsed tag pills, inline tag picker, skeleton loading, pagination, ⌘K shortcut
- `Browse.tsx` — left sidebar (quick filters, expandable category tree, pack list), breadcrumb, sort, results
- `Settings.tsx` — 3-tab layout (Library/AI Provider/About), watch folders, scan dashboard, provider config with Save & Test

**API Client** (`api.ts`)
- Typed interfaces for all data types
- Data normalization: `ai_tags`/`user_tags` string→array, categories object→tree, packs `pack_source`/`cnt`→`name`/`count`
- All 25 API endpoints wrapped

**Accessibility**
- Semantic `<button>` elements (no `<div onClick>`)
- `aria-label` on all interactive elements
- `aria-live` regions for dynamic content (results, errors)
- `aria-expanded` on expandable rows and categories
- `aria-pressed` on toggle buttons
- Global `:focus-visible` outline
- `prefers-reduced-motion` media query
- Error boundary with stack trace

### Tests (`tests/`)

- 97 passing, 0 failing, 2 xfailed
- `test_db.py` — schema, CRUD, browse, scan roots, scan errors, scan status, settings, edge cases
- `test_scanner.py` — audio extensions, instrument classification (6 edge cases), librosa mock
- `test_llm.py` — client config, JSON parsing, tag generation, query parsing, batch, retry, timeout, rate limit, error handling
- `test_routes.py` — all 25 API endpoints via `httpx.AsyncClient` + `ASGITransport`
- `conftest.py` — in-memory DB fixtures, auto-use env override, seeded DB

### Documentation

- `README.md` — project overview, quick start, architecture, API reference, project structure
- `ARCHITECTURE.md` — end-to-end system design with data flow diagrams, full schema, security model, v2 backlog
- `adr/001-004` — architecture decision records (hybrid AI, FastAPI+pywebview, search-first UI, SQLite+FTS5)

### Bug Fixes (Post-Build)

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Browse page crash — `d.map is not a function` | Backend returns `{category: {type: count}}` object, frontend expected array | `api.ts` transforms object to `CategoryTree[]` |
| Search page crash — `v.map is not a function` | `ai_tags` stored as JSON string, frontend expected array | `normalizeSample()` parses JSON strings to arrays |
| Pack list showing empty names | Backend returns `pack_source`/`cnt`, frontend expects `name`/`count` | `api.ts` maps field names |
| Star ratings not saving | `updateSample` sent `PUT`, backend route expects `PATCH` | Changed to `PATCH` method |
| Audio not playing | No `<audio>` element, play was visual-only | Added HTML5 `<audio>` with `GET /api/samples/{id}/audio` streaming endpoint |
| Multiple samples playing simultaneously | Each row had independent audio state | Global `AudioManager` context stops previous on new play |
| Waveform identical for all samples | Static SVG sine wave | Dynamic waveform from `spectral_centroid`, `rms_energy`, `zero_crossing_rate` |
| Direct URL navigation 404 | `StaticFiles` mount only serves exact file paths | SPA catch-all route returns `index.html` for any non-API path |
| Settings connection test always fails | LLM client singleton not loaded from DB | `test_connection` route auto-loads config from settings table |
| Settings key name mismatch | Frontend sends `base_url`, backend checks `llm_base_url` | Route accepts both naming conventions |
| FTS5 search returning no results | Content table `rowid` mismatch with `TEXT PRIMARY KEY` | FTS rebuild on seed; search falls back to browse queries |
| `gpt-4o-mini` deprecated | OpenAI model retired | Updated to `gpt-4.1-mini` |
| Kimi base URL incorrect | `.cn` TLD | Updated to `api.moonshot.ai/v1` |
| Settings UI confusing | Separate Save + Test buttons | Single "Save & Test Connection" button, provider status banner |
| Star rating only binary | Single star toggle on/off | 5-clickable-stars (☆☆☆☆☆ → ★★★★★) |
| Error handling opaque | Generic "Something went wrong" | ErrorBoundary shows error message + full stack trace |
| No delete functionality | Missing delete button and API call | 🗑 button with confirmation dialog, `DELETE /api/samples/{id}` |

### Known Issues

- **FTS5 triggers**: Content-sync triggers don't fire for `insert_sample()` due to `TEXT PRIMARY KEY` vs `rowid` mismatch. Browse works; text search requires explicit FTS rebuild.
- **Scanner coverage**: 30% in tests — `_scan_root` requires real audio files for integration testing.
- **Zombie server processes**: Background servers persist across restarts in sandboxed environment (not a production issue).
- **Seeded test data**: 11 synthetic samples with fake file paths and hardcoded tags — delete and re-scan real folders for accurate data.
