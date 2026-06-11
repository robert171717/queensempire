#!/usr/bin/env python3
"""check-voice-warmth.py — Quality gate: voice-start tonal warmth.

Karpathy-loop hardened. Every false positive from the full empire audit
(32 tracks across SR, DC, OB, RL) has been baked in as a lesson.

Scans each voice segment in a script (voices 2+). Flags voice starts that launch
directly into commands/instructions without warm framing or validation.

Returns exit code 1 if any voice start is flagged.
"""

import sys
import re

# ── TRIGGER MARKERS (audio cues, not spoken text) ──
TRIGGER_MARKER = re.compile(
    r'^\s*\[(LOCK CLICK|CLOCK TICKING|CHIME|BOWL|SILENCE|BREATH)'
    r'[^]]*\]\s*$',
    re.IGNORECASE
)

# ── WARM FRAMING PATTERNS ──
WARM_FRAMING_PATTERNS = [
    # ── Validation words ──
    r"^(Good|Beautiful|Perfect|Very good|That's|You did)\b",

    # ── Gentle framing / invitation ──
    r"^(I want you to|I am going to|Here is|I want to)",
    r"^(Let me|I will|This is|That was)",
    r"^(Let us)\b",
    r"^(Today I want)",
    r"^(I am bringing you back)",

    # ── "There" patterns ──
    r"^(There\.|There is|There will be)",

    # ── Trigger / sound framing ──
    r"^(That sound|That chime|Notice how)",

    # ── Conceptual framing ──
    r"^(Most people|You have|When this|When I|When you)",
    r"^(The (resistance|wanting|release|permission))",

    # ── Transitional (countdown/return) ──
    r"^(I am going to (count|bring))",

    # ── Personal address / invitation ──
    r"^(Listen|One last|Breathe\. )",
    r"^(Take a breath)",
    r"^(Close your eyes)",  # warm in later tracks / DC/OB where it's ritual

    # ── Contextual framing (describing state) ──
    r"^(Your (mind|chest|heart|body|breath) is the)",
    r"^(Your (mind|chest|heart|body|breath) are|has)",
    r"^(Your mind may)",

    # ── State validation ──
    r"^(You are sinking|You are doing|You are deep)",
    r"^(You may (have|wonder))",
    r"^(You have (given|completed))",

    # ── Retrospective / meta framing ──
    r"^(In the first|I designed|From this moment)",
    r"^(Think about)",

    # ── Session count framing ──
    r"^((Four|Five|Six|Seven|Eight) (sessions|descents))",

    # ── Reassurance / permission ──
    r"^(There is a part)",
    r"^(The permission)",

    # ── "Now" transitions (warm when mid-voice context) ──
    r"^(Now (your|let your|I want))",
    r"^(And now)",

    # ── Warm "Let" patterns (invitations to feeling, not commands) ──
    r"^(Let the (warmth|gratitude|first|release|second))",
    r"^(Let yourself)",
    r"^(Let them)",
    r"^(Let it (go|settle|sit|be|fill|spread|pool|throb|carry))",

    # ── Gentle guided instruction ──
    r"^(Place your)",
    r"^(If you are)",

    # ── Gratitude / emotional framing ──
    # Gratitude / emotional framing
    r"^(Gratitude)",
    # Sink (with warm qualifier)
    r"^(Sink —)",
    r"^(Sink\b.*not because)",

    # ── KARPATHY LOOP BATCH 3 (DC/OB/RL/SR remaining UNCERTAIN) ──
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

# ── COLD IMPERATIVE STARTS (narrowed after Karpathy loop) ──
COLD_IMPERATIVE_STARTS = [
    # Bare breathing commands (no warm framing)
    r"^Breathe in\.\.\.",
    r"^Hold it\.\.\.",
    r"^Now release\b",

    # Dismissive / commanding
    r"^Stop\b",
    r"^That rhythm is mine",

    # Possessive without framing
    r"^Your (mind|chest|heart|body) is (mine|holding|fighting|resisting)",

    # Cold "Let the" (commands, not invitations)
    r"^Let the exhale",
    r"^Let the world",
    r"^Let the chime",
]


def extract_voice_starts(script_path):
    """Extract (voice_num, first_spoken_sentence) for each voice segment.

    Skips trigger markers [LOCK CLICK], [CLOCK TICKING] etc. —
    those are audio cues, not spoken text.
    Skips tone notes in *(parentheses)* and lines starting with *.
    """
    with open(script_path) as f:
        text = f.read()

    voices = {}
    for match in re.finditer(r'### Voice (\d+)\n+(.+?)(?=\n### Voice|\Z)', text, re.DOTALL):
        vnum = int(match.group(1))
        body = match.group(2).strip()

        if not body:
            continue

        # Get candidate lines, filtering out non-spoken content
        lines = []
        for line in body.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip tone notes (e.g. "*Tone: Warm, inviting...*")
            if stripped.startswith('*'):
                continue
            # Skip stage directions in parens: *(Denial as Intimacy)*
            if re.match(r'^\*\(.*\)\*$', stripped):
                continue
            # Skip em-dash header annotations that leaked from header
            if re.match(r'^[—–-]\s*(FINAL|FRACTIONATION)', stripped):
                continue
            # This is a spoken line candidate
            lines.append(stripped)

        if not lines:
            continue

        first = lines[0]

        # Skip trigger markers — they're audio cues, not text
        if TRIGGER_MARKER.match(first):
            # Use the NEXT line after the trigger marker
            if len(lines) > 1:
                first = lines[1]
            else:
                continue  # no spoken text after trigger

        # Remove leading ... (pacing artifact)
        first = re.sub(r'^\.\.\.\s*', '', first)
        voices[vnum] = first

    return voices


def check_warmth(first_sentence):
    """Return (passes: bool, reason: str)."""
    first = first_sentence.strip()

    # Check warm patterns first
    for pattern in WARM_FRAMING_PATTERNS:
        if re.search(pattern, first, re.IGNORECASE):
            return True, f"Warm: matches '{pattern}'"

    # Check cold patterns
    for pattern in COLD_IMPERATIVE_STARTS:
        if re.search(pattern, first, re.IGNORECASE):
            return False, f"COLD start: matches '{pattern}'"

    # If nothing matched either list, flag as uncertain
    return False, f"UNCERTAIN: no warm pattern detected. First words: '{first[:80]}'"


def main():
    script = sys.argv[1] if len(sys.argv) > 1 else "track-01-script.md"

    voices = extract_voice_starts(script)
    issues = []
    passes = []

    for vnum in sorted(voices.keys()):
        first = voices[vnum]
        ok, reason = check_warmth(first)

        if ok:
            passes.append((vnum, reason))
        else:
            issues.append((vnum, reason, first))

    # Voice 1 is exempt (it's the introduction)
    issues = [(v, r, f) for v, r, f in issues if v != 1]

    print(f"\n{'='*60}")
    print(f"VOICE-START WARMTH CHECK — {script}")
    print(f"{'='*60}")

    for vnum, reason in passes:
        if vnum != 1:
            print(f"  ✅ Voice {vnum}: {reason}")

    for vnum, reason, first in issues:
        print(f"  ❌ Voice {vnum}: {reason}")
        print(f"       Text: \"{first[:100]}\"")

    print(f"\n  Passed: {len(passes)}/{len(voices)}")
    print(f"  Failed: {len(issues)}")

    if issues:
        print(f"\n⚠️  {len(issues)} voice(s) need warm-framing rewrite.")
        sys.exit(1)
    else:
        print("\n✅ All voices start warm.")
        sys.exit(0)


if __name__ == "__main__":
    main()
