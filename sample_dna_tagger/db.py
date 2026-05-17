"""
SQLite database layer with FTS5 full-text search.

Schema matches the design spec data model:
- samples: core table with audio features and AI tags
- scan_roots: configured watch folders
- scan_errors: per-file error log
- scan_status: scan progress (singleton row)
- settings: key/value configuration
- fts_index: FTS5 virtual table over filename + tags

Connection management uses a module-level singleton with asyncio.Lock
for serialised write access.  The DB path is configurable via the
SAMPLE_DNA_DB environment variable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

# ---------------------------------------------------------------------------
# Path & connection lifecycle
# ---------------------------------------------------------------------------

_AIOSQLITE_MIN_VERSION = (0, 20, 0)

DB_PATH = Path(
    os.environ.get("SAMPLE_DNA_DB", Path.home() / ".sample-dna-tagger" / "library.db")
)

_db: aiosqlite.Connection | None = None
_lock: asyncio.Lock | None = None
_initialised: bool = False

logger = logging.getLogger(__name__)


def _get_lock() -> asyncio.Lock:
    """Return the module-level asyncio lock, creating it on first call."""
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def get_db_path() -> Path:
    """Resolve database path, creating parent directory if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


async def get_connection() -> aiosqlite.Connection:
    """Open and return a *new* connection with WAL mode and foreign keys enabled.

    Prefer ``get_db()`` for module-level reuse; this function remains
    public for callers that genuinely need an independent connection.
    """
    db_path = await get_db_path()
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def get_db() -> aiosqlite.Connection:
    """Return the singleton database connection, opening it if necessary.

    The connection is shared across all callers.  Write operations inside
    this module are serialised via ``_get_lock()``.
    """
    global _db
    if _db is None:
        _db = await get_connection()
        await init_db(_db)
    return _db


async def close_db() -> None:
    """Close the singleton connection.  Safe to call multiple times."""
    global _db, _initialised
    if _db is not None:
        await _db.close()
        _db = None
    _initialised = False


# ---------------------------------------------------------------------------
# Schema – idempotent
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS samples (
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

    CREATE TABLE IF NOT EXISTS scan_roots (
        id              TEXT PRIMARY KEY,
        path            TEXT UNIQUE NOT NULL,
        last_scanned_at TEXT,
        file_count      INTEGER DEFAULT 0,
        enabled         INTEGER DEFAULT 1,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS scan_errors (
        id              TEXT PRIMARY KEY,
        sample_path     TEXT NOT NULL,
        error_type      TEXT NOT NULL,
        error_message   TEXT NOT NULL,
        occurred_at     TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS scan_status (
        id              INTEGER PRIMARY KEY CHECK(id = 1),
        state           TEXT NOT NULL DEFAULT 'idle',
        total_files     INTEGER DEFAULT 0,
        processed_files INTEGER DEFAULT 0,
        current_file    TEXT,
        started_at      TEXT,
        finished_at     TEXT
    );

    CREATE TABLE IF NOT EXISTS settings (
        key             TEXT PRIMARY KEY,
        value           TEXT NOT NULL DEFAULT ''
    );

    -- FTS5 external-content index over filename + AI tags + user tags
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
        sample_id,
        filename,
        ai_tags,
        user_tags,
        content='samples',
        content_rowid='rowid',
        tokenize='porter unicode61'
    );

    -- Triggers: keep FTS index in sync (explicit rowid for external-content)
    CREATE TRIGGER IF NOT EXISTS samples_ai_insert AFTER INSERT ON samples BEGIN
        INSERT INTO fts_index(rowid, sample_id, filename, ai_tags, user_tags)
        VALUES (new.rowid, new.id, new.filename, new.ai_tags, new.user_tags);
    END;

    CREATE TRIGGER IF NOT EXISTS samples_ai_delete AFTER DELETE ON samples BEGIN
        INSERT INTO fts_index(fts_index, rowid, sample_id, filename, ai_tags, user_tags)
        VALUES ('delete', old.rowid, old.id, old.filename, old.ai_tags, old.user_tags);
    END;

    CREATE TRIGGER IF NOT EXISTS samples_ai_update AFTER UPDATE ON samples BEGIN
        INSERT INTO fts_index(fts_index, rowid, sample_id, filename, ai_tags, user_tags)
        VALUES ('delete', old.rowid, old.id, old.filename, old.ai_tags, old.user_tags);
        INSERT INTO fts_index(rowid, sample_id, filename, ai_tags, user_tags)
        VALUES (new.rowid, new.id, new.filename, new.ai_tags, new.user_tags);
    END;

    -- Seed scan_status singleton row
    INSERT OR IGNORE INTO scan_status (id, state) VALUES (1, 'idle');

    -- Record current schema version for future migrations
    INSERT OR IGNORE INTO settings (key, value) VALUES ('schema_version', '1');
"""


async def init_db(conn: aiosqlite.Connection | None = None) -> None:
    """Create tables and seed data if they don't exist.  Idempotent.

    If *conn* is ``None`` the singleton connection is used and
    auto-created when needed.  The singleton connection is never
    closed by this function — call ``close_db()`` to shut it down.
    """
    global _initialised

    if conn is None:
        conn = await get_db()

    await conn.executescript(SCHEMA_SQL)
    await conn.commit()
    _initialised = True


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def new_uuid() -> str:
    """Return a new UUID4 as a string."""
    return str(uuid.uuid4())


def utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    """Convert an aiosqlite.Row to a plain dict, or return None."""
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows: list[aiosqlite.Row]) -> list[dict[str, Any]]:
    """Convert a list of aiosqlite.Row objects to plain dicts."""
    return [dict(r) for r in rows]


async def _execute_write(sql: str, params: tuple = ()) -> aiosqlite.Cursor:
    """Run a write statement under the module lock and commit."""
    db = await get_db()
    lock = _get_lock()
    async with lock:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor


async def _execute_read(sql: str, params: tuple = ()) -> aiosqlite.Cursor:
    """Run a read statement (no lock needed; WAL handles concurrency)."""
    db = await get_db()
    return await db.execute(sql, params)


# ---------------------------------------------------------------------------
# Samples CRUD
# ---------------------------------------------------------------------------

SAMPLE_COLUMNS = [
    "id", "path", "filename", "folder", "duration_seconds", "bpm", "key",
    "rms_energy", "spectral_centroid", "spectral_flatness", "zero_crossing_rate",
    "instrument_category", "instrument_type", "instrument_subtype",
    "pack_source", "ai_tags", "user_tags", "rating", "last_played_at",
    "play_count", "file_mtime", "file_size", "created_at", "updated_at",
]


async def insert_sample(data: dict[str, Any]) -> str:
    """Insert a new sample row.  Returns the new sample id.

    *data* must include at least ``path`` and ``filename``.
    Missing optional fields get sensible defaults.
    """
    sample_id = data.get("id") or new_uuid()
    now = utcnow()

    fields = {
        "id": sample_id,
        "path": data["path"],
        "filename": data["filename"],
        "folder": data.get("folder", ""),
        "duration_seconds": data.get("duration_seconds"),
        "bpm": data.get("bpm"),
        "key": data.get("key"),
        "rms_energy": data.get("rms_energy"),
        "spectral_centroid": data.get("spectral_centroid"),
        "spectral_flatness": data.get("spectral_flatness"),
        "zero_crossing_rate": data.get("zero_crossing_rate"),
        "instrument_category": data.get("instrument_category"),
        "instrument_type": data.get("instrument_type"),
        "instrument_subtype": data.get("instrument_subtype"),
        "pack_source": data.get("pack_source", ""),
        "ai_tags": _json_dump(data.get("ai_tags", [])),
        "user_tags": _json_dump(data.get("user_tags", [])),
        "rating": data.get("rating", 0),
        "last_played_at": data.get("last_played_at"),
        "play_count": data.get("play_count", 0),
        "file_mtime": data.get("file_mtime"),
        "file_size": data.get("file_size"),
        "created_at": data.get("created_at", now),
        "updated_at": now,
    }

    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    values = tuple(fields.values())

    await _execute_write(
        f"INSERT INTO samples ({columns}) VALUES ({placeholders})", values
    )
    return sample_id


async def update_sample(sample_id: str, data: dict[str, Any]) -> None:
    """Update fields on an existing sample row.

    Only the keys present in *data* are changed.  ``id`` and ``path``
    cannot be updated — they are silently ignored.
    """
    updatable = {
        "filename", "folder", "duration_seconds", "bpm", "key",
        "rms_energy", "spectral_centroid", "spectral_flatness",
        "zero_crossing_rate", "instrument_category", "instrument_type",
        "instrument_subtype", "pack_source", "ai_tags", "user_tags",
        "rating", "last_played_at", "play_count", "file_mtime", "file_size",
    }

    set_clauses = []
    values: list[Any] = []

    for key in updatable:
        if key not in data:
            continue
        val = data[key]
        if key in ("ai_tags", "user_tags"):
            val = _json_dump(val if val is not None else [])
        set_clauses.append(f"{key} = ?")
        values.append(val)

    if not set_clauses:
        return

    set_clauses.append("updated_at = ?")
    values.append(utcnow())
    values.append(sample_id)

    await _execute_write(
        f"UPDATE samples SET {', '.join(set_clauses)} WHERE id = ?",
        tuple(values),
    )


async def delete_sample(sample_id: str) -> bool:
    """Delete a sample by id.  Returns ``True`` if a row was deleted."""
    cursor = await _execute_write("DELETE FROM samples WHERE id = ?", (sample_id,))
    return cursor.rowcount > 0


async def get_sample(sample_id: str) -> dict[str, Any] | None:
    """Return a single sample as a dict, or ``None``."""
    cursor = await _execute_read("SELECT * FROM samples WHERE id = ?", (sample_id,))
    row = await cursor.fetchone()
    return _row_to_dict(row)


async def record_play(sample_id: str) -> dict[str, Any] | None:
    """Record a play event: increment play_count and set last_played_at."""
    now = datetime.now(timezone.utc).isoformat()
    await _execute_write(
        "UPDATE samples SET play_count = play_count + 1, "
        "last_played_at = ?, updated_at = ? WHERE id = ?",
        (now, now, sample_id),
    )
    return await get_sample(sample_id)


async def list_samples(
    *,
    folder: str | None = None,
    category: str | None = None,
    instrument_type: str | None = None,
    pack: str | None = None,
    min_rating: int | None = None,
    has_user_tags: bool | None = None,
    sort_by: str = "updated_at",
    sort_dir: str = "DESC",
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List samples with optional filters.

    Valid *sort_by* values: any sample column.  Default is ``updated_at``.
    """
    where: list[str] = []
    params: list[Any] = []

    if folder is not None:
        where.append("folder = ?")
        params.append(folder)
    if category is not None:
        where.append("instrument_category = ?")
        params.append(category)
    if instrument_type is not None:
        where.append("instrument_type = ?")
        params.append(instrument_type)
    if pack is not None:
        where.append("pack_source = ?")
        params.append(pack)
    if min_rating is not None:
        where.append("rating >= ?")
        params.append(min_rating)
    if has_user_tags is True:
        where.append("user_tags != '[]'")
    elif has_user_tags is False:
        where.append("user_tags = '[]'")

    # Validate sort column (simple allow-list to avoid injection)
    safe_sort = sort_by if sort_by in SAMPLE_COLUMNS else "updated_at"
    direction = "DESC" if sort_dir.upper() == "DESC" else "ASC"

    sql = f"SELECT * FROM samples"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {safe_sort} {direction} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await _execute_read(sql, tuple(params))
    rows = await cursor.fetchall()
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# FTS5 search
# ---------------------------------------------------------------------------

_FTS_SPECIAL = re.compile(r'["^()+\-~\\]')


def _sanitise_fts_query(query: str) -> str:
    """Strip FTS5 special characters, preserving ``*`` for prefix matching."""
    return _FTS_SPECIAL.sub("", query).strip()


def _build_fts_match(query: str) -> str:
    """Build a safe FTS5 MATCH expression from user input."""
    cleaned = _sanitise_fts_query(query)
    if not cleaned:
        return ""
    # Quote each token so they are treated as literals
    tokens = [f'"{t}"' if "*" not in t else f'"{t}"' for t in cleaned.split()]
    return " ".join(tokens)


def _build_search_clauses(
    query: str, filters: dict[str, Any]
) -> tuple[str, str, str, str, list[Any]]:
    """Build WHERE clause, FROM clause, SELECT cols, ORDER BY, and params for search.

    Returns (where_clause, from_clause, select_cols, order_clause, params).
    """
    fts_match = _build_fts_match(query) if query else ""
    where: list[str] = []
    params: list[Any] = []

    if fts_match:
        where.append("fts_index MATCH ?")
        params.append(fts_match)

    if filters.get("category"):
        where.append("s.instrument_category = ?")
        params.append(filters["category"])
    if filters.get("type"):
        where.append("s.instrument_type = ?")
        params.append(filters["type"])
    if filters.get("subtype"):
        where.append("s.instrument_subtype = ?")
        params.append(filters["subtype"])
    if filters.get("pack"):
        where.append("s.pack_source = ?")
        params.append(filters["pack"])
    if filters.get("energy"):
        where.append("json_extract(s.ai_tags, '$.energy') = ?")
        params.append(filters["energy"])
    if filters.get("min_rating") is not None:
        where.append("s.rating >= ?")
        params.append(filters["min_rating"])
    if filters.get("min_duration") is not None:
        where.append("s.duration_seconds >= ?")
        params.append(filters["min_duration"])
    if filters.get("max_duration") is not None:
        where.append("s.duration_seconds <= ?")
        params.append(filters["max_duration"])
    if filters.get("has_user_tags") is not None:
        if filters["has_user_tags"]:
            where.append("s.user_tags != '[]'")
        else:
            where.append("s.user_tags = '[]'")
    if filters.get("not_heard_days") is not None:
        days = int(filters["not_heard_days"])
        where.append(
            "(s.last_played_at IS NULL OR s.last_played_at < datetime('now', ?))"
        )
        params.append(f"-{days} days")

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    if fts_match:
        select_cols = "s.*, rank"
        from_clause = "FROM fts_index JOIN samples s ON fts_index.rowid = s.rowid"
        order_clause = "ORDER BY rank"
    else:
        select_cols = "s.*"
        from_clause = "FROM samples s"
        order_clause = "ORDER BY s.updated_at DESC"

    return where_clause, from_clause, select_cols, order_clause, params


async def search_samples(
    query: str,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Full-text search across filename and tags with optional column filters.

    Returns list of sample dicts with optional ``fts_rank`` key.
    """
    filters = filters or {}
    where_clause, from_clause, select_cols, order_clause, params = _build_search_clauses(
        query, filters
    )

    sql = (
        f"SELECT {select_cols} {from_clause} {where_clause} "
        f"{order_clause} LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    cursor = await _execute_read(sql, tuple(params))
    rows = await cursor.fetchall()

    results = []
    for r in rows:
        d = dict(r)
        if "rank" in d:
            d["fts_rank"] = d.pop("rank")
        results.append(d)

    return results


async def search_samples_paginated(
    query: str = "",
    filters: dict[str, Any] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated search. Returns ``{results, total, page, pages}``."""
    filters = filters or {}
    where_clause, from_clause, _select_cols, _order_clause, params = _build_search_clauses(
        query, filters
    )

    # Count
    count_sql = f"SELECT COUNT(*) {from_clause} {where_clause}"
    cursor = await _execute_read(count_sql, tuple(params))
    row = await cursor.fetchone()
    total = row[0] if row else 0

    # Results — reuse search_samples for consistent result formatting
    results = await search_samples(query, filters, limit, offset)

    pages = max(1, (total + limit - 1) // limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1

    return {"results": results, "total": total, "page": page, "pages": pages}


# ---------------------------------------------------------------------------
# Scan roots CRUD
# ---------------------------------------------------------------------------

async def add_scan_root(root_path: str) -> str:
    """Add a watch folder.  Returns the new UUID."""
    root_id = new_uuid()
    now = utcnow()
    await _execute_write(
        "INSERT INTO scan_roots (id, path, created_at) VALUES (?, ?, ?)",
        (root_id, root_path, now),
    )
    return root_id


async def remove_scan_root(root_id: str) -> bool:
    """Remove a scan root by id.  Returns ``True`` if a row was deleted."""
    cursor = await _execute_write(
        "DELETE FROM scan_roots WHERE id = ?", (root_id,)
    )
    return cursor.rowcount > 0


async def list_scan_roots() -> list[dict[str, Any]]:
    """Return all configured watch folders."""
    cursor = await _execute_read("SELECT * FROM scan_roots ORDER BY path")
    rows = await cursor.fetchall()
    return _rows_to_dicts(rows)


async def update_scan_root(root_id: str, data: dict[str, Any]) -> None:
    """Update fields on a scan root row.

    Updatable keys: ``last_scanned_at``, ``file_count``, ``enabled``.
    """
    allowed = {"last_scanned_at", "file_count", "enabled"}
    set_clauses = []
    values: list[Any] = []

    for key in allowed:
        if key in data:
            set_clauses.append(f"{key} = ?")
            values.append(data[key])

    if not set_clauses:
        return

    values.append(root_id)
    await _execute_write(
        f"UPDATE scan_roots SET {', '.join(set_clauses)} WHERE id = ?",
        tuple(values),
    )


# ---------------------------------------------------------------------------
# Scan errors
# ---------------------------------------------------------------------------

async def log_scan_error(
    sample_path: str, error_type: str, error_message: str
) -> str:
    """Record a scan error.  Returns the new error UUID."""
    error_id = new_uuid()
    now = utcnow()
    await _execute_write(
        "INSERT INTO scan_errors (id, sample_path, error_type, error_message, occurred_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (error_id, sample_path, error_type, error_message, now),
    )
    return error_id


async def get_scan_errors(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent scan errors, newest first."""
    cursor = await _execute_read(
        "SELECT * FROM scan_errors ORDER BY occurred_at DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Scan status (singleton row id=1)
# ---------------------------------------------------------------------------

async def get_scan_status() -> dict[str, Any] | None:
    """Return the current scan status row."""
    cursor = await _execute_read("SELECT * FROM scan_status WHERE id = 1")
    row = await cursor.fetchone()
    return _row_to_dict(row)


async def update_scan_status(data: dict[str, Any]) -> None:
    """Update the scan status row (id=1).

    Updatable keys: ``state``, ``total_files``, ``processed_files``,
    ``current_file``, ``started_at``, ``finished_at``.
    """
    allowed = {
        "state", "total_files", "processed_files",
        "current_file", "started_at", "finished_at",
    }
    set_clauses = []
    values: list[Any] = []

    for key in allowed:
        if key in data:
            set_clauses.append(f"{key} = ?")
            values.append(data[key])

    if not set_clauses:
        return

    values.append(1)
    await _execute_write(
        f"UPDATE scan_status SET {', '.join(set_clauses)} WHERE id = ?",
        tuple(values),
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

async def get_setting(key: str) -> str | None:
    """Return the value for *key*, or ``None`` if not found."""
    cursor = await _execute_read(
        "SELECT value FROM settings WHERE key = ?", (key,)
    )
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_setting(key: str, value: str) -> None:
    """Insert or update a setting."""
    await _execute_write(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


async def list_settings() -> list[dict[str, Any]]:
    """Return all settings as a list of {key, value} dicts."""
    cursor = await _execute_read("SELECT * FROM settings ORDER BY key")
    rows = await cursor.fetchall()
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Schema versioning
# ---------------------------------------------------------------------------

async def get_schema_version() -> int:
    """Return the current schema version (default 0 if not yet initialised)."""
    val = await get_setting("schema_version")
    return int(val) if val is not None else 0


# ---------------------------------------------------------------------------
# Browse / aggregation queries
# ---------------------------------------------------------------------------

async def get_category_tree() -> dict[str, dict[str, int]]:
    """Return ``{category: {type: count, ...}, ...}`` for all samples."""
    cursor = await _execute_read(
        "SELECT instrument_category, instrument_type, COUNT(*) AS cnt "
        "FROM samples "
        "GROUP BY instrument_category, instrument_type "
        "ORDER BY instrument_category, instrument_type"
    )
    rows = await cursor.fetchall()

    tree: dict[str, dict[str, int]] = {}
    for r in rows:
        cat = r["instrument_category"] or "Uncategorised"
        typ = r["instrument_type"] or "Other"
        tree.setdefault(cat, {})[typ] = r["cnt"]
    return tree


async def get_pack_list() -> list[dict[str, Any]]:
    """Return ``[{pack_source, count}, ...]`` for non-empty pack sources."""
    cursor = await _execute_read(
        "SELECT pack_source, COUNT(*) AS cnt "
        "FROM samples "
        "WHERE pack_source != '' "
        "GROUP BY pack_source "
        "ORDER BY pack_source"
    )
    rows = await cursor.fetchall()
    return _rows_to_dicts(rows)


async def get_quick_filter_counts() -> dict[str, int]:
    """Return counts for quick-filter badges.

    Keys: ``not_heard_recently`` (7 days), ``unreviewed`` (rating=0),
    ``starred`` (rating >= 4).
    """
    cursor = await _execute_read("""
        SELECT
            COALESCE(SUM(CASE WHEN last_played_at IS NULL
                               OR last_played_at < datetime('now', '-7 days')
                          THEN 1 ELSE 0 END), 0) AS not_heard_recently,
            COALESCE(SUM(CASE WHEN rating = 0 THEN 1 ELSE 0 END), 0) AS unreviewed,
            COALESCE(SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END), 0) AS starred
        FROM samples
    """)
    row = await cursor.fetchone()
    if row is None:
        return {"not_heard_recently": 0, "unreviewed": 0, "starred": 0}
    return {
        "not_heard_recently": row["not_heard_recently"],
        "unreviewed": row["unreviewed"],
        "starred": row["starred"],
    }


async def browse_samples(
    *,
    category: str | None = None,
    instrument_type: str | None = None,
    pack: str | None = None,
    quick_filter: str | None = None,
    sort_by: str = "filename",
    sort_dir: str = "ASC",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated browse with quick-filter support.

    Returns ``{results, total, page, pages}``.

    *quick_filter* is one of: ``not_heard``, ``unreviewed``, ``starred``.
    """
    where: list[str] = []
    params: list[Any] = []

    if category is not None:
        where.append("instrument_category = ?")
        params.append(category)
    if instrument_type is not None:
        where.append("instrument_type = ?")
        params.append(instrument_type)
    if pack is not None:
        where.append("pack_source = ?")
        params.append(pack)

    if quick_filter == "not_heard":
        where.append(
            "(last_played_at IS NULL OR last_played_at < datetime('now', '-30 days'))"
        )
    elif quick_filter == "unreviewed":
        where.append("rating = 0 AND (user_tags = '[]' OR user_tags IS NULL OR user_tags = '')")
    elif quick_filter == "starred":
        where.append("rating >= 4")

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    # Validate sort column
    safe_sort = sort_by if sort_by in SAMPLE_COLUMNS else "filename"
    direction = "DESC" if sort_dir.upper() == "DESC" else "ASC"

    # Count
    count_sql = f"SELECT COUNT(*) FROM samples {where_clause}"
    cursor = await _execute_read(count_sql, tuple(params))
    row = await cursor.fetchone()
    total = row[0] if row else 0

    # Results
    sql = (
        f"SELECT * FROM samples {where_clause} "
        f"ORDER BY {safe_sort} {direction} LIMIT ? OFFSET ?"
    )
    cursor = await _execute_read(sql, tuple(params) + (limit, offset))
    rows = await cursor.fetchall()
    results = _rows_to_dicts(rows)

    pages = max(1, (total + limit - 1) // limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1

    return {"results": results, "total": total, "page": page, "pages": pages}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _json_dump(obj: Any) -> str:
    """Serialize *obj* to a compact JSON string."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
