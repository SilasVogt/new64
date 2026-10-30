#!/usr/bin/env bash
# Fixed-camera screenshots of a course: runs testmods/shots.lua for the given
# course and builds a contact sheet. Usage: shots.sh <ffj|sgi> <outdir> [seconds] [only]
# where only is a comma list of shot numbers to retake (e.g. 3,4,6).
# Compare two runs: shot_sheet.py --compare <before dir> <after dir> <out prefix>
set -euo pipefail
which=$1; out=$2; secs=${3:-}; only=${4:-}
here=$(cd "$(dirname "$0")" && pwd)
save=${NEW64_SAVE:-/tmp/new64-save}
mkdir -p "$save/mods"
only_lua=nil; [ -z "$only" ] || only_lua="{ $only }"
sed -e "s/^local WHICH = .*/local WHICH = \"$which\"/" -e "s/^local ONLY = nil/local ONLY = $only_lua/" \
    "$here/testmods/shots.lua" > "$save/mods/new64-test.lua"
[ -n "$secs" ] || secs=$([ "$which" = ffj ] && echo 110 || echo 45)
NEW64_SAVE="$save" NEW64_SHOT_EVERY=${NEW64_SHOT_EVERY:-30} "$here/testrun.sh" "$secs" "$out" > /dev/null
grep -q "new64-shot: done" "$out/game.log" || echo "warning: the shot list did not finish (raise the time limit)"
python3 "$here/shot_sheet.py" "$out"
