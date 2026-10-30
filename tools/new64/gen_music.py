#!/usr/bin/env python3
"""Compose new64's course music and encode it as SM64 sequences (.m64).

The songs are written below in a small note language and assembled straight
into the N64 sequence format, played through the game's own instruments. Each
song uses one vanilla sound bank (the same banks the original music uses). Output: src/pc/new64_music_data.h
(byte arrays the game compiles in) and, with --m64 DIR, the raw .m64 files.

Notes: "A4q" = A4 quarter, "C#5e." = dotted eighth, "r h" = half rest.
Durations: w h q e s, t = eighth triplet; "." dots; "!" accents.

Usage: gen_music.py <repo root> [--m64 DIR]
"""
import math
import re
import sys
from pathlib import Path

TPB = 48                     # ticks per quarter note (TATUMS_PER_BEAT)
DUR = {"w": 192, "h": 96, "q": 48, "e": 24, "s": 12, "t": 16}
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Instrument slots per vanilla bank (sound/sound_banks/*.json, instrument_list)
DRUMS = 0x7F                 # chan_setinstr 0x7f: the bank's drum kit
# The shared drum kit, by key (note value, not pitch): kick 0-15, rimshot 16,
# tambourine 33-40, conga 51-62, clave 63. drumkey() turns a key into a note.
KIT_KICK, KIT_RIM, KIT_TAMB, KIT_CONGA, KIT_CLAVE = 15, 16, 36, 55, 63


def drumkey(k):
    return k + 21


# bank 0x22 (Bob-omb Battlefield's bank)
B22_BRASS, B22_SLAP_BASS, B22_ORGAN, B22_HIHAT, B22_SPLASH = 0, 6, 7, 10, 11
# bank 0x25
B25_HARMONICA, B25_RHODES, B25_PIANO, B25_HORNS, B25_PANFLUTE, B25_STRINGS = 0, 3, 4, 5, 6, 7
B25_HIHAT, B25_SPLASH, B25_TRIANGLE, B25_PIANO2 = 10, 11, 12, 15
# bank 0x1C
B1C_MUSICBOX, B1C_MUSICBOX2, B1C_STRINGS, B1C_STRINGS2, B1C_STRINGS3 = 0, 1, 4, 5, 6
# bank 0x1A
B1A_TRUMPET, B1A_TROMBONE, B1A_HORNS, B1A_STRINGS, B1A_BRASS = 0, 1, 2, 3, 4
B1A_TIMPANI, B1A_SPLASH, B1A_SNARE = 10, 11, 12

# Octave corrections, measured by recording every instrument playing C4 and G4
# (tools/new64/gen_music.py --calibrate): some samples sound an octave off.
TUNE = {
    (0x25, B25_PANFLUTE): -12,
    (0x1C, B1C_MUSICBOX): -12, (0x1C, B1C_MUSICBOX2): -12,
    (0x1A, B1A_TROMBONE): -12, (0x1A, B1A_BRASS): +12, (0x1A, B1A_STRINGS): -12,
}

# Vanilla writes the named percussion instruments at General MIDI keys
SNARE_NOTE, SPLASH_NOTE, HAT_NOTE, OPEN_HAT_NOTE, TRI_NOTE = 38, 49, 42, 46, 94


# --------------------------------------------------------------------------
# Note language
# --------------------------------------------------------------------------
TOKEN = re.compile(r"^(r|[A-G][#b]?\d)([whqest])(\.?)(!?)$")


def midi(name):
    acc = 1 if "#" in name else (-1 if "b" in name[1:] else 0)
    return 12 * (int(name[-1]) + 1) + NOTE[name[0]] + acc


def line(text, start=0, vel=92, gate=0xD8):
    """Parse a melody string into events [(tick, midi, len, vel, gate)]."""
    t, out = start, []
    for tok in text.split():
        m = TOKEN.match(tok)
        if not m:
            raise ValueError(f"bad token {tok!r}")
        name, d, dot, acc = m.groups()
        length = int(DUR[d] * (1.5 if dot else 1))
        if name != "r":
            out.append((t, midi(name), length, min(127, vel + (22 if acc else 0)), gate))
        t += length
    return out, t


def phrase(text, bar_len, start_bar, vel=92, gate=0xD8):
    """A melody written bar by bar ("|" between bars); every bar must be full."""
    out = []
    for i, bar in enumerate(text.split("|")):
        ev, end = line(bar, (start_bar + i) * bar_len, vel, gate)
        got = end - (start_bar + i) * bar_len
        assert got == bar_len, f"bar {start_bar + i} ({bar.strip()!r}) is {got} ticks, expected {bar_len}"
        out += ev
    return out


CHORD = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
         "sus2": (0, 2, 7), "sus4": (0, 5, 7), "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14), "5": (0, 7, 12),
         "dim": (0, 3, 6)}
CHORD_RE = re.compile(r"^([A-G][#b]?)(maj7|madd9|add9|sus2|sus4|dim|m7|m|7|5)?$")


def chord(sym, octave=3):
    m = CHORD_RE.match(sym)
    root = midi(m.group(1) + str(octave))
    return [root + i for i in CHORD[m.group(2) or ""]]


def tones(sym, octave, count):
    """Chord tones climbing through octaves: root, 3rd, 5th, root+12, ..."""
    base = chord(sym, octave)[:3]
    out = []
    k = 0
    while len(out) < count:
        out.append(base[k % 3] + 12 * (k // 3))
        k += 1
    return out


def per_bar(progression, bar_len, fn, start=0):
    out = []
    for i, sym in enumerate(progression):
        out += fn(sym, start + i * bar_len)
    return out


def arpeggio(progression, bar_len, octave, pattern, step, vel=70, gate=0xA0, start=0):
    def bar(sym, t0):
        ts = tones(sym, octave, max(pattern) + 1)
        return [(t0 + j * step, ts[p], step, vel - (0 if j == 0 else 8), gate)
                for j, p in enumerate(pattern) if j * step < bar_len]
    return per_bar(progression, bar_len, bar, start)


def pad(progression, bar_len, octave, voice, vel=58, gate=0xFF, start=0):
    """One voice (0 = root, 1 = third, 2 = fifth) of sustained chords."""
    def bar(sym, t0):
        return [(t0, tones(sym, octave, 3)[voice], bar_len, vel, gate)]
    return per_bar(progression, bar_len, bar, start)


def bass(progression, bar_len, octave, rhythm, vel=88, gate=0xC0, start=0):
    """rhythm: [(offset, length, degree)] with degree 0 root, 1 fifth, 2 octave."""
    def bar(sym, t0):
        r = chord(sym, octave)[0]
        pick = {0: r, 1: r + 7, 2: r + 12, 3: r - 5}
        return [(t0 + o, pick[d], ln, vel, gate) for o, ln, d in rhythm]
    return per_bar(progression, bar_len, bar, start)


def drum(bars, bar_len, hits, key, vel=80, gate=0x80, start=0, length=12):
    """hits: offsets within a bar (ticks)."""
    return [(start + b * bar_len + o, key, length, vel - (0 if o == 0 else 10), gate)
            for b in range(bars) for o in hits]


def shift(events, ticks):
    return [(t + ticks, n, ln, v, g) for t, n, ln, v, g in events]


def diatonic(events, steps, tonic, scale=(0, 2, 4, 5, 7, 9, 11)):
    """Move notes by scale degrees (e.g. -2 = a third below), staying in key."""
    t0 = NOTE[tonic[0]] + (1 if "#" in tonic else -1 if tonic.endswith("b") and len(tonic) > 1 else 0)
    out = []
    for t, n, ln, v, g in events:
        rel = (n - t0) % 12
        deg = min(range(len(scale)), key=lambda i: abs(scale[i] - rel))
        octv = (n - t0 - scale[deg]) // 12
        d = deg + steps
        out.append((t, t0 + 12 * (octv + d // len(scale)) + scale[d % len(scale)], ln, v, g))
    return out


def transpose(events, semis):
    return [(t, n + semis, ln, v, g) for t, n, ln, v, g in events]


# --------------------------------------------------------------------------
# Encoder
# --------------------------------------------------------------------------
def var(n):
    assert 0 <= n <= 0x7FFF, n
    return [n] if n < 0x80 else [0x80 | (n >> 8), n & 0xFF]


class Channel:
    def __init__(self, instr, vol, pan=64, reverb=20, priority=8, layers=(), layer_instr=None, vibrato=None):
        self.instr, self.vol, self.pan, self.reverb, self.priority = instr, vol, pan, reverb, priority
        self.vibrato = vibrato      # (rate, extent) like the vanilla leads, or None
        self.layers = [sorted(l) for l in layers if l]
        self.layer_instr = layer_instr or [None] * len(self.layers)
        assert 1 <= len(self.layers) <= 4


def encode_layer(events, instr=None):
    out = []
    if instr is not None:
        out += [0xC6, instr]                       # layer_setinstr
    lo = min(n for _, n, _, _, _ in events)
    hi = max(n for _, n, _, _, _ in events)
    trans = 0
    if hi - 21 > 63:
        trans = 12 * math.ceil((hi - 21 - 63) / 12)
    assert lo - 21 - trans >= 0, f"note range {lo}-{hi} does not fit"
    if trans:
        out += [0xC2, trans]                       # layer_transpose
    cursor = 0
    for t, n, ln, vel, gate in events:
        assert t >= cursor, f"overlapping notes at tick {t} (cursor {cursor})"
        gap = t - cursor
        while gap > 0:
            d = min(gap, 0x7FFF)
            out += [0xC0] + var(d)                 # layer_delay
            gap -= d
        out += [n - 21 - trans] + var(ln) + [max(1, min(127, vel)), gate]   # layer_note0
        cursor = t + ln
    out.append(0xFF)
    return out


def encode_sequence(channels, tempo, total, volume=100, bank=None):
    assert len(channels) <= 16
    hdr_len = 2 + 3 + 2 + 2 + 3 * len(channels) + 3 + 3 + 3
    # Channel scripts, then layer data; compute offsets in two passes.
    chan_scripts, layer_blobs = [], []
    for ch in channels:
        blobs = []
        for l, li in zip(ch.layers, ch.layer_instr):
            tune = 0 if ch.instr == DRUMS else TUNE.get((bank, li if li is not None else ch.instr), 0)
            blobs.append(encode_layer(transpose(l, tune), li))
        layer_blobs.append(blobs)
        chan_scripts.append(None)

    def chan_bytes(ch, layer_offs):
        out = [0xC4]                                # chan_largenoteson
        for i, off in enumerate(layer_offs):
            out += [0x90 + i, off >> 8, off & 0xFF]  # chan_setlayer (US encoding)
        out += [0xD4, ch.reverb, 0xDF, ch.vol, 0xDD, ch.pan, 0xC1, ch.instr, 0x60 + ch.priority]
        if ch.vibrato:
            out += [0xD7, ch.vibrato[0], 0xD8, ch.vibrato[1]]   # chan_setvibratorate / extent
        rest = total
        while rest > 0:
            d = min(rest, 0x7FFF)
            out += [0xFD] + var(d)                  # chan_delay
            rest -= d
        out.append(0xFF)
        return out

    # sizes of channel scripts don't depend on offsets (fixed-width u16)
    pos = hdr_len
    chan_off = []
    for ch, blobs in zip(channels, layer_blobs):
        chan_off.append(pos)
        pos += len(chan_bytes(ch, [0] * len(blobs)))
    layer_off = []
    for blobs in layer_blobs:
        offs = []
        for b in blobs:
            offs.append(pos)
            pos += len(b)
        layer_off.append(offs)
    assert pos < 0x10000

    mask = sum(1 << i for i in range(len(channels)))
    seq = [0xD3, 0x80, 0xD7, mask >> 8, mask & 0xFF, 0xDB, volume, 0xDD, tempo]
    loop = len(seq)
    for i, off in enumerate(chan_off):
        seq += [0x90 + i, off >> 8, off & 0xFF]   # seq_startchannel
    d = min(total, 0x7FFF)
    seq += [0xFD] + [0x80 | (d >> 8), d & 0xFF]   # seq_delay (always 2-byte var)
    assert total <= 0x7FFF, "song longer than one seq_delay"
    seq += [0xFB, loop >> 8, loop & 0xFF]         # seq_jump back to restart channels
    seq += [0xFF]
    assert len(seq) <= hdr_len, (len(seq), hdr_len)
    seq += [0x00] * (hdr_len - len(seq))
    for ch, blobs, offs in zip(channels, layer_blobs, layer_off):
        seq += chan_bytes(ch, offs)
    for blobs in layer_blobs:
        for b in blobs:
            seq += b
    return bytes(seq)


def max_polyphony(channels):
    ev = []
    for ch in channels:
        for l in ch.layers:
            for t, n, ln, v, g in l:
                ev += [(t, 1), (t + ln, -1)]
    cur = best = 0
    for _, d in sorted(ev):
        cur += d
        best = max(best, cur)
    return best


# ==========================================================================
# 1. Sky Garden Isles: bright and airy, D major, 4/4 (bank 0x22, Bob-omb
#    Battlefield's brass, organ and slap bass)
# ==========================================================================
def sky_garden():
    BAR = 192
    intro = ["D", "G", "D", "A"]
    A = ["D", "Bm", "G", "A", "D", "Bm", "Em", "A"]
    A2 = ["D", "Bm", "G", "A", "F#m", "Bm", "G", "D"]
    B = ["G", "A", "F#m", "Bm", "Em", "A", "G", "A7"]
    prog = intro + A + A2 + B + A2
    total = len(prog) * BAR

    melA = ("A4q D5e E5e F#5q A5q | G5e F#5e E5q D5e B4e D5q | B4q D5e G5e B5q. A5e | G5e F#5e E5e C#5e E5h | "
            "A4q D5e E5e F#5q A5q | B5q A5e F#5e D5q F#5q | G5q. F#5e E5q D5q | C#5h E5q rq")
    melA2 = ("A4q D5e E5e F#5q A5q | G5e F#5e E5q D5e B4e D5q | B4q D5e G5e B5q. A5e | G5e F#5e E5e G5e A5h | "
             "A5q. F#5e C#5q E5q | D5q. B4e F#5h | G5q B5q A5q C#6q | D6h. rq")
    melB = ("B5h. A5e G5e | A5h. G5e F#5e | F#5q A5q C#6q A5q | B5h D6h | "
            "G5q. F#5e E5q B5q | A5q. G5e F#5q E5q | D5q G5q B5q D6q | C#6h E6h")
    lead = []
    for text, bar in ((melA, 4), (melA2, 12), (melB, 20), (melA2, 28)):
        lead += phrase(text, BAR, bar, vel=104, gate=0xD8)
    # A third below the tune when it comes back, like the vanilla brass parts
    harm = diatonic(phrase(melA2, BAR, 28, vel=80, gate=0xD8), -2, "D")
    counter = phrase("D5h F#5h | F#5w | D5h G5h | E5w | C#5w | D5w | B4h C#5h | A4w", BAR, 20, vel=70, gate=0xF0)

    organ = arpeggio(prog, BAR, 4, [0, 1, 2, 1, 0, 1, 2, 1], 24, vel=76, gate=0xB0)
    bassl = bass(prog, BAR, 2, [(0, 36, 0), (48, 24, 0), (72, 24, 1), (96, 36, 0), (144, 24, 2), (168, 24, 1)], vel=104)

    bars = len(prog)
    kick = drum(bars - 4, BAR, [0, 72, 96], drumkey(KIT_KICK), vel=104, start=4 * BAR)
    rim = drum(bars - 4, BAR, [48, 144], drumkey(KIT_RIM), vel=84, start=4 * BAR)
    tamb = drum(bars, BAR, [24, 72, 120, 168], drumkey(KIT_TAMB), vel=60)
    hats = [(b * BAR + i * 24, HAT_NOTE if i % 4 != 3 else OPEN_HAT_NOTE, 12, 70 if i % 2 == 0 else 54, 0x80)
            for b in range(4, bars) for i in range(8)]
    splash = [(b * BAR, SPLASH_NOTE, 96, 90, 0xFF) for b in (4, 12, 20, 28)]

    chans = [
        Channel(B22_BRASS, 120, pan=64, reverb=20, priority=10, layers=[lead]),
        Channel(B22_BRASS, 92, pan=84, reverb=20, priority=9, layers=[harm]),
        Channel(B22_ORGAN, 96, pan=40, reverb=25, layers=[organ, counter]),
        Channel(B22_SLAP_BASS, 116, pan=64, reverb=10, priority=9, layers=[bassl]),
        Channel(DRUMS, 108, pan=64, reverb=10, priority=9, layers=[kick, rim, tamb]),
        Channel(B22_HIHAT, 90, pan=76, reverb=10, layers=[hats, splash], layer_instr=[B22_HIHAT, B22_SPLASH]),
    ]
    return chans, 126, total


# ==========================================================================
# 2. Frostfire Fjord highlands: Icelandic folk ballad, A dorian, 6/8 (bank 0x25)
# ==========================================================================
def frostfire():
    BAR = 144                    # 6/8: six eighths
    intro = ["Am", "G", "Am", "Em"]
    A = ["Am", "G", "F", "G", "Am", "C", "D", "Em"]
    A2 = ["Am", "G", "F", "G", "Am", "C", "G", "Am"]
    B = ["F", "C", "G", "Am", "F", "C", "Dm", "E"]
    out = ["Am", "G", "F", "Am"]
    prog = intro + A + A2 + B + A2 + out
    total = len(prog) * BAR

    melA = ("E5q. A5e G5e E5e | D5q B4e D5q E5e | C5q. A4e C5e D5e | B4q. D5q. | "
            "E5q. A5e B5e C6e | G5q. E5e D5e C5e | D5q. F#5q A5e | E5h.")
    melA2 = ("E5q. A5e G5e E5e | D5q B4e D5q E5e | C5q. A4e B4e C5e | D5q. B4e A4e G4e | "
             "A4q. C5e E5e A5e | G5q. E5e G5e C6e | B5q A5e G5q D5e | A5h.")
    melB = ("C5q. A4e G4e F4e | E4q. G4q. | D4e E4e F4e G4q B4e | C5q. B4e A4e E4e | "
            "F4q. A4e C5e F5e | E5q. D5e C5e G4e | D5q. C5e A4e F4e | E4q. G#4q.")
    melOut = "E5h. | D5h. | C5q. D5q. | A4h."
    flute = []
    for text, bar in ((melA, 4), (melA2, 12), (melA2, 28), (melOut, 36)):
        flute += phrase(text, BAR, bar, vel=102, gate=0xE8)
    horns = phrase(melB, BAR, 20, vel=104, gate=0xE8)
    harm = transpose(phrase(melA2, BAR, 28, vel=68, gate=0xE0), -12)   # harmonica an octave down

    piano = arpeggio(prog, BAR, 3, [0, 1, 2, 3, 2, 1], 24, vel=76, gate=0xC0)
    drone_root = [(i * BAR, chord(s, 2)[0] + 12, BAR, 56, 0xFF) for i, s in enumerate(prog)]
    drone_fifth = [(i * BAR, chord(s, 2)[0] + 19, BAR, 52, 0xFF) for i, s in enumerate(prog)]
    pads = [pad(prog[20:36], BAR, 4, v, vel=54, start=20 * BAR) for v in (1, 2)]
    bassl = bass(prog, BAR, 2, [(0, 72, 0), (72, 72, 1)], vel=94, gate=0xD8)
    tri = [(b * BAR, TRI_NOTE, 24, 70, 0xA0) for b in range(4, 20)]
    frame = drum(len(prog) - 4, BAR, [0, 72], drumkey(KIT_KICK), vel=84, start=4 * BAR, length=24)
    frame += [(b * BAR + 120, drumkey(KIT_KICK), 12, 64, 0x80) for b in range(20, 36)]
    frame = sorted(frame)
    rim = drum(16, BAR, [72], drumkey(KIT_RIM), vel=60, start=20 * BAR, length=12)
    splash = [(b * BAR, SPLASH_NOTE, 72, 76, 0xFF) for b in (20, 28)]

    chans = [
        Channel(B25_PANFLUTE, 108, pan=60, reverb=45, priority=10, layers=[flute]),
        Channel(B25_HORNS, 100, pan=70, reverb=40, priority=10, layers=[horns]),
        Channel(B25_HARMONICA, 70, pan=82, reverb=40, layers=[harm]),
        Channel(B25_PIANO, 80, pan=42, reverb=30, layers=[piano]),
        Channel(B25_STRINGS, 74, pan=64, reverb=55, layers=[drone_root, drone_fifth] + pads),
        Channel(B25_PIANO2, 92, pan=64, reverb=15, priority=9, layers=[bassl]),
        Channel(DRUMS, 82, pan=64, reverb=12, layers=[frame, rim]),
        Channel(B25_TRIANGLE, 66, pan=96, reverb=30, layers=[tri, splash], layer_instr=[B25_TRIANGLE, B25_SPLASH]),
    ]
    return chans, 105, total


# ==========================================================================
# 3. Glacier cave: music box over cold strings, E minor, 4/4 (bank 0x1C)
# ==========================================================================
def glacier_cave():
    BAR = 192
    loop = ["Emadd9", "Cmaj7", "G", "D", "Em", "Cmaj7", "Am7", "Bsus4"]
    prog = loop * 3
    total = len(prog) * BAR

    box = arpeggio(prog, BAR, 5, [0, 1, 2, 3, 2, 1, 0, 1], 24, vel=70, gate=0x90)
    pads = [pad(prog, BAR, 3, v, vel=58) for v in range(3)]
    bassl = [(i * BAR, chord(s, 2)[0], BAR, 80, 0xF0) for i, s in enumerate(prog)]
    mel = phrase("B5h. A5q | G5h E5h | D5h. B4q | A4w | E5h G5h | B5h. C6q | B5h A5h | F#5w", BAR, 8, vel=92, gate=0xF0)
    mel2 = phrase("E6h. D6q | B5h G5h | A5h. B5q | F#5w | G5h B5h | E6h. D6q | C6h A5h | B5w", BAR, 16, vel=86, gate=0xC0)
    chime = [(b * BAR + 96, midi("E6") if b % 2 == 0 else midi("B5"), 48, 66, 0xC0) for b in range(8, 16)]

    chans = [
        Channel(B1C_MUSICBOX, 118, pan=44, reverb=60, layers=[box]),
        Channel(B1C_STRINGS, 104, pan=64, reverb=70, layers=pads),
        Channel(B1C_STRINGS2, 112, pan=64, reverb=40, priority=9, layers=[bassl]),
        Channel(B1C_STRINGS3, 124, pan=70, reverb=70, priority=10, layers=[mel]),
        Channel(B1C_MUSICBOX2, 112, pan=86, reverb=80, layers=[mel2, chime]),
    ]
    return chans, 76, total


# ==========================================================================
# 4. Magma hall: driving brass and timpani, C minor, 4/4 (bank 0x1A)
# ==========================================================================
def magma_hall():
    BAR = 192
    intro = ["Cm", "Cm"]
    A = ["Cm", "Cm", "Db", "Cm", "Cm", "Ab", "Bb", "Cm"]
    B = ["Ab", "Bb", "Cm", "Cm", "Ab", "Bb", "G", "G"]
    prog = intro + A + A + B + A
    total = len(prog) * BAR

    melA = ("C5q. D5e Eb5q G5q | F5q. Eb5e D5h | Db5q. Eb5e F5q Ab5q | G5w | "
            "C6q. Bb5e G5q Eb5q | Ab5q. G5e F5q Eb5q | D5q. Eb5e F5q Bb5q | C6h. rq")
    melB = ("Eb5q Ab5q C6q Eb6q | D6h. C6e Bb5e | C6q G5q Eb5q G5q | C6w | "
            "Eb6h. C6q | D6q. C6e Bb5q D6q | B5h. D6q | G5h B5h")
    horns = phrase(melA, BAR, 2, vel=106, gate=0xD8) + phrase(melA, BAR, 26, vel=106, gate=0xD8)
    trumpet = phrase(melA, BAR, 10, vel=100, gate=0xC8) + phrase(melB, BAR, 18, vel=110, gate=0xD0)
    horn_harm = transpose(phrase(melB, BAR, 18, vel=88, gate=0xD8), -12)

    def ostinato(sym, t0):
        r = chord(sym, 2)[0]
        third = chord(sym, 2)[1]
        pat = [r, r, r + 7, r, third + 12, r, r + 7, r + 10]
        return [(t0 + i * 24, n, 24, 104 if i in (0, 4) else 88, 0xA8) for i, n in enumerate(pat)]
    low = per_bar(prog, BAR, ostinato)
    strings = per_bar(prog[2:], BAR, lambda s, t0: [(t0 + i * 24, chord(s, 4)[i % 2 * 2], 24, 70, 0x90)
                                                     for i in range(8)], start=2 * BAR)
    timp = [(b * BAR + o, chord(prog[b], 3)[0] - (5 if o == 96 else 0), 48, 104 if o == 0 else 90, 0xFF)
            for b in range(len(prog)) for o in (0, 96)]
    timp += [(b * BAR + 144 + i * 12, chord(prog[b], 3)[0], 12, 80 + 6 * i, 0xC0)
             for b in (9, 17, 25, 33) for i in range(4)]
    timp = sorted(timp)
    clean_timp, cursor = [], -1
    for e in timp:
        if e[0] >= cursor:
            clean_timp.append(e)
            cursor = e[0] + e[2]
    snare = drum(len(prog) - 2, BAR, [48, 144], SNARE_NOTE, vel=84, start=2 * BAR)
    snare += [(b * BAR + 168, SNARE_NOTE, 12, 70, 0x80) for b in range(9, len(prog), 8)]
    snare = sorted(snare)
    splash = [(b * BAR, SPLASH_NOTE, 96, 92, 0xFF) for b in (2, 10, 18, 26)]
    kick = drum(len(prog) - 2, BAR, [0, 96], drumkey(KIT_KICK), vel=100, start=2 * BAR)

    chans = [
        Channel(B1A_HORNS, 116, pan=58, reverb=30, priority=10, layers=[horns, horn_harm]),
        Channel(B1A_TRUMPET, 100, pan=70, reverb=30, priority=10, layers=[trumpet]),
        Channel(B1A_BRASS, 88, pan=64, reverb=20, priority=9, layers=[low]),
        Channel(B1A_STRINGS, 74, pan=88, reverb=30, layers=[strings]),
        Channel(B1A_TIMPANI, 100, pan=60, reverb=30, layers=[clean_timp]),
        Channel(B1A_SNARE, 82, pan=64, reverb=12, layers=[snare, splash], layer_instr=[B1A_SNARE, B1A_SPLASH]),
        Channel(DRUMS, 86, pan=64, reverb=8, layers=[kick]),
    ]
    return chans, 144, total


# id, name, composer, bank, default volume
SONGS = [
    (0x70, "sky_garden", sky_garden, 0x22, 82),
    (0x71, "frostfire", frostfire, 0x25, 100),
    (0x72, "glacier_cave", glacier_cave, 0x1C, 118),
    (0x73, "magma_hall", magma_hall, 0x1A, 100),
]
# Sequence master volume; levels were matched against recordings of the
# vanilla Bob-omb Battlefield and Cool, Cool Mountain themes.
SEQ_VOLUME = {"sky_garden": 100, "frostfire": 127, "glacier_cave": 127, "magma_hall": 127}


# --------------------------------------------------------------------------
# Calibration: every melodic instrument of a song's bank plays C4 E4 G4 C5,
# one instrument after another, so recorded pitches can be checked.
# --------------------------------------------------------------------------
CALIBRATION = {
    0x22: [B22_BRASS, B22_ORGAN, B22_SLAP_BASS],
    0x25: [B25_PANFLUTE, B25_HORNS, B25_HARMONICA, B25_PIANO, B25_STRINGS, B25_PIANO2],
    0x1C: [B1C_MUSICBOX, B1C_STRINGS, B1C_STRINGS2, B1C_STRINGS3],
    0x1A: [B1A_HORNS, B1A_TRUMPET, B1A_TROMBONE, B1A_BRASS, B1A_STRINGS, B1A_TIMPANI],
}


def calibration(bank):
    def fn():
        chans = []
        step = 6 * TPB          # two 2-beat notes + 2 beats of silence (60 bpm: 2 s notes)
        for i, inst in enumerate(CALIBRATION[bank]):
            ev = [(i * step, 60, 2 * TPB - 4, 110, 0xFF), (i * step + 2 * TPB, 67, 2 * TPB - 4, 110, 0xFF)]
            chans.append(Channel(inst, 120, pan=64, reverb=0, layers=[ev]))
        return chans, 60, len(CALIBRATION[bank]) * 6 * TPB + 4 * TPB
    return fn

def main():
    root = Path(sys.argv[1])
    m64dir = Path(sys.argv[sys.argv.index("--m64") + 1]) if "--m64" in sys.argv else None
    out = ["// Generated by tools/new64/gen_music.py. Do not edit.",
           "// SM64 sequences for the new64 courses (one vanilla sound bank each).", ""]
    table = []
    songs = SONGS
    if "--calibrate" in sys.argv:
        songs = [(i, n, calibration(b), b, 127) for i, n, _, b, _ in SONGS]
    for seq_id, name, fn, bank, vol in songs:
        chans, tempo, total = fn()
        if "--no-drums" in sys.argv:   # analysis aid: pitched instruments only
            chans = [c for c in chans if c.instr not in (DRUMS, B22_HIHAT, B25_TRIANGLE, B1A_SNARE)]
        data = encode_sequence(chans, tempo, total, volume=SEQ_VOLUME.get(name, 100), bank=bank)
        poly = max_polyphony(chans)
        secs = total / TPB * 60 / tempo
        print(f"{name}: {len(data)} bytes, {len(chans)} channels, {secs:.0f} s loop, max {poly} notes")
        if m64dir:
            m64dir.mkdir(parents=True, exist_ok=True)
            (m64dir / f"{name}.m64").write_bytes(data)
        out.append(f"static const u8 sNew64Seq_{name}[{len(data)}] = {{")
        for i in range(0, len(data), 24):
            out.append("    " + ", ".join(f"0x{b:02X}" for b in data[i:i + 24]) + ",")
        out.append("};")
        out.append("")
        table.append(f"    {{ 0x{seq_id:02X}, 0x{bank:02X}, {vol}, sNew64Seq_{name}, sizeof(sNew64Seq_{name}) }},")
    out.append("static const struct New64Song sNew64Songs[] = {")
    out += table
    out.append("};")
    out.append("")
    (root / "src/pc/new64_music_data.h").write_text("\n".join(out))


if __name__ == "__main__":
    main()
