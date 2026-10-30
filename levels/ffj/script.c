#include <ultra64.h>
#include "sm64.h"
#include "behavior_data.h"
#include "model_ids.h"
#include "seq_ids.h"
#include "dialog_ids.h"
#include "segment_symbols.h"
#include "level_commands.h"

#include "game/level_update.h"

#include "levels/scripts.h"

#include "actors/common1.h"
#include "actors/group7.h"
#include "actors/group16.h"

#include "make_const_nonconst.h"
#include "levels/ffj/header.h"
#include "levels/ffj/layout.h"
#include "levels/lll/header.h"

#include "levels/ffj/areas/1/objects.inc.c"
#include "levels/ffj/areas/2/objects.inc.c"
#include "levels/ffj/areas/3/objects.inc.c"

// Collecting a star, dying or leaving the course return Mario to the second
// warp pipe on the castle grounds.
#define FFJ_EXIT_WARPS() \
    WARP_NODE(/*id*/ 0xF0, /*destLevel*/ LEVEL_CASTLE_GROUNDS, /*destArea*/ 0x01, /*destNode*/ 0x21, /*flags*/ WARP_NO_CHECKPOINT), \
    WARP_NODE(/*id*/ 0xF1, /*destLevel*/ LEVEL_CASTLE_GROUNDS, /*destArea*/ 0x01, /*destNode*/ 0x21, /*flags*/ WARP_NO_CHECKPOINT)

const LevelScript level_ffj_entry[] = {
    INIT_LEVEL(),
    LOAD_MIO0(        /*seg*/ 0x07, _ffj_segment_7SegmentRomStart, _ffj_segment_7SegmentRomEnd),
    LOAD_MIO0_TEXTURE(/*seg*/ 0x09, _generic_mio0SegmentRomStart, _generic_mio0SegmentRomEnd),
    LOAD_MIO0(        /*seg*/ 0x0A, _ccm_skybox_mio0SegmentRomStart, _ccm_skybox_mio0SegmentRomEnd),
    LOAD_MIO0(        /*seg*/ 0x05, _group7_mio0SegmentRomStart, _group7_mio0SegmentRomEnd),
    LOAD_RAW(         /*seg*/ 0x0C, _group7_geoSegmentRomStart,  _group7_geoSegmentRomEnd),
    LOAD_MIO0(        /*seg*/ 0x06, _group16_mio0SegmentRomStart, _group16_mio0SegmentRomEnd),
    LOAD_RAW(         /*seg*/ 0x0D, _group16_geoSegmentRomStart,  _group16_geoSegmentRomEnd),
    LOAD_MIO0(        /*seg*/ 0x08, _common0_mio0SegmentRomStart, _common0_mio0SegmentRomEnd),
    LOAD_RAW(         /*seg*/ 0x0F, _common0_geoSegmentRomStart,  _common0_geoSegmentRomEnd),
    ALLOC_LEVEL_POOL(),
    MARIO(/*model*/ MODEL_MARIO, /*behParam*/ 0x00000001, /*beh*/ bhvMario),
    JUMP_LINK(script_func_global_1),
    JUMP_LINK(script_func_global_8),
    JUMP_LINK(script_func_global_17),
    LOAD_MODEL_FROM_GEO(MODEL_LLL_ROTATING_BLOCK_FIRE_BARS, lll_geo_000B38),
    LOAD_MODEL_FROM_GEO(MODEL_LLL_SINKING_SQUARE_PLATFORMS, lll_geo_000BE0),
    LOAD_MODEL_FROM_GEO(MODEL_FFJ_LUNDI,                    ffj_lundi_geo),
    LOAD_MODEL_FROM_GEO(MODEL_FFJ_GEYSER_STEAM,             ffj_steam_geo),

    // The highlands: beach, sea stacks, geysers, glacier and volcano.
    AREA(/*index*/ 1, ffj_area_1_geo),
        JUMP_LINK(ffj_area_1_objects),
        WARP_NODE(/*id*/ 0x0A, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x01, /*destNode*/ 0x0A, /*flags*/ WARP_NO_CHECKPOINT),
        WARP_NODE(/*id*/ 0x0B, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x02, /*destNode*/ 0x0B, /*flags*/ WARP_NO_CHECKPOINT),
        WARP_NODE(/*id*/ 0x0C, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x01, /*destNode*/ 0x0C, /*flags*/ WARP_NO_CHECKPOINT),
        WARP_NODE(/*id*/ 0x0D, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x03, /*destNode*/ 0x0D, /*flags*/ WARP_NO_CHECKPOINT),
        WARP_NODE(/*id*/ 0x0E, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x01, /*destNode*/ 0x0E, /*flags*/ WARP_NO_CHECKPOINT),
        FFJ_EXIT_WARPS(),
        TERRAIN(/*terrainData*/ ffj_area_1_collision),
        MACRO_OBJECTS(/*objList*/ ffj_area_1_macro_objs),
        SET_BACKGROUND_MUSIC(/*settingsPreset*/ 0x0000, /*seq*/ SEQ_LEVEL_SNOW),
        TERRAIN_TYPE(/*terrainType*/ TERRAIN_SNOW),
    END_AREA(),

    // The glacier ice cave, entered through the mouth in the ice cliff.
    AREA(/*index*/ 2, ffj_area_2_geo),
        JUMP_LINK(ffj_area_2_objects),
        WARP_NODE(/*id*/ 0x0B, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x02, /*destNode*/ 0x0B, /*flags*/ WARP_NO_CHECKPOINT),
        WARP_NODE(/*id*/ 0x0C, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x01, /*destNode*/ 0x0C, /*flags*/ WARP_NO_CHECKPOINT),
        FFJ_EXIT_WARPS(),
        TERRAIN(/*terrainData*/ ffj_area_2_collision),
        MACRO_OBJECTS(/*objList*/ ffj_area_2_macro_objs),
        SET_BACKGROUND_MUSIC(/*settingsPreset*/ 0x0001, /*seq*/ SEQ_LEVEL_UNDERGROUND),
        TERRAIN_TYPE(/*terrainType*/ TERRAIN_SNOW),
    END_AREA(),

    // The lava tube and magma hall, entered through the skylight on the volcano.
    AREA(/*index*/ 3, ffj_area_3_geo),
        JUMP_LINK(ffj_area_3_objects),
        WARP_NODE(/*id*/ 0x0D, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x03, /*destNode*/ 0x0D, /*flags*/ WARP_NO_CHECKPOINT),
        WARP_NODE(/*id*/ 0x0E, /*destLevel*/ LEVEL_FFJ, /*destArea*/ 0x01, /*destNode*/ 0x0E, /*flags*/ WARP_NO_CHECKPOINT),
        FFJ_EXIT_WARPS(),
        TERRAIN(/*terrainData*/ ffj_area_3_collision),
        MACRO_OBJECTS(/*objList*/ ffj_area_3_macro_objs),
        SET_BACKGROUND_MUSIC(/*settingsPreset*/ 0x0001, /*seq*/ SEQ_LEVEL_HOT),
        TERRAIN_TYPE(/*terrainType*/ TERRAIN_STONE),
    END_AREA(),

    FREE_LEVEL_POOL(),
    MARIO_POS(/*area*/ 1, /*yaw*/ 180, /*pos*/ 0, FFJ_SPAWN_Y, 5350),
    CALL(/*arg*/ 0, /*func*/ lvl_init_or_update),
    CALL_LOOP(/*arg*/ 1, /*func*/ lvl_init_or_update),
    CLEAR_LEVEL(),
    SLEEP_BEFORE_EXIT(/*frames*/ 1),
    EXIT(),
};
