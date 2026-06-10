#!/bin/bash
# ============================================================
# QE Obedience Sessions Track Builder v1.0 — ElevenLabs Serafina
# LOCKED SPEC: 0.70x | Warm Singing Bowl trigger (288Hz)
# Chain: highpass=80→vol=1.8→aecho=0.8:0.4:10:0.15→afftdn=nr=12
# Target: 7-9 min per track
# ============================================================
set -e

SCRIPT_DIR="/home/robert/etsy_products/asmr-tracks"
SERIES="rl"  # Obedience Sessions
EK=$(doppler secrets get ELEVENLABS_API_KEY --plain)
VOICE_ID="4tRn1lSkEn13EVTuqb0g"  # Serafina - Sensual Temptress
SPEED=0.70
MODEL="eleven_multilingual_v2"
POP_SRC="$SCRIPT_DIR/release-pop-trigger.mp3"

usage() {
    echo "Usage: $0 <track_number> <script_md>"
    echo "  track_number: 01-08"
    echo "  script_md: markdown file with voice segments marked ### Voice N"
    exit 1
}

[ $# -ne 2 ] && usage
TRACK="$1"
SCRIPT_MD="$2"

WORK="$SCRIPT_DIR/build-${SERIES}-t${TRACK}"
rm -rf "$WORK"
mkdir -p "$WORK"

echo "=== QE Release Sessions Builder v1.0 — Track ${TRACK} ==="
echo ""

# -----------------------------------------------------------
# Step 0: Preflight gate — mandatory, exit on failure
# -----------------------------------------------------------
echo "[0/6] Running preflight gate..."
python3 "$SCRIPT_DIR/preflight-comprehensive.py" "$SCRIPT_MD"
echo "  ✅ Preflight passed"
echo ""

# -----------------------------------------------------------
# Step 1: Extract voice segments from markdown
# -----------------------------------------------------------
echo "[1/6] Extracting voice segments from $(basename "$SCRIPT_MD")..."
python3 "$SCRIPT_DIR/extract-voices.py" "$SCRIPT_MD" "$WORK" 2>&1 || { echo "ERROR: Script parsing failed"; exit 1; }

NUM_SEGMENTS=$(ls "$WORK"/voice-*.txt | wc -l)
echo ""

# -----------------------------------------------------------
# Step 1.5: Check voice cache
# -----------------------------------------------------------
CACHE_DIR="$SCRIPT_DIR/.voice-cache"
mkdir -p "$CACHE_DIR"

# Compute cache key from voice text + voice settings
CACHE_KEY=$(cat "$WORK"/voice-*.txt | sha256sum | cut -d' ' -f1)
CACHE_KEY="${CACHE_KEY:0:16}_s${SPEED}"
CACHE_PATH="$CACHE_DIR/$CACHE_KEY"

if [ -d "$CACHE_PATH" ] && [ -f "$CACHE_PATH/voice-proc-1.mp3" ]; then
    echo "[CACHE HIT] $CACHE_KEY — reusing cached voices"
    cp "$CACHE_PATH"/voice-proc-*.mp3 "$WORK/"
    SKIP_VOICE_GEN=1
else
    echo "[CACHE MISS] $CACHE_KEY — generating voices"
    SKIP_VOICE_GEN=0
fi

# -----------------------------------------------------------
# Step 2: Generate voices with ElevenLabs Serafina
# -----------------------------------------------------------
if [ "$SKIP_VOICE_GEN" -eq 0 ]; then
echo "[2/6] Generating ${NUM_SEGMENTS} voice segments with ElevenLabs Serafina (${SPEED}x)..."
for i in $(seq 1 $NUM_SEGMENTS); do
    echo -n "  Voice ${i}... "
    # Use Python for safe JSON handling
    python3 -c "
import json, subprocess, sys, time
with open('$WORK/voice-${i}.txt') as f:
    text = f.read().strip()
payload = json.dumps({
    'text': text,
    'model_id': '${MODEL}',
    'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'speed': ${SPEED}}
})
# Retry with backoff for rate limits
for attempt in range(5):
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}',
        '-H', 'xi-api-key: ${EK}',
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '-o', '$WORK/voice-raw-${i}.mp3',
        '-w', '%{http_code}'
    ], capture_output=True, text=True)
    code = r.stdout.strip()
    if code == '200':
        break
    if code == '429':
        wait = (attempt + 1) * 5
        print(f'rate_limited_retry_{wait}s', end='', flush=True)
        time.sleep(wait)
    else:
        break
size = subprocess.run(['stat', '-c%s', '$WORK/voice-raw-${i}.mp3'], capture_output=True, text=True).stdout.strip()
print(f'{code} — {size} bytes', flush=True)
if code != '200':
    sys.exit(1)
"
    [ $? -ne 0 ] && { echo "  ERROR: ElevenLabs API failed"; exit 1; }
done

# -----------------------------------------------------------
# Step 3: Apply production chain (LOCKED)
# -----------------------------------------------------------
echo "[3/6] Applying production chain: highpass=80→vol=1.8→aecho=0.8:0.4:10:0.15→afftdn=nr=12"
for i in $(seq 1 $NUM_SEGMENTS); do
    echo -n "  Processing voice ${i}... "
    ffmpeg -y -i "$WORK/voice-raw-${i}.mp3" \
        -af "highpass=f=80,volume=1.8,aecho=0.8:0.4:10:0.15,afftdn=nr=12" \
        -ac 2 -b:a 192k "$WORK/voice-proc-${i}.mp3" \
        2>&1 | tail -1
done
echo ""

# Save to voice cache for future rebuilds
if [ ! -d "$CACHE_PATH" ]; then
    mkdir -p "$CACHE_PATH"
    cp "$WORK"/voice-proc-*.mp3 "$CACHE_PATH/"
    echo "  [CACHE SAVED] $CACHE_KEY"
fi
fi  # end SKIP_VOICE_GEN

# -----------------------------------------------------------
# Step 4: Generate singing bowl gradient
# -----------------------------------------------------------
echo "[4/6] Generating cheek pop gradient (warm, under voice)..."
POP_SRC="$SCRIPT_DIR/release-pop-trigger.mp3"

# Get voice loudness reference from first voice
VOICE_LOUD=$(ffmpeg -i "$WORK/voice-proc-1.mp3" -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null /dev/null 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['input_i'])" 2>/dev/null || echo "-18")

# Gradient: 22/18/18/14/14/12% under voice (gentler than ding)
for level in 25 20 20 15 15 12; do
    vol=$(python3 -c "print(round(-${level}/100 * abs(float('${VOICE_LOUD}')) + 6, 1))")
    ffmpeg -y -i "$POP_SRC" -af "volume=${vol}dB" -b:a 192k "$WORK/pop-${level}.mp3" 2>&1 | tail -1
done
echo ""

# -----------------------------------------------------------
# Step 5: Build concat + mix final track
# -----------------------------------------------------------
echo "[5/6] Mixing final track..."

# Generate silence files
for dur in 2 3 5 6 8 10 12 15 20 30 45 60; do
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t $dur -b:a 192k "$WORK/silence-${dur}s.mp3" 2>/dev/null
done

# Build concat list
CONCAT="$WORK/concat.txt"
> "$CONCAT"

# Bowl gradient levels
POP_LEVELS=(25 20 20 15 15 12)

# Per-track layouts for Obedience Sessions
case "$TRACK" in
    01)
        # The First Request — gentle entry, warm spacing
        echo "file '$WORK/silence-2s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-25.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
        echo "file '$WORK/voice-proc-1.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-8s.mp3'" >> "$CONCAT"
        for i in $(seq 2 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file '$WORK/silence-2s.mp3'" >> "$CONCAT"
            echo "file '$WORK/pop-${POP_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-8s.mp3'" >> "$CONCAT"
        done
        echo "file '$WORK/silence-8s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-12.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-15s.mp3'" >> "$CONCAT"
        ;;
    02)
        # Learning to Please — moderate warmth
        echo "file '$WORK/silence-2s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-25.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
        echo "file '$WORK/voice-proc-1.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-8s.mp3'" >> "$CONCAT"
        for i in $(seq 2 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file '$WORK/silence-2s.mp3'" >> "$CONCAT"
            echo "file '$WORK/pop-${POP_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-8s.mp3'" >> "$CONCAT"
        done
        echo "file '$WORK/silence-6s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-12.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-15s.mp3'" >> "$CONCAT"
        ;;
    03|04)
        # Reward Rhythm / Softening — longer silence for fractionation depth
        for i in $(seq 1 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/pop-${POP_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-10s.mp3'" >> "$CONCAT"
        done
        echo "file '$WORK/silence-10s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-12.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-15s.mp3'" >> "$CONCAT"
        ;;
    05|06|07)
        # Natural/Craving/Trusting — deep, spacious
        for i in $(seq 1 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/pop-${POP_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-10s.mp3'" >> "$CONCAT"
        done
        echo "file '$WORK/silence-12s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-12.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-15s.mp3'" >> "$CONCAT"
        ;;
    08)
        # Always Yours — peaceful landing, longest spaces
        for i in $(seq 1 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/pop-${POP_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-3s.mp3'" >> "$CONCAT"
            echo "file '$WORK/voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file '$WORK/silence-12s.mp3'" >> "$CONCAT"
        done
        echo "file '$WORK/silence-15s.mp3'" >> "$CONCAT"
        echo "file '$WORK/pop-12.mp3'" >> "$CONCAT"
        echo "file '$WORK/silence-15s.mp3'" >> "$CONCAT"
        ;;
esac

OUTPUT="$SCRIPT_DIR/track-${SERIES}-${TRACK}-serafina.mp3"
ffmpeg -y -f concat -safe 0 -i "$CONCAT" -c copy "$OUTPUT" 2>&1 | tail -3

DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUTPUT")
SIZE=$(stat -c%s "$OUTPUT")
echo ""
echo "============================================"
echo "  Track RL-${TRACK} COMPLETE"
echo "  Duration: ${DURATION}s ($(python3 -c "print(f'{float($DURATION)/60:.1f}')")min)"
echo "  Size: $(python3 -c "print(f'{int($SIZE)/1024/1024:.1f}')")MB"
echo "  Output: $(basename "$OUTPUT")"
echo "============================================"

# Post-build validation
echo ""
echo "=== Post-Build Validation ==="
python3 "$SCRIPT_DIR/validate-build.py" "$OUTPUT" "$WORK" 2>&1
VALIDATE_EXIT=$?
if [ $VALIDATE_EXIT -ne 0 ]; then
    echo "⚠️  Validation found issues — review before publishing"
fi
