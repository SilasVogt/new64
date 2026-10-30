#!/usr/bin/env bash
# Write a throwaway Lua mod into the test save dir that warps Mario to a level
# and then teleports him through a list of poses, holding each for HOLD frames.
# Usage: make_testmod.sh <savedir> <level> <area> <act> ["x,y,z,yaw;x,y,z,yaw;..."]
# Env: HOLD (frames per pose, default 150)
set -euo pipefail
save=$1; lvl=$2; area=$3; act=$4; poses=${5:-}
hold=${HOLD:-150}
mkdir -p "$save/mods"
lua_poses=""
IFS=';' read -ra items <<< "$poses"
for it in "${items[@]}"; do
    [ -z "$it" ] && continue
    IFS=',' read -r x y z yaw <<< "$it"
    lua_poses+="{${x},${y},${z},${yaw:-0}},"
done
cat > "$save/mods/new64-test.lua" <<LUA
-- name: new64-test
-- description: automated test harness (not for play)
local poses = { $lua_poses }
local t = 0
local warped = false
local inLevel = 0
hook_event(HOOK_UPDATE, function()
    t = t + 1
    if not warped and t > 30 then
        warped = true
        warp_to_level($lvl, $area, $act)
    end
end)
hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 then return end
    m.health = 0x880
    if gNetworkPlayers[0].currLevelNum ~= $lvl then return end
    inLevel = inLevel + 1
    local idx = math.floor(inLevel / $hold) + 1
    local p = poses[idx]
    if p ~= nil and inLevel % $hold == 1 then
        m.pos.x, m.pos.y, m.pos.z = p[1], p[2], p[3]
        m.faceAngle.y = degrees_to_sm64(p[4])
        m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
        m.forwardVel = 0
        set_mario_action(m, ACT_FREEFALL, 0)
        print(string.format("new64-test: pose %d at frame %d", idx, inLevel))
    end
    if p ~= nil and inLevel % $hold == 40 then
        print(string.format("new64-test: pose %d floor %.0f action %08x", idx, m.floorHeight, m.action))
    end
end)
LUA
