#!/usr/bin/env python3
"""Extract voice segments from a markdown script file. Used by all QE builders."""
import re, sys, os

script_md = sys.argv[1]
work_dir = sys.argv[2]

with open(script_md) as f:
    text = f.read()

# Split on ### Voice N headers
segments = re.split(r'### Voice \d+', text)
segments = [s.strip() for s in segments[1:]]

cleaned = []
for s in segments:
    s = re.sub(r'\*Tone:.*?\*', '', s)
    s = re.sub(r'\*\([^)]+\)\*', '', s)
    s = re.sub(r'^\([^)]+\)\s*', '', s)
    s = re.sub(r'\[LOCK CLICK[^\]]*\]', '', s)
    s = re.sub(r'\[CLOCK TICKING[^\]]*\]', '', s)
    s = re.sub(r'\[CHIME[^\]]*\]', '', s)
    s = re.sub(r'—?\s*FRACTIONATION\s*MOMENT\s*(?:—\s*FINAL\s*—)?\s*[★*]?\s*', '', s)
    s = re.sub(r'\[Silence\s*[—–-]\s*[^\]]+\]', '', s)
    s = re.sub(r'^---\s*$', '', s, flags=re.MULTILINE)
    s = re.sub(r'\n\s*\n+', ' ', s).strip()
    if s:
        cleaned.append(s)

for i, seg in enumerate(cleaned):
    path = os.path.join(work_dir, f'voice-{i+1}.txt')
    with open(path, 'w') as f:
        f.write(seg)
    print(f'  Segment {i+1}: {len(seg)} chars → voice-{i+1}.txt')

print(f'Total: {len(cleaned)} segments')
