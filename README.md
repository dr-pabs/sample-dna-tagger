# Sample DNA Tagger

**AI-tag your sample library. Find anything with natural language.**

A desktop app for music producers that analyses your sample library, generates expressive semantic tags via AI, and lets you search with natural language — "dark, tense, no transients" — or browse by category, pack, and recency.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- An OpenAI-compatible API key (DeepSeek, OpenAI, Kimi, or local Ollama)

### Development

```bash
# Terminal 1 — backend
cd sample-dna-tagger
pip install -e ".[dev]"
python launch.py --dev

# Terminal 2 — frontend
cd frontend
npm install --cache .npm-cache
npm run dev
```

The app opens in a native desktop window. The Vite dev server proxies `/api` calls to the FastAPI backend on port 8000.

### Production

```bash
pip install .
python launch.py        # builds frontend, starts server, opens window
python launch.py --no-window  # server-only, no GUI
```

On first launch, the database is created at `~/.sample-dna-tagger/library.db`. Configure your watch folders and AI provider in Settings before scanning.

## Architecture

```
┌─────────────────────────────────────────────┐
│                 Desktop App                  │
│  pywebview window → localhost React SPA      │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │         FastAPI (Python)             │   │
│  │  ┌──────────┐ ┌───────┐ ┌────────┐  │   │
│  │  │ Scanner  │ │  LLM  │ │ SQLite │  │   │
│  │  │  Engine  │ │ Layer │ │   DB   │  │   │
│  │  └──────────┘ └───────┘ └────────┘  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### How tagging works

1. **Scanner** walks your watch folders. For each new or modified audio file, it runs local analysis via librosa — extracting BPM, RMS energy, spectral centroid, spectral flatness, zero-crossing rate, and instrument classification.
2. **LLM Layer** receives the structured features (never audio) and sends them to your configured AI endpoint. The LLM returns expressive tags: energy, texture, mood, emotional quality, motion, and refined instrument type/subtype.
3. **Database** stores everything in SQLite with FTS5 full-text search across filenames and tags.

## Project Structure

```
sample-dna-tagger/
├── launch.py                     # Entry point — starts server + window
├── pyproject.toml                # Python project config + dependencies
├── SampleDNA.spec                # PyInstaller packaging spec
├── build-macos.sh / build-windows.bat
├── adr/                          # Architecture Decision Records
├── design spec/                  # UI mockups (open in browser)
├── sample_dna_tagger/
│   ├── __init__.py
│   ├── server.py                 # FastAPI app + static file serving
│   ├── db.py                     # SQLite + FTS5 + CRUD operations
│   ├── scanner.py                # Watch-folder walker + audio analysis
│   ├── llm.py                    # OpenAI-compatible client + prompts
│   └── routes/
│       ├── search.py             # Natural language → tag pills + search
│       ├── browse.py             # Category tree, packs, quick filters
│       ├── samples.py            # CRUD + play tracking
│       ├── scan.py               # Scan control + status
│       └── settings.py           # Configuration + LLM connection test
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx              # React entry
        ├── App.tsx               # Router: Search | Browse | Settings
        ├── api.ts                # Typed API client
        ├── index.css             # Dark theme design system
        ├── App.css               # Navigation bar
        ├── components/
        │   ├── SampleRow.tsx     # Reusable result row
        │   ├── TagPill.tsx       # Tag pill with optional remove
        │   └── WaveformPlaceholder.tsx
        └── pages/
            ├── Search.tsx        # Natural language → tag pills → results
            ├── Browse.tsx        # Sidebar filters + category tree
            └── Settings.tsx      # Library / AI Provider / About
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/search/parse` | Parse natural language → structured filters |
| `GET` | `/api/search` | Search samples with text and filters |
| `GET` | `/api/samples/{id}` | Single sample detail |
| `PATCH` | `/api/samples/{id}` | Update user tags, rating |
| `POST` | `/api/samples/{id}/play` | Record play event |
| `DELETE`| `/api/samples/{id}` | Remove from library |
| `GET` | `/api/browse/categories` | Category tree with counts |
| `GET` | `/api/browse/packs` | Pack list with counts |
| `GET` | `/api/browse/quick-filters` | Quick filter counts |
| `GET` | `/api/browse` | Browse with filters |
| `GET` | `/api/scan/status` | Current scan progress |
| `POST` | `/api/scan/start` | Start full scan |
| `GET` | `/api/scan/roots` | List watch folders |
| `POST` | `/api/scan/roots` | Add watch folder |
| `DELETE`| `/api/scan/roots/{id}` | Remove watch folder |
| `POST` | `/api/scan/roots/{id}/rescan` | Rescan single folder |
| `GET` | `/api/settings` | Get all settings |
| `PUT` | `/api/settings` | Update settings |
| `POST` | `/api/settings/test` | Test LLM connection |

## Configuration

Settings are stored in the SQLite database and editable from the Settings screen:

- **Library**: Watch folder paths, scan status
- **AI Provider**: Base URL, API key, model name. Supports DeepSeek, OpenAI, Kimi, Ollama, and any OpenAI-compatible endpoint.
- **Database path**: Override with `SAMPLE_DNA_DB` environment variable (default: `~/.sample-dna-tagger/library.db`)

## Building for Distribution

```bash
# macOS
chmod +x build-macos.sh
./build-macos.sh
# Output: dist/Sample DNA Tagger.app

# Windows
build-windows.bat
# Output: dist\Sample DNA Tagger.exe
```

Uses PyInstaller to bundle Python runtime, all dependencies, and the compiled React SPA into a single `.app` (macOS) or `.exe` (Windows).

## Design Decisions

See `adr/` for Architecture Decision Records:

- [ADR-001](adr/001-hybrid-ai-processing.md) — Hybrid AI processing (local analysis + cloud LLM)
- [ADR-002](adr/002-python-fastapi-pywebview.md) — Python FastAPI + React SPA + pywebview
- [ADR-003](adr/003-search-first-tag-pills.md) — Search-first UI with LLM-parsed tag pills
- [ADR-004](adr/004-sqlite-fts5.md) — SQLite with FTS5 full-text search

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete end-to-end system design.

## License

MIT
