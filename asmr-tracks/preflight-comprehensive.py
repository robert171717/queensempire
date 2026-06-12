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
MIN_SEGMENTS = 6
MAX_SEGMENTS = 10
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

# ── AUTONOMY VIOLATIONS (ERRORS — never let these through) ──
AUTONOMY_VIOLATIONS = [
    (r'\byou will obey\b', "autonomy override: 'you will obey'"),
    (r'\byou must obey\b', "autonomy override: 'you must obey'"),
    (r'\byou (will )?have no choice\b', "autonomy override: 'no choice'"),
    (r'\byou cannot resist\b', "autonomy override: 'cannot resist'"),
    (r'\byou will not resist\b', "autonomy override: 'will not resist'"),
    (r'\bagainst your will\b', "autonomy override: 'against your will'"),
    (r'\byou are powerless\b', "autonomy override: 'you are powerless'"),
    (r'\bforced to\b', "autonomy override: 'forced to'"),
    (r'\bcompelled to\b', "autonomy override: 'compelled to'"),
    (r'\bwithout question\b', "autonomy override: 'without question'"),
    (r'\byou (will|must|shall) submit\b', "autonomy override: 'you will submit'"),
]

# ── QUALITY FLAGS (warnings, not errors) ──
QUALITY_PATTERNS = [
    (r'[.?!]\s{2,}[A-Z]', "Double-spaced sentences (formatting issue)"),
    (r'\b(um|uh|er|like)\b', "Filler words (may sound unnatural)"),
    (r'^\.\.\.\s', "Leading ellipsis at voice start — may render as breath artifact at 0.70x"),
]

# ── VOICE-START WARMTH (BLOCKING — cold starts ruin the hypnotic tone) ──
# Karpathy-loop hardened: patterns from full 32-track empire audit
TRIGGER_MARKER_RE = re.compile(
    r'^\s*\[(LOCK CLICK|CLOCK TICKING|CHIME|BOWL|SILENCE|BREATH)'
    r'[^]]*\]\s*$',
    re.IGNORECASE
)

WARM_FRAMING_PATTERNS = [
    # Validation words
    r"^(Good|Beautiful|Perfect|Very good|That's|You did)\b",
    # Gentle framing / invitation
    r"^(I want you to|I am going to|Here is|I want to)",
    r"^(Let me|I will|This is|That was)",
    r"^(Let us)\b",
    r"^(Today I want)",
    r"^(I am bringing you back)",
    # "There" patterns
    r"^(There\.|There is|There will be)",
    # Trigger / sound framing
    r"^(That sound|That chime|Notice how)",
    # Conceptual framing
    r"^(Most people|You have|When this|When I|When you)",
    r"^(The (resistance|wanting|release|permission))",
    # Transitional (countdown/return)
    r"^(I am going to (count|bring))",
    # Personal address / invitation
    r"^(Listen|One last|Breathe\. )",
    r"^(Take a breath)",
    r"^(Close your eyes)",  # warm in later tracks / ritual context
    # Contextual framing (describing state)
    r"^(Your (mind|chest|heart|body|breath) is the)",
    r"^(Your (mind|chest|heart|body|breath) are|has)",
    r"^(Your mind may)",
    # State validation
    r"^(You are sinking|You are doing|You are deep)",
    r"^(You may (have|wonder))",
    r"^(You have (given|completed))",
    # Retrospective / meta framing
    r"^(In the first|I designed|From this moment)",
    r"^(Think about)",
    # Session count framing
    r"^((Four|Five|Six|Seven|Eight) (sessions|descents))",
    # Reassurance / permission
    r"^(There is a part)",
    r"^(The permission)",
    # "Now" transitions (warm in mid-voice context)
    r"^(Now (your|let your|I want))",
    r"^(And now)",
    # Warm "Let" patterns (invitations, not commands)
    r"^(Let the (warmth|gratitude|first|release|second))",
    r"^(Let yourself)",
    r"^(Let them)",
    r"^(Let it (go|settle|sit|be|fill|spread|pool|throb|carry))",
    # Gentle guided instruction
    r"^(Place your)",
    r"^(If you are)",
    # Gratitude / emotional framing
    r"^(Gratitude)",
    # Sink (with warm qualifier)
    r"^(Sink —)",
    r"^(Sink\b.*not because)",

    # ── KARPATHY LOOP BATCH 3 (cross-series remaining UNCERTAIN) ──
    r"^(Something is changing)",
    r"^(Float here)",
    r"^(Where do you go)",
    r"^(By now)",
    r"^(Here's what)",
    r"^(Before you go)",
    r"^(Your breath has found)",
    r"^(Every time you)",
    r"^(Now —)",
    r"^(The aftershock)",
    r"^(In track)",
    r"^(Today's)",

    # ── KARPATHY LOOP BATCH 4 (DC poetic/question patterns) ──
    r"^(Why do you)",
    r"^(What would you)",
    r"^(It never)",
    r"^(We are)",
    r"^(Between sessions)",
    r"^(There was a time)",
    r"^(Think back)",
    r"^(I'm going to bring you up)",
    r"^(Float\.)",
    r"^(Now\. )",
]

COLD_IMPERATIVE_STARTS = [
    r"^Breathe in\.\.\.",
    r"^Hold it\.\.\.",
    r"^Now release\b",
    r"^Stop\b",
    r"^That rhythm is mine",
    r"^Your (mind|chest|heart|body) is (mine|holding|fighting|resisting)",
    r"^Let the exhale",
    r"^Let the world",
    r"^Let the chime",
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
    if actual_count < MIN_SEGMENTS:
        errors.append(f"Too few voice segments: {actual_count} (minimum {MIN_SEGMENTS})")
    elif actual_count > MAX_SEGMENTS:
        errors.append(f"Too many voice segments: {actual_count} (maximum {MAX_SEGMENTS})")
    elif actual_count != EXPECTED_SEGMENTS:
        warnings.append(f"Non-standard segment count: {actual_count} (default is {EXPECTED_SEGMENTS})")
    
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

        # 2c. Autonomy violations (BLOCKING errors)
        for pattern, desc in AUTONOMY_VIOLATIONS:
            if re.search(pattern, seg_clean, re.IGNORECASE):
                errors.append(f"Voice {i+1}: {desc} — autonomy violation, must be rewritten")

    # 3. Structural checks
    for pattern, desc in REQUIRED_PATTERNS:
        if not re.search(pattern, content):
            errors.append(f"Missing: {desc}")

    # 4. Quality warnings
    for pattern, desc in QUALITY_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            warnings.append(f"{desc}: {len(matches)} occurrence(s)")

    # 5. Voice-start warmth (BLOCKING — cold starts are errors)
    for i, seg in enumerate(segments):
        seg_clean = seg.strip()
        if not seg_clean:
            continue
        # Voice 1 is exempt (it's the introduction)
        if i == 0:
            continue
        # Get candidate spoken lines (skip tone notes, stage directions, trigger markers)
        lines = []
        for line in seg_clean.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('*'):
                continue
            if re.match(r'^\*\(.*\)\*$', stripped):
                continue
            if re.match(r'^[—–-]\s*(FINAL|FRACTIONATION)', stripped):
                continue
            lines.append(stripped)

        if not lines:
            continue

        first = lines[0]

        # Skip trigger markers — they're audio cues, not text
        if TRIGGER_MARKER_RE.match(first):
            if len(lines) > 1:
                first = lines[1]
            else:
                continue

        first = re.sub(r'^\.\.\.\s*', '', first)

        # Check warm patterns first
        is_warm = False
        for pattern in WARM_FRAMING_PATTERNS:
            if re.search(pattern, first, re.IGNORECASE):
                is_warm = True
                break

        if not is_warm:
            # Check if it matches a known cold pattern
            cold_reason = None
            for pattern in COLD_IMPERATIVE_STARTS:
                if re.search(pattern, first, re.IGNORECASE):
                    cold_reason = f"COLD start: '{first[:60]}...'"
                    break
            if not cold_reason:
                cold_reason = f"NO WARM FRAMING: '{first[:60]}...'"
            errors.append(f"Voice {i+1}: {cold_reason} — add validation/context before instruction")

    # 6. Optional trigger markers (warn, not error — some series handle triggers in pipeline)
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
