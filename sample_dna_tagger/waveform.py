"""
Waveform generation — renders small PNG waveforms from audio files.

Caches waveforms in ~/.sample-dna-tagger/waveforms/{sample_id}.png
so they are only generated once per sample.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Cache directory — same parent as the DB
WAVEFORM_DIR = Path(
    os.environ.get(
        "SAMPLE_DNA_WAVEFORMS",
        Path.home() / ".sample-dna-tagger" / "waveforms",
    )
)

# Default dimensions (width should match the frontend placeholder)
DEFAULT_WIDTH = 400
DEFAULT_HEIGHT = 60

# Theme colours matching the dark UI
BG_COLOUR = (30, 30, 50)
WAVE_COLOUR = (99, 102, 241)  # indigo accent


def _get_cache_path(sample_id: str) -> Path:
    """Return the filesystem path for a sample's cached waveform PNG."""
    WAVEFORM_DIR.mkdir(parents=True, exist_ok=True)
    return WAVEFORM_DIR / f"{sample_id}.png"


def generate_waveform(
    audio_path: str,
    sample_id: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    force: bool = False,
) -> Optional[Path]:
    """Generate a waveform PNG for an audio file and cache it.

    Returns the path to the PNG, or ``None`` on failure.
    If the cached PNG already exists and *force* is ``False``,
    the cached path is returned immediately.
    """
    cache_path = _get_cache_path(sample_id)
    if cache_path.exists() and not force:
        return cache_path

    try:
        from PIL import Image, ImageDraw

        import librosa

        # Load audio (mono, downsampled for speed)
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        if len(y) == 0:
            logger.warning("Empty audio file, skipping waveform: %s", audio_path)
            return None

        # Downsample amplitude envelope to *width* points
        hop = max(1, len(y) // width)
        frames = np.array(
            [np.max(np.abs(y[i * hop : (i + 1) * hop])) for i in range(width)]
        )

        # Create image
        img = Image.new("RGB", (width, height), BG_COLOUR)
        draw = ImageDraw.Draw(img)
        mid = height // 2

        for i, amp in enumerate(frames):
            h = int(amp * mid * 0.95)  # 95% of half-height max
            if h < 1:
                continue
            draw.line([(i, mid - h), (i, mid + h)], fill=WAVE_COLOUR, width=1)

        img.save(cache_path, "PNG")
        logger.debug("Waveform saved: %s", cache_path)
        return cache_path

    except Exception:
        logger.exception("Failed to generate waveform for %s", audio_path)
        return None


def get_waveform_path(sample_id: str) -> Optional[Path]:
    """Return the cached waveform path if it exists, else ``None``."""
    cache_path = _get_cache_path(sample_id)
    return cache_path if cache_path.exists() else None


def delete_waveform(sample_id: str) -> None:
    """Remove the cached waveform PNG for a sample."""
    cache_path = _get_cache_path(sample_id)
    if cache_path.exists():
        cache_path.unlink()
        logger.debug("Deleted waveform: %s", cache_path)
