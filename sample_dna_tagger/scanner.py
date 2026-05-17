"""
Scanner Engine — walks watch folders, runs local audio analysis, delegates to LLM.

Runs in a background thread pool. Processes only files that are new or
modified since last scan. Writes progress to scan_status table.

Audio analysis uses librosa for:
- BPM, key detection
- RMS energy, spectral centroid, spectral flatness, zero-crossing rate
- Instrument classification
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Audio file extensions we recognise
AUDIO_EXTENSIONS = frozenset(
    {".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg", ".m4a", ".opus"}
)


# ---------------------------------------------------------------------------
# Audio analysis (CPU-bound → offload to executor)
# ---------------------------------------------------------------------------

async def analyze_audio(file_path: str, executor: Optional[ThreadPoolExecutor] = None) -> dict:
    """Extract audio features using librosa. Offloads CPU-bound work to executor.

    Returns a dict with all extracted features. On failure, returns any
    features that succeeded plus an ``_error`` key.
    """
    loop = asyncio.get_event_loop()

    def _analyze() -> dict:
        features: dict = {}
        try:
            import numpy as np

            import librosa

            # Load audio — mono, native sample rate
            y, sr = librosa.load(file_path, sr=None, mono=True)
            if len(y) == 0:
                features["_error"] = "Empty audio file (zero samples)"
                return features

            # Duration
            features["duration_seconds"] = round(float(librosa.get_duration(y=y, sr=sr)), 3)

            # BPM — take first tempo value
            try:
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                features["bpm"] = round(float(tempo), 1) if tempo > 0 else None
            except Exception:
                features["bpm"] = None

            # RMS energy (mean across frames)
            try:
                rms = librosa.feature.rms(y=y)
                features["rms_energy"] = round(float(np.mean(rms)), 6)
            except Exception:
                features["rms_energy"] = None

            # Spectral centroid (mean across frames, in Hz)
            try:
                cent = librosa.feature.spectral_centroid(y=y, sr=sr)
                features["spectral_centroid"] = round(float(np.mean(cent)), 1)
            except Exception:
                features["spectral_centroid"] = None

            # Spectral flatness (mean across frames)
            try:
                flat = librosa.feature.spectral_flatness(y=y)
                features["spectral_flatness"] = round(float(np.mean(flat)), 6)
            except Exception:
                features["spectral_flatness"] = None

            # Zero-crossing rate (mean across frames)
            try:
                zcr = librosa.feature.zero_crossing_rate(y)
                features["zero_crossing_rate"] = round(float(np.mean(zcr)), 6)
            except Exception:
                features["zero_crossing_rate"] = None

            # Key — librosa's key estimation is unreliable; leave null
            features["key"] = None

        except Exception as exc:
            features["_error"] = str(exc)

        return features

    # Run the CPU-bound analysis in a thread pool
    if executor is not None:
        return await loop.run_in_executor(executor, _analyze)
    return await loop.run_in_executor(None, _analyze)


# ---------------------------------------------------------------------------
# Instrument classification (heuristics, before LLM refinement)
# ---------------------------------------------------------------------------

def classify_instrument(features: dict) -> str:
    """Basic heuristic instrument classification.

    Priority order:
    - Very short (< 0.5 s) + high ZCR → Drums
    - Low spectral centroid (< 500 Hz) → Bass
    - High spectral flatness (> 0.25) → FX
    - Default → Synth

    The LLM layer refines ``instrument_type`` and ``instrument_subtype`` later.
    """
    dur = features.get("duration_seconds")
    zcr = features.get("zero_crossing_rate")
    centroid = features.get("spectral_centroid")
    flatness = features.get("spectral_flatness")

    # Drums: very short, percussive (high ZCR)
    if (
        dur is not None
        and zcr is not None
        and dur < 0.5
        and zcr > 0.1
    ):
        return "Drums"

    # Bass: low spectral centroid
    if centroid is not None and centroid < 500:
        return "Bass"

    # FX / Atmosphere: noise-like (high spectral flatness)
    if flatness is not None and flatness > 0.25:
        return "FX"

    return "Synth"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_files(root_path: str, extensions: frozenset[str]) -> list[tuple[str, float, int]]:
    """Walk a directory and return (path, mtime, size) tuples for audio files.

    Offloaded to executor — may be slow for large trees.
    """
    results: list[tuple[str, float, int]] = []
    for dirpath, _dirnames, filenames in os.walk(root_path):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in extensions:
                continue
            full = os.path.join(dirpath, fname)
            try:
                st = os.stat(full)
                results.append((full, st.st_mtime, st.st_size))
            except OSError:
                continue
    return results


def _detect_pack_source(root_path: str, file_path: str) -> str:
    """Return the top-level folder under *root_path* that contains *file_path*.

    Examples::

        root = /library, file = /library/Kicks/808/boom.wav  →  "Kicks"
        root = /library, file = /library/loop.wav             →  ""
    """
    try:
        rel = os.path.relpath(file_path, root_path)
    except ValueError:
        return ""
    parts = rel.split(os.sep)
    if len(parts) > 1:
        return parts[0]
    return ""


def _flatten_llm_tags(llm_result: dict) -> list[str]:
    """Convert the structured LLM response into a flat list of tag strings
    suitable for the ``ai_tags`` JSON column (and FTS5 indexing)."""
    if not isinstance(llm_result, dict) or "error" in llm_result:
        return []

    tags: list[str] = []

    # Energy
    energy = llm_result.get("energy")
    if isinstance(energy, str):
        tags.append(f"{energy} energy")

    # Texture
    texture = llm_result.get("texture")
    if isinstance(texture, str):
        tags.append(f"{texture} texture")

    # Mood
    mood = llm_result.get("mood")
    if isinstance(mood, str):
        tags.append(f"{mood} mood")

    # Emotional quality
    eq_ = llm_result.get("emotional_quality")
    if isinstance(eq_, str):
        tags.append(eq_)

    # Motion
    motion = llm_result.get("motion")
    if isinstance(motion, str):
        tags.append(motion)

    # Instrument type / subtype (LLM-refined)
    inst_type = llm_result.get("instrument_type")
    if isinstance(inst_type, str):
        tags.append(inst_type)
    inst_sub = llm_result.get("instrument_subtype")
    if isinstance(inst_sub, str):
        tags.append(inst_sub)

    # Descriptive tags
    desc = llm_result.get("descriptive_tags")
    if isinstance(desc, list):
        for d in desc:
            if isinstance(d, str) and d.strip():
                tags.append(d.strip())

    return tags


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class Scanner:
    """Manages incremental scanning of watch folders."""

    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._scanning = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_root(self, root_path: str) -> str:
        """Add a watch folder, validate it, and trigger an initial scan."""
        from sample_dna_tagger.db import get_connection, new_uuid, utcnow

        # Normalise and validate
        root_path = os.path.abspath(os.path.expanduser(str(root_path)))
        if not os.path.isdir(root_path):
            raise ValueError(f"Not a directory: {root_path}")

        conn = await get_connection()
        try:
            # Check for duplicate
            cursor = await conn.execute(
                "SELECT id FROM scan_roots WHERE path = ?", (root_path,)
            )
            existing = await cursor.fetchone()
            if existing:
                # Already registered — trigger rescan
                root_id = existing["id"]
                asyncio.create_task(self.rescan_root(root_id))
                return root_id

            root_id = new_uuid()
            now = utcnow()
            await conn.execute(
                "INSERT INTO scan_roots (id, path, created_at) VALUES (?, ?, ?)",
                (root_id, root_path, now),
            )
            await conn.commit()
        finally:
            await conn.close()

        logger.info("Added scan root %s → %s", root_id, root_path)

        # Trigger initial scan in the background
        asyncio.create_task(self.rescan_root(root_id))
        return root_id

    async def remove_root(self, root_id: str) -> None:
        """Remove a watch folder and all its samples from the database."""
        from sample_dna_tagger.db import get_connection

        conn = await get_connection()
        try:
            # Find the root path first so we can delete its samples
            cursor = await conn.execute(
                "SELECT path FROM scan_roots WHERE id = ?", (root_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Scan root not found: {root_id}")

            root_path = row["path"]

            # Delete samples belonging to this root
            await conn.execute(
                "DELETE FROM samples WHERE path LIKE ? || '%'",
                (root_path + os.sep,),
            )
            await conn.execute(
                "DELETE FROM samples WHERE path = ?", (root_path,)
            )

            # Delete the scan root
            await conn.execute("DELETE FROM scan_roots WHERE id = ?", (root_id,))
            await conn.commit()
        finally:
            await conn.close()

        logger.info("Removed scan root %s", root_id)

    async def scan_all(self) -> None:
        """Start a full scan of all enabled watch folders."""
        from sample_dna_tagger.db import get_connection

        if self._scanning:
            logger.warning("Scan already in progress, skipping")
            return

        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT id, path FROM scan_roots WHERE enabled = 1"
            )
            roots = await cursor.fetchall()
        finally:
            await conn.close()

        if not roots:
            logger.info("No enabled scan roots to scan")
            return

        logger.info("Starting full scan of %d root(s)", len(roots))
        self._scanning = True
        try:
            for row in roots:
                await self._scan_root(row["id"], row["path"])
        finally:
            self._scanning = False

    async def rescan_root(self, root_id: str) -> None:
        """Rescan a single watch folder."""
        from sample_dna_tagger.db import get_connection

        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT path FROM scan_roots WHERE id = ?", (root_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Scan root not found: {root_id}")
            root_path = row["path"]
        finally:
            await conn.close()

        logger.info("Rescanning root %s → %s", root_id, root_path)
        await self._scan_root(root_id, root_path)

    async def get_status(self) -> dict:
        """Return current scan status from the ``scan_status`` table."""
        from sample_dna_tagger.db import get_connection

        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT state, total_files, processed_files, current_file, "
                "started_at, finished_at FROM scan_status WHERE id = 1"
            )
            row = await cursor.fetchone()
        finally:
            await conn.close()

        if row is None:
            return {
                "state": "idle",
                "total_files": 0,
                "processed_files": 0,
                "current_file": None,
                "started_at": None,
                "finished_at": None,
            }
        return dict(row)

    def is_audio_file(self, path: str) -> bool:
        """Return True if *path* has a recognised audio extension."""
        return Path(path).suffix.lower() in AUDIO_EXTENSIONS

    # ------------------------------------------------------------------
    # Internal scan logic
    # ------------------------------------------------------------------

    async def _scan_root(self, root_id: str, root_path: str) -> None:
        """Walk *root_path*, analyze audio files, and write results to the DB.

        Steps:
        1. Mark scan_status as 'scanning'
        2. Collect audio files (offloaded to executor)
        3. For each new/modified file: analyze → classify → LLM-tag → insert
        4. Update scan_root stats
        5. Mark scan_status as 'idle'
        """
        from sample_dna_tagger.db import get_connection, new_uuid, utcnow
        from sample_dna_tagger.llm import llm_client

        if not os.path.isdir(root_path):
            logger.error("Scan root path no longer exists: %s", root_path)
            return

        # --- Step 1: mark scanning ---
        conn = await get_connection()
        try:
            now = utcnow()
            await conn.execute(
                "UPDATE scan_status SET state = 'scanning', started_at = ?, "
                "processed_files = 0, total_files = 0, current_file = NULL, "
                "finished_at = NULL WHERE id = 1",
                (now,),
            )
            await conn.commit()

            # --- Step 2: collect audio files (offloaded) ---
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                self.executor,
                _collect_files,
                root_path,
                AUDIO_EXTENSIONS,
            )
            total = len(files)
            await conn.execute(
                "UPDATE scan_status SET total_files = ? WHERE id = 1", (total,)
            )
            await conn.commit()

            processed = 0
            error_count = 0

            # --- Step 3: process each file ---
            for file_path, file_mtime, file_size in files:
                # Skip if already in DB with same mtime
                cursor = await conn.execute(
                    "SELECT id, ai_tags, user_tags, instrument_type, instrument_subtype "
                    "FROM samples WHERE path = ? AND file_mtime = ?",
                    (file_path, file_mtime),
                )
                existing = await cursor.fetchone()
                if existing:
                    processed += 1
                    continue

                filename = os.path.basename(file_path)
                folder = os.path.dirname(file_path)
                pack_source = _detect_pack_source(root_path, file_path)

                # Analyse audio (CPU-bound)
                features = await analyze_audio(file_path, self.executor)

                if "_error" in features:
                    # Log error and skip
                    error_id = new_uuid()
                    await conn.execute(
                        "INSERT INTO scan_errors (id, sample_path, error_type, "
                        "error_message, occurred_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            error_id,
                            file_path,
                            "analysis_failure",
                            features["_error"],
                            utcnow(),
                        ),
                    )
                    error_count += 1
                    processed += 1
                    # Update progress
                    await conn.execute(
                        "UPDATE scan_status SET processed_files = ?, "
                        "current_file = ? WHERE id = 1",
                        (processed, file_path),
                    )
                    await conn.commit()
                    continue

                # Heuristic instrument classification
                features["instrument_category"] = classify_instrument(features)

                # Prepare DB row values (analysis-derived fields)
                sample_id = new_uuid() if existing is None else existing["id"]
                duration_s = features.get("duration_seconds")
                bpm = features.get("bpm")
                key = features.get("key")
                rms = features.get("rms_energy")
                centroid = features.get("spectral_centroid")
                flatness = features.get("spectral_flatness")
                zcr = features.get("zero_crossing_rate")
                inst_cat = features.get("instrument_category")
                inst_type = None
                inst_sub = None
                ai_tags_json = "[]"

                # --- LLM tagging ---
                try:
                    llm_result = await llm_client.generate_tags(features)
                    if "error" not in llm_result:
                        # Refine instrument type/subtype from LLM
                        inst_type = llm_result.get("instrument_type")
                        inst_sub = llm_result.get("instrument_subtype")

                        # Flatten structured response to tag list
                        flat_tags = _flatten_llm_tags(llm_result)
                        if flat_tags:
                            ai_tags_json = json.dumps(flat_tags, ensure_ascii=False)
                except RuntimeError:
                    # LLM client not configured — store without AI tags
                    pass
                except Exception as exc:
                    logger.warning("LLM tagging failed for %s: %s", file_path, exc)

                # Build the features dict we'll pass to the LLM next time
                # (only analysis features, not LLM output)
                analysis_features = {
                    k: v
                    for k, v in features.items()
                    if k not in ("instrument_category", "_error")
                }

                # Determine whether to insert or update
                cursor = await conn.execute(
                    "SELECT id FROM samples WHERE path = ?", (file_path,)
                )
                row = await cursor.fetchone()

                if row:
                    # Update existing (preserve user_tags, rating, play stats)
                    await conn.execute(
                        "UPDATE samples SET "
                        "filename = ?, folder = ?, duration_seconds = ?, bpm = ?, "
                        "key = ?, rms_energy = ?, spectral_centroid = ?, "
                        "spectral_flatness = ?, zero_crossing_rate = ?, "
                        "instrument_category = ?, instrument_type = ?, "
                        "instrument_subtype = ?, pack_source = ?, ai_tags = ?, "
                        "file_mtime = ?, file_size = ?, updated_at = ? "
                        "WHERE path = ?",
                        (
                            filename,
                            folder,
                            duration_s,
                            bpm,
                            key,
                            rms,
                            centroid,
                            flatness,
                            zcr,
                            inst_cat,
                            inst_type,
                            inst_sub,
                            pack_source,
                            ai_tags_json,
                            file_mtime,
                            file_size,
                            utcnow(),
                            file_path,
                        ),
                    )
                else:
                    # Insert new
                    now_ts = utcnow()
                    await conn.execute(
                        "INSERT INTO samples ("
                        "id, path, filename, folder, duration_seconds, bpm, key, "
                        "rms_energy, spectral_centroid, spectral_flatness, "
                        "zero_crossing_rate, instrument_category, instrument_type, "
                        "instrument_subtype, pack_source, ai_tags, file_mtime, "
                        "file_size, created_at, updated_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            new_uuid(),
                            file_path,
                            filename,
                            folder,
                            duration_s,
                            bpm,
                            key,
                            rms,
                            centroid,
                            flatness,
                            zcr,
                            inst_cat,
                            inst_type,
                            inst_sub,
                            pack_source,
                            ai_tags_json,
                            file_mtime,
                            file_size,
                            now_ts,
                            now_ts,
                        ),
                    )

                processed += 1

                # Incremental progress update
                await conn.execute(
                    "UPDATE scan_status SET processed_files = ?, "
                    "current_file = ? WHERE id = 1",
                    (processed, file_path),
                )
                await conn.commit()

            # --- Step 4: update scan_root stats ---
            await conn.execute(
                "UPDATE scan_roots SET last_scanned_at = ?, file_count = ? "
                "WHERE id = ?",
                (utcnow(), processed - error_count, root_id),
            )

            # --- Step 5: mark idle ---
            await conn.execute(
                "UPDATE scan_status SET state = 'idle', finished_at = ? WHERE id = 1",
                (utcnow(),),
            )
            await conn.commit()

            logger.info(
                "Scan complete for %s: %d files, %d errors",
                root_path,
                processed,
                error_count,
            )

        except Exception:
            logger.exception("Scan failed for root %s", root_id)
            try:
                await conn.execute(
                    "UPDATE scan_status SET state = 'error', finished_at = ? "
                    "WHERE id = 1",
                    (utcnow(),),
                )
                await conn.commit()
            except Exception:
                pass
            raise
        finally:
            await conn.close()


# Singleton
scanner = Scanner()
