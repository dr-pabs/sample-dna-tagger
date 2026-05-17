"""
Search routes — natural language query parsing and execution.

POST /api/search/parse  — LLM parses natural language to structured tags
GET  /api/search        — execute search with filters, return paginated results
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sample_dna_tagger.db import search_samples_paginated
from sample_dna_tagger.llm import llm_client

router = APIRouter(tags=["search"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ParseRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")


class TagFilter(BaseModel):
    dimension: str
    value: str
    negate: bool = False


class ParseResponse(BaseModel):
    tags: list[TagFilter]


class SearchResponse(BaseModel):
    results: list[dict]
    total: int
    page: int
    pages: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/search/parse", response_model=ParseResponse)
async def parse_search(request: ParseRequest):
    """Parse a natural language query into structured tag filters via LLM."""
    try:
        tags = await llm_client.parse_search_query(request.query)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM parse failed: {e}")

    return ParseResponse(
        tags=[TagFilter(**t) for t in tags if isinstance(t, dict)]
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str | None = Query(None, description="Full-text search query"),
    tags: str | None = Query(None, description="JSON array of structured tag filters"),
    category: str | None = Query(None, description="Filter by instrument_category"),
    type: str | None = Query(None, description="Filter by instrument_type"),
    subtype: str | None = Query(None, description="Filter by instrument_subtype"),
    pack: str | None = Query(None, description="Filter by pack_source"),
    energy: str | None = Query(None, description="Filter by energy level (low/medium/high)"),
    min_rating: int | None = Query(None, ge=0, le=5, description="Minimum rating filter"),
    sort: str = Query("relevance", description="Sort order: relevance, filename, last_played, date_added, rating"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Search samples with combined text search, tag filters, and category/pack filters.
    Returns paginated results.
    """
    filters: dict = {}
    if category:
        filters["category"] = category
    if type:
        filters["type"] = type
    if subtype:
        filters["subtype"] = subtype
    if pack:
        filters["pack"] = pack
    if energy:
        filters["energy"] = energy
    if min_rating is not None:
        filters["min_rating"] = min_rating
    if tags:
        import json

        try:
            tag_list = json.loads(tags) if isinstance(tags, str) else tags
            for tag in tag_list:
                dim = tag.get("dimension", "")
                val = tag.get("value", "")
                if dim == "energy":
                    filters["energy"] = val
                elif dim == "mood":
                    filters["not_heard_days"] = None  # mood is searched via FTS
        except (json.JSONDecodeError, TypeError):
            pass

    result = await search_samples_paginated(
        query=q or "",
        filters=filters or None,
        limit=limit,
        offset=offset,
    )
    return SearchResponse(**result)
