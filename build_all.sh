#!/usr/bin/env bash
# One-shot build of the WC26 promo: clip cache -> frames -> sfx -> mux.
set -euo pipefail
cd "$(dirname "$0")"

# 1. clip frame cache (build_video.py reads JPEG sequences from /tmp/cf)
for c in assets/clips/*.mp4; do
  name="$(basename "$c" .mp4)"
  if [ ! -d "/tmp/cf/$name" ]; then
    mkdir -p "/tmp/cf/$name"
    ffmpeg -v error -i "$c" -q:v 3 "/tmp/cf/$name/f_%04d.jpg"
  fi
done

# 2. silent video + sfx
python3 build_sfx.py
python3 build_video.py

# 3. mux voiceover (full) + synthesized sfx bed (under it)
ffmpeg -v error -y \
  -i output/video_silent.mp4 -i assets/voiceover.mp3 -i output/sfx.wav \
  -filter_complex "[1:a]volume=1.0[vo];[2:a]volume=0.55[sx];[vo][sx]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest \
  output/wc26_promo.mp4
echo "done -> output/wc26_promo.mp4"
