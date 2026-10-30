// new64: custom objects for Frostfire Fjord (course 17).
//
// Lundi: the frostfire puffins of the sea stacks. They perch, circle over
// their nest and dive-bomb Mario. Stomp or punch them. When the last one in
// the area falls, the star in its first behParam byte appears above the
// tallest sea stack.
//
// Geyser: erupts on a cycle and throws Mario into a slow, steerable twirl.
// behParams: byte 1 = phase offset in frames, byte 2 = launch speed.

#include "levels/ffj/layout.h"
#include "pc/lua/utils/smlua_obj_utils.h"

// Defined in obj_behaviors_2.c without a header declaration.
void obj_die_if_health_non_positive(void);

#define NEW64_CLAMP(x, lo, hi) ((x) < (lo) ? (lo) : ((x) > (hi) ? (hi) : (x)))

#define LUNDI_ACT_PERCH  0
#define LUNDI_ACT_CIRCLE 1
#define LUNDI_ACT_DIVE   2
#define LUNDI_ACT_CLIMB  3

#define LUNDI_ORBIT_RADIUS 520.0f
#define LUNDI_WAKE_DIST    2600.0f
#define LUNDI_GIVE_UP_DIST 5000.0f

static struct ObjectHitbox sLundiHitbox = {
    .interactType = INTERACT_BOUNCE_TOP,
    .downOffset = 0,
    .damageOrCoinValue = 1,
    .health = 0,
    .numLootCoins = 2,
    .radius = 90,
    .height = 80,
    .hurtboxRadius = 60,
    .hurtboxHeight = 60,
};

static Vec3f sLundiStarPos = FFJ_LUNDI_STAR_POS;

static void lundi_flap(s32 speed) {
    static const s8 sFrames[] = { 1, 2, 3, 2 };
    s32 before = (o->oLundiFlapTimer / 8) & 3;
    o->oLundiFlapTimer += speed;
    s32 after = (o->oLundiFlapTimer / 8) & 3;
    o->oAnimState = sFrames[after];
    if (before != after && after == 0) {
        cur_obj_play_sound_2(SOUND_OBJ_UNKNOWN6);
    }
}

// Keep clear of the ground while flying.
static void lundi_keep_above_floor(void) {
    f32 floorY = find_floor_height(o->oPosX, o->oPosY + 300.0f, o->oPosZ);
    if (floorY > -10000.0f && o->oPosY < floorY + 70.0f) {
        o->oPosY = floorY + 70.0f;
        if (o->oVelY < 0.0f) { o->oVelY = 0.0f; }
    }
}

// Fly toward a point, turning smoothly; returns the remaining distance.
static f32 lundi_fly_toward(f32 x, f32 y, f32 z, f32 speed, s16 turn) {
    f32 dx = x - o->oPosX, dy = y - o->oPosY, dz = z - o->oPosZ;
    f32 dist = sqrtf(dx * dx + dy * dy + dz * dz);
    s16 yaw = atan2s(dz, dx);
    o->oMoveAngleYaw = approach_s16_symmetric(o->oMoveAngleYaw, yaw, turn);
    o->oForwardVel = approach_f32(o->oForwardVel, speed, 2.0f, 2.0f);
    o->oVelY = approach_f32(o->oVelY, NEW64_CLAMP(dy * 0.08f, -speed, speed), 2.0f, 2.0f);
    return dist;
}

static void lundi_apply_motion(void) {
    o->oPosX += sins(o->oMoveAngleYaw) * o->oForwardVel;
    o->oPosZ += coss(o->oMoveAngleYaw) * o->oForwardVel;
    o->oPosY += o->oVelY;
    lundi_keep_above_floor();

    // Face the way we move: nose down when diving, bank into turns.
    s16 targetPitch = -atan2s(o->oForwardVel + 1.0f, o->oVelY);
    o->oFaceAnglePitch = approach_s16_symmetric(o->oFaceAnglePitch, targetPitch, 0x300);
    s16 turn = (s16)(o->oMoveAngleYaw - o->oFaceAngleYaw);
    o->oFaceAngleRoll = approach_s16_symmetric(o->oFaceAngleRoll, NEW64_CLAMP(turn * 6, -0x2800, 0x2800), 0x200);
    o->oFaceAngleYaw = o->oMoveAngleYaw;
}

static struct MarioState *lundi_target(f32 *distOut) {
    struct MarioState *m = nearest_mario_state_to_object(o);
    if (m == NULL || m->marioObj == NULL) { *distOut = 100000.0f; return NULL; }
    *distOut = dist_between_objects(o, m->marioObj);
    return m;
}

static void lundi_act_perch(void) {
    f32 dist;
    lundi_target(&dist);
    o->oPosX = o->oHomeX;
    o->oPosY = o->oHomeY + 4.0f * sins(o->oTimer * 0x400);
    o->oPosZ = o->oHomeZ;
    o->oFaceAnglePitch = 0;
    o->oFaceAngleRoll = 0;
    o->oForwardVel = 0.0f;
    o->oVelY = 0.0f;
    // Look around now and then, flap once in a while.
    if ((o->oTimer % 90) == 0) {
        o->oMoveAngleYaw += (s16)(random_sign() * 0x2000);
    }
    o->oFaceAngleYaw = approach_s16_symmetric(o->oFaceAngleYaw, o->oMoveAngleYaw, 0x400);
    o->oAnimState = ((o->oTimer % 120) < 16) ? 1 + ((o->oTimer / 4) & 1) : 0;

    if (dist < LUNDI_WAKE_DIST) {
        o->oAction = LUNDI_ACT_CIRCLE;
        o->oLundiOrbitAngle = o->oMoveAngleYaw;
        o->oVelY = 18.0f;
        cur_obj_play_sound_2(SOUND_OBJ2_SWOOP);
    }
}

static void lundi_act_circle(void) {
    f32 dist;
    struct MarioState *m = lundi_target(&dist);

    o->oLundiOrbitAngle += 0x120;
    f32 tx = o->oHomeX + sins(o->oLundiOrbitAngle) * LUNDI_ORBIT_RADIUS;
    f32 tz = o->oHomeZ + coss(o->oLundiOrbitAngle) * LUNDI_ORBIT_RADIUS;
    f32 ty = o->oLundiCruiseY + 80.0f * sins(o->oTimer * 0x300);
    lundi_fly_toward(tx, ty, tz, 22.0f, 0x500);
    lundi_flap(2);

    if (dist > LUNDI_GIVE_UP_DIST) {
        o->oAction = LUNDI_ACT_CLIMB;
        o->oLundiDiveTimer = -1; // -1: head home and perch
        return;
    }
    // Dive at Mario when he is below us and close enough.
    if (m != NULL && o->oTimer > o->oLundiDiveTimer && dist < 2200.0f && m->pos[1] < o->oPosY - 150.0f) {
        o->oAction = LUNDI_ACT_DIVE;
        o->oMoveAngleYaw = atan2s(m->pos[2] - o->oPosZ, m->pos[0] - o->oPosX);
        o->oForwardVel = 30.0f;
        cur_obj_play_sound_2(SOUND_OBJ2_SWOOP);
    }
}

static void lundi_act_dive(void) {
    f32 dist;
    struct MarioState *m = lundi_target(&dist);
    o->oAnimState = 0; // wings tucked

    if (m != NULL && o->oTimer < 40) {
        // Home in on Mario's chest for the first part of the dive.
        lundi_fly_toward(m->pos[0], m->pos[1] + 80.0f, m->pos[2], 46.0f, 0x280);
        o->oVelY = approach_f32(o->oVelY, NEW64_CLAMP((m->pos[1] + 80.0f - o->oPosY) * 0.15f, -40.0f, 10.0f), 4.0f, 4.0f);
    }
    if (o->oTimer > 70 || (m != NULL && o->oTimer > 40 && dist > 900.0f)) {
        o->oAction = LUNDI_ACT_CLIMB;
    }
}

static void lundi_act_climb(void) {
    f32 dist;
    lundi_target(&dist);
    lundi_flap(3);
    if (o->oLundiDiveTimer == -1) {
        // Going home to perch
        if (lundi_fly_toward(o->oHomeX, o->oHomeY + 40.0f, o->oHomeZ, 26.0f, 0x600) < 60.0f) {
            o->oAction = LUNDI_ACT_PERCH;
            o->oLundiDiveTimer = 0;
        }
        return;
    }
    f32 tx = o->oHomeX + sins(o->oLundiOrbitAngle) * LUNDI_ORBIT_RADIUS;
    f32 tz = o->oHomeZ + coss(o->oLundiOrbitAngle) * LUNDI_ORBIT_RADIUS;
    if (lundi_fly_toward(tx, o->oLundiCruiseY, tz, 28.0f, 0x500) < 200.0f || o->oTimer > 150) {
        o->oAction = LUNDI_ACT_CIRCLE;
        o->oLundiDiveTimer = 50 + (s32)(random_float() * 70.0f);
    }
}

// Other puffins still flying. Objects marked for deletion this frame are
// skipped, so two puffins defeated on the same frame still reveal the star.
static s32 lundi_count_others_alive(void) {
    s32 count = 0;
    struct Object *obj = obj_get_first_with_behavior_id(id_bhvNew64Lundi);
    while (obj != NULL) {
        if (obj != o && obj->activeFlags != ACTIVE_FLAG_DEACTIVATED) { count++; }
        obj = obj_get_next_with_same_behavior_id(obj);
    }
    return count;
}

static void lundi_defeated(void) {
    // The last puffin standing reveals the star.
    if (lundi_count_others_alive() == 0) {
        spawn_default_star(sLundiStarPos[0], sLundiStarPos[1], sLundiStarPos[2]);
    }
    spawn_mist_particles_variable(0, 0, 46.0f);
    spawn_triangle_break_particles(12, MODEL_DIRT_ANIMATION, 0.6f, 4);
    o->oDeathSound = SOUND_OBJ_KOOPA_FLYGUY_DEATH;
    obj_die_if_health_non_positive();
}

void bhv_new64_lundi_init(void) {
    o->oLundiCruiseY = o->oHomeY + 450.0f + 60.0f * (o->oBehParams2ndByte & 3);
    o->oLundiDiveTimer = 40;
    o->oDrawingDistance = 9000.0f;
    o->oMoveAngleYaw = o->oFaceAngleYaw;
}

void bhv_new64_lundi_loop(void) {
    // Share flight and defeats with other players, like the vanilla flyers.
    if (!sync_object_is_initialized(o->oSyncID)) {
        sync_object_init(o, 6000.0f);
        sync_object_init_field(o, o->oLundiOrbitAngle);
        sync_object_init_field(o, o->oLundiCruiseY);
        sync_object_init_field(o, o->oLundiDiveTimer);
        sync_object_init_field(o, o->oFaceAnglePitch);
        sync_object_init_field(o, o->oFaceAngleRoll);
    }

    switch (o->oAction) {
        case LUNDI_ACT_PERCH:  lundi_act_perch();  break;
        case LUNDI_ACT_CIRCLE: lundi_act_circle(); break;
        case LUNDI_ACT_DIVE:   lundi_act_dive();   break;
        case LUNDI_ACT_CLIMB:  lundi_act_climb();  break;
    }
    if (o->oAction != LUNDI_ACT_PERCH) {
        lundi_apply_motion();
    }

    obj_set_hitbox(o, &sLundiHitbox);
    if (o->oInteractStatus & INT_STATUS_INTERACTED) {
        if (o->oInteractStatus & INT_STATUS_ATTACKED_MARIO) {
            // Hit Mario: peel away and circle again.
            o->oAction = LUNDI_ACT_CLIMB;
            o->oLundiDiveTimer = 60;
        } else {
            lundi_defeated();
        }
        o->oInteractStatus = 0;
    }
}

// ---------------------------------------------------------------------------

#define GEYSER_PERIOD      210
#define GEYSER_RUMBLE_AT   120
#define GEYSER_ERUPT_AT    150
#define GEYSER_ERUPT_END   200
#define GEYSER_RADIUS      210.0f
#define GEYSER_COLUMN      1600.0f // model height at scale 1

void bhv_new64_geyser_init(void) {
    o->oDrawingDistance = 20000.0f;
    o->oGeyserHeight = 0.1f;
}

void bhv_new64_geyser_loop(void) {
    s32 t = (gGlobalTimer + ((o->oBehParams >> 24) & 0xFF)) % GEYSER_PERIOD;
    f32 launch = (f32)((o->oBehParams >> 16) & 0xFF);
    f32 target;

    if (t < GEYSER_RUMBLE_AT) {
        target = 0.10f + 0.025f * sins(t * 0x900);
    } else if (t < GEYSER_ERUPT_AT) {
        target = 0.22f + 0.08f * sins(t * 0x2400);
        if (t == GEYSER_RUMBLE_AT) { cur_obj_play_sound_2(SOUND_GENERAL_QUIET_BUBBLE); }
        if ((t & 7) == 0) { spawn_mist_particles_variable(2, 40, 30.0f); }
    } else if (t < GEYSER_ERUPT_END) {
        target = 1.0f + 0.07f * sins(t * 0x1C00);
        if (t == GEYSER_ERUPT_AT) {
            cur_obj_play_sound_2(SOUND_OBJ_FLAME_BLOWN);
            cur_obj_shake_screen(SHAKE_POS_SMALL);
        }
        if ((t & 3) == 0) {
            spawn_mist_particles_variable(3, (s32)(o->oGeyserHeight * GEYSER_COLUMN * 0.8f), 70.0f);
        }
    } else {
        target = 0.10f;
    }

    f32 rate = (target > o->oGeyserHeight) ? 0.18f : 0.05f;
    o->oGeyserHeight = approach_f32(o->oGeyserHeight, target, rate, rate);
    f32 width = 0.55f + 0.45f * fminf(o->oGeyserHeight, 1.0f);
    obj_scale_xyz(o, width, o->oGeyserHeight, width);

    // Launch Mario while the column is up.
    if (launch > 0.0f && t >= GEYSER_ERUPT_AT && t < GEYSER_ERUPT_END && o->oGeyserHeight > 0.6f) {
        struct MarioState *m = &gMarioStates[0];
        f32 dx = m->pos[0] - o->oPosX, dz = m->pos[2] - o->oPosZ;
        // Only from the vent itself, so one eruption is one launch.
        if (dx * dx + dz * dz < GEYSER_RADIUS * GEYSER_RADIUS
            && m->pos[1] > o->oPosY - 120.0f && m->pos[1] < o->oPosY + 250.0f
            && !(m->action == ACT_TWIRLING && m->vel[1] > 10.0f)
            && !(m->action & (ACT_FLAG_SWIMMING | ACT_FLAG_INTANGIBLE))) {
            mario_stop_riding_and_holding(m);
            set_mario_action(m, ACT_TWIRLING, 0);
            m->vel[1] = launch;
            m->forwardVel *= 0.3f;
            play_sound(SOUND_GENERAL_SWISH_WATER, m->marioObj->header.gfx.cameraToObject);
        }
    }
}
