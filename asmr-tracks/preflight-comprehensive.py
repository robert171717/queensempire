#!/usr/bin/env python3
"""
Queen's Empire Audio Pipeline — Comprehensive Preflight Gate
Run before ANY track build. Catches ALL known failure modes.
Exit code 1 = fix before building. No track gets built without a green light.

Karpathy loop principle: every bug we've hit goes in here so we never hit it twice.
"""
import re, sys, os, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── CONFIG ───────────────────────────────────────────────
EXPECTED_SEGMENTS = 6
MIN_SEGMENT_CHARS = 200     # warn if shorter
MAX_SEGMENT_CHARS = 1500    # warn if longer
TARGET_DURATION_MIN = 420   # 7 min minimum
TARGET_DURATION_MAX = 660   # 11 min maximum

# ── LEAK PATTERNS (will be spoken unless pipeline strips them) ──
LEAK_PATTERNS = [
    (r'—\s*FRACTIONATION\s*MOMENT', "FRACTIONATION marker"),
    (r'\[Silence\s*[—–-]', "[Silence] marker"),
]

# ── STRUCTURAL PATTERNS (should be present) ──
REQUIRED_PATTERNS = [
    (r'### Voice \d+', "Voice segment markers"),
]

# ── OPTIONAL TRIGGER MARKERS (warn if missing, series-dependent) ──
TRIGGER_PATTERNS = [
    (r'\[(LOCK CLICK|CHIME)\]', "Trigger markers (LOCK CLICK or CHIME)"),
]

# ── QUALITY FLAGS (warnings, not errors) ──
QUALITY_PATTERNS = [
    (r'[.?!]\s{2,}[A-Z]', "Double-spaced sentences (formatting issue)"),
    (r'\b(um|uh|er|like)\b', "Filler words (may sound unnatural)"),
]


def check_script(filepath):
    """Full structural + content check of a track script."""
    with open(filepath) as f:
        content = f.read()

    errors = []
    warnings = []

    # 1. Segment count
    segments = re.split(r'### Voice \d+', content)
    segments = segments[1:]  # skip header
    actual_count = len([s for s in segments if s.strip()])
    if actual_count != EXPECTED_SEGMENTS:
        errors.append(f"Expected {EXPECTED_SEGMENTS} voice segments, found {actual_count}")
    
    # 2. Check each segment
    for i, seg in enumerate(segments):
        seg_clean = seg.strip()
        if not seg_clean and i < len(segments) - 1:
            continue
            
        # 2a. Character count
        chars = len(seg_clean)
        if chars < MIN_SEGMENT_CHARS:
            warnings.append(f"Voice {i+1}: only {chars} chars (very short)")
        elif chars > MAX_SEGMENT_CHARS:
            warnings.append(f"Voice {i+1}: {chars} chars (may exceed API limits)")
        
        # 2b. Leak patterns
        for pattern, desc in LEAK_PATTERNS:
            matches = re.findall(pattern, seg_clean, re.MULTILINE)
            for m in matches:
                idx = seg_clean.find(m)
                ctx = seg_clean[max(0,idx-15):idx+len(m)+15].replace('\n',' ').strip()
                errors.append(f"Voice {i+1}: {desc} — \"{m}\" in ...{ctx}...")

    # 3. Structural checks
    for pattern, desc in REQUIRED_PATTERNS:
        if not re.search(pattern, content):
            errors.append(f"Missing: {desc}")

    # 4. Quality warnings
    for pattern, desc in QUALITY_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            warnings.append(f"{desc}: {len(matches)} occurrence(s)")

    # 5. Optional trigger markers (warn, not error — some series handle triggers in pipeline)
    for pattern, desc in TRIGGER_PATTERNS:
        if not re.search(pattern, content):
            warnings.append(f"No trigger markers found ({desc}) — ensure pipeline adds them")

    return errors, warnings


def check_build_log(build_dir, track_num):
    """Post-build: verify extracted text is clean."""
    if not os.path.isdir(build_dir):
        return [], []
    
    errors = []
    for i in range(1, EXPECTED_SEGMENTS + 1):
        voice_file = os.path.join(build_dir, f"voice-{i}.txt")
        if not os.path.exists(voice_file):
            continue
        with open(voice_file) as f:
            text = f.read()
        for pattern, desc in LEAK_PATTERNS:
            if re.search(pattern, text):
                errors.append(f"BUILD LEAK: Voice {i} still contains {desc} after extraction")
    
    return errors, []


def estimate_credits(filepath):
    """Rough credit estimation for the track."""
    with open(filepath) as f:
        content = f.read()
    # Count characters in voice segments only
    segments = re.split(r'### Voice \d+', content)[1:]
    total_chars = sum(len(s.strip()) for s in segments if s.strip())
    # ElevenLabs: ~1 credit per character for multilingual_v2
    return total_chars


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = sorted(os.path.join(SCRIPT_DIR, f) for f in os.listdir(SCRIPT_DIR) 
                      if f.startswith('track-dc-') and f.endswith('-script.md'))
    
    all_errors = []
    all_warnings = []
    total_credits = 0
    
    for f in files:
        if not os.path.exists(f):
            continue
        
        name = os.path.basename(f)
        errors, warnings = check_script(f)
        
        # Also check extracted build directory if it exists
        track_num = re.search(r'dc-(\d+)', name)
        if track_num:
            build_dir = os.path.join(SCRIPT_DIR, f"build-dc-t{track_num.group(1)}")
            build_errors, build_warnings = check_build_log(build_dir, track_num.group(1))
            errors.extend(build_errors)
            warnings.extend(build_warnings)
        
        credits = estimate_credits(f)
        total_credits += credits
        
        status = "❌" if errors else "✅"
        print(f"{status} {name} — {credits:,} estimated chars")
        for e in errors:
            print(f"   🔴 {e}")
            all_errors.append(e)
        for w in warnings:
            print(f"   🟡 {w}")
            all_warnings.append(w)
    
    print(f"\n{'═'*50}")
    print(f"  Errors:   {len(all_errors)}")
    print(f"  Warnings: {len(all_warnings)}")
    print(f"  Est. credits needed: {total_credits:,}")
    print(f"  ~121K Creator limit: {total_credits/121000*100:.0f}% used")
    print(f"{'═'*50}")
    
    if all_errors:
        print(f"\n🚫 BLOCKED: {len(all_errors)} error(s). Fix before building.\n")
        sys.exit(1)
    
    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} warning(s). Review, then build.\n")
    else:
        print(f"\n✅ All gates passed. Ready to build.\n")
    sys.exit(0)


if __name__ == '__main__':
    main()
