#!/usr/bin/env python3
"""
QE ASMR Script Quality Gate — audits script before voice generation.
Scores pacing, trigger integration, fractionation, tone, safety, arc.
Flags issues BEFORE credits are burned on ElevenLabs.

Also runs series-aware word check: flags words inappropriate for the
script's series (e.g. "obey" in a Surrender track).
"""
import json, sys, os, subprocess, re

SCRIPT_MD = sys.argv[1]
SERIES = sys.argv[2] if len(sys.argv) > 2 else None  # sr, dc, ob, rl

# Read script
with open(SCRIPT_MD) as f:
    text = f.read()

# ─── Series-aware word check ───
SERIES_WORDS = {
    "sr": {  # Surrender — words that should NOT appear
        "forbidden": ["obey", "kneel", "submit", "beg", "master", "mistress", "worship", "owned"],
        "expected": ["surrender", "let go", "sink", "release", "float", "trust", "give in"],
        "label": "Surrender"
    },
    "dc": {  # Denial & Craving
        "forbidden": ["obey", "kneel", "submit", "release", "flood", "pleasure cascade"],
        "expected": ["denial", "ache", "wait", "want", "crave", "withhold", "earn"],
        "label": "Denial & Craving"
    },
    "ob": {  # Obedience
        "forbidden": ["surrender", "let go", "float", "release", "flood", "pleasure cascade"],
        "expected": ["obey", "submit", "serve", "kneel", "follow", "command", "good girl"],
        "label": "Obedience"
    },
    "rl": {  # Release
        "forbidden": ["obey", "kneel", "submit", "surrender", "denial", "withhold"],
        "expected": ["release", "flood", "pleasure", "cascade", "wave", "wash over", "let it out"],
        "label": "Release"
    }
}

series_warnings = []
if SERIES and SERIES in SERIES_WORDS:
    rules = SERIES_WORDS[SERIES]
    text_lower = text.lower()
    for word in rules["forbidden"]:
        # Word-boundary match — "beg" should NOT match "begins"
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower):
            # Find the actual line
            for i, line in enumerate(text.split('\n'), 1):
                if re.search(pattern, line.lower()):
                    series_warnings.append(f"⚠️  SERIES VIOLATION: '{word}' found (Voice area, line {i}) — this is not a {rules['label']}-series word")
                    break
    if series_warnings:
        print("┌─ Series-Aware Word Check ──────────────────────────────")
        for w in series_warnings:
            print(f"│ {w}")
        print("└────────────────────────────────────────────────────────\n")

# Extract voice segments
segments = re.split(r'### Voice \d+\n', text)[1:]
if not segments:
    print("ERROR: No voice segments found")
    sys.exit(1)

# Get API key from Doppler
api_key = subprocess.run(
    ['doppler', 'secrets', 'get', 'DEEPSEEK_API_KEY', '--plain'],
    capture_output=True, text=True
).stdout.strip()

if not api_key:
    print("⚠️  No DeepSeek API key — skipping critique (non-fatal)")
    sys.exit(0)

# Build the rubric prompt
rubric = f"""You are an ASMR/hypnosis script quality auditor for a premium audio series called Queen's Empire.

The voice is "Serafina" — a sensual, authoritative female voice at 0.70x speed.
Each script is split into 6 voice segments marked ### Voice N.
Trigger sounds: ding/chime between segments.

Analyze this script across these dimensions. Score each 1-10 and give ONE actionable fix per dimension:

1. PACING: Are segment lengths balanced? Any segment over 1,200 chars will sound rushed at 0.70x. CRITICAL: leading '...' at voice starts renders as breath artifacts — use paragraph breaks (blank line) instead for natural pauses.
2. TRIGGER INTEGRATION: Does the script naturally reference the chime/trigger sound?
3. FRACTIONATION ARC: Does the countdown (if present) escalate depth properly?
4. TONE CONSISTENCY: Does Serafina's persona stay consistent throughout?
5. LISTENER SAFETY: Proper wakening protocol at the end? No problematic suggestions?
6. EMOTIONAL ARC: Does the script build tension and release it?

Return ONLY valid JSON:
{{
  "overall_score": 6.5,
  "verdict": "PASS" or "REVIEW" or "FAIL",
  "dimensions": {{
    "pacing": {{"score": 7, "issue": "Voice 5 is 1855 chars — may sound rushed at 0.70x", "fix": "Split voice 5 into two segments at the countdown"}},
    "trigger_integration": {{"score": 8, "issue": null, "fix": null}},
    "fractionation_arc": {{"score": 6, "issue": "...", "fix": "..."}},
    "tone_consistency": {{"score": 9, "issue": null, "fix": null}},
    "listener_safety": {{"score": 10, "issue": null, "fix": null}},
    "emotional_arc": {{"score": 7, "issue": "...", "fix": "..."}}
  }},
  "top_fix": "Split voice 5 into two segments to improve pacing.",
  "estimated_credit_savings": "Split prevents 1,855 char regeneration on pacing fixes"
}}

Segments with character counts:
"""
for i, seg in enumerate(segments, 1):
    rubric += f"Voice {i}: {len(seg.strip())} chars\n"

rubric += f"\nFull script:\n```\n{text}\n```"

# Call DeepSeek
import urllib.request
payload = json.dumps({
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": rubric}],
    "temperature": 0.3,
    "max_tokens": 800
}).encode()

req = urllib.request.Request(
    "https://api.deepseek.com/v1/chat/completions",
    data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
)

try:
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    content = resp["choices"][0]["message"]["content"]
    # Extract JSON from response (may have markdown wrapping)
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    result = json.loads(content)
except Exception as e:
    print(f"⚠️  Critique API error: {e} — skipping (non-fatal)")
    sys.exit(0)

# Display results
dims = result.get("dimensions", {})
scores = []
for dim, data in dims.items():
    s = data.get("score", 0)
    if isinstance(s, (int, float)):
        scores.append(s)

# Compute overall from actual dimension scores — never trust DeepSeek's aggregate
overall = round(sum(scores) / len(scores), 1) if scores else 0
verdict = "PASS" if overall >= 6 else "REVIEW" if overall >= 4 else "FAIL"

print(f"\n📋 SCRIPT QUALITY GATE: {os.path.basename(SCRIPT_MD)}")
# Show per-dimension breakdown first
for dim, data in dims.items():
    name = dim.replace("_", " ").title()
    score = data.get("score", "?")
    icon = "✅" if score >= 8 else "🟡" if score >= 6 else "🔴"
    print(f"   {icon} {name}: {score}/10")
    if data.get("issue"):
        print(f"      → {data['issue']}")
# Then overall (computed, not hallucinated)
print(f"\n   Overall: {overall}/10 — {verdict}")

top_fix = result.get("top_fix", "")
if top_fix:
    print(f"\n💡 TOP FIX: {top_fix}")
if result.get("estimated_credit_savings"):
    print(f"💰 {result['estimated_credit_savings']}")

# Exit codes
if verdict == "FAIL":
    print("\n🛑 Gate: FAIL — fix issues before building")
    sys.exit(1)
elif verdict == "REVIEW":
    print("\n⚠️  Gate: REVIEW — recommended fixes before building")
    # Non-fatal — continue with warning
else:
    print("\n✅ Gate: PASS")
