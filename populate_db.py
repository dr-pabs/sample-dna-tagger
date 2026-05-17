import sqlite3, json, sys

DB = sys.argv[1] if len(sys.argv) > 1 else '/Volumes/ExtDisk1/sample-dna-tagger/test_library.db'

db = sqlite3.connect(DB)
data = [
    ('a1','/Samples/Cymatics/pad_dark_tension_long.wav','pad_dark_tension_long.wav','Cymatics',12.3,128.0,0.42,840.0,0.31,0.12,'Synth','Synth Pad','Warm Pad','Cymatics',json.dumps(['tension','smooth','dark']),json.dumps(['cinematic']),4,'2026-05-17T12:00:00',12),
    ('a2','/Samples/Cymatics/atmos_cold.wav','atmos_cold.wav','Cymatics',8.1,None,0.28,4200.0,0.62,0.31,'Atmosphere','Atmosphere','Cold Pad','Cymatics',json.dumps(['tense','airy']),json.dumps([]),0,None,0),
    ('a3','/Samples/Personal/riser_bright.wav','riser_bright.wav','Personal',4.2,None,0.35,3100.0,0.55,0.28,'FX','FX','Riser','Personal',json.dumps(['tension','bright']),json.dumps([]),0,None,0),
    ('a4','/Samples/Loopmasters/kick_808.wav','kick_808.wav','Loopmasters',1.8,140.0,0.81,140.0,0.09,0.04,'Drums','Kick','808','Loopmasters',json.dumps(['heavy','punchy']),json.dumps([]),5,'2026-03-16T10:30:00',45),
    ('a5','/Samples/Loopmasters/kick_click.wav','kick_click.wav','Loopmasters',0.9,None,0.73,380.0,0.14,0.11,'Drums','Kick','Punchy Kick','Loopmasters',json.dumps(['bright','clicky']),json.dumps([]),0,None,0),
    ('a6','/Samples/Loopmasters/kick_vinyl.wav','kick_vinyl.wav','Loopmasters',1.1,90.0,0.55,220.0,0.18,0.06,'Drums','Kick','Punchy Kick','Loopmasters',json.dumps(['warm','lo-fi']),json.dumps([]),0,'2026-02-15T08:00:00',3),
    ('a7','/Samples/Cymatics/snare_punchy.wav','snare_punchy.wav','Cymatics',0.6,None,0.88,1800.0,0.22,0.19,'Drums','Snare','Punchy Snare','Cymatics',json.dumps(['punchy','tight']),json.dumps([]),3,'2026-05-17T12:00:00',8),
    ('a8','/Samples/Cymatics/hihat_crisp.wav','hihat_crisp.wav','Cymatics',0.3,None,0.12,8200.0,0.71,0.58,'Drums','Hi-hat','Open Hi-hat','Cymatics',json.dumps(['crisp','bright']),json.dumps([]),0,None,0),
    ('a9','/Samples/Personal/bass_sub.wav','bass_sub.wav','Personal',3.5,120.0,0.68,95.0,0.08,0.02,'Bass','Bass','Sub Bass','Personal',json.dumps(['deep','growl']),json.dumps(['keep']),5,'2026-05-17T12:00:00',67),
    ('aa','/Samples/Personal/bass_reese.wav','bass_reese.wav','Personal',5.2,174.0,0.61,310.0,0.25,0.09,'Bass','Bass','Reese Bass','Personal',json.dumps(['moving','dark']),json.dumps([]),4,'2026-05-10T18:00:00',23),
]
for d in data:
    db.execute('INSERT OR REPLACE INTO samples (id,path,filename,folder,duration_seconds,bpm,rms_energy,spectral_centroid,spectral_flatness,zero_crossing_rate,instrument_category,instrument_type,instrument_subtype,pack_source,ai_tags,user_tags,rating,last_played_at,play_count,file_mtime,file_size,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (*d, 1234567890.0, 44100, '2026-05-17', '2026-05-17'))
db.commit()
db.close()
