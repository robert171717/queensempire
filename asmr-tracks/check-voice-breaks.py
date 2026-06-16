#!/usr/bin/env python3
"""
Pre-generation voice gate — catches ElevenLabs speed-burst triggers BEFORE API call.

Two checks:
1. Break tag count — >15 triggers speed burst (ElevenLabs documented)
2. Rhythmic phrasing — repeated "X... Y..." patterns trigger acceleration

Usage:
  python3 check-voice-breaks.py voice-7.txt           # exit 0 = PASS, exit 1 = BLOCKED
  python3 check-voice-breaks.py voice-7.txt --warn     # exit 0 always, prints warnings
  python3 check-voice-breaks.py voice-7.txt --json     # machine-readable output
"""

import re, sys, os, json
from collections import Counter

MAX_BREAKS = 15            # ElevenLabs documented threshold
MIN_RHYTHMIC_LENGTH = 8    # words minimum for pattern comparison
RHYTHMIC_WINDOW = 4        # compare within this many lines

def strip_ssml(text):
    """Remove SSML tags, keep text content."""
    text = re.sub(r'<[^>]+>', '', text)
    # Remove [DIRECTION: ...] blocks
    text = re.sub(r'\[DIRECTION:.*?\]', '', text)
    return text

def count_breaks(text):
    """Count SSML break tags."""
    return len(re.findall(r'<break\s+time="[^"]*"\s*/?>', text))

def extract_sentence_skeletons(text):
    """
    Extract rhythmic skeletons from text lines.
    Strips words, keeps structure: "... X ... Y ..." becomes "... _ ... _ ..."
    """
    plain = strip_ssml(text)
    lines = [l.strip() for l in plain.split('\n') if l.strip()]
    skeletons = []
    for line in lines:
        words = line.split()
        if len(words) < MIN_RHYTHMIC_LENGTH:
            continue
        # Build skeleton: replace words with _, keep punctuation and ellipsis
        skeleton = []
        for w in words:
            if w in ('...', '—', ',', '.', ';'):
                skeleton.append(w)
            else:
                # Keep leading/trailing punctuation on words
                cleaned = re.sub(r'[a-zA-Z]+', '_', w)
                skeleton.append(cleaned)
        skeletons.append(' '.join(skeleton))
    return skeletons, lines

def find_rhythmic_patterns(text):
    """
    Find repeated rhythmic structures within a voice.
    Returns list of (line_a_idx, line_b_idx, skeleton, line_a_text, line_b_text)
    """
    skeletons, lines = extract_sentence_skeletons(text)
    findings = []
    for i in range(len(skeletons)):
        for j in range(i + 1, min(i + RHYTHMIC_WINDOW + 1, len(skeletons))):
            if skeletons[i] == skeletons[j]:
                findings.append({
                    'line_a': i + 1,
                    'line_b': j + 1,
                    'skeleton': skeletons[i],
                    'text_a': lines[i][:120],
                    'text_b': lines[j][:120]
                })
    return findings

def check_voice(filepath, mode='strict'):
    """Run all checks on a voice file. Returns (passed, report_dict)."""
    with open(filepath) as f:
        text = f.read()

    report = {
        'file': os.path.basename(filepath),
        'break_count': count_breaks(text),
        'break_limit': MAX_BREAKS,
        'breaks_over': False,
        'rhythmic_patterns': [],
        'char_count': len(strip_ssml(text)),
        'warnings': [],
        'errors': []
    }

    # Check 1: Break count
    if report['break_count'] > MAX_BREAKS:
        report['breaks_over'] = True
        msg = f"BREAK OVERFLOW: {report['break_count']} break tags (limit {MAX_BREAKS}) — WILL trigger speed burst. Split this voice."
        report['errors'].append(msg)

    # Check 2: Rhythmic phrasing
    patterns = find_rhythmic_patterns(text)
    if patterns:
        report['rhythmic_patterns'] = patterns
        for p in patterns:
            msg = f"RHYTHMIC ECHO: lines {p['line_a']}-{p['line_b']} share skeleton '{p['skeleton']}' — may trigger speed burst"
            report['warnings'].append(msg)

    passed = len(report['errors']) == 0
    return passed, report

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <voice-file> [--warn|--json]", file=sys.stderr)
        sys.exit(2)

    filepath = sys.argv[1]
    mode = 'strict'
    if '--warn' in sys.argv:
        mode = 'warn'
    output_json = '--json' in sys.argv

    passed, report = check_voice(filepath, mode)

    if output_json:
        report['passed'] = passed
        print(json.dumps(report, indent=2))
    else:
        if report['errors']:
            for e in report['errors']:
                print(f"  ❌ {e}")
        if report['warnings']:
            for w in report['warnings']:
                print(f"  ⚠️  {w}")
        if not report['errors'] and not report['warnings']:
            print(f"  ✅ {report['file']}: {report['break_count']} breaks (≤{MAX_BREAKS}), no rhythmic echoes — safe")
        print(f"  📊 {report['break_count']} breaks, {report['char_count']} chars text")

    if mode == 'strict' and not passed:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
