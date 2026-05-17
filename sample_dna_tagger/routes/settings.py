"""
Settings routes — configuration and LLM connection test.

GET  /api/settings      — return all settings as key/value
PUT  /api/settings      — upsert settings
POST /api/settings/test — test LLM connection
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sample_dna_tagger.db import get_setting, list_settings, set_setting
from sample_dna_tagger.llm import llm_client

router = APIRouter(tags=["settings"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestConnectionResponse(BaseModel):
    ok: bool
    model: str | None = None
    response: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/settings")
async def get_settings():
    """Return all settings as a flat key/value dict."""
    rows = await list_settings()
    return {r["key"]: r["value"] for r in rows}


@router.put("/settings")
async def update_settings(body: dict):
    """Upsert settings. Body is a flat key/value object."""
    if not body:
        raise HTTPException(status_code=400, detail="No settings provided")

    for key, value in body.items():
        await set_setting(key, str(value))

    # If LLM-related settings were updated, reconfigure the client.
    # Accept both naming conventions: frontend sends base_url/api_key/model,
    # internal settings use llm_base_url/llm_api_key/llm_model.
    llm_keys = {"base_url", "api_key", "model", "llm_base_url", "llm_api_key", "llm_model"}
    if llm_keys & set(body.keys()):
        base_url = (await get_setting("base_url") or await get_setting("llm_base_url") or "")
        api_key = (await get_setting("api_key") or await get_setting("llm_api_key") or "")
        model = (await get_setting("model") or await get_setting("llm_model") or "deepseek-chat")
        if base_url and api_key:
            await llm_client.configure(base_url, api_key, model)

    rows = await list_settings()
    return {r["key"]: r["value"] for r in rows}


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
