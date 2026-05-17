import asyncio
from sample_dna_tagger import db

async def seed():
    conn = await db.get_db()
    now = '2026-05-17T12:00:00'
    
    items = [
        ('pad_dark_tension_long.wav', 'Cymatics Nova Vol 2', 12.3, 128.0, 0.42, 840.0, 0.31, 0.12, 'Synth', 'Synth Pad', 'Warm Pad', 'Cymatics Nova Vol 2', '["tension","smooth","dark","cinematic","evolving"]', '["cinematic","project:avalon"]', 4, now, 12),
        ('atmos_cold_high_shimmer.wav', 'Cymatics Nova Vol 2', 8.1, None, 0.28, 4200.0, 0.62, 0.31, 'Atmosphere', 'Atmosphere', 'Cold Pad', 'Cymatics Nova Vol 2', '["tense","airy","cold","shimmer"]', '[]', 0, None, 0),
        ('riser_bright_filtered_slow.wav', 'Personal', 4.2, None, 0.35, 3100.0, 0.55, 0.28, 'FX', 'FX', 'Riser', 'Personal', '["tension","bright","rising"]', '[]', 0, None, 0),
        ('kick_808_distorted_heavy.wav', 'Loopmasters Deep House', 1.8, 140.0, 0.81, 140.0, 0.09, 0.04, 'Drums', 'Kick', '808', 'Loopmasters Deep House', '["heavy","punchy","sub","distorted"]', '[]', 5, now, 45),
        ('kick_click_bright_transient.wav', 'Loopmasters Deep House', 0.9, None, 0.73, 380.0, 0.14, 0.11, 'Drums', 'Kick', 'Punchy Kick', 'Loopmasters Deep House', '["bright","clicky","transient"]', '[]', 0, None, 0),
        ('kick_vinyl_lofi_warm.wav', 'Loopmasters Deep House', 1.1, 90.0, 0.55, 220.0, 0.18, 0.06, 'Drums', 'Kick', 'Punchy Kick', 'Loopmasters Deep House', '["warm","lo-fi","vinyl"]', '[]', 0, '2026-02-15T08:00:00', 3),
        ('snare_punchy_tight.wav', 'Cymatics Nova Vol 2', 0.6, None, 0.88, 1800.0, 0.22, 0.19, 'Drums', 'Snare', 'Punchy Snare', 'Cymatics Nova Vol 2', '["punchy","tight","crisp"]', '[]', 3, now, 8),
        ('hihat_crisp_open.wav', 'Cymatics Nova Vol 2', 0.3, None, 0.12, 8200.0, 0.71, 0.58, 'Drums', 'Hi-hat', 'Open Hi-hat', 'Cymatics Nova Vol 2', '["crisp","bright","sizzle"]', '[]', 0, None, 0),
        ('bass_sub_deep_growl.wav', 'Personal', 3.5, 120.0, 0.68, 95.0, 0.08, 0.02, 'Bass', 'Bass', 'Sub Bass', 'Personal', '["deep","growl","sub","heavy","dark"]', '["keep"]', 5, now, 67),
        ('bass_reese_moving.wav', 'Personal', 5.2, 174.0, 0.61, 310.0, 0.25, 0.09, 'Bass', 'Bass', 'Reese Bass', 'Personal', '["moving","evolving","dark","aggressive"]', '[]', 4, '2026-05-10T18:00:00', 23),
    ]

    for s in items:
        await conn.execute(
            'INSERT INTO samples (id, path, filename, folder, duration_seconds, bpm, rms_energy, spectral_centroid, spectral_flatness, zero_crossing_rate, instrument_category, instrument_type, instrument_subtype, pack_source, ai_tags, user_tags, rating, last_played_at, play_count, file_mtime, file_size, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (db.new_uuid(), '/Samples/' + s[1] + '/' + s[0], *s, 1234567890.0, 44100, now, now)
        )

    await conn.execute("INSERT INTO fts_index(fts_index) VALUES ('rebuild')")
    await conn.commit()

    c = await conn.execute('SELECT COUNT(*) FROM samples')
    r = await c.fetchone()
    print(f'OK: {r[0]} samples')
    await db.close_db()

asyncio.run(seed())
