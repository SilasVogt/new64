-- name: new64-test
-- description: Fixed-camera screenshots of new64's courses, for before/after
-- comparisons. Holds Mario at a spot, locks the camera to a pose and lets the
-- frame dumper (NEW64_SHOT_DIR) capture it. Pair with tools/new64/shot_sheet.py.
-- tools/new64/shots.sh picks the course by rewriting WHICH. Not for play.

local WHICH = "ffj"
local ONLY = nil -- e.g. { 3, 4, 6 } to retake a few shots (shots.sh sets this)
local HOLD = 100 -- frames per shot

-- { area, label, mario x, mario z, camera x, y, z, focus x, y, z }
local SHOTS = {
    ffj = {
        { 1, "beach, volcano and glacier",  0, 5350,     -600, 800, 6900,     1500, 1500, -1500 },
        { 1, "sea stacks and columns",      -1500, 5300, -400, 1000, 5600,    2500, 1300, 8000 },
        { 1, "lava river from the east",    3800, 900,   4300, 2400, 1300,    2300, 700, -1700 },
        { 1, "lava pool",                   2100, 600,   2700, 1200, 1800,    1300, 250, 100 },
        { 1, "volcano from the south",      2000, 1000,  1500, 2400, 1900,    5200, 2700, -5600 },
        { 1, "crater from the rim",         4040, -4930, 3500, 5400, -4300,   5200, 3600, -5700 },
        { 1, "inside the crater",           4100, -4950, 4250, 4350, -4950,   5300, 3700, -5700 },
        { 1, "waterfall",                   -7000, -600, -7350, 1500, 1100,   -7800, 1450, -2000 },
        { 1, "waterfall close",             -7050, -650, -7250, 700, -1050,   -7800, 800, -2000 },
        { 1, "geysers and spire",           3800, 3300,  2600, 1700, 4400,    4700, 1300, 2200 },
        { 1, "hot spring and village",      -2600, 2200, -1600, 1200, 1300,   -3800, 300, 3300 },
        { 1, "glacier and ice cave",        -4300, -3400, -2600, 1800, -1500, -5300, 900, -3400 },
        { 1, "lava tube skylight",          400, -5200,  -200, 3300, -3900,   1200, 1500, -5200 },
        { 2, "ice cave entry",              0, 2600,     0, 450, 3300,        0, 300, 1000 },
        { 2, "crystal hall",                0, 1300,     900, 700, 1200,      -300, 200, -400 },
        { 2, "upper gallery",               3400, -1700, 2600, 1300, -1000,   3500, 800, -1900 },
        { 2, "maze tunnel",                 -2900, 0,    -2300, 450, 0,       -3300, 250, 0 },
        { 2, "ice slide",                   3300, -2400, 3000, 1000, -2600,   1900, 400, -3900 },
        { 3, "lava tube",                   300, 4300,   0, 500, 4800,        0, 200, 3000 },
        { 3, "magma hall from the tube",    300, 2300,   0, 900, 2500,        0, 200, -1300 },
        { 3, "ice floe",                    0, -800,     1800, 1100, 300,     0, 300, -1300 },
        { 3, "islands and sinking platforms", 0, -600,   -300, 1400, -300,    2300, 200, -2400 },
    },
    sgi = {
        { 1, "spawn isle and tower",        0, 5700,     -900, 900, 7400,     0, 1200, 0 },
        { 1, "central garden",              -300, 1500,  -2400, 1300, 2600,   200, 600, -300 },
        { 1, "King Bob-omb's arena",        4300, -300,  2300, 2200, 900,     5400, 1100, -700 },
        { 1, "west islets",                 -3100, 900,  -1200, 1900, 1800,   -4300, 700, -2000 },
        { 1, "north bridge and isle",       -150, -3050, 900, 1600, -1200,    -300, 800, -5600 },
        { 1, "lonely isle",                 1500, -700,  1200, 2300, -2400,   3200, 2000, -5200 },
        { 1, "under the islands",           0, 4800,     1800, -900, 3600,    0, 0, 1500 },
    },
}

local LEVELS = { ffj = LEVEL_FFJ, sgi = LEVEL_SGI }
local NODES = { [1] = 0x0A, [2] = 0x0B, [3] = 0x0D }
local shots = SHOTS[WHICH]
if ONLY ~= nil then
    local some = {}
    for _, n in ipairs(ONLY) do some[#some + 1] = shots[n] end
    shots = some
end
local level = LEVELS[WHICH]

local t, i, f = 0, 1, 0
local warping = false

local function log(s) print("new64-shot: " .. s) end

hook_event(HOOK_ON_DIALOG, function() return false end)

hook_event(HOOK_UPDATE, function()
    t = t + 1
    if t == 2 then
        for n, s in ipairs(shots) do log(string.format("plan %d %d %d %s", n, s[3], s[4], s[2])) end
    end
    if t == 30 then warp_to_level(level, 1, 1) end
end)

hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or gNetworkPlayers[0].currLevelNum ~= level then return end
    m.health = 0x880
    local s = shots[i]
    if s == nil then
        if f == 0 then log("done") end
        f = 1
        return
    end
    if gNetworkPlayers[0].currAreaIndex ~= s[1] then
        if not warping then
            warping = true
            warp_to_warpnode(level, s[1], 1, NODES[s[1]])
        end
        return
    end
    warping = false
    hud_hide()
    camera_freeze()
    disable_time_stop() -- boss intros would freeze the shot list
    f = f + 1

    -- Hold Mario on the ground at the shot's spot.
    local y = find_floor_height(s[3], 20000, s[4])
    m.pos.x, m.pos.y, m.pos.z = s[3], y, s[4]
    m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
    m.forwardVel = 0
    if m.action ~= ACT_IDLE then set_mario_action(m, ACT_IDLE, 0) end

    local l = gLakituState
    l.pos.x, l.pos.y, l.pos.z = s[5], s[6], s[7]
    l.focus.x, l.focus.y, l.focus.z = s[8], s[9], s[10]
    l.curPos.x, l.curPos.y, l.curPos.z = s[5], s[6], s[7]
    l.curFocus.x, l.curFocus.y, l.curFocus.z = s[8], s[9], s[10]
    l.roll = 0

    if f == 1 then log(string.format("shot %d %s", i, s[2])) end
    if f >= HOLD then
        f = 0
        i = i + 1
    end
end)
