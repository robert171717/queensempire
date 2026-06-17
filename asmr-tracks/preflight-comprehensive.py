#!/usr/bin/env python3
"""
Queen's Empire Audio Pipeline — Comprehensive Preflight Gate
Run before ANY track build. Catches ALL known failure modes.
Exit code 1 = fix before building. No track gets built without a green light.

Karpathy loop principle: every bug we've hit goes in here so we never hit it twice.
"""
import re, sys, os, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── SERIES ARGUMENT ──────────────────────────────────────
SERIES = 'sr'  # default
if '--series' in sys.argv:
    idx = sys.argv.index('--series')
    if idx + 1 < len(sys.argv):
        SERIES = sys.argv[idx + 1].lower()
if SERIES not in ('sr', 'dc', 'ob', 'rl'):
    print(f"ERROR: Unknown series '{SERIES}'. Use: sr, dc, ob, rl", file=sys.stderr)
    sys.exit(1)

# ── PER-SERIES CONFIG ────────────────────────────────────
# Each series has a different psychological frame and tolerance for direct language.
SERIES_PROFILES = {
    'sr': {
        'name': 'Surrender',
        'frame': 'Letting go, trusting, passive release of control',
        'max_stacked_commands': 1,     # flag at ANY command — SR is permissive-only
        'autonomy_strict': True,        # autonomy violations are BLOCKING errors
        'forbidden_words': ['obey', 'kneel', 'submit', 'beg', 'master', 'mistress', 'worship', 'owned',
                           'command', 'must', 'forced', 'powerless', 'helpless'],
        'expected_words': ['surrender', 'let go', 'sink', 'release', 'float', 'trust', 'give in',
                          'allow', 'notice', 'wonder', 'perhaps', 'maybe', 'when you are ready'],
        # Warm framing: words/phrases that make an opening line feel like an invitation
        'warm_openers': ['notice how', 'that chime', 'that sound', 'you can feel', 'allow yourself',
                        'when you', 'i wonder', 'perhaps you', 'maybe you', 'let the',
                        'the warmth', 'this feeling', 'there is', 'feel how', 'take a moment'],
    },
    'dc': {
        'name': 'Denial & Craving',
        'frame': 'Wanting what you cannot have, earning, aching',
        'max_stacked_commands': 2,
        'autonomy_strict': True,
        'forbidden_words': ['obey', 'kneel', 'submit', 'release', 'flood', 'pleasure cascade',
                           'surrender', 'float', 'let go'],
        'expected_words': ['denial', 'ache', 'wait', 'want', 'crave', 'withhold', 'earn',
                          'not yet', 'soon', 'imagine', 'anticipate', 'longing'],
        'warm_openers': ['i know you', 'waiting is', 'you want', 'can you feel', 'imagine how',
                        'soon you', 'the ache', 'not yet', 'you crave', 'close your eyes'],
    },
    'ob': {
        'name': 'Obedience',
        'frame': 'Following, serving, active submission with pride',
        'max_stacked_commands': 4,     # OB by design has more authority
        'autonomy_strict': False,       # autonomy warnings are warnings, not errors
        'forbidden_words': ['surrender', 'let go', 'float', 'release', 'flood', 'pleasure cascade',
                           'helpless', 'powerless'],
        'expected_words': ['obey', 'submit', 'serve', 'kneel', 'follow', 'command', 'good girl',
                          'yes', 'now', 'listen', 'focus', 'again'],
        'warm_openers': ['good', 'that is right', 'you are doing', 'you have earned', 'now',
                        'listen closely', 'focus on', 'again', 'you know', 'you remember'],
    },
    'rl': {
        'name': 'Release',
        'frame': 'Permission to feel, release of tension, pleasure as catharsis',
        'max_stacked_commands': 2,
        'autonomy_strict': True,
        'forbidden_words': ['obey', 'kneel', 'submit', 'surrender', 'denial', 'withhold',
                           'command', 'must'],
        'expected_words': ['release', 'flood', 'pleasure', 'cascade', 'wave', 'wash over',
                          'let it out', 'feel it', 'allow it', 'now'],
        'warm_openers': ['let it', 'allow the', 'feel it', 'release now', 'let go now',
                        'it is time', 'you may', 'you have', 'this is', 'now'],
    },
}
PROFILE = SERIES_PROFILES[SERIES]

# ── CONFIG ───────────────────────────────────────────────
EXPECTED_SEGMENTS = 6
MIN_SEGMENTS = 6
MAX_SEGMENTS = 10
MIN_SEGMENT_CHARS = 200     # warn if shorter
MAX_SEGMENT_CHARS = 800     # ElevenLabs official: >800 chars risks speed-burst instability
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
# Generated from series profile warm_openers + universal warm starts that work across all series
UNIVERSAL_WARM = [
    "i am going to", "you have", "you did", "good", "beautiful", "perfect",
    "now", "and now", "there is", "this is", "that was", "let me",
    "i want you to", "i will", "here is", "most people", "when you",
    "your mind", "your body", "your breath", "think about", "take a",
    "place your", "if you are", "by now", "every time you", "something is"
]
WARM_FRAMING_PATTERNS = [
    r"^(?:" + "|".join(
        re.escape(opener) for opener in PROFILE['warm_openers'] + UNIVERSAL_WARM
    ) + r")\b"
]

TRIGGER_MARKER_RE = re.compile(
    r'^\s*\[(LOCK CLICK|CLOCK TICKING|CHIME|BOWL|SILENCE|BREATH)'
    r'[^]]*\]\s*$',
    re.IGNORECASE
)


COLD_IMPERATIVE_STARTS = [
    r"^Breathe in\.\.\.",
    r"^Hold it\.\.\.",
    r"^Now release\b",
    r"^Stop\b",
    r"^That rhythm is mine",
    r"^(Your (mind|chest|heart|body) is (mine|holding|fighting|resisting))",
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
            errors.append(f"Voice {i+1}: {chars} chars exceeds ElevenLabs 800-char limit (risks mid-generation speed burst). Split this voice into two segments.")
        
        # 2b. Leak patterns
        for pattern, desc in LEAK_PATTERNS:
            matches = re.findall(pattern, seg_clean, re.MULTILINE)
            for m in matches:
                idx = seg_clean.find(m)
                ctx = seg_clean[max(0,idx-15):idx+len(m)+15].replace('\n',' ').strip()
                errors.append(f"Voice {i+1}: {desc} — \"{m}\" in ...{ctx}...")

        # 2c. Autonomy violations (BLOCKING errors for SR/DC/RL, warnings for OB)
        for pattern, desc in AUTONOMY_VIOLATIONS:
            if re.search(pattern, seg_clean, re.IGNORECASE):
                if PROFILE['autonomy_strict']:
                    errors.append(f"Voice {i+1}: {desc} — autonomy violation ({PROFILE['name']} series), must be rewritten")
                else:
                    warnings.append(f"Voice {i+1}: {desc} — autonomy concern ({PROFILE['name']} series), review")

        # 2d. Series-forbidden words (BLOCKING — wrong-series vocabulary breaks the trance frame)
        for word in PROFILE['forbidden_words']:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, seg_clean, re.IGNORECASE):
                errors.append(f"Voice {i+1}: '{word}' is forbidden in {PROFILE['name']} series — belongs to a different psychological frame")

        # 2e. Series-expected word presence (WARNING — total absence suggests wrong frame)
        expected_found = False
        for word in PROFILE['expected_words']:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, seg_clean, re.IGNORECASE):
                expected_found = True
                break
        if not expected_found:
            warnings.append(f"Voice {i+1}: no {PROFILE['name']}-expected words found — verify frame alignment")

        # 2f. Stacked commands (WARNING — tolerance varies by series)
        # NOTE: SR uses a narrow imperatives list — "let," "feel," "notice" are permissive, not commanding
        IMPERATIVES = {'open','close','drop','hold','stop','focus','count','say','tell','repeat'}
        sentences = re.split(r'(?<=[.!?])\s+', seg_clean)
        imperative_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # Connector + verb: "Now/And/Then [—] verb"
            m = re.match(r'^(Now|And|Then)\s*[—–-]?\s*([a-z]+)', sent, re.IGNORECASE)
            if m and m.group(2).lower() in IMPERATIVES:
                imperative_sentences.append(sent[:60])
                continue
            # Bare imperative: first word capitalized + in list
            m = re.match(r'^([A-Z][a-z]+)\b', sent)
            if m and m.group(1).lower() in IMPERATIVES:
                imperative_sentences.append(sent[:60])
                continue
            # Non-imperative: check if we had a stack
            if len(imperative_sentences) >= PROFILE['max_stacked_commands']:
                ctx = ' → '.join(imperative_sentences[:4])
                warnings.append(f"Voice {i+1}: {len(imperative_sentences)} stacked commands (sounds commanding, {PROFILE['name']} tolerance ≤{PROFILE['max_stacked_commands']}): {ctx}")
            imperative_sentences = []
        # Check at end of voice
        if len(imperative_sentences) >= PROFILE['max_stacked_commands']:
            ctx = ' → '.join(imperative_sentences[:4])
            warnings.append(f"Voice {i+1}: {len(imperative_sentences)} stacked commands (sounds commanding, {PROFILE['name']} tolerance ≤{PROFILE['max_stacked_commands']}): {ctx}")

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
    # Filter out --series flag from file list
    raw_args = sys.argv[1:] if len(sys.argv) > 1 else []
    files = []
    skip_next = False
    for i, arg in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if arg == '--series':
            skip_next = True
            continue
        files.append(arg)
    
    if not files:
        files = sorted(os.path.join(SCRIPT_DIR, f) for f in os.listdir(SCRIPT_DIR) 
                      if f.startswith('track-') and f.endswith('-script.md'))
    
    print(f"\n{'═'*60}")
    print(f"  Queen's Empire Preflight — {PROFILE['name']} Series ({SERIES.upper()})")
    print(f"  Frame: {PROFILE['frame']}")
    print(f"  Command tolerance: ≤{PROFILE['max_stacked_commands']} consecutive")
    print(f"  Autonomy strict: {'Yes' if PROFILE['autonomy_strict'] else 'No (warnings only)'}")
    print(f"  Forbidden: {', '.join(PROFILE['forbidden_words'][:6])}...")
    print(f"{'═'*60}\n")
    
    all_errors = []
    all_warnings = []
    total_credits = 0
    
    for f in files:
        if not os.path.exists(f):
            continue
        
        name = os.path.basename(f)
        errors, warnings = check_script(f)
        
        # Also check extracted build directory if it exists
        track_num = re.search(r'(\d+)', name)
        if track_num:
            build_dir = os.path.join(SCRIPT_DIR, f"build-{SERIES}-t{track_num.group(1)}")
            if not os.path.isdir(build_dir):
                # fallback: old naming convention
                build_dir = os.path.join(SCRIPT_DIR, f"build-t{track_num.group(1)}")
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
