#!/bin/bash
# ======================================================
# Pre-flight Validation for QE ASMR Build Pipeline
# Runs BEFORE any track build. Fails LOUDLY on issues.
# ======================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "${GREEN}  ✓${NC} $1"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}  ✗${NC} $1"; FAIL=$((FAIL+1)); }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; WARN=$((WARN+1)); }

echo "=== QE Pipeline Pre-flight Check ==="
echo ""

# 1. Doppler access
echo "[1] Doppler secrets access..."
if doppler secrets get ELEVENLABS_API_KEY --plain > /dev/null 2>&1; then
    pass "Doppler accessible — ELEVENLABS_API_KEY found"
else
    fail "Cannot access Doppler. Run: doppler setup"
fi

# 2. ElevenLabs API key validity
echo "[2] ElevenLabs API key validity..."
EK=$(doppler secrets get ELEVENLABS_API_KEY --plain 2>/dev/null)
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -H "xi-api-key: $EK" "https://api.elevenlabs.io/v1/user" 2>/dev/null)
if [ "$HTTP" = "200" ]; then
    pass "ElevenLabs API key valid"
else
    fail "ElevenLabs API key returned HTTP $HTTP. Check Doppler."
fi

# 3. Voice ID check
echo "[3] Voice ID validation..."
VOICE_ID="4tRn1lSkEn13EVTuqb0g"
VOICE_NAME=$(curl -s -H "xi-api-key: $EK" "https://api.elevenlabs.io/v1/voices/$VOICE_ID" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('name','UNKNOWN'))" 2>/dev/null)
if [ "$VOICE_NAME" = "Serafina" ]; then
    pass "Voice ID valid — Serafina confirmed"
else
    warn "Voice name is '$VOICE_NAME' (expected Serafina). ID may have changed."
fi

# 4. Master script exists
echo "[4] Master script..."
SCRIPT_DIR="/home/robert/etsy_products/asmr-tracks"
MASTER="$SCRIPT_DIR/SURRENDER_SESSIONS_v2_GROK_REVISED.md"
if [ -f "$MASTER" ]; then
    TRACKS=$(grep -c "^## TRACK 0" "$MASTER")
    pass "Master script found — $TRACKS tracks"
else
    fail "Master script not found: $MASTER"
fi

# 5. Ding file
echo "[5] Ding file..."
DING="$SCRIPT_DIR/ding-a3.mp3"
if [ -f "$DING" ]; then
    DUR=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$DING" 2>/dev/null)
    pass "Ding file found — ${DUR}s"
else
    fail "Ding file missing: $DING"
fi

# 6. ffmpeg
echo "[6] ffmpeg..."
if command -v ffmpeg > /dev/null 2>&1; then
    VER=$(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)
    pass "ffmpeg $VER"
else
    fail "ffmpeg not found"
fi

# 7. No edge-tts fallback risk
echo "[7] Edge-tts check..."
if command -v edge-tts > /dev/null 2>&1; then
    warn "edge-tts is installed — ensure pipeline never falls back to it"
else
    pass "edge-tts not installed — no fallback risk"
fi

# 8. Metadata config
echo "[8] Metadata config..."
if [ -f "$SCRIPT_DIR/config/metadata.json" ]; then
    pass "metadata.json found"
else
    warn "metadata.json not found — using build script defaults"
fi

# 9. Build script
echo "[9] Build pipeline..."
BUILD="$SCRIPT_DIR/build-track.sh"
if [ -x "$BUILD" ]; then
    pass "build-track.sh executable"
else
    fail "build-track.sh not executable: chmod +x $BUILD"
fi

# Summary
echo ""
echo "============================================"
TOTAL=$((PASS + FAIL + WARN))
echo -e "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC} ($TOTAL checks)"
echo "============================================"

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}PRE-FLIGHT FAILED — fix $FAIL issue(s) before building${NC}"
    exit 1
else
    echo -e "${GREEN}PRE-FLIGHT PASSED — ready to build${NC}"
    exit 0
fi
