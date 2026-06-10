#!/usr/bin/env python3
"""
Preflight: Scan track scripts for unspoken markers that would leak into voice audio.
Run before building any track. Exit code 1 = fix required.
"""
import re, sys, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Patterns that should NOT appear in spoken voice text
FORBIDDEN_PATTERNS = [
    (r'—\s*FRACTIONATION\s*MOMENT', "FRACTIONATION marker (script direction — will leak into voice)"),
    (r'\[Silence\s*[—–-]', "[Silence] marker (script direction — will leak into voice)"),
]

def check_script(filepath):
    with open(filepath) as f:
        content = f.read()
    
    errors = []
    # Split into voice segments
    segments = re.split(r'### Voice \d+', content)
    segments = segments[1:]  # skip header
    
    for i, seg in enumerate(segments):
        seg_clean = seg.strip()
        for pattern, desc in FORBIDDEN_PATTERNS:
            matches = re.findall(pattern, seg_clean, re.MULTILINE)
            for m in matches:
                # Show context
                idx = seg_clean.find(m)
                ctx = seg_clean[max(0,idx-20):idx+len(m)+20].replace('\n',' ')
                errors.append(f"  Voice {i+1}: {desc}")
                errors.append(f"    Found: \"{m}\"")
                errors.append(f"    Context: ...{ctx}...")
    
    return errors

def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = sorted(os.path.join(SCRIPT_DIR, f) for f in os.listdir(SCRIPT_DIR) 
                      if f.startswith('track-dc-') and f.endswith('-script.md'))
    
    total_errors = 0
    for f in files:
        if not os.path.exists(f):
            continue
        errors = check_script(f)
        if errors:
            print(f"❌ {os.path.basename(f)} — {len(errors)//3} issue(s):")
            for e in errors:
                print(e)
            total_errors += len(errors)//3
        else:
            print(f"✅ {os.path.basename(f)} — clean")
    
    if total_errors:
        print(f"\n🚫 {total_errors} total issues found. Fix before building.")
        sys.exit(1)
    else:
        print(f"\n✅ All scripts clean.")
        sys.exit(0)

if __name__ == '__main__':
    main()
