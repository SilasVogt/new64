-- name: new64-test
-- description: Frostfire Fjord camera tour: visits viewpoints in all three
-- areas for screenshots (pair with tools/new64/pick_shots.py). Not for play.

-- area, x, y, z, yaw (Mario drops from y and faces yaw; the camera follows)
local TOUR = {
    { 1, -200, 900, 5000, 160 },     -- spawn: beach looking at volcano and glacier
    { 1, 700, 900, 5900, 20 },       -- basalt columns and sea stacks
    { 1, 3500, 1200, 1500, 55 },     -- geyser field and spire
    { 1, -3200, 1200, 2600, 270 },   -- hot spring
    { 1, -3700, 1500, -3520, 270 },  -- ice cave mouth
    { 1, -7800, 1000, -400, 180 },   -- waterfall
    { 1, 2900, 1700, -1500, 270 },   -- lava river (from its east bank)
    { 1, 3760, 4300, -5600, 90 },    -- crater (from the west rim)
    { 2, 0, 300, 2600, 180 },        -- ice cave: entry to crystal hall
    { 2, 0, 300, 900, 180 },         -- crystal hall and frozen lake
    { 2, 3300, 1000, -1400, 200 },   -- gallery
    { 3, 0, 300, 3900, 180 },        -- lava tube
    { 3, 0, 300, 2300, 180 },        -- magma hall from the tube mouth
    { 3, 0, 500, -500, 180 },        -- ice floe and the Big Chill Bully
}
local NODES = { [1] = 0x0A, [2] = 0x0B, [3] = 0x0D }
local HOLD = 160

local t, f, i = 0, 0, 1
local warping = false

hook_event(HOOK_ON_DIALOG, function() return false end)

hook_event(HOOK_UPDATE, function()
    t = t + 1
    if t == 30 then warp_to_level(LEVEL_FFJ, 1, 1) end
end)

hook_event(HOOK_MARIO_UPDATE, function(m)
    if m.playerIndex ~= 0 or gNetworkPlayers[0].currLevelNum ~= LEVEL_FFJ then return end
    m.health = 0x880
    local p = TOUR[i]
    if p == nil then return end
    if gNetworkPlayers[0].currAreaIndex ~= p[1] then
        if not warping then
            warping = true
            warp_to_warpnode(LEVEL_FFJ, p[1], 1, NODES[p[1]])
        end
        return
    end
    warping = false
    f = f + 1
    if f == 20 then
        m.pos.x, m.pos.y, m.pos.z = p[2], p[3], p[4]
        m.vel.x, m.vel.y, m.vel.z = 0, 0, 0
        m.forwardVel = 0
        m.faceAngle.y = degrees_to_sm64(p[5])
        set_mario_action(m, ACT_FREEFALL, 0)
        print(string.format("new64-tour: %d", i))
    end
    if f >= HOLD then
        f = 0
        i = i + 1
    end
end)
