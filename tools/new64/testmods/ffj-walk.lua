-- name: new64-test
-- description: Frostfire route checks with real stick input: walks Mario up
-- the volcano from several sides and into the crater by the entry column,
-- logging whether each route works. Not for play.

local VOLC_X, VOLC_Z, RIM_R = 5200, -5600, 1350

-- name, start x, z, target x, z, frames, done(m) -> true when the route worked
local function rim_reached(m)
    return math.sqrt((m.pos.x - VOLC_X) ^ 2 + (m.pos.z - VOLC_Z) ^ 2) < RIM_R + 30
end
local RUNS = {}
for _, deg in ipairs({ 0, 45, 90, 135, 180, 225, 270, 300, 345 }) do
    local a = math.rad(deg)
    RUNS[#RUNS + 1] = { string.format("climb %d", deg), VOLC_X + math.sin(a) * 3800, VOLC_Z + math.cos(a) * 3800,
                        VOLC_X, VOLC_Z, 1500, rim_reached }
end
-- From the rim at the way in, walk carefully across the stones and hop onto
-- the spire: done when Mario stands on the spire top.
local ex, ez = -0.82, 0.57
local n = math.sqrt(ex * ex + ez * ez)
ex, ez = ex / n, ez / n
local function on_spire(m)
    local rr = math.sqrt((m.pos.x - VOLC_X) ^ 2 + (m.pos.z - VOLC_Z) ^ 2)
    return rr < 230 and m.pos.y == m.floorHeight and m.floorHeight > 3600
end
RUNS[#RUNS + 1] = { "crater route", VOLC_X + ex * 1400, VOLC_Z + ez * 1400, VOLC_X, VOLC_Z, 400, on_spire, 45, 470 }

local t, i, f = 0, 1, 0
local stick = nil
local jumped = false
local maxY, lastY, still = -1e9, 0, 0

local function log(s) print("new64-walk: " .. s) end

hook_event(HOOK_ON_DIALOG, function() return false end)
hook_event(HOOK_UPDATE, function()
    t = t + 1
    if t == 30 then warp_to_level(LEVEL_FFJ, 1, 1) end
end)

hook_event(HOOK_BEFORE_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or stick == nil then return end
    local c = m.controller
    c.stickX, c.stickY, c.stickMag = stick[1], stick[2], stick[3] or 64
end)

hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or gNetworkPlayers[0].currLevelNum ~= LEVEL_FFJ then return end
    m.health = 0x880
    if t < 150 then return end
    local r = RUNS[i]
    if r == nil then
        if stick ~= nil then log("done") end
        stick = nil
        return
    end
    f = f + 1
    if f == 1 then
        local y = find_floor_height(r[2], 20000, r[3])
        m.pos.x, m.pos.y, m.pos.z = r[2], y + 30, r[3]
        m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
        m.forwardVel = 0
        set_mario_action(m, ACT_FREEFALL, 0)
        stick = nil
        jumped = false
        maxY, still = -1e9, 0
        return
    end
    if f < 25 then return end
    -- Steer at the target relative to the camera
    local yaw = atan2s(r[5] - m.pos.z, r[4] - m.pos.x)
    local d = yaw - m.area.camera.yaw
    local mag = r[8] or 64
    stick = { math.floor(mag * sins(d)), math.floor(-mag * coss(d)), mag }
    -- One jump when within r[9] of the target (the hop onto the spire)
    local tr = math.sqrt((m.pos.x - r[4]) ^ 2 + (m.pos.z - r[5]) ^ 2)
    if r[9] ~= nil and tr < r[9] and not jumped and m.pos.y == m.floorHeight then
        jumped = true
        m.controller.buttonPressed = m.controller.buttonPressed | A_BUTTON
        m.input = m.input | INPUT_A_PRESSED
        set_mario_action(m, ACT_JUMP, 0)
    end
    if m.pos.y > maxY + 2 then maxY, still = m.pos.y, 0 else still = still + 1 end
    local ok = r[7] ~= nil and r[7](m)
    if ok or f >= r[6] or still > 240 then
        local rr = math.sqrt((m.pos.x - VOLC_X) ^ 2 + (m.pos.z - VOLC_Z) ^ 2)
        log(string.format("%s: %s after %d frames, at r %.0f y %.0f (max y %.0f) floor %.0f action %08x",
            r[1], ok and "REACHED" or (still > 240 and "STUCK" or "ended"), f, rr, m.pos.y, maxY, m.floorHeight, m.action))
        f = 0
        i = i + 1
    end
end)
