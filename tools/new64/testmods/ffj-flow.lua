-- name: new64-test
-- description: Frostfire Fjord flow test. Rides the real geysers, stomps the
-- Lundi puffins, walks through the area warps, and collects all 7 stars.
-- Run with coop_stay_in_level_after_star 1. Not for play.

local t, step, wait = 0, 1, 0
local maxY, tracking = -1e9, false
local puffinTries = 0

local function log(s) print("new64-ffj: " .. s) end

local function tp(x, y, z, yaw)
    local m = gMarioStates[0]
    m.pos.x, m.pos.y, m.pos.z = x, y, z
    m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
    m.forwardVel = 0
    if yaw then m.faceAngle.y = degrees_to_sm64(yaw) end
    set_mario_action(m, ACT_FREEFALL, 0)
end

local function flags()
    return save_file_get_star_flags(get_current_save_file_num() - 1, COURSE_FFJ - 1)
end

local function area() return gNetworkPlayers[0].currAreaIndex end

local function grab(beh)
    local o = obj_get_first_with_behavior_id(beh)
    if o == nil then log("no object for behavior " .. beh) return end
    tp(o.oPosX, o.oPosY - 20, o.oPosZ)
end

-- {name, frames, fn, [until-fn]}: wait `frames`, or until `until` returns true
local seq = {}
local function add(name, frames, fn, untilFn) seq[#seq + 1] = { name, frames, fn, untilFn } end

add("stand on geyser A", 260, function() tp(4250, 450, 2050); maxY = -1e9; tracking = true end)
add("geyser A result", 5, function() log(string.format("geyser A peak y %.0f (ground 419, ledge top 1500)", maxY)); tracking = false end)
add("stand on geyser B", 260, function() tp(4700, 1550, 2300); maxY = -1e9; tracking = true end)
add("geyser B result", 5, function() log(string.format("geyser B peak y %.0f (spire top 2600)", maxY)); tracking = false end)
add("spire star", 100, function() tp(5200, 2830, 2450) end)

add("lundi hunt", 20, function()
    local o = obj_get_first_with_behavior_id(id_bhvNew64Lundi)
    if o == nil then return end
    puffinTries = puffinTries + 1
    local m = gMarioStates[0]
    tp(o.oPosX, o.oPosY + 140, o.oPosZ)
    m.vel.y = -30
end)
add("lundi check", 1, function()
    local n = obj_count_objects_with_behavior_id(id_bhvNew64Lundi)
    if n > 0 and puffinTries < 60 then step = step - 2 end
    if n == 0 then log(string.format("all Lundi defeated after %d stomps", puffinTries)) end
end)
add("wait lundi star", 160, function() end)
add("lundi star", 100, function() tp(2600, 2640, 8300) end)

add("waterfall ray", 5, function()
    local ok, info = pcall(collision_find_surface_on_ray, -7800, 640, -1700, 0, 0, -700)
    if ok and info and info.surface then
        log(string.format("ray into alcove hit at z %.0f (star z -2456)", info.hitPos.z))
    else
        log("ray into alcove: clear")
    end
end)
add("waterfall star", 100, function() tp(-7800, 720, -2456) end)
add("crater rim", 60, function() tp(3760, 4300, -5600) end)
add("crater rim result", 5, function() log(string.format("crater rim floor %.0f", gMarioStates[0].floorHeight)) end)
add("crater star", 100, function() tp(5200, 4250, -5600) end)

add("walk into ice cave", 400, function() tp(-5530, 760, -3520) end, function() return area() == 2 end)
add("in ice cave", 30, function() log("area " .. area()) end)
local reds = { { 600, 0, -500 }, { -700, 0, 300 }, { -3300, 260, -2700 }, { -3300, 60, 2250 }, { -4400, 180, -300 },
               { 3600, 720, -1500 }, { 3000, 720, -2200 }, { 1200, 380, -3700 } }
for i, p in ipairs(reds) do add("red " .. i, 25, function() tp(p[1], p[2] + 40, p[3]) end) end
add("wait red star", 200, function() end)
add("red star", 100, function() tp(0, 540, 0) end)
add("leave ice cave", 400, function() tp(0, 40, 4350) end, function() return area() == 1 end)
add("back outside", 30, function()
    local m = gMarioStates[0]
    log(string.format("area %d at %.0f %.0f %.0f", area(), m.pos.x, m.pos.y, m.pos.z))
end)

add("drop into lava tube", 400, function() tp(1200, 1900, -5200) end, function() return area() == 3 end)
add("in magma hall", 60, function() log("area " .. area()) end)
add("push bully into lava", 300, function()
    local b = obj_get_first_with_behavior_id(id_bhvBigChillBully)
    if b == nil then log("no big chill bully") return end
    b.oPosX, b.oPosY, b.oPosZ = 0, 450, -2700
    tp(0, 320, -1600)
end)
add("chill star", 100, function() tp(0, 930, -1300) end)
add("99 coins", 30, function()
    local m = gMarioStates[0]
    m.numCoins = 99
    hud_set_value(HUD_DISPLAY_COINS, 99)
    local c = obj_get_first_with_behavior_id(id_bhvYellowCoin)
    if c ~= nil then tp(c.oPosX, c.oPosY, c.oPosZ) else log("no coin") end
end)
add("wait 100 coin star", 150, function() end)
add("100 coin star", 100, function() grab(id_bhvSpawnedStarNoLevelExit) end)
add("leave magma hall", 400, function() tp(0, 40, 5000) end, function() return area() == 1 end)
add("done", 30, function()
    local m = gMarioStates[0]
    log(string.format("FINAL flags 0x%02X, back in area %d at %.0f %.0f %.0f", flags(), area(), m.pos.x, m.pos.y, m.pos.z))
end)

hook_event(HOOK_ON_DIALOG, function() return false end)

hook_event(HOOK_UPDATE, function()
    t = t + 1
    if t == 30 then warp_to_level(LEVEL_FFJ, 1, 1) end
end)

hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 then return end
    m.health = 0x880
    if gNetworkPlayers[0].currLevelNum ~= LEVEL_FFJ then return end
    if tracking and m.pos.y > maxY then maxY = m.pos.y end
    local cur = seq[step - 1]
    if wait > 0 then
        wait = wait - 1
        if cur and cur[4] and cur[4]() then wait = 0 end
        return
    end
    if step == 1 and t < 150 then return end
    local s = seq[step]
    if s == nil then return end
    disable_time_stop()
    local before = flags()
    step = step + 1
    s[3]()
    log(string.format("step %d %s (flags before 0x%02X)", step - 1, s[1], before))
    wait = s[2]
end)
