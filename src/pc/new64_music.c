#include "new64_music.h"
#include "seq_ids.h"
#include "audio/external.h"
#include "pc/configfile.h"

struct New64Song {
    u8 seqId;
    u8 bank;
    u8 volume;
    const u8 *data;
    u32 size;
};

#include "new64_music_data.h"

bool new64_music_override(u8 seqId, s32 *bankId, void **seqData) {
    for (u32 i = 0; i < sizeof(sNew64Songs) / sizeof(sNew64Songs[0]); i++) {
        if (sNew64Songs[i].seqId == seqId) {
            *bankId = sNew64Songs[i].bank;
            *seqData = (void *) sNew64Songs[i].data;
            return true;
        }
    }
    return false;
}

// Background music volume is looked up per sequence id; ids past the vanilla
// table default to 0, so set ours before anything plays.
__attribute__((constructor)) static void new64_music_init(void) {
    for (u32 i = 0; i < sizeof(sNew64Songs) / sizeof(sNew64Songs[0]); i++) {
        sound_set_background_music_default_volume(sNew64Songs[i].seqId, sNew64Songs[i].volume);
    }
}

// Vanilla songs to fall back on when custom course music is switched off.
static const u8 sNew64Fallback[][2] = {
    { SEQ_NEW64_SKY_GARDEN,   SEQ_LEVEL_GRASS },
    { SEQ_NEW64_FROSTFIRE,    SEQ_LEVEL_SNOW },
    { SEQ_NEW64_GLACIER_CAVE, SEQ_LEVEL_UNDERGROUND },
    { SEQ_NEW64_MAGMA_HALL,   SEQ_LEVEL_HOT },
};

static bool new64_music_is_ours(u8 seqId) {
    for (u32 i = 0; i < sizeof(sNew64Fallback) / sizeof(sNew64Fallback[0]); i++) {
        if (sNew64Fallback[i][0] == seqId) { return true; }
    }
    return false;
}

u8 new64_music_remap(u8 seqId) {
    if (configNew64CustomMusic) { return seqId; }
    for (u32 i = 0; i < sizeof(sNew64Fallback) / sizeof(sNew64Fallback[0]); i++) {
        if (sNew64Fallback[i][0] == seqId) { return sNew64Fallback[i][1]; }
    }
    return seqId;
}

void new64_music_refresh(void) {
    u16 current = get_current_background_music();
    if (current == 0xFFFF || !new64_music_is_ours(current & 0xFF)) { return; }
    // Re-queue the same id; the loader picks the custom or vanilla song.
    stop_background_music(current);
    play_music(SEQ_PLAYER_LEVEL, current, 0);
}
