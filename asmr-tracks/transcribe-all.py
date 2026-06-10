import subprocess, json, os, glob, re

EK = subprocess.run(['doppler','secrets','get','ELEVENLABS_API_KEY','--plain'], capture_output=True, text=True).stdout.strip()
BASE = '/home/robert/etsy_products/asmr-tracks'

def transcribe(filepath):
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.elevenlabs.io/v1/speech-to-text',
        '-H', f'xi-api-key: {EK}',
        '-F', f'file=@{filepath}',
        '-F', 'model_id=scribe_v1'
    ], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)['text']
    except:
        return None

# Tracks 02-04: individual voice files
for track in ['2', '3', '4']:
    files = sorted(glob.glob(f'{BASE}/t{track}-voice-el-*.mp3'))
    # Filter out sub-segments (like 6a, 6b) by only keeping the base files
    # Actually, include all — we want everything
    script_lines = [f'# Track 0{track} — Recovered Script']
    script_lines.append('## Seraphina — Surrender Sessions')
    script_lines.append('')
    
    for f in files:
        fname = os.path.basename(f)
        print(f'Transcribing {fname}...', flush=True)
        text = transcribe(f)
        if text:
            # Determine segment number
            match = re.search(r'voice-el-(\w+)\.mp3', fname)
            seg = match.group(1) if match else '?'
            script_lines.append(f'### Voice {seg}')
            script_lines.append(f'*Tone: Recovered from transcription*')
            script_lines.append('')
            script_lines.append(text)
            script_lines.append('')
            print(f'  ✓ {len(text)} chars', flush=True)
        else:
            print(f'  ✗ FAILED', flush=True)
    
    outpath = f'{BASE}/track-0{track}-script.md'
    with open(outpath, 'w') as f:
        f.write('\n'.join(script_lines))
    print(f'Saved: {outpath}\n', flush=True)

# Track 01: transcribe full track
print('Transcribing Track 01 (full track)...', flush=True)
t1_files = sorted(glob.glob(f'{BASE}/track-01-v5.mp3'))
if not t1_files:
    t1_files = sorted(glob.glob(f'{BASE}/track-01-serafina.mp3'))
if t1_files:
    text = transcribe(t1_files[0])
    if text:
        with open(f'{BASE}/track-01-script-recovered.txt', 'w') as f:
            f.write(text)
        print(f'  ✓ Track 01: {len(text)} chars — saved as track-01-script-recovered.txt', flush=True)
    else:
        print('  ✗ Track 01 transcription failed', flush=True)

print('\n=== All transcriptions complete ===')
