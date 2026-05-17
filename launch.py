#!/usr/bin/env python3
"""
Launch script — starts the FastAPI server on a free port, waits for it to
respond, then opens a native pywebview window. On window close, the server
process exits.

Usage:
    python launch.py              # production: serves built frontend
    python launch.py --dev        # development: proxies to Vite dev server
"""

from __future__ import annotations

import argparse
import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("launch")


def find_free_port() -> int:
    """Return an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build_frontend() -> bool:
    """Run 'npm run build' in the frontend directory. Returns True on success."""
    frontend_dir = Path(__file__).resolve().parent / "frontend"
    if not (frontend_dir / "package.json").exists():
        logger.warning("frontend/ not found — skipping build")
        return False

    logger.info("Building frontend...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Frontend build failed:\n%s", result.stderr)
        return False
    logger.info("Frontend built successfully")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample DNA Tagger")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    parser.add_argument("--port", type=int, default=0, help="Port (0 = auto)")
    parser.add_argument("--no-window", action="store_true", help="Run server only, no window")
    args = parser.parse_args()

    port = args.port or find_free_port()
    url = f"http://127.0.0.1:{port}"

    if not args.dev:
        if not (Path(__file__).resolve().parent / "frontend" / "dist").is_dir():
            if not build_frontend():
                sys.exit(1)

    logger.info("Starting server on %s", url)

    # Start FastAPI via uvicorn in the main thread.
    # pywebview must run on the main thread on macOS, so we start the server
    # in a daemon thread then open the window.
    import threading

    server_thread = threading.Thread(
        target=uvicorn.run,
        args=("sample_dna_tagger.server:app",),
        kwargs={"host": "127.0.0.1", "port": port, "log_level": "info"},
        daemon=True,
    )
    server_thread.start()

    # Wait for the server to become responsive
    import urllib.request

    for _ in range(50):
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    else:
        logger.error("Server did not start within 5 seconds")
        sys.exit(1)

    logger.info("Server ready at %s", url)

    if args.no_window:
        logger.info("Running headless — server will stay up until Ctrl+C")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down")
        return

    import webview

    # Window title
    title = "Sample DNA Tagger"

    if args.dev:
        # In dev mode, use the Vite dev server URL (typically port 5173)
        dev_url = "http://localhost:5173"
        logger.info("Opening dev window to %s", dev_url)
        window = webview.create_window(title, dev_url, width=1200, height=800, min_size=(900, 600))
    else:
        window = webview.create_window(title, url, width=1200, height=800, min_size=(900, 600))

    webview.start()
    logger.info("Window closed — exiting")


if __name__ == "__main__":
    main()
