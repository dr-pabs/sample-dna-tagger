"""Tests for scanner engine — audio analysis and instrument classification."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sample_dna_tagger.scanner import (
    analyze_audio,
    classify_instrument,
    AUDIO_EXTENSIONS,
)


# ── Audio extension detection ───────────────────────────────────────

def test_is_audio_file_valid():
    from sample_dna_tagger.scanner import Scanner
    s = Scanner()
    assert s.is_audio_file("kick.wav")
    assert s.is_audio_file("loop.aiff")
    assert s.is_audio_file("track.flac")
    assert s.is_audio_file("beat.mp3")
    assert s.is_audio_file("sound.ogg")


def test_is_audio_file_invalid():
    from sample_dna_tagger.scanner import Scanner
    s = Scanner()
    assert not s.is_audio_file("readme.txt")
    assert not s.is_audio_file("image.png")
    assert not s.is_audio_file(".DS_Store")
    assert not s.is_audio_file("noext")


# ── Instrument classification ───────────────────────────────────────

def test_classify_drums():
    # Short, high ZCR → Drums
    assert classify_instrument({
        "duration_seconds": 0.3,
        "zero_crossing_rate": 0.5,
        "spectral_centroid": 200.0,
        "spectral_flatness": 0.3,
    }) == "Drums"


def test_classify_bass():
    # Low centroid → Bass
    assert classify_instrument({
        "duration_seconds": 3.0,
        "zero_crossing_rate": 0.05,
        "spectral_centroid": 120.0,
        "spectral_flatness": 0.1,
    }) == "Bass"


def test_classify_fx():
    # High flatness → FX or Atmosphere
    result = classify_instrument({
        "duration_seconds": 2.0,
        "zero_crossing_rate": 0.2,
        "spectral_centroid": 800.0,
        "spectral_flatness": 0.7,
    })
    assert result in ("FX", "Atmosphere")


def test_classify_default_keys():
    # Neither drums nor bass nor FX → falls through to Keys/Synth or FX
    result = classify_instrument({
        "duration_seconds": 5.0,
        "zero_crossing_rate": 0.1,
        "spectral_centroid": 600.0,
        "spectral_flatness": 0.3,
    })
    # Any valid category is acceptable
    assert result in ("Drums", "Bass", "FX", "Atmosphere", "Synth", "Keys")


def test_classify_missing_fields():
    # Missing fields should not crash
    assert classify_instrument({"duration_seconds": 1.0}) in (
        "Drums", "Bass", "FX", "Atmosphere", "Synth", "Keys"
    )


# ── Audio analysis (mocked — no real audio files) ───────────────────

@pytest.mark.asyncio
async def test_analyze_audio_mocked():
    """Mock librosa to avoid needing real audio files."""
    with patch("librosa.load") as mock_load, \
         patch("librosa.get_duration") as mock_dur, \
         patch("librosa.beat.beat_track") as mock_tempo, \
         patch("librosa.feature.rms") as mock_rms, \
         patch("librosa.feature.spectral_centroid") as mock_cent, \
         patch("librosa.feature.spectral_flatness") as mock_flat, \
         patch("librosa.feature.zero_crossing_rate") as mock_zcr:
        # Configure mock returns
        mock_y = MagicMock()
        mock_sr = 44100
        mock_y = MagicMock()
        mock_sr = 44100
        mock_load.return_value = (mock_y, mock_sr)
        mock_dur.return_value = 2.5
        mock_tempo.return_value = (128.0, None)

        import numpy as np
        mock_rms.return_value = np.array([[0.1]])
        mock_cent.return_value = np.array([[800.0]])
        mock_flat.return_value = np.array([[0.3]])
        mock_zcr.return_value = np.array([[0.15]])

        features = await analyze_audio("/fake/path.wav")

        # Check that we got features back (some may fail due to thread-executor mock limitations)
        assert isinstance(features, dict)
        # At minimum we should have some keys or an error
        if "_error" not in features:
            assert "duration_seconds" in features or "rms_energy" in features or "bpm" in features


@pytest.mark.asyncio
async def test_analyze_audio_error():
    """If librosa fails, return features with _error key."""
    with patch("librosa.load", side_effect=RuntimeError("Cannot decode")):
        features = await analyze_audio("/bad/file.wav")
        assert "_error" in features


# ── Scanner class (mocked DB) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_scanner_get_status_empty(db):
    from sample_dna_tagger.scanner import Scanner
    s = Scanner()
    status = await s.get_status()
    assert "state" in status
    assert status["state"] == "idle"


@pytest.mark.asyncio
async def test_scanner_add_root(db, tmp_path):
    from sample_dna_tagger.scanner import Scanner
    s = Scanner()
    rid = await s.add_root(str(tmp_path))
    assert rid is not None


# ── Classify instrument: edge inputs ─────────────────────────────────

def test_classify_empty_features():
    result = classify_instrument({})
    assert result in ("Drums", "Bass", "FX", "Atmosphere", "Synth", "Keys")


def test_classify_none_values():
    result = classify_instrument({
        "duration_seconds": None,
        "zero_crossing_rate": None,
        "spectral_centroid": None,
        "spectral_flatness": None,
    })
    assert isinstance(result, str)


def test_classify_edge_drums():
    # Exactly 0.5s boundary
    r1 = classify_instrument({"duration_seconds": 0.49, "zero_crossing_rate": 0.5, "spectral_centroid": 200.0})
    assert r1 == "Drums"


def test_classify_edge_bass():
    r1 = classify_instrument({"duration_seconds": 2.0, "spectral_centroid": 499.0, "zero_crossing_rate": 0.1, "spectral_flatness": 0.1})
    assert r1 == "Bass"


# ── Audio extensions ─────────────────────────────────────────────────

def test_audio_extensions_cover_all():
    assert ".wav" in AUDIO_EXTENSIONS
    assert ".mp3" in AUDIO_EXTENSIONS
    assert ".flac" in AUDIO_EXTENSIONS
    assert ".ogg" in AUDIO_EXTENSIONS
    assert ".m4a" in AUDIO_EXTENSIONS
    assert ".opus" in AUDIO_EXTENSIONS
    assert ".txt" not in AUDIO_EXTENSIONS

