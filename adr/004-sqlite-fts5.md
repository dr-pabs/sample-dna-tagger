# ADR-004: SQLite with FTS5 Full-Text Search

**Date:** 2026-05-17  
**Status:** Accepted

## Context

The app needs to store tens of thousands of samples with audio features, AI tags, and user tags — and support fast full-text search across filenames and tags. It's a single-user desktop app with no concurrent write contention.

## Decision

**Chose SQLite with FTS5 virtual table.**

## Rationale

1. **Zero administration**: No server process, no connection strings, no user setup. The database is a single file in `~/.sample-dna-tagger/library.db`.
2. **FTS5 built-in**: SQLite's FTS5 extension provides full-text search with ranking, prefix queries, and phrase matching — all from a virtual table that stays in sync with the main table via triggers.
3. **Single writer**: SQLite's write serialization is not a problem for a single-user desktop app with one background scanner thread.
4. **Packaged with PyInstaller**: SQLite ships with Python's standard library — no extra binary to bundle.
5. **WAL mode**: Write-Ahead Logging enables concurrent reads during writes (scanner writes while UI reads).

## Schema Design

- **samples**: Main table with all audio features, tags (as JSON TEXT), and metadata. `path` is UNIQUE — identity is file path.
- **scan_roots**: Watch folders the user has added.
- **scan_errors**: Per-file error log for failed analysis.
- **scan_status**: Singleton row (id=1) tracking current scan progress.
- **settings**: Key/value pairs for LLM config, preferences.
- **fts_index**: FTS5 content table over `samples`, indexing `filename`, `ai_tags`, and `user_tags`. Kept in sync via INSERT/UPDATE/DELETE triggers.

## FTS5 Query Strategy

- Text queries match against the concatenated filename + AI tags + user tags
- Relevance ranking via `bm25()` or default FTS5 ranking
- Filters (category, type, energy, etc.) are applied as WHERE clauses on the samples table joined with FTS results
- For browse queries (no text), the main samples table is queried directly with GROUP BY aggregations

## Consequences

- Tags stored as JSON arrays in TEXT columns — requires `json_each()` for some queries, but acceptable for a single-user app
- FTS5 triggers add write overhead on every insert/update/delete (acceptable at ~100 samples/second scan rate)
- No built-in migration system — using `CREATE TABLE IF NOT EXISTS` as a simple forward-compatible approach
- Database file can grow large with full FTS index (~2x raw data size); tested fine at 50K samples
