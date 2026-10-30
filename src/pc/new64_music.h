#ifndef NEW64_MUSIC_H
#define NEW64_MUSIC_H

// new64: built-in music for the new courses. The songs are composed in
// tools/new64/gen_music.py and compiled in as SM64 sequences (bank 0x30).
// The ids sit above the vanilla range and below what mods usually allocate.

#define SEQ_NEW64_SKY_GARDEN    0x70
#define SEQ_NEW64_FROSTFIRE     0x71
#define SEQ_NEW64_GLACIER_CAVE  0x72
#define SEQ_NEW64_MAGMA_HALL    0x73

#ifndef __ASSEMBLER__
#include <stdbool.h>
#include "types.h"

// Called by the sequence loader before mod overrides; returns the song's
// data and bank if seqId is one of ours.
bool new64_music_override(u8 seqId, s32 *bankId, void **seqData);

// With the "custom course music" setting off, our ids play vanilla songs.
u8 new64_music_remap(u8 seqId);

// Restart the level music after the setting changes.
void new64_music_refresh(void);
#endif

#endif
