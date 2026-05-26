"""
FastAPI application — serves REST API and the compiled React SPA.

Routes are organised by domain:
- /api/search    — natural language query parsing and execution
- /api/samples   — CRUD for individual samples
- /api/scan      — scan control and status
- /api/settings  — configuration and LLM connection test
- /api/browse     — category/pack tree and filtered listing
- /               — static React SPA (production) or proxy (dev)
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from sample_dna_tagger.db import init_db, list_scan_roots
from sample_dna_tagger.routes import browse, samples, scan, search, settings
from sample_dna_tagger.scanner import scanner
from sample_dna_tagger.watcher import watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialise database and file-system watcher."""
    await init_db()

    # Start file-system watcher
    watcher.set_loop(asyncio.get_event_loop())
    watcher.start()

    # Watch all existing scan roots
    roots = await list_scan_roots()
    for r in roots:
        if r.get("enabled", 1):
            watcher.add_root(r["id"], r["path"], scanner)

    yield

    # Shutdown
    watcher.stop()


app = FastAPI(title="Sample DNA Tagger", version="0.1.0", lifespan=lifespan)

# CORS — allow pywebview (localhost on any port) and dev server
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

app.include_router(search.router, prefix="/api")
app.include_router(samples.router, prefix="/api")
app.include_router(browse.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


# ---------------------------------------------------------------------------
# SPA fallback — serve index.html for any non-API route
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    """Serve the React SPA for any route not caught by the API.

    Returns index.html so client-side routing handles /search, /browse, etc.
    Static assets (JS, CSS) are served directly if they exist on disk.
    """
    candidate = FRONTEND_DIST / full_path
    if candidate.is_file():
        return FileResponse(candidate)

    # Fall back to index.html for SPA routing
    if INDEX_HTML.is_file():
        return FileResponse(
            INDEX_HTML,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    return {"error": "Frontend not built — run 'npm run build' in frontend/"}  # type: ignore[return-value]
