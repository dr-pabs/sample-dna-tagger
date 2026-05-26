"""
Settings routes — configuration and LLM connection test.

GET  /api/settings      — return aggregated settings (watch folders, scan status, AI config)
PUT  /api/settings      — upsert settings
POST /api/settings/test — test LLM connection
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sample_dna_tagger.db import (
    get_scan_status,
    get_setting,
    list_scan_roots,
    list_settings,
    set_setting,
)
from sample_dna_tagger.llm import llm_client

router = APIRouter(tags=["settings"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WatchFolder(BaseModel):
    id: str
    path: str
    last_scanned: str | None = None
    file_count: int = 0


class ScanStatusSummary(BaseModel):
    state: str = "idle"
    indexed: int = 0
    tagged: int = 0
    queued: int = 0
    errors: int = 0


class SettingsResponse(BaseModel):
    watch_folders: list[WatchFolder]
    scan_status: ScanStatusSummary
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""


class TestConnectionResponse(BaseModel):
    ok: bool
    model: str | None = None
    response: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_scan_status(status: dict | None) -> ScanStatusSummary:
    """Map raw DB scan_status to the frontend-expected shape."""
    if status is None:
        return ScanStatusSummary()
    total = status.get("total_files", 0) or 0
    processed = status.get("processed_files", 0) or 0
    return ScanStatusSummary(
        state=status.get("state", "idle"),
        indexed=processed,
        tagged=processed,
        queued=max(0, total - processed),
        errors=0,  # errors tracked separately per-scan; frontend shows 0 for now
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Return aggregated settings: watch folders, scan status, and AI config."""
    # Watch folders
    roots = await list_scan_roots()
    watch_folders = [
        WatchFolder(
            id=r["id"],
            path=r["path"],
            last_scanned=r.get("last_scanned_at"),
            file_count=r.get("file_count", 0) or 0,
        )
        for r in roots
    ]

    # Scan status
    raw_status = await get_scan_status()
    scan_status = _map_scan_status(raw_status)

    # AI config (read from settings table with both naming conventions)
    provider = await get_setting("provider") or ""
    model = (
        await get_setting("model")
        or await get_setting("llm_model")
        or ""
    )
    base_url = (
        await get_setting("base_url")
        or await get_setting("llm_base_url")
        or ""
    )
    api_key = (
        await get_setting("api_key")
        or await get_setting("llm_api_key")
        or ""
    )

    return SettingsResponse(
        watch_folders=watch_folders,
        scan_status=scan_status,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(body: dict):
    """Upsert settings. Body may contain provider, model, base_url, api_key.
    Returns the updated aggregated settings response."""
    if not body:
        raise HTTPException(status_code=400, detail="No settings provided")

    # Persist raw keys
    for key, value in body.items():
        await set_setting(key, str(value))

    # Also persist with llm_ prefix for internal consistency
    mapping = {
        "base_url": "llm_base_url",
        "api_key": "llm_api_key",
        "model": "llm_model",
    }
    for front_key, internal_key in mapping.items():
        if front_key in body:
            await set_setting(internal_key, str(body[front_key]))

    # Reconfigure LLM client if credentials provided
    llm_keys = {"base_url", "api_key", "model", "llm_base_url", "llm_api_key", "llm_model"}
    if llm_keys & set(body.keys()):
        base_url = (await get_setting("base_url") or await get_setting("llm_base_url") or "")
        api_key = (await get_setting("api_key") or await get_setting("llm_api_key") or "")
        model = (await get_setting("model") or await get_setting("llm_model") or "deepseek-chat")
        if base_url and api_key:
            await llm_client.configure(base_url, api_key, model)

    # Return aggregated response (same shape as GET)
    return await get_settings()


@router.get("/version")
async def get_version():
    """Return the current app version."""
    return {"version": "0.1.0", "name": "Sample DNA Tagger"}


@router.post("/settings/test", response_model=TestConnectionResponse)
async def test_connection():
    """Test the LLM connection. Returns ok=true/false with details."""
    # Auto-load config from DB if client not yet configured
    if not llm_client._configured:
        base_url = await get_setting("base_url") or await get_setting("llm_base_url") or ""
        api_key = await get_setting("api_key") or await get_setting("llm_api_key") or ""
        model = await get_setting("model") or await get_setting("llm_model") or "deepseek-chat"
        if base_url and api_key:
            await llm_client.configure(base_url, api_key, model)

    try:
        result = await llm_client.test_connection()
        return TestConnectionResponse(**result)
    except Exception as e:
        return TestConnectionResponse(ok=False, error=str(e))
