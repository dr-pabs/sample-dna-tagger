"""
Scan routes — scan control and status.

GET    /api/scan/status          — current scan status
POST   /api/scan/start           — start full scan of all roots
GET    /api/scan/roots           — list scan roots
POST   /api/scan/roots           — add watch folder
DELETE /api/scan/roots/{id}      — remove watch folder
POST   /api/scan/roots/{id}/rescan — rescan single root
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from sample_dna_tagger.db import get_scan_status, list_scan_roots
from sample_dna_tagger.scanner import scanner

router = APIRouter(tags=["scan"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ScanStatusResponse(BaseModel):
    id: int = 1
    state: str = "idle"
    total_files: int = 0
    processed_files: int = 0
    current_file: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class ScanRoot(BaseModel):
    id: str
    path: str
    last_scanned_at: str | None = None
    file_count: int = 0
    enabled: int = 1
    created_at: str | None = None


class AddRootRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Absolute path to watch folder")


class StartScanResponse(BaseModel):
    ok: bool
    message: str


class DeleteRootResponse(BaseModel):
    ok: bool


class RescanResponse(BaseModel):
    ok: bool
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/scan/status", response_model=ScanStatusResponse)
async def scan_status():
    """Return current scan status from the scan_status table."""
    status = await get_scan_status()
    if status is None:
        raise HTTPException(status_code=500, detail="Scan status not initialised")
    return ScanStatusResponse(**status)


@router.post("/scan/start", response_model=StartScanResponse)
async def start_scan(background: BackgroundTasks):
    """Start a full scan of all enabled watch folders in the background."""
    background.add_task(scanner.scan_all)
    return StartScanResponse(ok=True, message="Scan started")


@router.get("/scan/roots", response_model=list[ScanRoot])
async def list_roots():
    """List all configured scan roots."""
    roots = await list_scan_roots()
    return [ScanRoot(**r) for r in roots]


@router.post("/scan/roots", response_model=ScanRoot, status_code=201)
async def add_root(request: AddRootRequest):
    """Add a watch folder."""
    root_id = await scanner.add_root(request.path)
    # Fetch the created root to return full details
    roots = await list_scan_roots()
    for r in roots:
        if r["id"] == root_id:
            return ScanRoot(**r)
    raise HTTPException(status_code=500, detail="Failed to create scan root")


@router.delete("/scan/roots/{root_id}", response_model=DeleteRootResponse)
async def remove_root(root_id: str):
    """Remove a watch folder."""
    try:
        await scanner.remove_root(root_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scan root not found")
    return DeleteRootResponse(ok=True)


@router.post("/scan/roots/{root_id}/rescan", response_model=RescanResponse)
async def rescan_root(root_id: str, background: BackgroundTasks):
    """Rescan a single watch folder in the background."""
    # First verify the root exists
    roots = await list_scan_roots()
    matching = [r for r in roots if r["id"] == root_id]
    if not matching:
        raise HTTPException(status_code=404, detail="Scan root not found")

    background.add_task(scanner.rescan_root, root_id)
    return RescanResponse(ok=True, message=f"Rescan started for {matching[0]['path']}")
