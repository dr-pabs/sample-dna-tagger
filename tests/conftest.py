"""Shared test fixtures for Sample DNA Tagger."""

import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _test_db_env(monkeypatch, tmp_path):
    """Redirect the database to a temp path for every test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("SAMPLE_DNA_DB", str(db_file))
    import sample_dna_tagger.db as db_mod

    db_mod.DB_PATH = db_file
    db_mod._db = None
    db_mod._lock = None
    db_mod._initialised = False
    return db_file


@pytest_asyncio.fixture
async def db():
    """Return an initialised database connection (module singleton)."""
    from sample_dna_tagger import db as db_mod

    conn = await db_mod.get_db()
    yield conn
    await db_mod.close_db()


@pytest_asyncio.fixture
async def seeded_db(db):
    """Database with 6 sample rows across multiple categories."""
    from sample_dna_tagger import db as db_mod

    now = "2026-05-17T12:00:00"
    rows = [
        {"path":"/Samples/Loopmasters/kick_808.wav","filename":"kick_808.wav","folder":"Loopmasters","duration_seconds":1.8,"bpm":140.0,"rms_energy":0.81,"spectral_centroid":140.0,"spectral_flatness":0.09,"zero_crossing_rate":0.04,"instrument_category":"Drums","instrument_type":"Kick","instrument_subtype":"808","pack_source":"Loopmasters","ai_tags":'["heavy","punchy","sub"]',"user_tags":"[]","rating":5,"last_played_at":now,"play_count":45,"file_mtime":1234567890.0,"file_size":44100},
        {"path":"/Samples/Cymatics/snare_punchy.wav","filename":"snare_punchy.wav","folder":"Cymatics","duration_seconds":0.6,"bpm":None,"rms_energy":0.88,"spectral_centroid":1800.0,"spectral_flatness":0.22,"zero_crossing_rate":0.19,"instrument_category":"Drums","instrument_type":"Snare","instrument_subtype":"Punchy Snare","pack_source":"Cymatics","ai_tags":'["punchy","tight","crisp"]',"user_tags":"[]","rating":3,"last_played_at":now,"play_count":8,"file_mtime":1234567890.0,"file_size":44100},
        {"path":"/Samples/Cymatics/hihat_crisp.wav","filename":"hihat_crisp.wav","folder":"Cymatics","duration_seconds":0.3,"bpm":None,"rms_energy":0.12,"spectral_centroid":8200.0,"spectral_flatness":0.71,"zero_crossing_rate":0.58,"instrument_category":"Drums","instrument_type":"Hi-hat","instrument_subtype":"Open Hi-hat","pack_source":"Cymatics","ai_tags":'["crisp","bright","sizzle"]',"user_tags":"[]","rating":0,"last_played_at":None,"play_count":0,"file_mtime":1234567890.0,"file_size":44100},
        {"path":"/Samples/Cymatics/pad_dark.wav","filename":"pad_dark.wav","folder":"Cymatics","duration_seconds":12.3,"bpm":128.0,"rms_energy":0.42,"spectral_centroid":840.0,"spectral_flatness":0.31,"zero_crossing_rate":0.12,"instrument_category":"Synth","instrument_type":"Synth Pad","instrument_subtype":"Warm Pad","pack_source":"Cymatics","ai_tags":'["tension","smooth","dark","cinematic"]',"user_tags":'["cinematic","project:avalon"]',"rating":4,"last_played_at":now,"play_count":12,"file_mtime":1234567890.0,"file_size":44100},
        {"path":"/Samples/Personal/bass_sub.wav","filename":"bass_sub.wav","folder":"Personal","duration_seconds":3.5,"bpm":120.0,"rms_energy":0.68,"spectral_centroid":95.0,"spectral_flatness":0.08,"zero_crossing_rate":0.02,"instrument_category":"Bass","instrument_type":"Bass","instrument_subtype":"Sub Bass","pack_source":"Personal","ai_tags":'["deep","growl","sub","heavy","dark"]',"user_tags":'["keep"]',"rating":5,"last_played_at":"2026-03-16T10:30:00","play_count":67,"file_mtime":1234567890.0,"file_size":44100},
        {"path":"/Samples/Personal/bass_reese.wav","filename":"bass_reese.wav","folder":"Personal","duration_seconds":5.2,"bpm":174.0,"rms_energy":0.61,"spectral_centroid":310.0,"spectral_flatness":0.25,"zero_crossing_rate":0.09,"instrument_category":"Bass","instrument_type":"Bass","instrument_subtype":"Reese Bass","pack_source":"Personal","ai_tags":'["moving","evolving","dark","aggressive"]',"user_tags":"[]","rating":4,"last_played_at":now,"play_count":23,"file_mtime":1234567890.0,"file_size":44100},
    ]

    for r in rows:
        await db_mod.insert_sample(r)

    await db.commit()
    yield db
    await db_mod.close_db()
