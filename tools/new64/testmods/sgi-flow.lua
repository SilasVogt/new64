-- name: new64-test
-- description: Sky Garden Isles flow test: collects all 7 stars by teleporting
-- (and one real double jump) and logs save flags. Not for play. The cannon
-- shot is covered by sgi-cannon.lua.
-- Run with coop_stay_in_level_after_star 1 so stars don't exit the course.

local LEVEL = LEVEL_SGI
local t, step, wait = 0, 1, 0
local holdA = 0

local function log(s) print("new64-flow: " .. s) end

local function tp(x, y, z, yaw)
    local m = gMarioStates[0]
    m.pos.x, m.pos.y, m.pos.z = x, y, z
    m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
    m.forwardVel = 0
    if yaw then m.faceAngle.y = degrees_to_sm64(yaw) end
    set_mario_action(m, ACT_FREEFALL, 0)
end

local function flags()
    return save_file_get_star_flags(get_current_save_file_num() - 1, COURSE_SGI - 1)
end

local function grab_star(beh)
    local o = obj_get_first_with_behavior_id(beh)
    if o == nil then log("no star object for behavior " .. beh) return end
    tp(o.oPosX, o.oPosY - 20, o.oPosZ)
end


local function diag(tag)
    local m = gMarioStates[0]
    local hrs = obj_get_first_with_behavior_id(id_bhvHiddenRedCoinStar)
    local hs = obj_get_first_with_behavior_id(id_bhvHiddenStar)
    log(string.format("%s: coins %d red %d trig %d hrsCounter %s hsCounter %s king %d spawnStar %d noExit %d spawned %d boxes %d",
        tag, m.numCoins, obj_count_objects_with_behavior_id(id_bhvRedCoin),
        obj_count_objects_with_behavior_id(id_bhvHiddenStarTrigger),
        hrs and tostring(hrs.oHiddenStarTriggerCounter) or "nil", hs and tostring(hs.oHiddenStarTriggerCounter) or "nil",
        obj_count_objects_with_behavior_id(id_bhvKingBobomb), obj_count_objects_with_behavior_id(id_bhvStarSpawnCoordinates),
        obj_count_objects_with_behavior_id(id_bhvSpawnedStarNoLevelExit), obj_count_objects_with_behavior_id(id_bhvSpawnedStar),
        obj_count_objects_with_behavior_id(id_bhvExclamationBox)))
end

-- Each entry: {name, frames to wait afterwards, function}
local seq = {}
local function add(name, frames, fn) seq[#seq + 1] = { name, frames, fn } end

add("tower star", 120, function() tp(0, 3260, 0) end)

local reds = {
    { -2900, 400, 800 }, { -3700, 500, 300 }, { -4300, 600, -300 }, { -5150, 1100, -1950 },
    { -4550, 900, -2500 }, { -3850, 1000, -3200 }, { -4350, 1000, -3050 }, { -2250, 300, 450 },
}
for i, p in ipairs(reds) do add("red coin " .. i, 20, function() tp(p[1], p[2] + 40, p[3]) end) end
add("wait red star", 200, function() end)
add("red coin star", 120, function() tp(-2600, 1150 + 230, -3700) end)

local secrets = { { 0, 260, -560 }, { 0, 60, 6000 }, { -700, 1240, -5900 }, { 6750, 1160, -700 } }
for i, p in ipairs(secrets) do add("secret " .. i, 20, function() tp(p[1], p[2] + 20, p[3]) end) end
add("secret 5", 20, function()
    local a = math.rad(11 * 26)
    tp(math.sin(a) * 650, 330 + 11 * 150 + 80, math.cos(a) * 650)
end)
add("wait secret star", 200, function() end)
add("secret star", 120, function() tp(-900, 600, 1000) end)

add("box platform", 45, function() tp(-150, 450, -3050) end)
add("double jump", 90, function()
    local m = gMarioStates[0]
    holdA = 30 -- releasing A early cuts a jump short
    set_mario_action(m, ACT_DOUBLE_JUMP, 0)
end)
add("box star", 120, function() grab_star(id_bhvSpawnedStar) end)

add("king defeat", 220, function()
    local k = obj_get_first_with_behavior_id(id_bhvKingBobomb)
    if k == nil then log("no king") return end
    tp(5000, 1150, -700)
    k.oAction = 8
end)
add("king star", 120, function() tp(5400, 1600 - 20, -700) end)

add("lonely star", 120, function() tp(3200, 2000 + 180, -5200) end)

add("99 coins", 30, function()
    local m = gMarioStates[0]
    m.numCoins = 99
    hud_set_value(HUD_DISPLAY_COINS, 99)
    local c = obj_get_first_with_behavior_id(id_bhvYellowCoin)
    if c ~= nil then tp(c.oPosX, c.oPosY, c.oPosZ) else log("no coin left") end
end)
add("wait 100 coin star", 150, function() log("coins now " .. gMarioStates[0].numCoins) end)
add("100 coin star", 120, function() grab_star(id_bhvSpawnedStarNoLevelExit) end)
add("done", 60, function()
    log(string.format("FINAL flags 0x%02X total %d", flags(),
        save_file_get_total_star_count(get_current_save_file_num() - 1, COURSE_MIN - 1, COURSE_MAX - 1)))
end)

hook_event(HOOK_ON_DIALOG, function() return false end)

hook_event(HOOK_UPDATE, function()
    t = t + 1
    if t == 30 then warp_to_level(LEVEL, 1, 1) end
end)

hook_event(HOOK_BEFORE_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or holdA <= 0 then return end
    holdA = holdA - 1
    m.input = m.input | INPUT_A_DOWN
    m.controller.buttonDown = m.controller.buttonDown | A_BUTTON
end)

hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 then return end
    m.health = 0x880
    if gNetworkPlayers[0].currLevelNum ~= LEVEL then return end
    if wait > 0 then wait = wait - 1 return end
    if step == 1 and t < 120 then return end
    local s = seq[step]
    if s == nil then return end
    -- Suppressed star dialogs never release the star dance time stop.
    disable_time_stop()
    local before = flags()
    s[3]()
    log(string.format("step %d %s (flags before 0x%02X)", step, s[1], before))
    diag("  after " .. s[1])
    wait = s[2]
    step = step + 1
end)
