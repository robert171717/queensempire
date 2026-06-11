#!/bin/bash
# ============================================================
# QE Denial & Craving Track Builder v1.0 — ElevenLabs Serafina
# LOCKED SPEC: 0.68x | Lock Click trigger | clock-tick secondary
# Chain: highpass=80→vol=1.8→aecho=0.8:0.4:10:0.15→afftdn=nr=12
# Binaural: apulsator=0.15Hz (Tracks 03+)
# Target: 9-11 min per track
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERIES="dc"  # Denial & Craving
EK=$(doppler secrets get ELEVENLABS_API_KEY --plain)
VOICE_ID="4tRn1lSkEn13EVTuqb0g"  # Serafina - Sensual Temptress
SPEED=0.70
MODEL="eleven_multilingual_v2"
LOCK_SRC="$SCRIPT_DIR/lock-click.mp3"
TICK_SRC="$SCRIPT_DIR/clock-tick.mp3"

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

echo "=== QE Denial & Craving Track Builder v1.0 — Track ${TRACK} ==="
echo ""

# -----------------------------------------------------------
# Step 0: Preflight gate — mandatory, exit on failure
# -----------------------------------------------------------
echo "[0/5] Running preflight gate..."
python3 "$SCRIPT_DIR/preflight-comprehensive.py" "$SCRIPT_MD"
echo "  ✅ Preflight passed"
echo ""

# -----------------------------------------------------------
# Step 0.3: Script quality gate — critique before credits
# -----------------------------------------------------------
echo "[0.3/5] Script quality gate..."
python3 "$SCRIPT_DIR/critique-script.py" "$SCRIPT_MD"
echo ""

# -----------------------------------------------------------
# Step 0.5: Git-lock gate — refuse uncommitted scripts
# -----------------------------------------------------------
echo "[0.5/5] Git-lock gate..."
bash "$SCRIPT_DIR/check-git-lock.sh" "$SCRIPT_MD"
echo ""

# -----------------------------------------------------------
# Step 1: Extract voice segments from markdown
# -----------------------------------------------------------
echo "[1/5] Extracting voice segments from $(basename "$SCRIPT_MD")..."
python3 "$SCRIPT_DIR/extract-voices.py" "$SCRIPT_MD" "$WORK" 2>&1 || { echo "ERROR: Script parsing failed"; exit 1; }

NUM_SEGMENTS=$(ls "$WORK"/voice-*.txt | wc -l)
echo ""

# -----------------------------------------------------------
# Step 1.5: Per-voice cache — each voice cached independently
# -----------------------------------------------------------
CACHE_DIR="$SCRIPT_DIR/.voice-cache"
mkdir -p "$CACHE_DIR"

# -----------------------------------------------------------
# Step 2: Generate voices with per-voice caching
# -----------------------------------------------------------
echo "[2/5] Generating ${NUM_SEGMENTS} voice segments with ElevenLabs Serafina (${SPEED}x)..."
for i in $(seq 1 $NUM_SEGMENTS); do
    python3 "$SCRIPT_DIR/gen-voice.py" \
        "$WORK/voice-${i}.txt" \
        "$VOICE_ID" \
        "$EK" \
        "$MODEL" \
        "$SPEED" \
        "$CACHE_DIR" \
        "$WORK/voice-proc-${i}.mp3"
    [ $? -ne 0 ] && { echo "  ERROR: Voice ${i} generation failed"; exit 1; }
done
echo ""

# -----------------------------------------------------------
# Step 4: Generate lock click gradient
# -----------------------------------------------------------
echo "[3/5] Generating lock click gradient (30/25/20/20/15/15% under voice)..."
LOCK_SRC="$SCRIPT_DIR/lock-click.mp3"

# Get voice loudness reference from first voice
VOICE_LOUD=$(ffmpeg -i "$WORK/voice-proc-1.mp3" -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null /dev/null 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['input_i'])" 2>/dev/null || echo "-18")

for level in 30 25 20 20 15 15; do
    vol=$(python3 -c "print(round(-${level}/100 * abs(float('${VOICE_LOUD}')) + 8.0, 1))")
    ffmpeg -y -i "$LOCK_SRC" -af "volume=${vol}dB" -b:a 192k "$WORK/lock-${level}.mp3" 2>&1 | tail -1
done

# Generate clock tick gradient if file exists
if [ -f "$TICK_SRC" ]; then
    echo "  Clock tick source found, generating gradient..."
    for level in 20 15 12 10; do
        vol=$(python3 -c "print(round(-${level}/100 * abs(float('${VOICE_LOUD}')) - 8, 1))")
        ffmpeg -y -i "$TICK_SRC" -af "volume=${vol}dB" -b:a 192k "$WORK/tick-${level}.mp3" 2>&1 | tail -1
    done
fi
echo ""

# -----------------------------------------------------------
# Step 5: Build concat + mix final track
# -----------------------------------------------------------
echo "[4/5] Mixing final track..."

# Generate silence files (including long ones for 9-11min target)
for dur in 2 3 5 6 8 10 12 15 20 30 45 60 90; do
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t $dur -b:a 192k "$WORK/silence-${dur}s.mp3" 2>/dev/null
done

# Build concat list
CONCAT="$WORK/concat.txt"
> "$CONCAT"

# Lock click gradient levels
LOCK_LEVELS=(30 25 20 20 15 15)

# Per-track layouts for Denial & Craving
case "$TRACK" in
    01)
        # The First Lock — heavy lock clicks, tight spacing
        echo "file 'silence-2s.mp3'" >> "$CONCAT"
        echo "file 'lock-30.mp3'" >> "$CONCAT"
        echo "file 'silence-3s.mp3'" >> "$CONCAT"
        echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
        echo "file 'silence-8s.mp3'" >> "$CONCAT"
        for i in $(seq 2 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file 'lock-${LOCK_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
        done
        echo "file 'silence-8s.mp3'" >> "$CONCAT"
        echo "file 'lock-15.mp3'" >> "$CONCAT"
        echo "file 'silence-15s.mp3'" >> "$CONCAT"
        ;;
    02)
        # Learning to Ache — lock clicks + clock ticking
        echo "file 'silence-2s.mp3'" >> "$CONCAT"
        echo "file 'lock-30.mp3'" >> "$CONCAT"
        echo "file 'silence-3s.mp3'" >> "$CONCAT"
        echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
        echo "file 'silence-8s.mp3'" >> "$CONCAT"
        for i in $(seq 2 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file 'lock-${LOCK_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
        done
        echo "file 'silence-10s.mp3'" >> "$CONCAT"
        echo "file 'lock-15.mp3'" >> "$CONCAT"
        echo "file 'silence-15s.mp3'" >> "$CONCAT"
        ;;
    03|04)
        # Lighter lock clicks, longer silence for depth
        for i in $(seq 1 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'lock-${LOCK_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file 'silence-12s.mp3'" >> "$CONCAT"
        done
        echo "file 'silence-10s.mp3'" >> "$CONCAT"
        echo "file 'lock-15.mp3'" >> "$CONCAT"
        echo "file 'silence-15s.mp3'" >> "$CONCAT"
        ;;
    *)
        # Default: minimal lock clicks, voice carries everything
        for i in $(seq 1 $NUM_SEGMENTS); do
            idx=$(( (i-1) % 6 ))
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'lock-${LOCK_LEVELS[$idx]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
            echo "file 'silence-10s.mp3'" >> "$CONCAT"
        done
        echo "file 'silence-10s.mp3'" >> "$CONCAT"
        echo "file 'lock-15.mp3'" >> "$CONCAT"
        echo "file 'silence-15s.mp3'" >> "$CONCAT"
        ;;
esac

OUTPUT="$SCRIPT_DIR/track-${SERIES}-${TRACK}-serafina.mp3"
ffmpeg -y -f concat -safe 0 -i "$CONCAT" -c copy "$OUTPUT" 2>&1 | tail -3

DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUTPUT")
SIZE=$(stat -c%s "$OUTPUT")
echo ""
echo "============================================"
echo "  Track DC-${TRACK} COMPLETE"
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
