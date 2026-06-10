#!/bin/bash
# QE 7-Day Starter Protocol Builder — Freebie Funnel
# Single-voice tracks, crystal chime trigger, Serafina 0.70x
set -e

SCRIPT_DIR="/home/robert/etsy_products/asmr-tracks"
SERIES="free"
EK=$(doppler secrets get ELEVENLABS_API_KEY --plain)
VOICE_ID="4tRn1lSkEn13EVTuqb0g"  # Serafina
SPEED=0.70
MODEL="eleven_multilingual_v2"

usage() { echo "Usage: $0 <day_number> <script_md>"; exit 1; }
[ $# -ne 2 ] && usage
DAY="$1"
SCRIPT_MD="$2"
WORK="$SCRIPT_DIR/build-free-d${DAY}"
rm -rf "$WORK"
mkdir -p "$WORK"

echo "=== QE Freebie Builder — Day ${DAY} ==="

# Step 1: Extract voice segment
echo "[1/5] Extracting voice..."
python3 -c "
import re
with open('$SCRIPT_MD') as f: text = f.read()
segments = re.split(r'### Voice \d+', text)
seg = [s.strip() for s in segments[1:]][0]
seg = re.sub(r'\*Tone:.*?\*', '', seg)
seg = re.sub(r'\*\([^)]+\)\*', '', seg)
seg = re.sub(r'^\([^)]+\)\s*', '', seg)
seg = re.sub(r'—?\s*FRACTIONATION\s*MOMENT\s*(?:—\s*FINAL\s*—)?\s*[★*]?\s*', '', seg)
seg = re.sub(r'\[Silence\s*[—–-]\s*[^\]]+\]', '', seg)
seg = re.sub(r'\[CHIME[^\]]*\]', '', seg)
seg = re.sub(r'^---\s*$', '', seg, flags=re.MULTILINE)
seg = re.sub(r'\n\s*\n+', ' ', seg).strip()
with open('$WORK/voice-1.txt', 'w') as f: f.write(seg)
print(f'  {len(seg)} chars')
"

# Step 2: Generate voice with ElevenLabs
echo "[2/5] Generating voice with Serafina (${SPEED}x)..."
python3 -c "
import json, subprocess, time
with open('$WORK/voice-1.txt') as f: text = f.read().strip()
payload = json.dumps({
    'text': text,
    'model_id': '${MODEL}',
    'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'speed': ${SPEED}}
})
for attempt in range(5):
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}',
        '-H', 'xi-api-key: ${EK}',
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '-o', '$WORK/voice-raw-1.mp3',
        '-w', '%{http_code}'
    ], capture_output=True, text=True)
    code = r.stdout.strip()
    if code == '200': break
    if code == '429': time.sleep((attempt + 1) * 5)
size = subprocess.run(['stat', '-c%s', '$WORK/voice-raw-1.mp3'], capture_output=True, text=True).stdout.strip()
print(f'  {code} — {size} bytes')
if code != '200': sys.exit(1)
"

# Step 3: Production chain
echo "[3/5] Applying chain: highpass=80→vol=1.8→aecho→afftdn..."
ffmpeg -y -i "$WORK/voice-raw-1.mp3" \
    -af "highpass=f=80,volume=1.8,aecho=0.8:0.4:10:0.15,afftdn=nr=12" \
    -ac 2 -b:a 192k "$WORK/voice-proc-1.mp3" 2>&1 | tail -1

# Step 4: Generate silence files
echo "[4/5] Preparing mix..."
for dur in 2 3 8 15; do
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t $dur -b:a 192k "$WORK/silence-${dur}s.mp3" 2>/dev/null
done
# Use the existing chime from the SR builder
cp "$SCRIPT_DIR/ding-a3.mp3" "$WORK/chime.mp3"

# Step 5: Mix final track
echo "[5/5] Mixing..."
CONCAT="$WORK/concat.txt"
cat > "$CONCAT" << EOF
file '$WORK/silence-2s.mp3'
file '$WORK/chime.mp3'
file '$WORK/silence-3s.mp3'
file '$WORK/voice-proc-1.mp3'
file '$WORK/silence-8s.mp3'
file '$WORK/chime.mp3'
file '$WORK/silence-15s.mp3'
EOF

OUTPUT="$SCRIPT_DIR/track-free-d${DAY}-serafina.mp3"
ffmpeg -y -f concat -safe 0 -i "$CONCAT" -c copy "$OUTPUT" 2>&1 | tail -1

DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUTPUT")
SIZE=$(stat -c%s "$OUTPUT")
echo ""
echo "  Day ${DAY} COMPLETE — $(python3 -c "print(f'{float($DURATION)/60:.1f}')")min, $(python3 -c "print(f'{int($SIZE)/1024/1024:.1f}')")MB"
echo "  Output: track-free-d${DAY}-serafina.mp3"
