#!/usr/bin/env bash
# Play new64 single player: hosts a game that only listens on localhost and
# keeps saves in ~/.local/share/new64 (the save layout differs from upstream
# sm64coopdx, so the two must not share a save folder).
#
# Needs a build (make) and the US ROM, either as baserom.us.z64 in the repo
# root or already copied into the save folder.
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
bin="$root/build/us_pc/sm64coopdx"
save="${NEW64_SAVE:-$HOME/.local/share/new64}"
[ -x "$bin" ] || { echo "No build found. Run: make -j\$(nproc)" >&2; exit 1; }
mkdir -p "$save"
if [ ! -f "$save/baserom.us.z64" ] && [ -f "$root/baserom.us.z64" ]; then
    cp "$root/baserom.us.z64" "$save/baserom.us.z64"
fi
cd "$root/build/us_pc"
NEW64_BIND_LOCALHOST=1 exec "$bin" --savepath "$save" --server 7777 --playercount 1 \
    --skip-update-check --no-discord "$@"
