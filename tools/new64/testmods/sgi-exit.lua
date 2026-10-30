-- name: new64-test
-- description: Sky Garden Isles exit test: enters through the castle grounds
-- pipe, enters act 2, collects the tower star, and checks
-- that Mario comes back out of the pipe with the star saved. Not for play.
-- Run with coop_stay_in_level_after_star 0.

local t, phase, f = 0, "boot", 0
local press = 0

local function log(s) print("new64-exit: " .. s) end

hook_event(HOOK_UPDATE, function()
    t = t + 1
    f = f + 1
    local lvl = gNetworkPlayers[0].currLevelNum
    local m = gMarioStates[0]
    if press ~= 0 then
        gControllers[0].buttonPressed = gControllers[0].buttonPressed | press
        press = 0
    end
    if phase == "boot" and t == 30 then
        warp_to_level(LEVEL_CASTLE_GROUNDS, 1, 0)
        phase, f = "grounds", 0
    elseif phase == "grounds" and lvl == LEVEL_CASTLE_GROUNDS and f == 90 then
        m.pos.x, m.pos.y, m.pos.z = -2000, 700, 4100
        m.vel.y = 0
        set_mario_action(m, ACT_FREEFALL, 0)
        log("dropped onto pipe")
        phase, f = "actselect", 0
    elseif phase == "actselect" then
        -- Injected buttons don't reach the act select menu, so once the pipe
        -- has taken us there, enter act 2 directly.
        if lvl == LEVEL_SGI and f == 200 then warp_to_level(LEVEL_SGI, 1, 2) end
        if lvl == LEVEL_SGI and f > 320 then
            log(string.format("in course, act %d", gNetworkPlayers[0].currActNum))
            phase, f = "star", 0
        end
    elseif phase == "star" and f == 60 then
        m.pos.x, m.pos.y, m.pos.z = 0, 3260, 0
        m.vel.y = 0
        set_mario_action(m, ACT_FREEFALL, 0)
        phase, f = "dance", 0
    elseif phase == "dance" then
        if f % 60 == 0 then press = A_BUTTON end -- close the post-star dialog
        if lvl == LEVEL_CASTLE_GROUNDS and f > 30 then phase, f = "back", 0 end
    elseif phase == "back" and f == 150 then
        local file = get_current_save_file_num() - 1
        log(string.format("back on grounds at %.0f %.0f %.0f action %08x; course flags 0x%02X total %d",
            m.pos.x, m.pos.y, m.pos.z, m.action, save_file_get_star_flags(file, COURSE_SGI - 1),
            save_file_get_total_star_count(file, COURSE_MIN - 1, COURSE_MAX - 1)))
        press = START_BUTTON
        phase, f = "pause", 0
    end
end)
