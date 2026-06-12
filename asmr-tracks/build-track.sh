#!/bin/bash
# ============================================================
# QE ASMR UNIFIED Track Builder v4.0 — ElevenLabs Serafina
# ============================================================
# One builder for all 4 series: SR, DC, OB, RL
#
# Usage: ./build-track.sh <track> <script>           → SR (backward compat)
#        ./build-track.sh <series> <track> <script>  → any series
#
# Series:  sr (Surrender)  | dc (Denial & Craving)
#          ob (Obedience)  | rl (Release)
#
# Chain:  highpass=80→vol=1.8→aecho=0.8:0.4:10:0.15→afftdn=nr=12
# Concat: concat FILTER (decodes to PCM — no MP3 frame drops)
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EK=$(doppler secrets get ELEVENLABS_API_KEY --plain)
VOICE_ID="4tRn1lSkEn13EVTuqb0g"  # Serafina - Sensual Temptress
MODEL="eleven_multilingual_v2"
CACHE_DIR="$SCRIPT_DIR/.voice-cache"
mkdir -p "$CACHE_DIR"

# ─── Args: backward-compatible with old 2-arg SR-only syntax ───
usage() {
    echo "Usage: $0 <track> <script>              → SR series (backward compat)"
    echo "       $0 <series> <track> <script>      → any series"
    echo ""
    echo "  series: sr | dc | ob | rl"
    echo "  track:  01-08"
    echo "  script: markdown file with ### Voice N segments"
    exit 1
}

if [ $# -eq 2 ]; then
    SERIES="sr"
    TRACK="$1"
    SCRIPT_MD="$2"
    SPEED=0.70
elif [ $# -eq 3 ]; then
    SERIES="$1"
    TRACK="$2"
    SCRIPT_MD="$3"
    SPEED=0.70
else
    usage
fi

# ─── Series configuration ───
case "$SERIES" in
    sr)
        SERIES_NAME="Surrender"
        TRIGGER_NAME="ding"
        TRIGGER_SRC="$SCRIPT_DIR/ding-a3.mp3"
        TRIGGER_LEVELS=(25 20 20 15 22 15)
        TRIGGER_VOL_OFFSET="-6"
        OUTPUT_PREFIX="track"
        ;;
    dc)
        SERIES_NAME="Denial & Craving"
        TRIGGER_NAME="lock"
        TRIGGER_SRC="$SCRIPT_DIR/lock-click.mp3"
        TRIGGER_LEVELS=(30 25 20 20 15 15)
        TRIGGER_VOL_OFFSET="+8.0"
        OUTPUT_PREFIX="track-dc"
        # DC also has optional clock-tick secondary trigger
        TICK_SRC="$SCRIPT_DIR/clock-tick.mp3"
        TICK_LEVELS=(20 15 12 10)
        ;;
    ob)
        SERIES_NAME="Obedience"
        TRIGGER_NAME="bowl"
        TRIGGER_SRC="$SCRIPT_DIR/singing-bowl-warm-v1.mp3"
        TRIGGER_LEVELS=(22 18 18 14 14 12)
        TRIGGER_VOL_OFFSET="+18"
        OUTPUT_PREFIX="track-ob"
        ;;
    rl)
        SERIES_NAME="Release"
        TRIGGER_NAME="pop"
        TRIGGER_SRC="$SCRIPT_DIR/release-pop-trigger.mp3"
        TRIGGER_LEVELS=(25 20 20 15 15 12)
        TRIGGER_VOL_OFFSET="+6"
        OUTPUT_PREFIX="track-rl"
        ;;
    *)
        echo "ERROR: Unknown series '$SERIES'. Use: sr, dc, ob, rl"
        exit 1
        ;;
esac

# Work directory uses series prefix to avoid collisions
WORK="$SCRIPT_DIR/build-${SERIES}-t${TRACK}"
rm -rf "$WORK"
mkdir -p "$WORK"

echo "=== QE ${SERIES_NAME} Builder v4.0 — Track ${TRACK} (${SERIES}) ===\n"

# ═══════════════════════════════════════════════════════════════
# Step 0: Preflight gate
# ═══════════════════════════════════════════════════════════════
echo "[0/5] Running preflight gate..."
python3 "$SCRIPT_DIR/preflight-comprehensive.py" "$SCRIPT_MD"
echo "  ✅ Preflight passed\n"

# ═══════════════════════════════════════════════════════════════
# Step 0.3: Script quality gate
# ═══════════════════════════════════════════════════════════════
echo "[0.3/5] Script quality gate..."
python3 "$SCRIPT_DIR/critique-script.py" "$SCRIPT_MD"
echo ""

# ═══════════════════════════════════════════════════════════════
# Step 0.5: Git-lock gate
# ═══════════════════════════════════════════════════════════════
echo "[0.5/5] Git-lock gate..."
bash "$SCRIPT_DIR/check-git-lock.sh" "$SCRIPT_MD"
echo ""

# ═══════════════════════════════════════════════════════════════
# Step 1: Extract voice segments
# ═══════════════════════════════════════════════════════════════
echo "[1/5] Extracting voice segments from $(basename "$SCRIPT_MD")..."
python3 "$SCRIPT_DIR/extract-voices.py" "$SCRIPT_MD" "$WORK" 2>&1 || { echo "ERROR: Script parsing failed"; exit 1; }
NUM_SEGMENTS=$(ls "$WORK"/voice-*.txt | wc -l)
echo ""

# ═══════════════════════════════════════════════════════════════
# Step 2: Generate voices (per-voice cached)
# ═══════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════
# Step 3: Generate trigger gradient
# ═══════════════════════════════════════════════════════════════
echo "[3/5] Generating ${TRIGGER_NAME} gradient (${TRIGGER_LEVELS[*]}% under voice)..."
VOICE_LOUD=$(ffmpeg -i "$WORK/voice-proc-1.mp3" -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null /dev/null 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['input_i'])" 2>/dev/null || echo "-18")

for level in "${TRIGGER_LEVELS[@]}"; do
    vol=$(python3 -c "print(round(-${level}/100 * abs(float('${VOICE_LOUD}')) ${TRIGGER_VOL_OFFSET}, 1))")
    ffmpeg -y -i "$TRIGGER_SRC" -af "volume=${vol}dB" -b:a 192k "$WORK/${TRIGGER_NAME}-${level}.mp3" 2>&1 | tail -1
done

# DC series: also generate clock-tick gradient
if [ "$SERIES" = "dc" ] && [ -f "$TICK_SRC" ]; then
    echo "  Clock tick gradient..."
    for level in "${TICK_LEVELS[@]}"; do
        vol=$(python3 -c "print(round(-${level}/100 * abs(float('${VOICE_LOUD}')) - 8, 1))")
        ffmpeg -y -i "$TICK_SRC" -af "volume=${vol}dB" -b:a 192k "$WORK/tick-${level}.mp3" 2>&1 | tail -1
    done
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# Step 4: Build concat layout + mix final track
# ═══════════════════════════════════════════════════════════════
echo "[4/5] Mixing final track..."

# Generate silence files
SILENCE_DURS="2 3 5 6 8 10 12 15 20 30 45 60"
[ "$SERIES" = "dc" ] && SILENCE_DURS="$SILENCE_DURS 90"
for dur in $SILENCE_DURS; do
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t $dur -b:a 192k "$WORK/silence-${dur}s.mp3" 2>/dev/null
done

# Build concat list
CONCAT="$WORK/concat.txt"
> "$CONCAT"

# All files use bare filenames (relative to WORK dir for concat-filter.py)
T="${TRIGGER_NAME}"
L=("${TRIGGER_LEVELS[@]}")

# ── Series-specific layout cases ──
if [ "$SERIES" = "sr" ]; then
    # SR: tight spacing for intro tracks, moderate for others
    case "$TRACK" in
        01)
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[0]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            for i in $(seq 2 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-8s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-6s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        02)
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[0]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            for i in $(seq 2 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-8s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-6s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        *)
            for i in $(seq 1 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-10s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
    esac
elif [ "$SERIES" = "dc" ]; then
    case "$TRACK" in
        01)
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[0]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            for i in $(seq 2 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-8s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        02)
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[0]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            for i in $(seq 2 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-8s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-10s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        03|04)
            for i in $(seq 1 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-12s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-10s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        *)
            for i in $(seq 1 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-10s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-10s.mp3'" >> "$CONCAT"
            echo "file '${T}-15.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
    esac
else
    # OB + RL: shared layout structure (8 tracks, grouped by depth)
    case "$TRACK" in
        01)
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[0]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            for i in $(seq 2 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-8s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[5]}.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        02)
            echo "file 'silence-2s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[0]}.mp3'" >> "$CONCAT"
            echo "file 'silence-3s.mp3'" >> "$CONCAT"
            echo "file 'voice-proc-1.mp3'" >> "$CONCAT"
            echo "file 'silence-8s.mp3'" >> "$CONCAT"
            for i in $(seq 2 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-2s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-8s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-6s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[5]}.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        03|04)
            for i in $(seq 1 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-10s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-10s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[5]}.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        05|06|07)
            for i in $(seq 1 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-10s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-12s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[5]}.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        08)
            for i in $(seq 1 $NUM_SEGMENTS); do
                idx=$(( (i-1) % 6 ))
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file '${T}-${L[$idx]}.mp3'" >> "$CONCAT"
                echo "file 'silence-3s.mp3'" >> "$CONCAT"
                echo "file 'voice-proc-${i}.mp3'" >> "$CONCAT"
                echo "file 'silence-10s.mp3'" >> "$CONCAT"
            done
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            echo "file '${T}-${L[5]}.mp3'" >> "$CONCAT"
            echo "file 'silence-15s.mp3'" >> "$CONCAT"
            ;;
        *)
            echo "ERROR: Track ${TRACK} not supported for series ${SERIES}"
            exit 1
            ;;
    esac
fi

# ═══════════════════════════════════════════════════════════════
# Step 5: Concat filter + encode
# ═══════════════════════════════════════════════════════════════
OUTPUT="$SCRIPT_DIR/${OUTPUT_PREFIX}-${TRACK}-serafina.mp3"
echo "[4/5] Building concat filter..."
python3 "$SCRIPT_DIR/concat-filter.py" "$CONCAT" "$OUTPUT" "$WORK" 2>&1 | tail -3

DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUTPUT")
SIZE=$(stat -c%s "$OUTPUT")
echo ""
echo "============================================"
echo "  ${SERIES_NAME} Track ${TRACK} COMPLETE"
echo "  Duration: ${DURATION}s ($(python3 -c "print(f'{float($DURATION)/60:.1f}')")min)"
echo "  Size: $(python3 -c "print(f'{int($SIZE)/1024/1024:.1f}')")MB"
echo "  Output: $(basename "$OUTPUT")"
echo "============================================"

# ═══════════════════════════════════════════════════════════════
# Post-build validation
# ═══════════════════════════════════════════════════════════════
echo ""
echo "=== Post-Build Validation ==="
python3 "$SCRIPT_DIR/validate-build.py" "$OUTPUT" "$WORK" 2>&1
VALIDATE_EXIT=$?
if [ $VALIDATE_EXIT -ne 0 ]; then
    echo "⚠️  Validation found issues — review before publishing"
fi

# ═══════════════════════════════════════════════════════════════
# Discord-optimized version
# ═══════════════════════════════════════════════════════════════
DISCORD_OUT="$SCRIPT_DIR/${OUTPUT_PREFIX}-${TRACK}-discord.mp3"
echo ""
echo "=== Discord Version ==="
ffmpeg -y -i "$OUTPUT" -af "loudnorm=I=-16:TP=-1.5:LRA=11" -b:a 128k "$DISCORD_OUT" 2>&1 | tail -1
echo "  Discord: $(basename "$DISCORD_OUT")"

# ═══════════════════════════════════════════════════════════════
# Auto-extract verification clips (SR series only for now)
# ═══════════════════════════════════════════════════════════════
if [ "$SERIES" = "sr" ]; then
    VERIFY_DIR="$WORK/verify"
    mkdir -p "$VERIFY_DIR"
    python3 -c "
import subprocess, os, hashlib

work = '$WORK'
cache_dir = '$CACHE_DIR'
verify_dir = '$VERIFY_DIR'
output = '$DISCORD_OUT'

segments = sorted([f for f in os.listdir(work) if f.startswith('voice-') and f.endswith('.txt')],
                   key=lambda x: int(x.split('-')[1].split('.')[0]))

timings = []
offset = 8  # opening: 2s silence + 3s trigger + 3s silence

for seg_file in segments:
    seg_num = int(seg_file.split('-')[1].split('.')[0])
    with open(os.path.join(work, seg_file)) as f:
        text = f.read().strip()
    key_raw = text + '_s0.7'
    h = hashlib.sha256(key_raw.encode()).hexdigest()[:16]
    cache_key = f'{h}_s0.70'
    cache_path = os.path.join(cache_dir, cache_key, 'voice.mp3')
    dur = 30
    if os.path.exists(cache_path):
        dur = float(subprocess.check_output(['ffprobe', '-v', 'quiet', '-show_entries',
                  'format=duration', '-of', 'csv=p=0', cache_path]).decode().strip())
    timings.append({'num': seg_num, 'start': offset, 'dur': dur})
    offset += dur + 8 + 8

for t in timings:
    if t['num'] == 2:
        start = max(0, t['start'] - 3)
        duration = t['dur'] + 15
        subprocess.run(['ffmpeg', '-y', '-ss', str(start), '-i', output,
                       '-t', str(duration), '-b:a', '128k',
                       os.path.join(verify_dir, 'voice2-region.mp3')],
                      capture_output=True)
        trans_start = t['start'] + t['dur'] - 5
        subprocess.run(['ffmpeg', '-y', '-ss', str(trans_start), '-i', output,
                       '-t', '30', '-b:a', '128k',
                       os.path.join(verify_dir, 'v23-transition.mp3')],
                      capture_output=True)
        break

subprocess.run(['ffmpeg', '-y', '-ss', '0', '-i', output,
               '-t', '30', '-b:a', '128k',
               os.path.join(verify_dir, 'opening.mp3')],
              capture_output=True)
print(f'  Verification clips: {verify_dir}/')
" 2>&1
fi

echo "============================================"
