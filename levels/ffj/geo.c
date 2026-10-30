#include <ultra64.h>
#include "sm64.h"
#include "geo_commands.h"

#include "game/level_geo.h"
#include "game/geo_misc.h"
#include "game/camera.h"
#include "game/moving_texture.h"
#include "game/screen_transition.h"
#include "game/paintings.h"
#include "game/envfx_snow.h"

#include "make_const_nonconst.h"

#include "levels/ffj/header.h"

#define FFJ_AREA_GEO(name, background, far, camMode, envfx, dlOpaque, dlTransparent) \
const GeoLayout name[] = { \
   GEO_NODE_SCREEN_AREA(10, SCREEN_WIDTH/2, SCREEN_HEIGHT/2, SCREEN_WIDTH/2, SCREEN_HEIGHT/2), \
   GEO_OPEN_NODE(), \
      GEO_ZBUFFER(0), \
      GEO_OPEN_NODE(), \
         GEO_NODE_ORTHO(100), \
         GEO_OPEN_NODE(), \
            background, \
         GEO_CLOSE_NODE(), \
      GEO_CLOSE_NODE(), \
      GEO_ZBUFFER(1), \
      GEO_OPEN_NODE(), \
         GEO_CAMERA_FRUSTUM_WITH_FUNC(45, 100, far, geo_camera_fov), \
         GEO_OPEN_NODE(), \
            GEO_CAMERA(camMode, 0, 2000, 6000, 0, 0, 0, geo_camera_main), \
            GEO_OPEN_NODE(), \
               GEO_DISPLAY_LIST(LAYER_OPAQUE, dlOpaque), \
               GEO_DISPLAY_LIST(LAYER_TRANSPARENT, dlTransparent), \
               GEO_RENDER_OBJ(), \
               GEO_ASM(envfx, geo_envfx_main), \
            GEO_CLOSE_NODE(), \
         GEO_CLOSE_NODE(), \
      GEO_CLOSE_NODE(), \
      GEO_ZBUFFER(0), \
      GEO_OPEN_NODE(), \
         GEO_ASM(0, geo_cannon_circle_base), \
      GEO_CLOSE_NODE(), \
   GEO_CLOSE_NODE(), \
   GEO_END(), \
}

// Area 1: the highlands under a snowy mountain sky, with light snowfall.
FFJ_AREA_GEO(ffj_area_1_geo, GEO_BACKGROUND(BACKGROUND_SNOW_MOUNTAINS, geo_skybox_main), 30000, CAMERA_MODE_FREE_ROAM,
             ENVFX_SNOW_NORMAL, ffj_area_1_dl_opaque, ffj_area_1_dl_transparent);
// Area 2: the glacier ice cave. Close camera like the vanilla interiors.
FFJ_AREA_GEO(ffj_area_2_geo, GEO_BACKGROUND_COLOR(0x0843), 14000, CAMERA_MODE_CLOSE,
             ENVFX_MODE_NONE, ffj_area_2_dl_opaque, ffj_area_2_dl_transparent);
// Area 3: the lava tube and magma hall, with bubbling lava.
FFJ_AREA_GEO(ffj_area_3_geo, GEO_BACKGROUND_COLOR(0x2001), 16000, CAMERA_MODE_CLOSE,
             ENVFX_LAVA_BUBBLES, ffj_area_3_dl_opaque, ffj_area_3_dl_transparent);

// Lundi, the frostfire puffin. Anim state picks the wing pose.
const GeoLayout ffj_lundi_geo[] = {
   GEO_SHADOW(SHADOW_CIRCLE_4_VERTS, 0x96, 90),
   GEO_OPEN_NODE(),
      GEO_DISPLAY_LIST(LAYER_OPAQUE, ffj_lundi_body_dl),
      GEO_SWITCH_CASE(4, geo_switch_anim_state),
      GEO_OPEN_NODE(),
         GEO_DISPLAY_LIST(LAYER_OPAQUE, ffj_lundi_wings0_dl),
         GEO_DISPLAY_LIST(LAYER_OPAQUE, ffj_lundi_wings1_dl),
         GEO_DISPLAY_LIST(LAYER_OPAQUE, ffj_lundi_wings2_dl),
         GEO_DISPLAY_LIST(LAYER_OPAQUE, ffj_lundi_wings3_dl),
      GEO_CLOSE_NODE(),
   GEO_CLOSE_NODE(),
   GEO_END(),
};

// Geyser steam column; the behavior scales it.
const GeoLayout ffj_steam_geo[] = {
   GEO_NODE_START(),
   GEO_OPEN_NODE(),
      GEO_DISPLAY_LIST(LAYER_TRANSPARENT, ffj_steam_column_dl),
   GEO_CLOSE_NODE(),
   GEO_END(),
};
