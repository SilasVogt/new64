-- name: new64-test
-- description: Sky Garden Isles cannon test: unlocks the cannon, climbs in,
-- fires at a sweep of pitches and logs where Mario lands. Not for play.

local CANNON = { 900, 600, -1250 }
local ISLE = { 3200, 2000, -5200 }
local PITCHES = { 30, 40, 45, 50, 55, 60, 64, 67, 70, 73, 76 }

local t, f, i, state, timer = 0, 0, 1, "enter", 0
local pressA = false

local function log(s) print("new64-cannon: " .. s) end

local function tp(m, x, y, z)
    m.pos.x, m.pos.y, m.pos.z = x, y, z
    m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
    m.forwardVel = 0
    set_mario_action(m, ACT_FREEFALL, 0)
end

hook_event(HOOK_ON_DIALOG, function() return false end)

hook_event(HOOK_UPDATE, function()
    t = t + 1
    if t == 20 then
        -- cannon flag for course N lives in the byte of course N (index N)
        save_file_set_star_flags(get_current_save_file_num() - 1, COURSE_SGI, 0x80)
    end
    if t == 30 then warp_to_level(LEVEL_SGI, 1, 1) end
end)

hook_event(HOOK_BEFORE_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or not pressA then return end
    pressA = false
    m.input = m.input | INPUT_A_PRESSED
    m.controller.buttonPressed = m.controller.buttonPressed | A_BUTTON
end)

hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or gNetworkPlayers[0].currLevelNum ~= LEVEL_SGI then return end
    m.health = 0x880
    f = f + 1
    if f < 60 or PITCHES[i] == nil then return end
    timer = timer + 1
    if state == "enter" then
        if timer == 1 then tp(m, CANNON[1], CANNON[2] + 400, CANNON[3]) end
        if m.action == ACT_IN_CANNON and m.actionState == 2 then
            state, timer = "aim", 0
        elseif timer > 150 then
            log(string.format("could not enter cannon (action %08x)", m.action))
            state, timer = "reset", 0
        end
    elseif state == "aim" then
        m.faceAngle.x = degrees_to_sm64(PITCHES[i])
        m.marioObj.oMarioCannonInputYaw = 0
        if timer == 10 then pressA = true end
        if timer == 9 then
            log(string.format("aim: objYaw %d inputYaw %d faceYaw %d pitch %d", m.marioObj.oMarioCannonObjectYaw,
                m.marioObj.oMarioCannonInputYaw, m.faceAngle.y, m.faceAngle.x))
        end
        if m.action == ACT_SHOT_FROM_CANNON then state, timer = "fly", 0 end
        if timer > 60 then log("did not fire"); state, timer = "reset", 0 end
    elseif state == "fly" then
        local d = math.sqrt((m.pos.x - ISLE[1]) ^ 2 + (m.pos.z - ISLE[3]) ^ 2)
        local airborne = (m.action & ACT_FLAG_AIR) ~= 0
        if (not airborne and timer > 5) or m.pos.y < 400 or timer > 400 then
            local hit = (not airborne) and math.abs(m.pos.y - ISLE[2]) < 50 and d < 800
            log(string.format("pitch %d: %s at %.0f %.0f %.0f (dist to isle %.0f, action %08x)",
                PITCHES[i], hit and "LANDED ON ISLE" or "missed", m.pos.x, m.pos.y, m.pos.z, d, m.action))
            state, timer = "reset", 0
        end
    elseif state == "reset" then
        if timer == 1 then tp(m, 600, 400, -900) end
        if timer > 90 then i = i + 1; state, timer = "enter", 0 end
    end
end)
