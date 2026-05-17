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

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sample_dna_tagger.db import init_db
from sample_dna_tagger.routes import browse, samples, scan, search, settings

app = FastAPI(title="Sample DNA Tagger", version="0.1.0")

# CORS — allow pywebview (localhost on any port) and dev server
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await init_db()


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
# Static files — serve compiled React SPA
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
