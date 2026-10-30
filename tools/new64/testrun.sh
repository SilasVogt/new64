#!/usr/bin/env bash
# Launch the built game briefly with frame dumps enabled, then convert the
# last frames to PNG. Usage: testrun.sh <seconds> <outdir> [extra game args...]
set -euo pipefail
secs=${1:-20}; out=${2:-/tmp/new64-shots}; shift 2 || true
root=$(cd "$(dirname "$0")/../.." && pwd)
rm -rf "$out"; mkdir -p "$out/raw"
save=${NEW64_SAVE:-/tmp/new64-save}; mkdir -p "$save"
cd "$root/build/us_pc"
NEW64_SHOT_DIR="$out/raw" NEW64_SHOT_EVERY=${NEW64_SHOT_EVERY:-30} SDL_AUDIODRIVER=dummy \
  timeout "$secs" ./sm64coopdx --savepath "$save" --windowed --width 960 --height 720 \
  --skip-update-check --no-discord --skip-intro "$@" > "$out/game.log" 2>&1 || true
for f in "$out"/raw/*.ppm; do magick "$f" "${f%.ppm}.png" && rm "$f"; done 2>/dev/null || true
ls "$out/raw" | tail -3
