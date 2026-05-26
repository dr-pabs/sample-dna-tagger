# Architecture — Sample DNA Tagger

> End-to-end system design for the Sample DNA Tagger desktop application.
> For individual design decisions, see `adr/`.

## System Overview

Sample DNA Tagger is a single-user desktop application for music producers. It scans sample libraries, extracts audio features locally, sends structured metadata to an AI endpoint for expressive semantic tagging, and provides natural-language search and category browsing.

**Platform**: Windows + macOS  
**Stack**: Python 3.11+ (FastAPI, librosa, OpenAI client) + React 18 (Vite, TypeScript) + SQLite (FTS5)  
**Packaging**: PyInstaller → `.app` (macOS) or `.exe` (Windows)  

```
                          ┌─────────────────────┐
                          │    pywebview window   │
                          │  (native OS chrome)   │
                          │                       │
                          │  ┌─────────────────┐  │
                          │  │   React SPA      │  │
                          │  │  localhost:PORT   │  │
                          │  └────────┬────────┘  │
                          └───────────┼───────────┘
                                      │ HTTP (localhost)
                          ┌───────────┼───────────┐
                          │  FastAPI   │           │
                          │            ▼           │
                          │  ┌──────────────────┐  │
                          │  │   REST API       │  │
                          │  │  /api/search     │  │
                          │  │  /api/browse     │  │
                          │  │  /api/samples    │  │
                          │  │  /api/scan       │  │
                          │  │  /api/settings   │  │
                          │  └───┬────┬────┬────┘  │
                          │      │    │    │       │
                          │  ┌───▼┐ ┌─▼─┐ ┌▼───┐  │
                          │  │ DB │ │LLM│ │Scan│  │
                          │  └────┘ └───┘ └────┘  │
                          └───────────────────────┘
                                     │
                              OpenAI-compatible API
                              (DeepSeek / OpenAI / Kimi / Ollama)
```

## Component Architecture

### 1. File-System Watcher (`watcher.py`)

**Purpose**: Monitor scan roots for file creation, modification, and deletion in real time.

**Thread model**: Runs in a background `watchdog.observers.Observer` thread. Bridges to asyncio via `asyncio.run_coroutine_threadsafe()`.

**Key behaviors**:
- **Create/modify** → debounced (2s) background rescan of the affected root
- **Delete file** → immediate `DELETE FROM samples WHERE path = ?`
- **Delete directory** → removes all samples under that path recursively
- **Add/remove root** → starts/stops the per-root `Observer` schedule dynamically

### 2. Scanner Engine (`scanner.py`)

**Purpose**: Walk watch folders, run local audio analysis, classify instruments, delegate to LLM for tagging, generate waveform PNGs.

**Thread model**: Runs in a background `ThreadPoolExecutor`. CPU-bound audio analysis (librosa) is offloaded to worker threads via `loop.run_in_executor()`. Database writes are serialised through a module-level `asyncio.Lock`.

**Scan flow**:
```
Add watch folder
      ↓
Scanner walks folder tree (os.walk)
      ↓
For each audio file:
  ├─ In DB and mtime unchanged? → skip
  ├─ New or modified?
  │     ↓
  │   analyze_audio() — librosa extraction
  │   ├─ duration_seconds, bpm
  │   ├─ rms_energy, spectral_centroid
  │   ├─ spectral_flatness, zero_crossing_rate
  │   └─ key (null — librosa unreliable)
  │     ↓
  │   classify_instrument() — heuristic
  │   ├─ Short + high ZCR → Drums
  │   ├─ Low centroid → Bass
  │   ├─ High flatness → FX / Atmosphere
  │   └─ Default → Synth / Keys
  │     ↓
  │   llm_client.generate_tags(features)
  │   ├─ energy, texture, mood
  │   ├─ emotional_quality, motion
  │   ├─ instrument_type, instrument_subtype
  │   └─ descriptive_tags[]
  │     ↓
  │   Write/update samples row
  │     ↓
  │   Update scan_status.processed_files
  └─ Error? → log to scan_errors, continue
      ↓
Update scan_roots.last_scanned_at + file_count
      ↓
Mark scan_status as idle
```

**Incremental scanning**: Only processes files whose `mtime` differs from the stored value. New files get UUIDs; existing files preserve their ID to maintain user tags and ratings.

**Pack detection**: The top-level folder under the scan root containing the file is used as `pack_source`.

### 3. LLM Layer (`llm.py`)

**Purpose**: Send structured audio features to an OpenAI-compatible endpoint and return expressive semantic tags. Also parses natural-language search queries into structured filters.

**Design**: The LLM never sees raw audio. It receives only the feature vector extracted by the scanner — typically ~1KB of JSON per sample.

**Key capabilities**:
- `generate_tags(features)` — Single-sample tag generation with few-shot examples
- `generate_tags_batch(features[])` — Batch processing to reduce API costs
- `parse_search_query(query)` — Natural language → structured filters for search
- `test_connection()` — Verify API key and endpoint
- `load_config()` / `configure()` — Read/write settings to SQLite

**Resilience**:
- Exponential backoff with jitter (up to 3 retries)
- 30-second timeout per call
- Rate limiting via configurable `calls_per_minute` semaphore
- Graceful degradation: returns features without tags on persistent failure

**System prompts**: Two distinct prompts — one for tag generation (with few-shot examples for Kick, Pad, Hi-hat), one for search query parsing. Both enforce JSON-only responses with no markdown.

### 4. Database Layer (`db.py`)

**Schema**: 6 tables

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `samples` | Core audio sample data | id, path (UNIQUE), filename, folder, 6 audio features, instrument_category/type/subtype, pack_source, ai_tags (JSON), user_tags (JSON), rating, last_played_at, play_count, file_mtime |
| `scan_roots` | Watch folders | id, path (UNIQUE), last_scanned_at, file_count |
| `scan_errors` | Per-file error log | id, sample_path, error_type, error_message |
| `scan_status` | Scan progress (singleton) | id=1, state, total_files, processed_files, current_file |
| `settings` | Key/value config | key (PK), value |
| `fts_index` | FTS5 virtual table | sample_id, filename, ai_tags, user_tags |

**FTS5**: Virtual content table over `samples` with `porter unicode61` tokenizer. Kept in sync via INSERT/UPDATE/DELETE triggers on the samples table. Text queries search across filename + AI tags + user tags simultaneously.

**Connection management**: Singleton connection with `asyncio.Lock` for write serialisation. WAL mode enabled for concurrent reads during writes. Database path configurable via `SAMPLE_DNA_DB` env var.

**CRUD operations**:
- `insert_sample`, `update_sample`, `delete_sample`, `get_sample`
- `search_samples(query, filters, limit, offset)` — FTS5 + filter combos
- `get_category_tree()`, `get_pack_list()`, `get_quick_filter_counts()`
- `browse_samples(category, type, pack, quick_filter, sort, limit, offset)`
- Plus full CRUD for scan_roots, scan_errors, scan_status, settings

### 5. REST API (6 route modules)

| Module | Routes | Description |
|--------|--------|-------------|
| `search.py` | POST `/parse`, GET `/` | LLM query parsing + filtered search |
| `samples.py` | GET/PATCH/DELETE `/{id}`, POST `/{id}/play`, GET `/{id}/waveform` | Sample CRUD + play tracking + waveform PNG |
| `browse.py` | GET `/categories`, `/packs`, `/quick-filters`, `/` | Browse tree + filtered listing |
| `scan.py` | GET `/status`, POST `/start`, GET/POST/DELETE `/roots`, POST `/roots/{id}/rescan` | Scan control |
| `settings.py` | GET `/`, PUT `/`, POST `/test` | Configuration + LLM test |
| `version.py` | GET `/` | App version for update checks |

All handlers are `async def`. Request/response bodies use Pydantic models. Database access goes through the `db` module's connection pooling.

**Server startup** (`server.py`):
1. `startup` event → `init_db()` (idempotent schema creation)
2. Health check on `/api/health`
3. API routes mounted under `/api`
4. React SPA mounted as static files at `/` (production) or proxied via Vite (dev)

### 6. React Frontend

**Stack**: React 18 + TypeScript + Vite + React Router v6

**Component tree**:
```
App
├── Top Nav (Search | Browse | Settings tabs)
└── Routes
    ├── Search
    │   ├── SearchBar (⌘K shortcut)
    │   ├── TagPill[] (LLM-parsed filters)
    │   ├── TagPicker (add manual tags)
    │   ├── SampleRow[] (results list)
    │   │   ├── Play button
    │   │   ├── TagPill[] (AI tags)
    │   │   ├── WaveformPlaceholder (expanded)
    │   │   └── User tag editor (expanded)
    │   └── Pagination
    ├── Browse
    │   ├── Sidebar (220px)
    │   │   ├── QuickFilters (not heard, unreviewed, starred)
    │   │   ├── CategoryTree (expandable)
    │   │   └── PackList
    │   └── Main panel
    │       ├── Breadcrumb
    │       ├── SubFilterChips (mood/energy)
    │       ├── SortDropdown
    │       └── SampleRow[] (results)
    └── Settings
        ├── Left nav (Library | AI Provider | About)
        └── Content area
            ├── Library: watch folders + scan status + rescan/remove
            ├── AI Provider: endpoint config + test
            └── About: version

**Update banner**: Checks GitHub Releases API on startup. Shows a dismissible banner with download link when a newer version is available.
```

**Styling**: Dark theme with CSS custom properties. Matches the design mockups in `design spec/`. AI tags are indigo; user tags are green.

**API client** (`api.ts`): Typed `fetch()` wrapper. No external dependencies. All endpoints return typed interfaces.

### 7. Launch & Packaging (`launch.py`)

**Startup sequence**:
1. Find a free TCP port
2. Build frontend if `dist/` missing (production mode)
3. Start uvicorn in a daemon thread (macOS requires pywebview on main thread)
4. Poll `/api/health` until server responds (up to 5s)
5. Open pywebview window → `http://127.0.0.1:{port}`
6. On window close → process exits (daemon thread terminates)

**Dev mode** (`--dev`): Opens pywebview to Vite dev server (`localhost:5173`) instead. API calls proxy through Vite config.

## Data Flow

### Search flow
```
User types "dark tense no transients"
        ↓
POST /api/search/parse {query}
        ↓
LLM parses → [{dimension:"mood", value:"dark"}, {dimension:"mood", value:"tense"}, {dimension:"transients", value:"any", negate:true}]
        ↓
Frontend displays tag pills
        ↓
GET /api/search?tags=[...]&limit=50&offset=0
        ↓
db.search_samples() — FTS5 text match + filter WHERE clauses
        ↓
Results with relevance ranking
        ↓
Frontend renders SampleRow[] with pagination
```

### Scan flow
```
User adds /Users/paul/Samples as watch folder
        ↓
POST /api/scan/roots {path}
        ↓
scanner.add_root() → insert scan_root + trigger initial scan
        ↓
_scan_root() walks folder tree
        ↓
For each audio file:
  analyze_audio() → features dict
  classify_instrument() → category
  llm_client.generate_tags(features) → tags dict
  db.insert_sample() or db.update_sample()
        ↓
Progress updated in scan_status (polled by frontend)
        ↓
scan_status.state = 'idle'
```

## Security Model

- **Audio privacy**: Raw audio files never leave the user's machine. Only structured features (~1KB JSON) are sent to the LLM endpoint.
- **API key**: Stored in local SQLite database (not encrypted in v1). Only accessible to the user's OS account.
- **Network**: All HTTP traffic is localhost-only (CORS restricted to `localhost:*` and `127.0.0.1:*`).
- **Single-user**: No authentication. The database file is protected by filesystem permissions.

## Database Schema (Full)

```sql
CREATE TABLE samples (
    id                  TEXT PRIMARY KEY,
    path                TEXT UNIQUE NOT NULL,
    filename            TEXT NOT NULL,
    folder              TEXT NOT NULL DEFAULT '',
    duration_seconds    REAL,
    bpm                 REAL,
    key                 TEXT,
    rms_energy          REAL,
    spectral_centroid   REAL,
    spectral_flatness   REAL,
    zero_crossing_rate  REAL,
    instrument_category TEXT,
    instrument_type     TEXT,
    instrument_subtype  TEXT,
    pack_source         TEXT DEFAULT '',
    ai_tags             TEXT DEFAULT '[]',
    user_tags           TEXT DEFAULT '[]',
    rating              INTEGER DEFAULT 0 CHECK(rating >= 0 AND rating <= 5),
    last_played_at      TEXT,
    play_count          INTEGER DEFAULT 0,
    file_mtime          REAL,
    file_size           INTEGER,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE scan_roots (
    id              TEXT PRIMARY KEY,
    path            TEXT UNIQUE NOT NULL,
    last_scanned_at TEXT,
    file_count      INTEGER DEFAULT 0,
    enabled         INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE scan_errors (
    id              TEXT PRIMARY KEY,
    sample_path     TEXT NOT NULL,
    error_type      TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    occurred_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE scan_status (
    id              INTEGER PRIMARY KEY CHECK(id = 1),
    state           TEXT NOT NULL DEFAULT 'idle',
    total_files     INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    current_file    TEXT,
    started_at      TEXT,
    finished_at     TEXT
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE fts_index USING fts5(
    sample_id,
    filename,
    ai_tags,
    user_tags,
    content='samples',
    content_rowid='rowid',
    tokenize='porter unicode61'
);
```

## Key Design Decisions

| Decision | Rationale | ADR |
|----------|-----------|-----|
| Hybrid AI (local analysis + cloud LLM) | Audio privacy, rich tags, tiny API cost | [001](adr/001-hybrid-ai-processing.md) |
| Python FastAPI + React + pywebview | Single-language backend, no IPC, simple packaging | [002](adr/002-python-fastapi-pywebview.md) |
| Search-first UI with tag pills | Natural language → editable structured filters | [003](adr/003-search-first-tag-pills.md) |
| SQLite + FTS5 | Zero-admin, built-in full-text search, single-file | [004](adr/004-sqlite-fts5.md) |

## V2 Backlog (from spec)

| Feature | Notes |
|---------|-------|
| File-system watcher | Auto-detect new samples as they land |
| Bulk tag editor | Multi-select, apply/remove tags |
| Tag correction feedback | Mark AI tags as wrong; refine future prompts |
| Export playlist | Export filtered set as folder copy or M3U |
| Waveform generation | Pre-render PNGs during scan |
| Mobile companion | Browse/preview on iOS/Android |
| VST/plugin wrapper | In-DAW access without Alt-Tab |
| Collaborative libraries | Read-only remote DB for co-producers |
| Dedicated ML model | Fine-tuned instrument classification replacing LLM for that step |
