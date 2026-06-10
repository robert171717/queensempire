#!/bin/bash
EK=$(doppler secrets get ELEVENLABS_API_KEY --plain)
curl -s "https://api.elevenlabs.io/v1/sound-effects" \
  -H "xi-api-key: $EK" \
  -H "Content-Type: application/json" \
  -d '{"text":"crystal singing bowl resonance","duration_seconds":3,"prompt_influence":0.3}' \
  -o /home/robert/etsy_products/asmr-tracks/ding-a3-test.mp3 \
  -w "%{http_code} %{size_download}"
echo ""
