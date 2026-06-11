#!/usr/bin/env python3
"""Per-voice generation with individual caching. One cache key per voice."""
import json, subprocess, sys, os, hashlib

voice_file = sys.argv[1]      # e.g., /path/to/build-xx/voice-1.txt
voice_id = sys.argv[2]        # ElevenLabs voice ID
api_key = sys.argv[3]         # ElevenLabs API key
model = sys.argv[4]           # e.g., eleven_multilingual_v2
speed = float(sys.argv[5])    # e.g., 0.70
cache_dir = sys.argv[6]       # e.g., /path/to/.voice-cache
output_file = sys.argv[7]     # e.g., /path/to/build-xx/voice-proc-1.mp3

with open(voice_file) as f:
    text = f.read().strip()

# Per-voice cache key: SHA of text + speed
key_raw = text + f"_s{speed}"
voice_hash = hashlib.sha256(key_raw.encode()).hexdigest()[:16]
cache_key = f"{voice_hash}_s{speed:.2f}"
cache_path = os.path.join(cache_dir, cache_key)
cached_file = os.path.join(cache_path, os.path.basename(output_file))

# Check cache
if os.path.exists(cached_file):
    import shutil
    shutil.copy2(cached_file, output_file)
    print(f"  Voice {os.path.basename(voice_file)}: CACHE HIT ({cache_key})")
    sys.exit(0)

# Generate via ElevenLabs
payload = json.dumps({
    'text': text,
    'model_id': model,
    'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'speed': speed}
})

raw_file = output_file.replace('voice-proc-', 'voice-raw-')

for attempt in range(5):
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
        '-H', f'xi-api-key: {api_key}',
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '-o', raw_file,
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

size = os.path.getsize(raw_file)
print(f"  Voice {os.path.basename(voice_file)}: generated ({size} bytes)")

# Apply production chain
subprocess.run([
    'ffmpeg', '-y', '-i', raw_file,
    '-af', 'highpass=f=80,volume=1.8,aecho=0.8:0.4:10:0.15,afftdn=nr=12',
    '-ac', '2', '-b:a', '192k', output_file
], capture_output=True)

# Save to cache
os.makedirs(cache_path, exist_ok=True)
import shutil
shutil.copy2(output_file, cached_file)
print(f"  Voice {os.path.basename(voice_file)}: CACHED ({cache_key})")
