# QE ASMR Pipeline — Technical Documentation for Grok Review

## Overview
Production pipeline for 8-track erotic ASMR hypnosis series "Surrender Sessions." All audio generated through ElevenLabs (voice + sound effects). No Microsoft TTS, no external audio sources.

## Voice Generation (ElevenLabs Text-to-Speech)
- **Voice:** Serafina (ID: `4tRn1lSkEn13EVTuqb0g`) — "Sensual Temptress"
- **Model:** `eleven_multilingual_v2`
- **Speed:** 0.70x (slower, more seductive pacing)
- **Stability:** 0.5 (allows natural variation)
- **Similarity Boost:** 0.75 (stays true to Serafina's timbre)
- **API key:** Stored in Doppler (`ELEVENLABS_API_KEY`)
- **Retry logic:** 5 attempts with exponential backoff for 429 rate limits

## Sound Effects (ElevenLabs SFX)
- **Ding:** `ding-a3.mp3` — crystal singing bowl chime, 3 seconds
- **Generation:** ElevenLabs Sound Effects API (text-to-sfx)
- **Ding gradient:** 25/20/20/15/22/15% volume below voice level
- Six ding variants at different volumes for natural variation

## Production Chain (ffmpeg)
```
highpass=f=80 → volume=1.8 → aecho=0.8:0.4:10:0.15 → afftdn=nr=12
```
- `highpass=f=80`: Cuts sub-bass rumble below 80Hz
- `volume=1.8`: Boosts to full listening level
- `aecho=0.8:0.4:10:0.15`: Creates room ambience (NOT convolution reverb — rejected as too distant/echoey)
- `afftdn=nr=12`: Noise reduction to clean any digital artifacts

## Track Assembly
- **Build script:** `~/etsy_products/asmr-tracks/build-track.sh`
- **Script extraction:** Parses markdown with `### Voice N` headers
- **Silence generation:** ffmpeg `anullsrc` at 44100Hz stereo
- **Mixing:** ffmpeg concat demuxer (lossless join)
- **Discord compression:** 96kbps stereo MP3 (<8MB limit)

## Silence Timing
- Pre-ding: 2s
- Post-ding: 2-3s  
- Post-voice: 8-12s (varies by track)
- Total gap between voice segments: ~14-18s
- Trailing silence: 5-8s

## Chime Progression
| Track | Chimes | Philosophy |
|-------|--------|------------|
| 1-2 | 6 | Heavy anchoring — chime = Serafina's presence |
| 3-4 | 4 | Voice takeover — chime becomes reminder, not anchor |
| 5-6 | 3 | Minimal reliance — voice IS the addiction |
| 7-8 | 2 | Punctuation only — chime as familiar friend |

## Etsy Compliance Considerations
- **Content labeling:** Adult/mature content must be properly tagged
- **No prohibited content:** No sexual acts described, no nudity, no illegal themes
- **Hypnosis disclosure:** Etsy allows hypnosis/ASMR content; no specific restrictions
- **Age restriction:** Track descriptions should note "for adult listeners only"
- **Medical disclaimer:** Standard "not a substitute for medical treatment"
- **Download delivery:** MP3 files delivered as digital downloads
- **Shop policies:** Clear refund policy (digital goods = no refunds typically)

## ElevenLabs Utilization
Every audio element uses ElevenLabs:
- ✅ Voice: Text-to-Speech API
- ✅ Chime/Ding: Sound Effects API  
- ❌ NOT using: ElevenLabs Voice Changer, Speech-to-Speech, Dubbing
- Potential future: ElevenLabs ambient background generation for track intros

## Questions for Grok
1. Is the production chain optimal for erotic ASMR? Any filter order or parameter improvements?
2. Are the silence gaps appropriate for hypnosis/trance maintenance?
3. Is the chime progression (6→6→4→4→3→3→2→2) psychologically sound?
4. Can we use any additional ElevenLabs features we're currently missing?
5. Etsy compliance: are we missing anything that could get listings flagged?
6. The speed setting (0.70x): optimal for seductive ASMR, or should it vary by track?
7. Any recommended A/B testing methodology to validate our chain choices?
