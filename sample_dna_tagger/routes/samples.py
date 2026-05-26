"""
Sample routes — CRUD for individual samples.

GET    /api/samples/{id}        — single sample detail
PATCH  /api/samples/{id}        — update user_tags, rating
POST   /api/samples/{id}/play   — record play event
DELETE /api/samples/{id}        — remove sample from library
GET    /api/samples/{id}/audio  — stream the audio file
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from sample_dna_tagger.db import delete_sample, get_sample, record_play, update_sample
from sample_dna_tagger.waveform import delete_waveform, get_waveform_path

router = APIRouter(tags=["samples"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SampleDetail(BaseModel):
    id: str
    path: str
    filename: str
    folder: str = ""
    duration_seconds: float | None = None
    bpm: float | None = None
    key: str | None = None
    rms_energy: float | None = None
    spectral_centroid: float | None = None
    spectral_flatness: float | None = None
    zero_crossing_rate: float | None = None
    instrument_category: str | None = None
    instrument_type: str | None = None
    instrument_subtype: str | None = None
    pack_source: str = ""
    ai_tags: str = "[]"
    user_tags: str = "[]"
    rating: int = 0
    last_played_at: str | None = None
    play_count: int = 0
    file_mtime: float | None = None
    file_size: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SampleUpdate(BaseModel):
    user_tags: str | None = Field(None, description="JSON array of user-assigned tags")
    rating: int | None = Field(None, ge=0, le=5, description="Star rating 0-5")


class PlayResponse(BaseModel):
    ok: bool
    sample: SampleDetail | None = None


class DeleteResponse(BaseModel):
    ok: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/samples/{sample_id}", response_model=SampleDetail)
async def get_one(sample_id: str):
    """Return a single sample by ID."""
    sample = await get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    return SampleDetail(**sample)


@router.patch("/samples/{sample_id}", response_model=SampleDetail)
async def update_one(sample_id: str, body: SampleUpdate):
    """Update user_tags and/or rating on a sample."""
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing = await get_sample(sample_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    await update_sample(sample_id, data)
    result = await get_sample(sample_id)
    return SampleDetail(**result)


@router.post("/samples/{sample_id}/play", response_model=PlayResponse)
async def play_one(sample_id: str):
    """Record a play event — bumps play_count and sets last_played_at."""
    existing = await get_sample(sample_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    updated = await record_play(sample_id)
    return PlayResponse(ok=True, sample=SampleDetail(**updated) if updated else None)


@router.delete("/samples/{sample_id}", response_model=DeleteResponse)
async def delete_one(sample_id: str):
    """Remove a sample from the library and delete its waveform cache."""
    deleted = await delete_sample(sample_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sample not found")
    delete_waveform(sample_id)
    return DeleteResponse(ok=True)


@router.get("/samples/{sample_id}/waveform")
async def get_waveform(sample_id: str):
    """Serve the cached waveform PNG for a sample."""
    sample = await get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    wf_path = get_waveform_path(sample_id)
    if wf_path is None:
        raise HTTPException(status_code=404, detail="Waveform not generated yet")

    return FileResponse(
        path=str(wf_path),
        media_type="image/png",
        filename=f"{sample_id}.png",
    )


@router.get("/samples/{sample_id}/audio")
async def stream_audio(sample_id: str):
    """Stream the audio file for a sample."""
    sample = await get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    file_path = Path(sample["path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    # Determine media type from extension
    ext = file_path.suffix.lower()
    media_type = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aiff": "audio/aiff",
        ".aif": "audio/aiff",
        ".opus": "audio/opus",
    }.get(ext, "audio/wav")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )
