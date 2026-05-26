"""
File-system watcher — monitors scan roots for changes and triggers
incremental scans or immediate deletions.

Uses watchdog in a background thread. Bridges to asyncio for DB operations.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from sample_dna_tagger.db import get_connection
from sample_dna_tagger.scanner import AUDIO_EXTENSIONS

logger = logging.getLogger(__name__)

# Debounce delay in seconds — batch rapid events into a single rescan
_DEBOUNCE_SECONDS = 2.0


def _is_audio_file(path: str) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


class _SampleEventHandler(FileSystemEventHandler):
    """Handles filesystem events for a single scan root."""

    def __init__(
        self,
        root_id: str,
        root_path: str,
        loop: asyncio.AbstractEventLoop,
        scanner,
    ):
        self.root_id = root_id
        self.root_path = os.path.abspath(root_path)
        self.loop = loop
        self.scanner = scanner
        self._debounce_timer: Optional[threading.Timer] = None

    def _schedule_rescan(self) -> None:
        """Debounce rapid events into a single background rescan."""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()

        root_id = self.root_id
        loop = self.loop
        scanner = self.scanner

        def _run() -> None:
            if scanner._scanning:
                logger.debug("Scan already in progress, skipping watcher-triggered rescan")
                return
            asyncio.run_coroutine_threadsafe(
                scanner.rescan_root(root_id), loop
            )

        self._debounce_timer = threading.Timer(_DEBOUNCE_SECONDS, _run)
        self._debounce_timer.daemon = True
        self._debounce_timer.start()

    def _delete_sample(self, path: str) -> None:
        """Immediately remove a sample from the DB when its file is deleted."""
        abs_path = os.path.abspath(path)

        async def _do_delete() -> None:
            try:
                conn = await get_connection()
                try:
                    cursor = await conn.execute(
                        "SELECT id FROM samples WHERE path = ?", (abs_path,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        await conn.execute(
                            "DELETE FROM samples WHERE path = ?", (abs_path,)
                        )
                        await conn.commit()
                        logger.info("Removed deleted sample: %s", abs_path)
                finally:
                    await conn.close()
            except Exception:
                logger.exception("Failed to delete sample for path: %s", abs_path)

        asyncio.run_coroutine_threadsafe(_do_delete(), self.loop)

    def _delete_under_dir(self, dir_path: str) -> None:
        """Remove all samples under a deleted directory."""
        abs_path = os.path.abspath(dir_path)

        async def _do_delete() -> None:
            try:
                conn = await get_connection()
                try:
                    await conn.execute(
                        "DELETE FROM samples WHERE path LIKE ? || '%'",
                        (abs_path + os.sep,),
                    )
                    await conn.commit()
                    logger.info("Removed samples under deleted dir: %s", abs_path)
                finally:
                    await conn.close()
            except Exception:
                logger.exception("Failed to delete samples for dir: %s", abs_path)

        asyncio.run_coroutine_threadsafe(_do_delete(), self.loop)

    # ------------------------------------------------------------------
    # Event callbacks (run in watchdog thread)
    # ------------------------------------------------------------------

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if _is_audio_file(event.src_path):
            logger.debug("File created: %s", event.src_path)
            self._schedule_rescan()

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if _is_audio_file(event.src_path):
            logger.debug("File modified: %s", event.src_path)
            self._schedule_rescan()

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            self._delete_under_dir(event.src_path)
        elif _is_audio_file(event.src_path):
            logger.debug("File deleted: %s", event.src_path)
            self._delete_sample(event.src_path)

    def on_moved(self, event) -> None:
        # Treat as delete at old path + create at new path
        if not event.is_directory:
            if _is_audio_file(event.src_path):
                self._delete_sample(event.src_path)
            if _is_audio_file(event.dest_path):
                self._schedule_rescan()


class WatcherManager:
    """Manages watchdog observers for all scan roots."""

    def __init__(self) -> None:
        self.observer = Observer()
        self._handlers: dict[str, _SampleEventHandler] = {}  # root_id -> handler
        self._watches: dict[str, object] = {}  # root_id -> watchdog Watch
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def add_root(self, root_id: str, root_path: str, scanner) -> None:
        """Start watching a scan root."""
        if root_id in self._watches:
            logger.warning("Root %s already watched, skipping", root_id)
            return

        loop = self._loop or asyncio.get_event_loop()
        handler = _SampleEventHandler(root_id, root_path, loop, scanner)
        watch = self.observer.schedule(handler, root_path, recursive=True)
        self._handlers[root_id] = handler
        self._watches[root_id] = watch
        logger.info("Started watching root %s: %s", root_id, root_path)

    def remove_root(self, root_id: str) -> None:
        """Stop watching a scan root."""
        if root_id not in self._watches:
            return
        watch = self._watches.pop(root_id)
        self.observer.unschedule(watch)
        self._handlers.pop(root_id, None)
        logger.info("Stopped watching root %s", root_id)

    def start(self) -> None:
        self.observer.start()
        logger.info("File-system watcher started")

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join()
        logger.info("File-system watcher stopped")


# Singleton
watcher = WatcherManager()
