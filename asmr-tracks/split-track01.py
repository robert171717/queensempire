import re

with open('/home/robert/etsy_products/asmr-tracks/track-01-script-recovered.txt') as f:
    text = f.read()

# Split by chime markers
segments = re.split(r'\(Bell chimes once\)', text)
segments = [s.strip() for s in segments if s.strip()]

print(f"Found {len(segments)} segments")

lines = [
    '# Track 01 — The First Chime',
    '## Seraphina — Surrender Sessions',
    ''
]

for i, seg in enumerate(segments):
    lines.append(f'### Voice {i+1}')
    lines.append('*Tone: Recovered from transcription*')
    lines.append('')
    lines.append(seg)
    lines.append('')

out = '\n'.join(lines)
with open('/home/robert/etsy_products/asmr-tracks/track-01-script.md', 'w') as f:
    f.write(out)

print(f"Saved track-01-script.md: {len(out)} chars, {len(segments)} segments")
for i, seg in enumerate(segments):
    print(f"  Voice {i+1}: {len(seg)} chars")
