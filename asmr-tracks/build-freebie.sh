#!/bin/bash
# QE 7-Day Starter Protocol Builder — Freebie Funnel
# Single-voice tracks, crystal chime trigger, Serafina 0.70x
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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
echo "[1/4] Extracting voice..."
python3 "$SCRIPT_DIR/extract-voices.py" "$SCRIPT_MD" "$WORK" 2>&1 || { echo "ERROR: Script parsing failed"; exit 1; }

# Step 2: Generate voice with per-voice caching
echo "[2/4] Generating voice with Serafina (${SPEED}x)..."
CACHE_DIR="$SCRIPT_DIR/.voice-cache"
mkdir -p "$CACHE_DIR"
python3 "$SCRIPT_DIR/gen-voice.py" \
    "$WORK/voice-1.txt" \
    "$VOICE_ID" \
    "$EK" \
    "$MODEL" \
    "$SPEED" \
    "$CACHE_DIR" \
    "$WORK/voice-proc-1.mp3"
[ $? -ne 0 ] && { echo "  ERROR: Voice generation failed"; exit 1; }

# Step 3: Generate silence files
echo "[3/4] Preparing mix..."
for dur in 2 3 8 15; do
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t $dur -b:a 192k "$WORK/silence-${dur}s.mp3" 2>/dev/null
done
# Use the existing chime from the SR builder
cp "$SCRIPT_DIR/ding-a3.mp3" "$WORK/chime.mp3"

# Step 5: Mix final track
echo "[4/4] Mixing..."
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
