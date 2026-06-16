#!/usr/bin/env python3
"""
Arc coherence gate — verifies each voice fulfills its function in the series arc.
Warnings only (not blocking). Use to catch theme drift before committing.

Usage:
  python3 check-arc-coherence.py track-01-script.md sr
  python3 check-arc-coherence.py track-dc-01-script.md dc
"""

import re, sys, json

# === SERIES ARC DEFINITIONS ===
# voice_fn: role name
# expected: words/phrases that SHOULD appear (at least one from each category)
# forbidden_fn: words that would indicate wrong series function

ARC_MAPS = {
    'sr': {
        'name': 'The Surrender Series',
        'voices': {
            1: {
                'fn': 'Opening Anchor',
                'expected': {
                    'chime_anchor': ['chime', 'sound', 'ring', 'resonat', 'tone'],
                    'surrender_invite': ['surrender', 'sink', 'drop', 'let go', 'give in'],
                    'eye_closure': ['close your eyes', 'eyes close', 'let your eyes'],
                },
                'forbidden_fn': ['obey', 'kneel', 'submit', 'command'],
            },
            2: {
                'fn': 'Trust Building',
                'expected': {
                    'safety': ['safe', 'nothing expected', 'nowhere else', 'held'],
                    'breath': ['breath', 'inhale', 'exhale'],
                    'warmth': ['good', 'gift', 'intimate', 'trust'],
                },
                'forbidden_fn': ['obey', 'kneel', 'beg'],
            },
            3: {
                'fn': 'Early Deepening',
                'expected': {
                    'deepening': ['deeper', 'sink', 'drop', 'further', 'down'],
                    'sensory': ['feel', 'notice', 'warm', 'soft', 'heavy'],
                },
            },
            4: {
                'fn': 'Mid Deepening',
                'expected': {
                    'deepening': ['deeper', 'further', 'falling', 'sinking'],
                    'fractionation': ['again', 'return', 'back', 'once more'],
                },
            },
            5: {
                'fn': 'Late Deepening',
                'expected': {
                    'deepening': ['deeper', 'deepest', 'further still'],
                    'surrender': ['surrender', 'let go', 'give yourself', 'belong'],
                },
            },
            6: {
                'fn': 'Descent Countdown',
                'expected': {
                    'counting': [r'\b(Ten|Nine|Eight|Seven|Six|Five|Four|Three|Two|One)\b'],
                    'anchoring': ['my voice', 'only', 'follow', 'each'],
                },
            },
            7: {
                'fn': 'Foundation',
                'expected': {
                    'deepest': ['deepest', 'foundation', 'no further', 'bottom'],
                    'surrender': ['surrender', 'belong', 'yours', 'give', 'let go'],
                    'stillness': ['only this', 'nothing else', 'just', 'now'],
                },
            },
            8: {
                'fn': 'Emergence',
                'expected': {
                    'counting': [r'\b(Ten|Nine|Eight|Seven|Six|Five|Four|Three|Two|One)\b'],
                    'body_return': ['body', 'finger', 'shoulder', 'breath', 'heart', 'skin'],
                    'carrying_depth': ['with you', 'stay', 'never leave', 'still'],
                },
            },
            9: {
                'fn': 'Closing',
                'expected': {
                    'completion': ['completed', 'first', 'beginning', 'return'],
                    'anticipation': ['next', 'again', 'reach', 'want', 'before'],
                    'surrender_close': ['surrender', 'beginning', 'only the start'],
                },
            },
        },
    },
    'dc': {
        'name': 'The Denial Series',
        'voices': {
            1: {
                'fn': 'Denial Anchor',
                'expected': {
                    'chime_anchor': ['chime', 'sound', 'remember'],
                    'denial_setup': ['wait', 'not yet', 'earn', 'crave'],
                },
                'forbidden_fn': ['surrender', 'release', 'flood', 'cascade'],
            },
        },
    },
    'ob': {
        'name': 'The Obedience Series',
        'voices': {
            1: {
                'fn': 'Obedience Anchor',
                'expected': {
                    'chime_anchor': ['chime', 'sound'],
                    'command_framing': ['obey', 'follow', 'good girl', 'serve'],
                },
                'forbidden_fn': ['surrender', 'let go', 'float', 'release'],
            },
        },
    },
    'rl': {
        'name': 'The Release Series',
        'voices': {
            1: {
                'fn': 'Release Anchor',
                'expected': {
                    'chime_anchor': ['chime', 'sound'],
                    'release_framing': ['release', 'flood', 'cascade', 'wave', 'wash over'],
                },
                'forbidden_fn': ['obey', 'kneel', 'submit', 'denial'],
            },
        },
    },
}


def parse_voices(script_path):
    """Extract voice segments from markdown script."""
    with open(script_path) as f:
        text = f.read()
    segments = re.split(r'### Voice (\d+)', text)
    voices = {}
    i = 1
    while i < len(segments):
        try:
            vnum = int(segments[i].strip())
            content = segments[i + 1].strip()
            # Clean metadata
            content = re.sub(r'\*[^*\n]+\*', '', content)
            content = re.sub(r'\[LOCK CLICK[^\]]*\]', '', content)
            content = re.sub(r'\[CHIME[^\]]*\]', '', content)
            content = re.sub(r'\[Silence[^\]]+\]', '', content)
            content = re.sub(r'—?\s*FRACTIONATION[^\n]*', '', content)
            voices[vnum] = content.strip()
            i += 2
        except (ValueError, IndexError):
            i += 1
    return voices


def check_voice(voice_num, text, arc_def):
    """Check one voice against its arc function. Returns list of findings."""
    findings = []
    fn_def = arc_def.get(voice_num)
    if not fn_def:
        return findings

    voice_fn = fn_def['fn']
    text_lower = text.lower()

    # Check expected elements
    for category, patterns in fn_def.get('expected', {}).items():
        found = False
        for pat in patterns:
            if re.search(pat, text_lower):
                found = True
                break
        if not found:
            findings.append({
                'voice': voice_num,
                'fn': voice_fn,
                'severity': 'warning',
                'category': category,
                'msg': f"Voice {voice_num} ({voice_fn}): missing '{category}' — expected: {', '.join(p[:30] for p in patterns[:3])}"
            })

    # Check for wrong-series function words
    for word in fn_def.get('forbidden_fn', []):
        if re.search(r'\b' + word + r'\b', text_lower):
            findings.append({
                'voice': voice_num,
                'fn': voice_fn,
                'severity': 'error',
                'category': 'forbidden_fn',
                'msg': f"Voice {voice_num} ({voice_fn}): contains '{word}' which belongs to different series function"
            })

    return findings


def check_script(script_path, series):
    """Run arc coherence on entire script. Returns (summary, findings_list)."""
    arc_def = ARC_MAPS.get(series, {}).get('voices', {})
    if not arc_def:
        return {'error': f"Series '{series}' not defined in arc map"}, []

    voices = parse_voices(script_path)
    all_findings = []
    missing_voices = []

    for vnum in sorted(arc_def.keys()):
        if vnum not in voices:
            missing_voices.append(vnum)
            continue
        findings = check_voice(vnum, voices[vnum], arc_def)
        all_findings.extend(findings)

    summary = {
        'series': series,
        'series_name': ARC_MAPS.get(series, {}).get('name', 'Unknown'),
        'total_voices': len(voices),
        'expected_voices': len(arc_def),
        'missing_voices': missing_voices,
        'warnings': len([f for f in all_findings if f['severity'] == 'warning']),
        'errors': len([f for f in all_findings if f['severity'] == 'error']),
    }

    return summary, all_findings


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <script.md> <series> [--json]", file=sys.stderr)
        print(f"  Series: sr, dc, ob, rl", file=sys.stderr)
        sys.exit(2)

    script_path = sys.argv[1]
    series = sys.argv[2]
    output_json = '--json' in sys.argv

    summary, findings = check_script(script_path, series)

    if output_json:
        print(json.dumps({'summary': summary, 'findings': findings}, indent=2))
    else:
        print(f"🔍 Arc Coherence: {summary['series_name']} ({series.upper()})")
        print(f"   Voices: {summary['total_voices']} present / {summary['expected_voices']} expected")
        if summary['missing_voices']:
            print(f"   ⚠️  Missing voices: {summary['missing_voices']}")
        print(f"   Errors: {summary['errors']}  |  Warnings: {summary['warnings']}")
        print()

        for f in findings:
            icon = '❌' if f['severity'] == 'error' else '⚠️'
            print(f"  {icon} {f['msg']}")

        if not findings:
            print("  ✅ All voices match arc functions")

    sys.exit(1 if summary.get('errors', 0) > 0 else 0)


if __name__ == '__main__':
    main()
