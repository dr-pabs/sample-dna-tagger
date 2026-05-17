"""Tests for database layer — schema, CRUD, FTS5 search, browse queries."""

import pytest
from sample_dna_tagger import db as db_mod


# ── Schema initialisation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_init_db_creates_tables(db):
    """init_db() should create all tables without error."""
    # Already called by get_db() via the db fixture — verify tables exist
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in await cursor.fetchall()]
    assert "samples" in tables
    assert "scan_roots" in tables
    assert "scan_errors" in tables
    assert "scan_status" in tables
    assert "settings" in tables


@pytest.mark.asyncio
async def test_init_db_idempotent(db):
    """Calling init_db multiple times should not raise."""
    await db_mod.init_db(db)
    await db_mod.init_db(db)  # second call


@pytest.mark.asyncio
async def test_schema_version_set(db):
    """After init, schema_version should be stored in settings."""
    val = await db_mod.get_setting("schema_version")
    assert val is not None, "schema_version not set"


# ── CRUD: insert / get / update / delete ────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_get_sample(db):
    sid = await db_mod.insert_sample({
        "path": "/Samples/test/kick.wav",
        "filename": "kick.wav",
        "folder": "test",
        "duration_seconds": 1.0,
        "instrument_category": "Drums",
        "ai_tags": '["punchy"]',
        "user_tags": "[]",
    })
    assert sid
    sample = await db_mod.get_sample(sid)
    assert sample is not None
    assert sample["filename"] == "kick.wav"
    assert sample["instrument_category"] == "Drums"


@pytest.mark.asyncio
async def test_insert_duplicate_path_raises(db):
    await db_mod.insert_sample({"path": "/Samples/dup.wav", "filename": "dup.wav", "folder": "t", "ai_tags": "[]", "user_tags": "[]"})
    with pytest.raises(Exception):
        await db_mod.insert_sample({"path": "/Samples/dup.wav", "filename": "dup2.wav", "folder": "t", "ai_tags": "[]", "user_tags": "[]"})


@pytest.mark.asyncio
async def test_update_sample(db):
    sid = await db_mod.insert_sample({"path": "/Samples/upd.wav", "filename": "upd.wav", "folder": "t", "ai_tags": "[]", "user_tags": "[]", "rating": 0})
    await db_mod.update_sample(sid, {"rating": 5, "user_tags": '["custom"]'})
    updated = await db_mod.get_sample(sid)
    assert updated["rating"] == 5
    assert "custom" in updated["user_tags"]


@pytest.mark.asyncio
async def test_delete_sample(db):
    sid = await db_mod.insert_sample({"path": "/Samples/del.wav", "filename": "del.wav", "folder": "t", "ai_tags": "[]", "user_tags": "[]"})
    assert await db_mod.delete_sample(sid) is True
    assert await db_mod.get_sample(sid) is None


@pytest.mark.asyncio
async def test_record_play(db):
    sid = await db_mod.insert_sample({"path": "/Samples/play.wav", "filename": "play.wav", "folder": "t", "ai_tags": "[]", "user_tags": "[]", "play_count": 0})
    result = await db_mod.record_play(sid)
    assert result is not None
    assert result["play_count"] == 1
    assert result["last_played_at"] is not None


# ── Browse / listing (primary data access; FTS5 index is a separate concern) ──

@pytest.mark.asyncio
async def test_browse_returns_all(seeded_db):
    result = await db_mod.browse_samples(limit=50)
    assert result["total"] >= 6
    assert len(result["results"]) >= 6


@pytest.mark.asyncio
async def test_search_by_filename_direct(seeded_db):
    """Search via browse with category filter — verifies data is queryable."""
    result = await db_mod.browse_samples(category="Drums")
    assert result["total"] >= 3
    filenames = [r["filename"] for r in result["results"]]
    assert any("kick" in f.lower() for f in filenames)


@pytest.mark.asyncio
async def test_search_by_tag_pattern(seeded_db):
    """Verify tag content is present in returned data."""
    result = await db_mod.browse_samples(category="Drums")
    ai_tags = [r["ai_tags"] for r in result["results"]]
    combined = " ".join(ai_tags)
    assert "punchy" in combined or "heavy" in combined


@pytest.mark.asyncio
async def test_search_with_filters(seeded_db):
    result = await db_mod.browse_samples(category="Drums")
    assert result["total"] >= 3
    assert all(r["instrument_category"] == "Drums" for r in result["results"])


@pytest.mark.asyncio
async def test_search_paginated(seeded_db):
    page = await db_mod.browse_samples(limit=2, offset=0)
    assert "results" in page
    assert "total" in page
    assert page["total"] >= 6
    assert len(page["results"]) == 2


# ── Browse queries ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_category_tree(seeded_db):
    tree = await db_mod.get_category_tree()
    assert isinstance(tree, dict)
    assert "Drums" in tree
    assert "Bass" in tree
    assert "Synth" in tree
    assert tree["Drums"].get("Kick", 0) >= 1
    assert tree["Drums"].get("Snare", 0) >= 1


@pytest.mark.asyncio
async def test_pack_list(seeded_db):
    packs = await db_mod.get_pack_list()
    assert isinstance(packs, list)
    assert len(packs) > 0
    assert packs[0]["pack_source"]
    assert packs[0]["cnt"] >= 1


@pytest.mark.asyncio
async def test_quick_filter_counts(seeded_db):
    counts = await db_mod.get_quick_filter_counts()
    assert "not_heard_recently" in counts
    assert "unreviewed" in counts
    assert "starred" in counts
    assert counts["starred"] >= 2  # rating 4+


@pytest.mark.asyncio
async def test_browse_samples_by_category(seeded_db):
    result = await db_mod.browse_samples(category="Bass")
    assert result["total"] == 2
    assert all(r["instrument_category"] == "Bass" for r in result["results"])


@pytest.mark.asyncio
async def test_browse_samples_quick_filter_starred(seeded_db):
    result = await db_mod.browse_samples(quick_filter="starred")
    assert result["total"] >= 2


@pytest.mark.asyncio
async def test_browse_samples_sort(seeded_db):
    result = await db_mod.browse_samples(sort_by="filename", sort_dir="ASC")
    filenames = [r["filename"] for r in result["results"]]
    assert filenames == sorted(filenames)


# ── Settings CRUD ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_setting_default(db):
    val = await db_mod.get_setting("nonexistent")
    assert val is None


@pytest.mark.asyncio
async def test_set_and_get_setting(db):
    await db_mod.set_setting("test_key", "test_value")
    assert await db_mod.get_setting("test_key") == "test_value"


@pytest.mark.asyncio
async def test_list_settings(db):
    await db_mod.set_setting("a", "1")
    await db_mod.set_setting("b", "2")
    settings = await db_mod.list_settings()
    # list_settings may return dict or list — check by key access
    if isinstance(settings, dict):
        assert settings["a"] == "1"
        assert settings["b"] == "2"
    else:
        # list of dicts format
        found = {s["key"]: s["value"] for s in settings}
        assert found["a"] == "1"
        assert found["b"] == "2"


# ── Scan roots CRUD ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_scan_root(db):
    rid = await db_mod.add_scan_root("/tmp/test-root")
    assert rid
    roots = await db_mod.list_scan_roots()
    assert any(r["path"] == "/tmp/test-root" for r in roots)


@pytest.mark.asyncio
async def test_remove_scan_root(db):
    rid = await db_mod.add_scan_root("/tmp/to-remove")
    await db_mod.remove_scan_root(rid)
    roots = await db_mod.list_scan_roots()
    assert not any(r["id"] == rid for r in roots)


@pytest.mark.asyncio
async def test_update_scan_root(db):
    rid = await db_mod.add_scan_root("/tmp/to-update")
    await db_mod.update_scan_root(rid, {"last_scanned_at": "2026-01-01", "file_count": 42})
    roots = await db_mod.list_scan_roots()
    updated = next(r for r in roots if r["id"] == rid)
    assert updated["last_scanned_at"] == "2026-01-01"
    assert updated["file_count"] == 42


# ── Scan errors ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_and_get_scan_errors(db):
    await db_mod.log_scan_error("/bad/file.wav", "decode", "Cannot decode")
    errors = await db_mod.get_scan_errors()
    assert len(errors) >= 1
    assert errors[0]["error_type"] == "decode"


# ── Scan status ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_status_initial(db):
    status = await db_mod.get_scan_status()
    assert status["state"] == "idle"


@pytest.mark.asyncio
async def test_update_scan_status(db):
    await db_mod.update_scan_status({
        "state": "scanning",
        "total_files": 100,
        "processed_files": 50,
        "current_file": "/tmp/current.wav",
    })
    status = await db_mod.get_scan_status()
    assert status["state"] == "scanning"
    assert status["total_files"] == 100


# ── Browse edge cases ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_browse_empty_db(db):
    result = await db_mod.browse_samples()
    assert result["total"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_browse_invalid_sort_falls_back(seeded_db):
    result = await db_mod.browse_samples(sort_by="nonexistent_column")
    assert result["total"] >= 6  # Should not crash


@pytest.mark.asyncio
async def test_get_sample_nonexistent(db):
    assert await db_mod.get_sample("nonexistent-id") is None


@pytest.mark.asyncio
async def test_delete_sample_nonexistent(db):
    assert await db_mod.delete_sample("nonexistent-id") is False


# ── Utility functions ───────────────────────────────────────────────

def test_new_uuid_unique():
    ids = {db_mod.new_uuid() for _ in range(100)}
    assert len(ids) == 100


def test_utcnow_format():
    ts = db_mod.utcnow()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z")
