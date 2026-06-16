#!/usr/bin/env python3
"""Per-voice generation with individual caching. One cache key per voice."""
import json, subprocess, sys, os, hashlib, re

voice_file = sys.argv[1]      # e.g., /path/to/build-xx/voice-1.txt
voice_id = sys.argv[2]        # ElevenLabs voice ID
api_key = sys.argv[3]         # ElevenLabs API key
model = sys.argv[4]           # e.g., eleven_multilingual_v2
speed = float(sys.argv[5])    # e.g., 0.70
cache_dir = sys.argv[6]       # e.g., /path/to/.voice-cache
output_file = sys.argv[7]     # e.g., /path/to/build-xx/voice-proc-1.mp3

# Optional: --previous-text, --next-text, --previous-request-id, --next-request-id
previous_text = None
next_text = None
previous_request_ids = []
next_request_ids = []
voice_settings_override = {}
remaining = sys.argv[8:]
i = 0
while i < len(remaining):
    if remaining[i] == '--previous-text' and i + 1 < len(remaining):
        previous_text = remaining[i + 1]
        i += 2
    elif remaining[i] == '--next-text' and i + 1 < len(remaining):
        next_text = remaining[i + 1]
        i += 2
    elif remaining[i] == '--previous-request-id' and i + 1 < len(remaining):
        previous_request_ids.append(remaining[i + 1])
        i += 2
    elif remaining[i] == '--next-request-id' and i + 1 < len(remaining):
        next_request_ids.append(remaining[i + 1])
        i += 2
    elif remaining[i] == '--stability' and i + 1 < len(remaining):
        voice_settings_override['stability'] = float(remaining[i + 1])
        i += 2
    elif remaining[i] == '--similarity' and i + 1 < len(remaining):
        voice_settings_override['similarity_boost'] = float(remaining[i + 1])
        i += 2
    elif remaining[i] == '--style' and i + 1 < len(remaining):
        voice_settings_override['style'] = float(remaining[i + 1])
        i += 2
    elif remaining[i] == '--seed' and i + 1 < len(remaining):
        voice_settings_override['seed'] = int(remaining[i + 1])
        i += 2
    else:
        i += 1

# === PRE-GENERATION GATE: check-voice-breaks.py ===
# Catches speed-burst triggers BEFORE burning ElevenLabs credits.
# BLOCKING on break overflow (>15 breaks). Warnings on rhythmic echoes.
import subprocess as sp_breaks
breaks_result = sp_breaks.run(
    [sys.executable, os.path.join(os.path.dirname(__file__), 'check-voice-breaks.py'),
     voice_file, '--json'],
    capture_output=True, text=True
)
if breaks_result.returncode != 0:
    try:
        breaks_report = json.loads(breaks_result.stdout or '{}')
        for err in breaks_report.get('errors', []):
            print(f"  ❌ GATE BLOCKED: {err}", file=sys.stderr)
    except:
        print(f"  ❌ GATE BLOCKED: {breaks_result.stdout.strip()}", file=sys.stderr)
    sys.exit(1)
# Print warnings even on pass
try:
    breaks_report = json.loads(breaks_result.stdout or '{}')
    for warn in breaks_report.get('warnings', []):
        print(f"  ⚠️  {warn}")
    bc = breaks_report.get('break_count', 0)
    cc = breaks_report.get('char_count', 0)
    print(f"  📊 Voice gate: {bc} breaks, {cc} chars text")
except:
    pass
# === END GATE ===

with open(voice_file) as f:
    text = f.read().strip()

# Strip [DIRECTION: ...] blocks — these are script documentation,
# not text to be spoken. Future: send via ElevenLabs prompt_inject.
text = re.sub(r'\n?\[DIRECTION:.*?\]\n?', '\n', text).strip()

# v2 does NOT support ElevenLabs audio tags (e.g., [sensually], [whispers]).
# v3 processes them natively. Strip standalone audio tag lines for v2.
if 'eleven_multilingual_v2' in model or 'eleven_monolingual_v1' in model:
    text = re.sub(r'\n?\[(?!DIRECTION:)[^\]]+\]\n?', '\n', text).strip()

# Per-voice cache key: SHA of text + model + all voice settings + stitch context
voice_settings = f"st0.71_sb0.80_sty0.45_spk1"
if voice_settings_override:
    vs = {'stability': 0.71, 'similarity_boost': 0.80, 'style': 0.45, 'use_speaker_boost': True}
    vs.update(voice_settings_override)
    voice_settings = f"st{vs['stability']:.2f}_sb{vs['similarity_boost']:.2f}_sty{vs['style']:.2f}_spk{1 if vs['use_speaker_boost'] else 0}"
    if 'seed' in vs:
        voice_settings += f"_seed{vs['seed']}"
key_raw = text + f"_s{speed}_{model}_{voice_settings}"
if previous_text:
    key_raw += f"_prev={previous_text[-80:]}"
if next_text:
    key_raw += f"_next={next_text[-80:]}"
if previous_request_ids:
    key_raw += f"_prids={'+'.join(previous_request_ids)}"
if next_request_ids:
    key_raw += f"_nrids={'+'.join(next_request_ids)}"
voice_hash = hashlib.sha256(key_raw.encode()).hexdigest()[:16]
cache_key = f"{voice_hash}_s{speed:.2f}"
cache_path = os.path.join(cache_dir, cache_key)
cached_file = os.path.join(cache_path, "voice.mp3")

# Check cache
if os.path.exists(cached_file):
    import shutil
    shutil.copy2(cached_file, output_file)
    print(f"  Voice {os.path.basename(voice_file)}: CACHE HIT ({cache_key})")
    sys.exit(0)

# Generate via ElevenLabs
base_settings = {'stability': 0.71, 'similarity_boost': 0.80, 'style': 0.45, 'use_speaker_boost': True, 'speed': speed}
if voice_settings_override:
    base_settings.update(voice_settings_override)
payload_dict = {
    'text': text,
    'model_id': model,
    'voice_settings': base_settings
}
if previous_text:
    payload_dict['previous_text'] = previous_text
if next_text:
    payload_dict['next_text'] = next_text
if previous_request_ids:
    payload_dict['previous_request_ids'] = previous_request_ids
if next_request_ids:
    payload_dict['next_request_ids'] = next_request_ids
payload = json.dumps(payload_dict)

raw_file = output_file.replace('voice-proc-', 'voice-raw-')
headers_file = output_file.replace('voice-proc-', 'voice-headers-').replace('.mp3', '.txt')

for attempt in range(5):
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
        '-H', f'xi-api-key: {api_key}',
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '-o', raw_file,
        '-D', headers_file,
        '-w', '%{http_code}'
    ], capture_output=True, text=True)
    code = r.stdout.strip()
    if code == '200':
        break
    if code == '429':
        import time
        wait = (attempt + 1) * 5
        time.sleep(wait)
    else:
        print(f"  ERROR: ElevenLabs API returned {code}", file=sys.stderr)
        sys.exit(1)

if code != '200':
    print(f"  ERROR: ElevenLabs API failed after 5 attempts", file=sys.stderr)
    sys.exit(1)

# Extract request_id from response headers
request_id = None
if os.path.exists(headers_file):
    with open(headers_file) as hf:
        for line in hf:
            if line.lower().startswith('request-id:'):
                request_id = line.split(':', 1)[1].strip()
                break
    os.remove(headers_file)

# Save request_id alongside output
rid_file = output_file.replace('.mp3', '.request-id')
with open(rid_file, 'w') as rf:
    rf.write(request_id or 'unknown')

size = os.path.getsize(raw_file)
print(f"  Voice {os.path.basename(voice_file)}: generated ({size} bytes), rid={request_id}")

# Apply production chain with loudness normalization
subprocess.run([
    'ffmpeg', '-y', '-i', raw_file,
    '-af', 'highpass=f=80,volume=1.8,aecho=0.8:0.4:10:0.15,afftdn=nr=12,atempo=0.94,loudnorm=I=-16:TP=-1.5:LRA=11',
    '-ac', '2', '-b:a', '192k', output_file
], capture_output=True)

# Save to cache
os.makedirs(cache_path, exist_ok=True)
import shutil
shutil.copy2(output_file, cached_file)
# Also cache the request-id file
cached_rid_file = os.path.join(cache_path, "voice.request-id")
if os.path.exists(rid_file):
    shutil.copy2(rid_file, cached_rid_file)
print(f"  Voice {os.path.basename(voice_file)}: CACHED ({cache_key})")
