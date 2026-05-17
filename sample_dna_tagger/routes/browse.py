"""
Browse routes — category tree, pack list, quick filters, and paginated listing.

GET /api/browse/categories    — nested category tree with counts
GET /api/browse/packs         — pack list with counts
GET /api/browse/quick-filters — counts for quick filter options
GET /api/browse               — paginated filtered listing
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from sample_dna_tagger.db import browse_samples, get_category_tree, get_pack_list, get_quick_filter_counts

router = APIRouter(tags=["browse"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BrowseResponse(BaseModel):
    results: list[dict]
    total: int
    page: int
    pages: int


class QuickFiltersResponse(BaseModel):
    not_heard_recently: int
    unreviewed: int
    starred: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/browse/categories")
async def categories():
    """Return nested category tree: {category: {type: count, ...}, ...}"""
    return await get_category_tree()


@router.get("/browse/packs")
async def packs():
    """Return list of packs with sample counts."""
    return await get_pack_list()


@router.get("/browse/quick-filters", response_model=QuickFiltersResponse)
async def quick_filters():
    """Return counts for quick filter buttons."""
    data = await get_quick_filter_counts()
    return QuickFiltersResponse(**data)


@router.get("/browse", response_model=BrowseResponse)
async def browse(
    category: str | None = Query(None, description="Filter by instrument_category"),
    type: str | None = Query(None, description="Filter by instrument_type"),
    pack: str | None = Query(None, description="Filter by pack_source"),
    quick_filter: str | None = Query(
        None,
        description="Quick filter: not_heard, unreviewed, starred",
    ),
    sort: str = Query("filename", description="Sort order: filename, last_played, date_added, rating, updated_at"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Browse samples filtered by category, type, pack, or quick filter. Paginated."""
    # Map sort names to DB column names
    sort_map = {
        "last_played": "last_played_at",
        "date_added": "created_at",
        "rating": "rating",
        "filename": "filename",
    }
    sort_by = sort_map.get(sort, "filename")
    sort_dir = "DESC" if sort in ("last_played", "date_added", "rating") else "ASC"

    result = await browse_samples(
        category=category,
        instrument_type=type,
        pack=pack,
        quick_filter=quick_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return BrowseResponse(**result)
