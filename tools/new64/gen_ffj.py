#!/usr/bin/env python3
"""Generate Frostfire Fjord (levels/ffj), new64's course 17.

Iceland in miniature: a black sand beach and basalt sea stacks with puffins,
moss lava fields, a geyser field, a milky blue hot spring, a turf-house
village, a glacier with blue ice cliffs and a waterfall, and a volcano with a
lava river and a crater lake. Inside: a glacier ice cave (area 2) and a lava
tube that opens into a magma hall with the Big Chill Bully (area 3).

Usage: gen_ffj.py <repo root> [map.png]
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from levelgen import Level, Light, Grid, Noise, Model, Region, smoothstep, lerp, norm  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
L = Level("ffj", ROOT)

# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
# Lava scrolls downstream (-x, +z) in every area; the glow layer on top runs
# faster, which reads as a hot current over a slower crust.
L.mat("blacksand", "fire_09001800", tint=(105, 105, 115), vary=0.14)
L.mat("seabed", "fire_09001800", tint=(80, 95, 105), vary=0.1)
L.mat("moss", "fire_09002800", tint=(215, 240, 190), vary=0.18)
L.mat("grass", "outside_09004000", tint=(190, 215, 160), vary=0.16)
L.mat("rock", "fire_09002000", tint=(205, 205, 210), vary=0.14)
L.mat("basalt", "fire_09005800", tint=(185, 190, 205), vary=0.12)
L.mat("ash", "fire_09001800", tint=(85, 80, 82), vary=0.14)
L.mat("scoria", "grass_09009800", tint=(200, 135, 120), vary=0.14)
L.mat("craterwall", "cave_09000000", tint=(150, 108, 100), world=360.0, vary=0.1, glow=1.3)
L.mat("lava", "fire_09009000", tint=(255, 245, 235), unlit=True, glow=0.0, surface="SURFACE_BURNING", world=420.0,
      scroll=(-6, 10))
L.mat("lavaglow", "mountain_0900C000", tint=(255, 235, 150), alpha=150, unlit=True, glow=0.0, surface=None,
      world=480.0, scroll=(-14, 22))
L.mat("lavafall", "fire_09009000", tint=(255, 240, 220), unlit=True, glow=0.0, world=300.0, scroll=(0, 120))
L.mat("snow", "snow_09008800", tint=(245, 250, 255), vary=0.08)
L.mat("ice", "snow_09000800", tint=(215, 235, 255), surface="SURFACE_ICE")
L.mat("icewall", "snow_09002800", tint=(205, 228, 255), world=320.0, vary=0.16)
L.mat("icecrack", "snow_09002000", tint=(225, 240, 255), vary=0.1)
L.mat("icecrystal", "snow_09000800", tint=(200, 235, 255), alpha=200, unlit=True, surface=None)
L.mat("crystal", "snow_09000800", tint=(200, 235, 255), alpha=200, unlit=True)      # solid pillars
L.mat("floewall", "snow_09002800", tint=(185, 215, 255), world=320.0, vary=0.1, glow=0.22)
L.mat("floeice", "snow_09000800", tint=(215, 235, 255), surface="SURFACE_ICE", glow=0.45)
L.mat("water", "water_09000000", tint=(120, 175, 215), alpha=170, surface=None, world=600.0, scroll=(3, 2))
L.mat("lagoon", "water_09000000", tint=(175, 240, 235), alpha=215, surface=None, world=500.0, scroll=(2, -2))
# Waterfall curtains: same textures, different speeds, so the layers slide
# past each other. The stream on the glacier runs toward the lip (+z).
L.mat("fall", "water_09003800", tint=(235, 248, 255), alpha=215, surface=None, world=260.0, unlit=True, glow=0.0,
      scroll=(0, 150))
L.mat("fall2", "water_09006800", tint=(225, 240, 255), alpha=160, surface=None, world=330.0, unlit=True, glow=0.0,
      scroll=(0, 105))
L.mat("fall3", "water_09003800", tint=(255, 255, 255), alpha=120, surface=None, world=200.0, unlit=True, glow=0.0,
      scroll=(0, 230))
L.mat("stream", "water_09000000", tint=(170, 215, 240), alpha=210, surface=None, world=360.0, unlit=True, glow=0.0,
      scroll=(0, 60))
L.mat("silica", "snow_09006000", tint=(230, 245, 240))
L.mat("foam", "snow_09008800", tint=(255, 255, 255), alpha=170, surface=None, unlit=True, glow=0.0)
L.mat("wood", "grass_09006800", tint=(200, 160, 120))
L.mat("whitewall", "grass_09007000", tint=(250, 250, 245))
L.mat("redroof", "fire_0900A800", tint=(255, 120, 100))
L.mat("darkness", "fire_09005800", tint=(0, 0, 0), unlit=True, glow=0.0, surface=None)
L.mat("obsidian", "fire_09005800", tint=(120, 115, 130), vary=0.12)
L.mat("tuberock", "mountain_09004000", tint=(150, 118, 108), world=300.0, vary=0.14)
L.mat("snowpack", "snow_09006000", tint=(215, 230, 245), vary=0.1)
L.mat("scree", "generic_09003000", tint=(150, 150, 165), vary=0.12)
L.mat("mist", "snow_09009000", tint=(255, 255, 255), alpha=150, surface=None, unlit=True, glow=0.0, world=420.0,
      scroll=(0, -40))

N1 = Noise(1)
N2 = Noise(2)
N3 = Noise(3)

# ==========================================================================
# Area 1: the highlands
# ==========================================================================
X0, Z0, CELL, NC = -11200, -11200, 320, 70
EDGE = X0 + CELL * NC

VOLC = (5200, -5600)
V_R, V_H, RC, LR = 6600.0, 3700.0, 1350.0, 1050.0     # ~33 deg flanks: walkable from every side
RIVER = [(4300, -4600), (3500, -3700), (2600, -2600), (1900, -1500), (1500, -500), (1300, 250)]
RIVER_W = 300.0
LAVA_POOL = (1300, 250, 650)
LAGOON = (-4300, 2600, 900)
GEYSERS = [(4250, 2050, 104), (4700, 2300, 108), (2600, 1300, 100)]   # x, z, launch (rise ~ v^2 / 7.6)
SPIRE = (5200, 2450, 450, 2600)                                       # x, z, r, top
LEDGE = (4700, 2300, 270, 1500)
POOL = (-7800, -1000, 800)
TUBE_PIT = (1200, -5200)


def shore(x):
    return 6000 + 400 * N1.fbm(x / 3000, 7.3)


def base(x, z, rough=1.0):
    s = shore(x)
    if z > s:
        h = max(-700.0, -(z - s) * 0.35)
    elif z > s - 1300:
        h = 40 + (s - z) * 0.03
    else:
        d = (s - 1300) - z
        h = 80 + d * 0.085 + 160 * rough * N2.fbm(x / 2500, z / 2500)
    # Mountains around the north, east and west edges keep Mario in.
    edge = min(x - X0, EDGE - x, z - Z0 + 2000)
    if z < s - 1300:
        h += 3800 * (1 - smoothstep(0, 2200, edge))
    return h


def cone(r):
    return V_H * max(0.0, 1 - r / V_R)


RIM_Y = base(*VOLC, rough=0.0) + cone(RC)
CRATER_LAVA_Y = RIM_Y - 700
LIP = 130           # flat walkway on the crater rim


def volcano(x, z):
    r = math.dist((x, z), VOLC)
    if r >= V_R:
        return None
    # The ground's own bumps fade out up the cone so its flanks stay walkable
    b = base(x, z, rough=1.0 - smoothstep(V_R, V_R * 0.7, r))
    if r >= RC:
        return b + cone(r) + 30 * N3.fbm(x / 1200, z / 1200, 2) * (1 - r / V_R)
    # A flat lip to walk around on, then a steep wall of layered rock down
    # into the bowl. The lava lake is a flat level over the bottom (region1).
    if r >= RC - LIP:
        return RIM_Y
    t = (r - LR) / (RC - LIP - LR)
    if t <= 0:
        return CRATER_LAVA_Y - 80 + 30 * (r / LR)
    gully = 25 * N2.fbm(math.atan2(x - VOLC[0], z - VOLC[1]) * 2.5, t * 2, 2)
    return lerp(CRATER_LAVA_Y - 50, RIM_Y, t ** 0.85) + gully * t * (1 - t) * 4


def dist_to_river(x, z):
    best = 1e9
    for (ax, az), (bx, bz) in zip(RIVER, RIVER[1:]):
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
        best = min(best, math.dist((x, z), (ax + dx * t, az + dz * t)))
    return best


def lowland(x, z):
    h = base(x, z)
    v = volcano(x, z)
    if v is not None:
        h = v if math.dist((x, z), VOLC) < RC else max(h, v)
    # Hot spring basin
    r = math.dist((x, z), LAGOON[:2])
    if r < LAGOON[2]:
        h -= 300 * (1 - (r / LAGOON[2]) ** 2)
    r = math.dist((x, z), POOL[:2])
    if r < POOL[2]:
        h -= 380 * (1 - (r / POOL[2]) ** 2)
    return h


# Glacier plateau (north-west) with a straight-ish east and south face.
def plateau_east(z):
    return -5000 + 350 * N1.fbm(z / 1800, 3.1)


def plateau_south(x):
    return -2000 + 350 * N2.fbm(x / 1800, 5.7)


def in_plateau(x, z):
    return x < plateau_east(z) and z < plateau_south(x)


def plateau_h(x, z):
    t = smoothstep(-5000, -10000, x + z * 0.5)
    return 2450 + 650 * t + 70 * N3.fbm(x / 1200, z / 1200)


ICE_MOUTH_Z = (-3750, -3100)
ICE_MOUTH_X1 = plateau_east(-3420)
ICE_MOUTH_X0 = ICE_MOUTH_X1 - 960
FALL_X = (-8120, -7480)
FALL_Z1 = plateau_south(-7800)
FALL_Z0 = FALL_Z1 - 700
TONGUE_A, TONGUE_B, TONGUE_W = (-3300, -1350), (-5600, -2700), 1100.0


def tongue_t(x, z):
    ax, az = TONGUE_A
    bx, bz = TONGUE_B
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = ((x - ax) * dx + (z - az) * dz) / L2
    px, pz = ax + dx * t, az + dz * t
    return t, math.dist((x, z), (px, pz))


def classify(cx, cz):
    if ICE_MOUTH_X0 <= cx <= ICE_MOUTH_X1 and ICE_MOUTH_Z[0] <= cz <= ICE_MOUTH_Z[1]:
        return "icemouth"
    if FALL_X[0] <= cx <= FALL_X[1] and FALL_Z0 <= cz <= FALL_Z1:
        return "alcove"
    t, d = tongue_t(cx, cz)
    if 0.0 <= t <= 1.0 and d < TONGUE_W / 2 and not in_plateau(cx, cz):
        return "tongue"
    if in_plateau(cx, cz):
        return "fall_ledge" if -8900 < cx < -6700 and cz > plateau_south(cx) - 1400 else "plateau"
    if abs(cx - TUBE_PIT[0]) < 320 and abs(cz - TUBE_PIT[1]) < 320:
        return "pit"
    return "lowland"


TONGUE_LOW = lowland(*TONGUE_A)


def corner_h(cls, x, z):
    if cls in ("plateau", "fall_ledge"):
        return plateau_h(x, z)
    if cls == "tongue":
        t, _ = tongue_t(x, z)
        t = max(0.0, min(1.0, t))
        return max(lowland(x, z), lerp(TONGUE_LOW, plateau_h(*TONGUE_B), t ** 1.1))
    if cls == "icemouth":
        return lowland(ICE_MOUTH_X1 + 200, -3420)
    if cls == "alcove":
        return lowland(-7800, FALL_Z1 + 260) + 30
    if cls == "pit":
        return lowland(*TUBE_PIT) - 620
    return lowland(x, z)


def terrain_normal(x, z):
    e = 60.0
    hx = lowland(x + e, z) - lowland(x - e, z)
    hz = lowland(x, z + e) - lowland(x, z - e)
    return norm((-hx, 2 * e, -hz))


def in_lava_flow(x, z, rv):
    """The lava river and the pool it ends in, with wavy banks."""
    if rv > RC + 40:
        w = RIVER_W * (1 + 0.22 * N1.fbm(x / 900, z / 900, 2))
        if dist_to_river(x, z) < w:
            return True
    rp = LAVA_POOL[2] * (1 + 0.16 * N2.fbm(x / 600, z / 600, 2))
    return math.dist((x, z), LAVA_POOL[:2]) < rp


def _reg(key, mat, **kw):
    return Region(key, mat, **kw)


REG1 = {m: _reg(m, m) for m in ("moss", "grass", "rock", "basalt", "ash", "scoria", "snow", "seabed", "blacksand",
                                 "silica")}
REG1["craterwall"] = _reg("craterwall", "craterwall", wall="craterwall")
REG1["lavaflow"] = _reg("lavaflow", "lava", drop=90, wall="basalt", overlay="lavaglow")
REG1["lavalake"] = _reg("lavalake", "lava", level=CRATER_LAVA_Y, wall="craterwall", overlay="lavaglow")


def region1(x, z):
    """Floor material (and lava) of the lowland at a point. Cells are split
    along the edges between these, so boundaries follow the noise."""
    rv = math.dist((x, z), VOLC)
    h = lowland(x, z)
    if rv < RC:
        if rv < RC - LIP - 10 and h < CRATER_LAVA_Y + 15:
            return REG1["lavalake"]
        return REG1["craterwall"] if rv < RC - LIP + 20 else REG1["scoria"]
    if in_lava_flow(x, z, rv):
        return REG1["lavaflow"]
    if rv < RC + 260 + 120 * N3.fbm(x / 500, z / 500, 2):
        return REG1["scoria"]
    if h < -30:
        return REG1["seabed"]
    if z > shore(x) - 1450 + 180 * N2.fbm(x / 700, 4.1, 2) and h < 170:
        return REG1["blacksand"]
    if math.dist((x, z), LAGOON[:2]) < LAGOON[2] + 120 + 70 * N1.fbm(x / 300, z / 300, 2):
        return REG1["silica"]
    if math.dist((x, z), POOL[:2]) < POOL[2] + 100 + 60 * N3.fbm(x / 300, z / 300, 2):
        return REG1["rock"]
    n = terrain_normal(x, z)
    slope = math.sqrt(max(0.0, 1 - n[1] * n[1])) / max(n[1], 0.05)
    if rv < V_R * 0.92:
        if slope > 0.8:
            return REG1["basalt"]
        return REG1["ash"] if N1.fbm(x / 700, z / 700, 3) > -0.1 else REG1["basalt"]
    if h > 2650 + 350 * N2.fbm(x / 1100, z / 1100, 3):
        return REG1["snow"]
    if slope > 0.75 or h > 3200:
        return REG1["rock"]
    return REG1["grass"] if N2.fbm(x / 2200, z / 2200) > 0.15 and h < 900 else REG1["moss"]


REG1["icecrack"] = _reg("icecrack", "icecrack")


def region_glacier(x, z):
    """Snow and cracked blue ice on the glacier and its tongue."""
    tt, d = tongue_t(x, z)
    if 0.0 <= tt <= 1.0 and d < TONGUE_W / 2 and not in_plateau(x, z):
        return REG1["snow"] if d < TONGUE_W * (0.3 + 0.06 * N1.fbm(x / 500, z / 500, 2)) else REG1["icecrack"]
    return REG1["snow"] if N3.fbm(x / 900, z / 900, 3) > -0.45 else REG1["icecrack"]


def cell_area1(i, k, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    cls = classify(cx, cz)
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    f = [corner_h(cls, x, z) for x, z in corners]
    c = {"floor": tuple(f), "mat": "moss", "wall": "rock", "cls": cls}
    if cls == "lowland":
        c["region"] = region1
        c["wall"] = "basalt" if math.dist((cx, cz), VOLC) < V_R else "rock"
    elif cls == "plateau":
        c["region"] = region_glacier
        c["wall"] = "icewall"
    elif cls == "fall_ledge":
        c["mat"] = "moss"
        c["wall"] = "basalt"
    elif cls == "tongue":
        c["region"] = region_glacier
        c["wall"] = "icewall"
    elif cls == "icemouth":
        c["mat"] = "snowpack"
        c["wall"] = "icewall"
    elif cls == "alcove":
        c["mat"] = "rock"
        c["wall"] = "basalt"
    elif cls == "pit":
        c["mat"] = "darkness"
        c["wall"] = "basalt"
    return c


def area1_glow(p):
    # Warm light from the lava river, pool and crater
    g = 0.0
    dr = dist_to_river(p[0], p[2])
    g += 0.6 * max(0.0, 1 - dr / 1300) ** 2
    g += 0.65 * max(0.0, 1 - math.dist((p[0], p[2]), LAVA_POOL[:2]) / 1600) ** 2
    rv = math.dist((p[0], p[2]), VOLC)
    if rv < RC + 300 and p[1] > CRATER_LAVA_Y - 50:
        g += 0.9 * max(0.0, 1 - (p[1] - CRATER_LAVA_Y) / 900)
    return (g * 1.0, g * 0.45, g * 0.12)


GROUND_MATS = {"moss", "grass", "blacksand", "ash", "basalt", "rock", "snow", "scoria", "silica", "seabed"}


def paint1(p, mat):
    x, y, z = p
    if mat == "lava":
        # Hot in the middle of a flow, crusting over toward the banks
        rv = math.dist((x, z), VOLC)
        if rv < RC:
            t = rv / LR
        else:
            t = min(dist_to_river(x, z) / RIVER_W, math.dist((x, z), LAVA_POOL[:2]) / LAVA_POOL[2])
        k = (1.0 - 0.3 * smoothstep(0.4, 1.05, t)) * (0.9 + 0.2 * N3.fbm(x / 350, z / 350, 2))
        return (k, k * 0.92, k * 0.85)
    if mat in GROUND_MATS:
        h = lowland(x, z)
        if abs(y - h) > 60:
            return None
        # Hollows a little darker, ridges a little lighter
        ring = sum(lowland(x + dx, z + dz) for dx, dz in ((450, 0), (-450, 0), (0, 450), (0, -450))) / 4
        k = max(0.78, min(1.12, 1.0 + (h - ring) / 900))
        return (k, k, k)
    return None


A1 = L.area(1, Light(sun=(-0.45, 0.55, 0.7), ambient=0.52, sun_color=(1.0, 0.95, 0.85),
                     ambient_color=(0.85, 0.9, 1.05), glow=area1_glow, paint=paint1))
G1 = Grid(A1, X0, Z0, CELL, NC, NC)
G1.fill(cell_area1)


def ground1(x, z):
    return G1.height_at(x, z, default=lowland(x, z))


G1.build(floor_normals=terrain_normal, merge_flat=True)

# Sea and water
A1.water_plane(X0, 3800, EDGE, EDGE, 0, "water", box=True, step=2800)
lag_y = lowland(LAGOON[0], LAGOON[1] - LAGOON[2]) - 70
A1.water_plane(LAGOON[0] - LAGOON[2], LAGOON[1] - LAGOON[2], LAGOON[0] + LAGOON[2], LAGOON[1] + LAGOON[2],
               lag_y, "lagoon", box=True, step=900)
pool_y = lowland(POOL[0], POOL[1] + POOL[2]) - 60
A1.water_plane(POOL[0] - POOL[2], POOL[1] - POOL[2] + 200, POOL[0] + POOL[2], POOL[1] + POOL[2],
               pool_y, "lagoon", box=True, step=800)

# Waterfall. A meltwater stream crosses the glacier to the lip, curls over it
# and falls in three layered curtains that scroll at different speeds. The
# curtains bow out as they fall, fade at the sides and dissolve into mist and
# foam on the pool. The middle layer is double sided so it shows from the
# alcove behind it too.
fall_top = plateau_h(-7800, FALL_Z1) + 10
FALL_L, FALL_R = FALL_X[0] - 60, FALL_X[1] + 60


def fall_curtain(mat, dz, alpha, bulge, cols=8, rows=8, back=False, seed=0):
    m = L.mats[mat]
    H = fall_top - (pool_y - 20)
    W = FALL_R - FALL_L

    def P(ci, ri):
        u, v = ci / cols, ri / rows
        wob = 18 * math.sin(u * 9.0 + seed) * v
        return (FALL_L + W * u, fall_top - H * v, FALL_Z1 + dz + bulge * v ** 1.6 + wob)

    def A(ci, ri):
        u, v = ci / cols, ri / rows
        side = smoothstep(0.0, 0.16, u) * smoothstep(1.0, 0.84, u)
        foot = 1 - 0.55 * smoothstep(0.7, 1.0, v)
        n = 0.85 + 0.3 * N2.fbm(u * 3 + seed, v * 2, 2)
        return int(max(0, min(255, alpha * side * foot * n)))
    for ci in range(cols):
        for ri in range(rows):
            pts = [P(ci, ri), P(ci + 1, ri), P(ci + 1, ri + 1), P(ci, ri + 1)]
            uvs = [((p[0] - FALL_L) / m.world, (fall_top - p[1]) / m.world) for p in pts]
            al = (A(ci, ri), A(ci + 1, ri), A(ci + 1, ri + 1), A(ci, ri + 1))
            A1.sheet(pts, mat, uvs, (0, 0, 1), alpha=al)
            if back:
                A1.sheet(pts, mat, uvs, (0, 0, -1), alpha=tuple(int(a * 0.8) for a in al))


fall_curtain("fall", 12, 215, 70, back=True, seed=1)
fall_curtain("fall2", 34, 165, 120, seed=2)
fall_curtain("fall3", 58, 120, 170, cols=6, rows=6, seed=3)

# The stream on the glacier and the lip where it curls over
STREAM_Z0 = FALL_Z1 - 1500
ALC_TOP = plateau_h(-7800, FALL_Z1 - 300)


def stream_ground(x, z):
    if FALL_X[0] - 20 <= x <= FALL_X[1] + 20 and FALL_Z0 - 60 <= z <= FALL_Z1 + 30:
        return ALC_TOP
    return G1.height_at(x, z, default=plateau_h(x, z))


def stream_edge(t):
    z = STREAM_Z0 + (FALL_Z1 - 4 - STREAM_Z0) * t
    x = -7800 + 70 * math.sin(t * 5.4)
    w = 140 + 230 * t ** 1.5
    return [(x - w, stream_ground(x - w, z) + 10, z), (x + w, stream_ground(x + w, z) + 10, z)]


for j in range(12):
    (a, b), (d, c) = stream_edge(j / 12), stream_edge((j + 1) / 12)
    A1.sheet([a, b, c, d], "stream", [(p[0] / 360, p[2] / 360) for p in (a, b, c, d)], (0, 1, 0))
lip = [(FALL_L + 40, fall_top - 4, FALL_Z1 - 6), (FALL_R - 40, fall_top - 4, FALL_Z1 - 6),
       (FALL_R - 20, fall_top - 70, FALL_Z1 + 22), (FALL_L + 20, fall_top - 70, FALL_Z1 + 22)]
A1.sheet(lip, "fall", [(0, 0), (2.4, 0), (2.4, 0.3), (0, 0.3)], (0, 0.7, 0.7), alpha=(220, 220, 215, 215))

# Mist rising off the pool: crossed sheets, and foam rings on the water
for j, (dx, w, h) in enumerate(((0, 520, 420), (-160, 380, 300), (170, 360, 330))):
    cx, cz = -7800 + dx, FALL_Z1 + 170 + 40 * j
    for ang in (0.35, -0.35):
        ex, ez = math.cos(ang) * w, math.sin(ang) * w
        pts = [(cx - ex, pool_y + h, cz - ez), (cx + ex, pool_y + h, cz + ez),
               (cx + ex, pool_y - 10, cz + ez), (cx - ex, pool_y - 10, cz - ez)]
        uvs = [(0, 0), (2 * w / 420, 0), (2 * w / 420, h / 420), (0, h / 420)]
        for want in ((-math.sin(ang), 0, math.cos(ang)), (math.sin(ang), 0, -math.cos(ang))):
            A1.sheet(pts, "mist", uvs, want, alpha=(0, 0, 150, 150))
A1.decal(-7800, pool_y, FALL_Z1 + 230, 600, "foam", 16, seed=9, lift=5, alpha=120)
A1.decal(-7800, pool_y, FALL_Z1 + 150, 380, "foam", 12, seed=10, lift=8, alpha=190)

# Roofs over the alcove and the ice cave mouth, flush with the cliff top
alc_floor = corner_h("alcove", 0, 0)
A1.box(((FALL_X[0] + FALL_X[1]) / 2, plateau_h(-7800, FALL_Z1 - 300), (FALL_Z0 + FALL_Z1) / 2 - 30),
       (FALL_X[1] - FALL_X[0] + 40, plateau_h(-7800, FALL_Z1 - 300) - alc_floor - 560, FALL_Z1 - FALL_Z0 + 60),
       0, top="moss", side="basalt", bottom="basalt")
A1.sheet([(FALL_X[0] + 5, alc_floor + 560, FALL_Z0 + 8), (FALL_X[1] - 5, alc_floor + 560, FALL_Z0 + 8),
          (FALL_X[1] - 5, alc_floor, FALL_Z0 + 8), (FALL_X[0] + 5, alc_floor, FALL_Z0 + 8)],
         "darkness", [(0, 0), (1, 0), (1, 1), (0, 1)], (0, 0, 1))
mouth_floor = corner_h("icemouth", 0, 0)
mouth_top = plateau_h(ICE_MOUTH_X1 - 400, -3420)
A1.box(((ICE_MOUTH_X0 + ICE_MOUTH_X1) / 2 - 30, mouth_top, sum(ICE_MOUTH_Z) / 2),
       (ICE_MOUTH_X1 - ICE_MOUTH_X0 + 60, mouth_top - mouth_floor - 650, ICE_MOUTH_Z[1] - ICE_MOUTH_Z[0] + 60),
       0, top="snow", side="icewall", bottom="icewall")
mouth_cells = [(i, k) for (i, k), c in G1.cells.items() if c["cls"] == "icemouth"]
MOUTH_BACK_X = X0 + min(i for i, _ in mouth_cells) * CELL
MOUTH_Z0 = Z0 + min(k for _, k in mouth_cells) * CELL
MOUTH_Z1 = Z0 + (max(k for _, k in mouth_cells) + 1) * CELL
A1.sheet([(MOUTH_BACK_X + 6, mouth_floor + 650, MOUTH_Z0), (MOUTH_BACK_X + 6, mouth_floor + 650, MOUTH_Z1),
          (MOUTH_BACK_X + 6, mouth_floor, MOUTH_Z1), (MOUTH_BACK_X + 6, mouth_floor, MOUTH_Z0)],
         "darkness", [(0, 0), (1, 0), (1, 1), (0, 1)], (1, 0, 0))
# Icicles hanging over the cave mouth
for j in range(6):
    zz = ICE_MOUTH_Z[0] + 60 + j * (ICE_MOUTH_Z[1] - ICE_MOUTH_Z[0] - 120) / 5
    A1.cone(ICE_MOUTH_X1 + 10, zz, 45, mouth_floor + 650, mouth_floor + 650 - 160 - 70 * (j % 2), 6, "icecrystal",
            down=True, seed=j)

# Sea stacks (Reynisdrangar) and the stepped basalt columns out to them
STACKS = [(2600, 8300, 430, 2400), (3500, 7800, 300, 1700), (1800, 7600, 290, 1300)]
for sx, sz, sr, top in STACKS:
    A1.prism(sx, sz, sr, -700, top, 7, side="basalt", cap="moss", yaw=sx % 40)
    A1.prism(sx + sr * 0.6, sz - sr * 0.5, sr * 0.45, -700, top * 0.55, 6, side="basalt", cap="basalt")
steps = []


def col_path(a, b, h0, h1, n):
    for t in range(n):
        f = (t + 0.5) / n
        steps.append((lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(h0, h1, f)))


col_path((1000, 6150), (1700, 7300), 180, 1150, 6)
col_path((1950, 7350), (3250, 7700), 1380, 1550, 3)
col_path((3450, 8050), (2950, 8350), 1820, 2250, 3)
for j, (x, z, top) in enumerate(steps):
    A1.prism(x, z, 175, -700, top, 6, side="basalt", cap="basalt", yaw=j * 17)

# Geyser field: a ledge column and the tall basalt spire
A1.prism(SPIRE[0], SPIRE[1], SPIRE[2], ground1(SPIRE[0], SPIRE[1]) - 50, SPIRE[3], 6, side="basalt", cap="moss")
for j in range(5):
    a = math.tau * j / 5
    A1.prism(SPIRE[0] + math.sin(a) * 430, SPIRE[1] + math.cos(a) * 430, 150, 0, SPIRE[3] - 500 - 260 * j, 6,
             side="basalt", cap="basalt", yaw=j * 11)
A1.prism(LEDGE[0], LEDGE[1], LEDGE[2], ground1(LEDGE[0], LEDGE[1]) - 50, LEDGE[3], 6, side="basalt", cap="basalt")
for x, z, _ in GEYSERS:
    if math.dist((x, z), LEDGE[:2]) > 100:
        A1.decal(x, ground1(x, z), z, 260, "silica", 10, seed=int(x), lift=4)
A1.decal(LEDGE[0], LEDGE[3], LEDGE[1], 200, "silica", 8, seed=77, lift=4)

# Volcano crater. A flat lip runs around the rim; at the way in (CRATER_DIR) a
# basalt column stands just below it, then stepping stones lead across the
# lava lake to the spire. Spatter boulders dot the lip elsewhere.
CRATER_DIR = norm((-0.82, 0.0, 0.57))
crater_steps = []
ENTRY_TOP = RIM_Y - 70
for r, top, rad in ((1150, ENTRY_TOP, 130), (930, ENTRY_TOP - 40, 115), (715, ENTRY_TOP - 80, 115),
                    (500, ENTRY_TOP - 115, 112)):
    x, z = VOLC[0] + CRATER_DIR[0] * r, VOLC[1] + CRATER_DIR[2] * r
    crater_steps.append((x, z, top))
    A1.prism(x, z, rad, CRATER_LAVA_Y - 300, top, 6, side="basalt", cap="basalt", yaw=r % 37)
CRATER_SPIRE_TOP = CRATER_LAVA_Y + 520
A1.prism(VOLC[0], VOLC[1], 240, CRATER_LAVA_Y - 300, CRATER_SPIRE_TOP, 6, side="basalt", cap="scoria")
ENTRY_ANG = math.atan2(CRATER_DIR[0], CRATER_DIR[2])
for j in range(11):
    a = ENTRY_ANG + math.tau * (j + 0.5) / 11
    if abs((a - ENTRY_ANG + math.pi) % math.tau - math.pi) < 0.45:
        continue
    rr = RC - LIP + 35 + 25 * (j % 2)
    x, z = VOLC[0] + math.sin(a) * rr, VOLC[1] + math.cos(a) * rr
    A1.rock(x, z, 60 + 12 * (j % 3), RIM_Y - 60, 120 + 35 * (j % 3), "scoria", 5, seed=300 + j)

# The lava river wells up from a vent just below the rim
for j in range(7):
    a = math.atan2(RIVER[0][0] - RIVER[1][0], RIVER[0][1] - RIVER[1][1]) + (j - 3) * 0.55
    x, z = RIVER[0][0] + math.sin(a) * 330, RIVER[0][1] + math.cos(a) * 330
    A1.rock(x, z, 75 + 15 * (j % 3), ground1(x, z) - 50, 150 + 40 * (j % 2), "scoria", 5, seed=320 + j)

# Turf-house village by the beach and a little white church
VILLAGE = (-2700, 4700)


def gable(cx, cz, w, d, wall_h, roof_h, wall_mat, roof_mat, yaw=0.0, gy=None):
    gy = ground1(cx, cz) if gy is None else gy
    A1.box((cx, gy + wall_h, cz), (w, wall_h + 40, d), yaw, top=roof_mat, side=wall_mat, bottom=wall_mat)
    r = math.radians(yaw)
    cs, sn = math.cos(r), math.sin(r)

    def P(lx, ly, lz):
        return (cx + lx * cs + lz * sn, gy + ly, cz - lx * sn + lz * cs)
    hw, hd, y0, y1 = w / 2 + 40, d / 2 + 40, wall_h, wall_h + roof_h
    ridge0, ridge1 = P(0, y1, -hd), P(0, y1, hd)
    for sgn in (-1, 1):
        e0, e1 = P(sgn * hw, y0, -hd), P(sgn * hw, y0, hd)
        out = (sgn * cs, 0.6, -sgn * sn)
        A1.quad(roof_mat, e0, e1, ridge1, ridge0, ((0, 0), (d / 256, 0), (d / 256, 1.2), (0, 1.2)), out)
    for sgn in (-1, 1):
        a, b, c = P(-w / 2, y0, sgn * d / 2), P(w / 2, y0, sgn * d / 2), P(0, y1, sgn * d / 2)
        A1.tri(wall_mat, a, b, c, ((0, 0), (1, 0), (0.5, 0.6)), (sgn * sn, 0, sgn * cs))


for j, (dx, dz, yaw) in enumerate([(0, 0, 10), (700, 150, -8), (-650, 250, 15)]):
    gable(VILLAGE[0] + dx, VILLAGE[1] + dz, 420, 560, 220, 260, "wood", "grass", yaw)
gable(VILLAGE[0] + 150, VILLAGE[1] - 900, 360, 640, 360, 240, "whitewall", "redroof", 5)
A1.prism(VILLAGE[0] + 150, VILLAGE[1] - 900 - 380, 90, ground1(VILLAGE[0] + 150, VILLAGE[1] - 1280) + 300,
         ground1(VILLAGE[0] + 150, VILLAGE[1] - 1280) + 820, 4, side="whitewall", cap="redroof", yaw=45)

# Lava tube skylight rim stones
for j in range(8):
    a = math.tau * j / 8
    x, z = TUBE_PIT[0] + math.sin(a) * 470, TUBE_PIT[1] + math.cos(a) * 470
    A1.prism(x, z, 70 + 25 * (j % 3), ground1(x, z) - 40, ground1(x, z) + 80 + 50 * (j % 2), 5,
             side="basalt", cap="basalt", yaw=j * 31)

A1.death_plane(-3000, 16000)
for a, b, want in [((X0, EDGE), (EDGE, EDGE), (0, 0, -1)), ((X0, X0 + 100), (X0, EDGE), (1, 0, 0)),
                   ((EDGE, X0), (EDGE, EDGE), (-1, 0, 0)), ((X0, Z0), (EDGE, Z0), (0, 0, 1))]:
    A1.invisible_wall(a, b, -1500, 9000, want)

# ---------------------------------------------------------------- objects --
spawn = (0, ground1(0, 5350), 5350)
A1.obj("MODEL_NONE", (spawn[0], spawn[1] + 600, spawn[2]), "bhvSpinAirborneWarp", 0x000A0000, yaw=180)
# Cave and tube connections
mouth_mid = (MOUTH_BACK_X + 230, mouth_floor, (MOUTH_Z0 + MOUTH_Z1) / 2)
A1.obj("MODEL_NONE", mouth_mid, "bhvWarp", 0x1E0B0000)                        # -> area 2
A1.obj("MODEL_NONE", (ICE_MOUTH_X1 + 450, mouth_floor + 20, mouth_mid[2]), "bhvInstantActiveWarp", 0x000C0000, yaw=90)
pit_floor = corner_h("pit", 0, 0)
A1.obj("MODEL_NONE", (TUBE_PIT[0], pit_floor, TUBE_PIT[1]), "bhvWarp", 0x280D0000)  # -> area 3
A1.obj("MODEL_NONE", (TUBE_PIT[0] - 800, ground1(TUBE_PIT[0] - 800, TUBE_PIT[1]) + 400, TUBE_PIT[1]),
       "bhvAirborneWarp", 0x000E0000, yaw=270)

# Star 2 (index 1): geysers to the basalt spire
for j, (x, z, launch) in enumerate(GEYSERS):
    gy = LEDGE[3] if math.dist((x, z), LEDGE[:2]) < 100 else ground1(x, z)
    A1.obj("MODEL_FFJ_GEYSER_STEAM", (x, gy, z), "bhvNew64Geyser", (j * 70 << 24) | (launch << 16))
for j, (x, z) in enumerate([(-4600, 2350), (-4050, 2900)]):
    A1.obj("MODEL_FFJ_GEYSER_STEAM", (x, lag_y, z), "bhvNew64Geyser", (j * 100 + 30) << 24)
A1.obj("MODEL_STAR", (SPIRE[0], SPIRE[3] + 220, SPIRE[1]), "bhvStar", 0x01000000)

# Star 4 (index 3): Lundi patrol. The last puffin reveals the star above the tallest stack.
lundi_homes = [(STACKS[0][0] - 150, STACKS[0][3], STACKS[0][1] + 120), (STACKS[1][0], STACKS[1][3], STACKS[1][1]),
               (STACKS[2][0], STACKS[2][3], STACKS[2][1]), (steps[4][0], steps[4][2], steps[4][1]),
               (steps[8][0], steps[8][2], steps[8][1])]
for j, (x, y, z) in enumerate(lundi_homes):
    A1.obj("MODEL_FFJ_LUNDI", (x, y, z), "bhvNew64Lundi", 0x03000000 | (j << 16), yaw=j * 70)
LUNDI_STAR = (STACKS[0][0], STACKS[0][3] + 260, STACKS[0][1])

# Star 5 (index 4): behind the waterfall
A1.obj("MODEL_STAR", ((FALL_X[0] + FALL_X[1]) / 2, alc_floor + 180, FALL_Z0 + 220), "bhvStar", 0x04000000)

# Star 6 (index 5): crater stepping stones
A1.obj("MODEL_STAR", (VOLC[0], CRATER_SPIRE_TOP + 220, VOLC[1]), "bhvStar", 0x05000000)
for j, (dx, dz) in enumerate([(-500, 500), (400, -300), (-200, -600), (600, 400)]):
    A1.obj("MODEL_NONE", (VOLC[0] + dx, CRATER_LAVA_Y, VOLC[1] + dz), "bhvBouncingFireball", 0)
for x, z in [(2200, -2050), (1650, -950)]:
    A1.obj("MODEL_NONE", (x, ground1(x, z), z), "bhvBouncingFireball", 0)

# Ambient sound: the waterfall and the volcano
A1.obj("MODEL_NONE", (-7800, pool_y, FALL_Z1 + 200), "bhvWaterfallSoundLoop", 0)
A1.obj("MODEL_NONE", (VOLC[0], RIM_Y, VOLC[1]), "bhvVolcanoSoundLoop", 0)

# Enemies and friends
plat_pts = [(-7600, -4300), (-6400, -5600), (-8200, -6400)]
for j, (x, z) in enumerate(plat_pts):
    A1.obj("MODEL_MR_BLIZZARD", (x, plateau_h(x, z), z), "bhvMrBlizzard", 0x00000000)
for x, z in [(-6200, -3600), (-4300, -2100)]:
    A1.obj("MODEL_SPINDRIFT", (x, ground1(x, z), z), "bhvSpindrift", 0)
for j in range(3):
    x, z = VOLC[0] - 1150 + 200 * j, VOLC[1] + 700 + 120 * j
    rx, rz = VOLC[0] + math.sin(2.4 + j * 0.5) * (RC + 120), VOLC[1] + math.cos(2.4 + j * 0.5) * (RC + 120)
    A1.obj("MODEL_CHILL_BULLY", (rx, ground1(rx, rz) + 30, rz), "bhvSmallChillBully", 0)
for x, z in [(-600, 5800), (500, 5700), (-1500, 5500)]:
    A1.obj("MODEL_PENGUIN", (x, ground1(x, z), z), "bhvSmallPenguin", 0)

# Coins (area 1)
def cline(x, z, yaw=0, dy=0):
    A1.macro("macro_coin_line_horizontal", (x, ground1(x, z) + dy, z), yaw=yaw)


def cring(x, z, dy=0, vertical=False):
    A1.macro("macro_coin_ring_vertical" if vertical else "macro_coin_ring_horizontal", (x, ground1(x, z) + dy, z))


cring(0, 4600)
cline(-1200, 5100, 90)
cline(1300, 4900, 90)
cring(-2700, 3900)
cline(400, 2600)
cline(1900, 3200, 45)
cring(LAGOON[0], LAGOON[1], dy=-100)
for x, z, _ in GEYSERS[:2]:
    pass
cring(2600, 1300, dy=650, vertical=True)
cline(3200, -1100, 135)
cline(2400, -3300, 135)
cring(-3700, -900)
cline(-4200, -1900, 135)
cline(-6600, -3000, 90)
cring(-7000, -5200)
cline(-9000, -3600)
cline(-7800, -1000 + 600, 90)
for j, (x, z, top) in enumerate(steps):
    if j % 2 == 0:
        A1.macro("macro_yellow_coin", (x, top + 40, z))
for x, z, top in crater_steps:
    A1.macro("macro_yellow_coin", (x, top + 40, z))
A1.macro("macro_1up", (STACKS[1][0], STACKS[1][3] + 40, STACKS[1][1]))
A1.macro("macro_box_ten_coins", (VILLAGE[0] + 900, ground1(VILLAGE[0] + 900, VILLAGE[1] + 700) + 240, VILLAGE[1] + 700))

# Basalt boulders (solid) and pebbles (visual only) across the moss fields and
# the beach, kept off the coin lines, paths, buildings and water.
KEEP_CLEAR = [((0, 5350), 1200), (VILLAGE, 1500), ((VILLAGE[0] + 150, VILLAGE[1] - 900), 800),
              (LAGOON[:2], LAGOON[2] + 450), (POOL[:2], POOL[2] + 500), (LAVA_POOL[:2], LAVA_POOL[2] + 550),
              ((SPIRE[0], SPIRE[1]), 900), ((LEDGE[0], LEDGE[1]), 700), (TUBE_PIT, 900),
              ((ICE_MOUTH_X1 + 300, -3420), 900), ((-7800, -1500), 1000), ((1350, 6700), 900)]
KEEP_CLEAR += [((x, z), 650) for x, z, _ in GEYSERS]
KEEP_CLEAR += [((x, z), 380) for _, _, (x, y, z), _ in A1.macros]
KEEP_CLEAR += [((x, z), 450) for _, (x, y, z), *_ in A1.objects]
ROCKY = {"moss", "grass", "ash", "blacksand", "basalt"}
RNG1 = random.Random(1717)


def scatter_spot(x, z, r):
    i, k = int((x - X0) // CELL), int((z - Z0) // CELL)
    c = G1.cells.get((i, k))
    if c is None or c["cls"] != "lowland" or region1(x, z).key not in ROCKY:
        return False
    if any(math.dist((x, z), q) < d + r for q, d in KEEP_CLEAR):
        return False
    if dist_to_river(x, z) < RIVER_W * 1.4 + r + 200 or math.dist((x, z), VOLC) < 2600:
        return False
    return terrain_normal(x, z)[1] > 0.82 and lowland(x, z) > 20


placed = []
for n in range(4000):
    if len(placed) >= 24:
        break
    x, z = RNG1.uniform(X0 + 2500, EDGE - 2500), RNG1.uniform(Z0 + 3500, 6200)
    r = RNG1.uniform(80, 170)
    if scatter_spot(x, z, r) and all(math.dist((x, z), q) > 650 for q in placed):
        placed.append((x, z))
        top_mat = "moss" if region1(x, z).key in ("moss", "grass") and RNG1.random() < 0.6 else "basalt"
        A1.rock(x, z, r, ground1(x, z) - 40, RNG1.uniform(100, 230) + 40, "basalt", RNG1.choice((5, 6)),
                seed=n, cap=top_mat, lean=RNG1.uniform(0, 0.12))
        for m in range(RNG1.randint(2, 4)):
            a, d = RNG1.uniform(0, math.tau), r + RNG1.uniform(60, 220)
            px, pz = x + math.sin(a) * d, z + math.cos(a) * d
            A1.rock(px, pz, RNG1.uniform(25, 50), ground1(px, pz) - 12, RNG1.uniform(30, 55), "basalt", 4,
                    seed=n * 10 + m, collide=False)
print(f"boulders {len(placed)}")

# ==========================================================================
# Area 2: the glacier ice cave
# ==========================================================================
C2 = 220
X2 = Z2 = -5280
N2C = 48


def caps(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / (dx * dx + dz * dz)))
    return math.dist((px, pz), (ax + dx * t, az + dz * t)), t


HALL = (0, 0, 1750)
LAKE_R = 1150
# tunnels: a, b, radius, floor a, floor b, height, kind
TUNNELS = [
    ((0, 4500), (0, 1500), 420, 0, 0, 720, "entry"),
    ((-1500, 0), (-3300, 0), 390, 40, 140, 700, "maze"),
    ((-3300, 0), (-3300, -2200), 370, 140, 260, 680, "maze"),
    ((-3300, 0), (-3300, 1900), 370, 140, 60, 680, "maze"),
    ((-3300, -2200), (-1800, -3300), 360, 260, 260, 660, "maze"),
    ((1500, -300), (3000, -1000), 410, 40, 720, 760, "ramp"),
    ((3400, -2300), (1900, -3900), 400, 720, 380, 740, "slide"),
    ((1900, -3900), (200, -3000), 400, 380, 40, 740, "slide"),
    ((200, -3000), (0, -1500), 420, 40, 40, 760, "slide"),
]
ROOMS2 = [((-3300, -2500), 520, 260, 700), ((-3300, 2100), 480, 60, 650), ((-4300, -300), 420, 180, 600),
          ((3400, -1700), 850, 720, 900), ((-1700, -3400), 420, 260, 600)]


def info2(x, z):
    """(floor, ceiling, kind) of the ice cave at a point, or None in solid ice."""
    best = None
    r = math.dist((x, z), HALL[:2])
    if r < HALL[2]:
        fl = 0 if r < LAKE_R else 50 * smoothstep(LAKE_R, HALL[2], r)
        ce = 1550 - 850 * (r / HALL[2]) ** 2
        best = (fl, ce, "lake" if r < LAKE_R + 60 * N1.fbm(x / 400, z / 400, 2) else "shore")
    for (rx, rz), rr, fl, hh in ROOMS2:
        d = math.dist((x, z), (rx, rz))
        if d < rr:
            ce = fl + hh - 250 * (d / rr) ** 2
            kind = "gallery" if fl > 600 else "room"
            if best is None or fl > best[0]:
                best = (fl, ce, kind)
    for a, b, rr, fa, fb, hh, kind in TUNNELS:
        d, t = caps(x, z, *a, *b)
        if d < rr:
            fl = lerp(fa, fb, t)
            ce = fl + hh - 120 * (d / rr) ** 2
            if best is None:
                best = (fl, ce, kind)
    return best


REG2 = {"lake": Region("lake", "ice"), "shore": Region("shore", "snowpack"), "room": Region("room", "snowpack"),
        "gallery": Region("gallery", "ice"), "entry": Region("entry", "snowpack"),
        "maze": Region("maze", "icecrack"), "ramp": Region("ramp", "snowpack"),
        "slide": Region("slide", "ice", surface="SURFACE_VERY_SLIPPERY")}


def region2(x, z):
    """Floor material of the ice cave (heights come from the cell corners)."""
    v = info2(x, z)
    if v is None:
        # Just outside the cave: the nearest tunnel or room decides
        best, kind = 1e9, "entry"
        for a, b, rr, fa, fb, hh, kd in TUNNELS:
            d, _ = caps(x, z, *a, *b)
            if d - rr < best:
                best, kind = d - rr, kd
        for (rx, rz), rr, fl, hh in ROOMS2:
            d = math.dist((x, z), (rx, rz)) - rr
            if d < best:
                best, kind = d, "gallery" if fl > 600 else "room"
        if math.dist((x, z), HALL[:2]) - HALL[2] < best:
            kind = "shore"
        return REG2[kind]
    return REG2[v[2]]


def cave2_cell(i, k, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    ci = info2(cx, cz)
    if ci is None:
        return None
    fl, ce, kind = ci
    f, cc = [], []
    for x, z in corners:
        v = info2(x, z)
        if v is None:
            v = ci
        f.append(v[0])
        cc.append(max(v[1], v[0] + 300))
    return {"floor": tuple(f), "ceil": tuple(cc), "mat": REG2[kind].mat, "wall": "icewall", "ceilmat": "icewall",
            "kind": kind, "region": region2}


def area2_glow(p):
    # Cold blue light filtering through the ice, brightest under the hall's dome
    f = max(0.0, 1 - math.dist((p[0], p[2]), HALL[:2]) / 2600) ** 1.5
    return (0.02 * f, 0.06 + 0.08 * f, 0.18 + 0.12 * f)


A2 = L.area(2, Light(sun=(0.2, 1.0, 0.3), ambient=0.62, sun_color=(0.75, 0.9, 1.1),
                     ambient_color=(0.7, 0.85, 1.15), glow=area2_glow))
G2 = Grid(A2, X2, Z2, C2, N2C, N2C)
G2.fill(cave2_cell)
G2.build()


def ground2(x, z):
    i, k = int((x - X2) // C2), int((z - Z2) // C2)
    c = G2.cells.get((i, k))
    if c is None:
        return 0
    fx, fz = (x - (X2 + i * C2)) / C2, (z - (Z2 + k * C2)) / C2
    f = c["floor"]
    return lerp(lerp(f[0], f[1], fx), lerp(f[3], f[2], fx), fz)


# Icicles and crystal pillars
for j in range(26):
    a = j * 2.39996
    r = 300 + (j * 53 % 1300)
    x, z = HALL[0] + math.sin(a) * r, HALL[1] + math.cos(a) * r
    ce = 1550 - 850 * (r / HALL[2]) ** 2
    A2.cone(x, z, 50 + (j % 3) * 18, ce + 20, ce - 220 - (j % 4) * 70, 6, "icecrystal", down=True, seed=j)
for j in range(7):
    a = j * math.tau / 7 + 0.3
    x, z = math.sin(a) * (LAKE_R + 180), math.cos(a) * (LAKE_R + 180)
    A2.prism(x, z, 90 + 30 * (j % 2), ground2(x, z) - 20, ground2(x, z) + 380 + 140 * (j % 3), 5,
             side="crystal", cap="crystal", collide=True, yaw=j * 20)
A2.prism(0, 0, 170, -20, 260, 6, side="crystal", cap="ice", collide=True)
for (rx, rz), rr, fl, hh in ROOMS2:
    for j in range(3):
        a = j * 2.1 + rx
        x, z = rx + math.sin(a) * rr * 0.6, rz + math.cos(a) * rr * 0.6
        A2.cone(x, z, 60, fl, fl + 240 + 60 * j, 6, "icecrystal", collide=True, seed=j)
# Icicles along every tunnel and room, crystal clusters where the floor meets
# the wall. Visual only; the tips stay well above Mario's jumps.
RNG2 = random.Random(22)
for (i, k), c in sorted(G2.cells.items()):
    x0, z0 = X2 + i * C2, Z2 + k * C2
    fl, ce = sum(c["floor"]) / 4, sum(c["ceil"]) / 4
    if RNG2.random() < 0.16 and ce - fl > 560 and math.dist((x0, z0), HALL[:2]) > HALL[2] - 200:
        x, z = x0 + RNG2.uniform(30, C2 - 30), z0 + RNG2.uniform(30, C2 - 30)
        L_ = min(RNG2.uniform(120, 300), ce - fl - 420)
        A2.cone(x, z, RNG2.uniform(28, 55), ce + 30, ce - L_, 5, "icecrystal", down=True, seed=i * 97 + k)
    solid = [n for n in ((i + 1, k), (i - 1, k), (i, k + 1), (i, k - 1)) if n not in G2.cells]
    if solid and RNG2.random() < 0.22:
        ni, nk = solid[0]
        x = x0 + C2 / 2 + (ni - i) * C2 * 0.32
        z = z0 + C2 / 2 + (nk - k) * C2 * 0.32
        y = ground2(x, z)
        for m in range(RNG2.randint(2, 3)):
            ox, oz = RNG2.uniform(-45, 45), RNG2.uniform(-45, 45)
            A2.cone(x + ox, z + oz, RNG2.uniform(22, 38), y - 10, y + RNG2.uniform(70, 190), 5, "icecrystal",
                    seed=i * 31 + k * 7 + m, jitter=0.2)

A2.obj("MODEL_NONE", (0, 0, 3700), "bhvInstantActiveWarp", 0x000B0000, yaw=180)
A2.obj("MODEL_NONE", (0, 0, 4350), "bhvWarp", 0x1E0C0000)                    # -> area 1 mouth

# Star 3 (index 2): eight red coins
A2.obj("MODEL_NONE", (0, 560, 0), "bhvHiddenRedCoinStar", 0x02000000)
reds2 = [(600, 0, -500), (-700, 0, 300), (-3300, 260, -2700), (-3300, 60, 2250), (-4400, 180, -300),
         (3600, 720, -1500), (3000, 720, -2200), (1200, 380, -3700)]
for x, y, z in reds2:
    A2.macro("macro_red_coin", (x, y, z))
A2.macro("macro_coin_ring_horizontal", (0, 0, 2600))
A2.macro("macro_coin_line_horizontal", (-2300, 90, 0), yaw=90)
A2.macro("macro_coin_line_horizontal", (-3300, 200, -1100))
A2.macro("macro_coin_line_horizontal", (2200, 300, -600), yaw=110)
A2.macro("macro_coin_ring_horizontal", (3400, 720, -1700))
A2.macro("macro_coin_line_horizontal", (2700, 560, -3100), yaw=135)
A2.macro("macro_coin_line_horizontal", (1000, 200, -3400), yaw=60)
A2.macro("macro_1up", (-1700, 260, -3400))
for x, z in [(800, 1200), (-1000, -900)]:
    A2.obj("MODEL_SPINDRIFT", (x, ground2(x, z), z), "bhvSpindrift", 0)
A2.obj("MODEL_MR_BLIZZARD", (-3300, 140, 600), "bhvMrBlizzard", 0)
for x, z in [(3200, -1400), (3700, -1900)]:
    A2.obj("MODEL_CHILL_BULLY", (x, 740, z), "bhvSmallChillBully", 0)

# ==========================================================================
# Area 3: lava tube and the magma hall
# ==========================================================================
C3 = 240
X3 = Z3 = -6000
N3C = 50
MAGMA_Y = -200
FLOE = (0, -1300, 1000, 300)
HALL3 = (0, -1300, 3900)
TUBE = ((0, 5100), (0, 2400), 480)
STONES3 = [(0, 1900, 40), (60, 1450, 110), (-40, 1000, 170), (40, 560, 240), (0, 150, 300)]
ISLANDS3 = [(-2300, -2200, 600, 120), (2300, -2400, 650, 160), (2400, 300, 450, 80)]


LAVA_COLUMNS = [(-1800, -2900), (1450, -3350), (-2650, 650)]


def info3(x, z):
    """(ceiling, kind, island) of the lava tube and magma hall, or None in rock."""
    r = math.dist((x, z), HALL3[:2])
    d, t = caps(x, z, *TUBE[0], *TUBE[1])
    stream = abs(x + 30 * N1.fbm(z / 500, 1.7, 2)) < 130 and z < 4300
    best = None
    if d < TUBE[2]:
        best = (820 - 220 * (d / TUBE[2]) ** 2, "stream" if stream else "tube", None)
    if r < HALL3[2]:
        ce = 2600 - 1300 * (r / HALL3[2]) ** 2
        a = math.atan2(x - HALL3[0], z - HALL3[1])
        if r > HALL3[2] - 450 + 70 * N2.fbm(a * 3, 0.5, 2):
            best = (ce, "stream" if stream else "rim", None)
        elif math.dist((x, z), FLOE[:2]) < FLOE[2] * (1 + 0.06 * N3.fbm(x / 300, z / 300, 2)):
            best = (ce, "floe", None)
        else:
            for n, (sx, sz, sr, top) in enumerate(ISLANDS3):
                if math.dist((x, z), (sx, sz)) < sr * (1 + 0.14 * N1.fbm(x / 350, z / 350, 2)):
                    return (ce, "island", n)
            if best is None:
                best = (ce, "magma", None)
    return best


REG3 = {"tube": Region("tube", "obsidian", level=0, wall="tuberock"),
        "rim": Region("rim", "obsidian", level=0, wall="tuberock"),
        "stream": Region("stream", "lava", level=-60, overlay="lavaglow", spill="lavafall"),
        "floe": Region("floe", "floeice", level=FLOE[3], wall="floewall"),
        "magma": Region("magma", "lava", level=MAGMA_Y, overlay="lavaglow")}
for n, (sx, sz, sr, top) in enumerate(ISLANDS3):
    REG3[f"island{n}"] = Region(f"island{n}", "basalt", level=top, wall="basalt")


def region3(x, z):
    v = info3(x, z)
    if v is None:
        return REG3["rim"]
    return REG3[f"island{v[2]}" if v[1] == "island" else v[1]]


def cave3_cell(i, k, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    ci = info3(cx, cz)
    if ci is None:
        return None
    f, cc = [], []
    for x, z in corners:
        r = region3(x, z)
        v = info3(x, z)
        f.append(r.level)
        cc.append(max(v[0] if v else ci[0], r.level + 350))
    reg = region3(cx, cz)
    return {"floor": tuple(f), "ceil": tuple(cc), "mat": reg.mat, "wall": "tuberock", "ceilmat": "tuberock",
            "kind": ci[1], "region": region3}


def area3_glow(p):
    x, y, z = p
    g = max(0.0, 1 - (y - MAGMA_Y) / 2400)
    if math.dist((x, z), HALL3[:2]) > HALL3[2] - 100:
        # Up the tube only the lava stream lights the walls
        g *= max(0.3, 1 - abs(x) / 700)
    for cx, cz in LAVA_COLUMNS:
        g += 0.45 * max(0.0, 1 - math.dist((x, z), (cx, cz)) / 1300) ** 2
    return (0.8 * g, 0.36 * g, 0.1 * g)


A3 = L.area(3, Light(sun=(0.0, -1.0, 0.2), ambient=0.38, sun_color=(1.0, 0.5, 0.2),
                     ambient_color=(0.75, 0.55, 0.55), glow=area3_glow))
G3 = Grid(A3, X3, Z3, C3, N3C, N3C)
G3.fill(cave3_cell)
G3.build()

for x, z, top in STONES3:
    A3.prism(x, z, 150, MAGMA_Y - 200, top, 6, side="basalt", cap="basalt", yaw=x % 30)
# Lava pouring from cracks in the roof into the lake (no collision)
for j, (x, z) in enumerate(LAVA_COLUMNS):
    ce = 2600 - 1300 * (math.dist((x, z), HALL3[:2]) / HALL3[2]) ** 2
    A3.prism(x, z, 75, MAGMA_Y - 10, ce + 60, 6, side="lavafall", cap=None, collide=False, yaw=j * 20)
    A3.decal(x, MAGMA_Y, z, 260, "lavaglow", 10, seed=40 + j, lift=8, alpha=210)
# Stalactites
for j in range(30):
    a = j * 2.39996
    r = 600 + (j * 97 % 3000)
    x, z = HALL3[0] + math.sin(a) * r, HALL3[1] + math.cos(a) * r
    ce = 2600 - 1300 * (r / HALL3[2]) ** 2
    A3.cone(x, z, 80 + (j % 3) * 30, ce + 30, ce - 300 - (j % 4) * 120, 6, "tuberock", down=True, seed=j)
# Ice spikes ringing the floe
for j in range(10):
    a = j * math.tau / 10
    x, z = FLOE[0] + math.sin(a) * (FLOE[2] - 90), FLOE[1] + math.cos(a) * (FLOE[2] - 90)
    if abs(a - math.pi * 0) > 0.35 and abs(a - math.tau) > 0.35:
        A3.cone(x, z, 70, FLOE[3], FLOE[3] + 200 + 80 * (j % 3), 6, "icecrystal", collide=True, seed=j)

A3.obj("MODEL_NONE", (0, 450, 4550), "bhvAirborneWarp", 0x000D0000, yaw=180)
A3.obj("MODEL_NONE", (0, 0, 5000), "bhvWarp", 0x1E0E0000)                    # -> area 1
# Star 1 (index 0): the Big Chill Bully on the ice floe (act 1)
A3.obj("MODEL_BIG_CHILL_BULLY", (FLOE[0], FLOE[3], FLOE[1] - 200), "bhvBigChillBully", 0x00000000, acts="ACT_1")
for x, z in [(-450, -900), (450, -1700)]:
    A3.obj("MODEL_CHILL_BULLY", (x, FLOE[3], z), "bhvSmallChillBully", 0, acts="ACT_1")
CHILL_STAR = (FLOE[0], FLOE[3] + 650, FLOE[1])
# Fire hazards
A3.obj("MODEL_LLL_ROTATING_BLOCK_FIRE_BARS", (ISLANDS3[0][0], ISLANDS3[0][3] + 0, ISLANDS3[0][1]),
       "bhvLllRotatingBlockWithFireBars", 0)
A3.obj("MODEL_LLL_ROTATING_BLOCK_FIRE_BARS", (0, 0, 3300), "bhvLllRotatingBlockWithFireBars", 0)
for x, z in [(-1500, 300), (1500, -300), (-1200, -3200), (1300, -3600), (2600, -1000), (-2700, -500)]:
    A3.obj("MODEL_NONE", (x, MAGMA_Y, z), "bhvBouncingFireball", 0)
for x, z, yaw in [(-460, 3800, 90), (460, 2900, -90)]:
    A3.obj("MODEL_NONE", (x, 120, z), "bhvFlamethrower", 0, yaw=yaw)
# Sinking platforms on the east route to the islands
for x, z in [(1600, 1500), (2100, 900), (2500, -800), (1900, -1500)]:
    A3.obj("MODEL_LLL_SINKING_SQUARE_PLATFORMS", (x, MAGMA_Y + 20, z), "bhvLllSinkingSquarePlatforms", 0)
# Coins (area 3)
A3.macro("macro_coin_line_horizontal", (-250, 0, 4400))
A3.macro("macro_coin_line_horizontal", (250, 0, 3600))
A3.macro("macro_coin_ring_horizontal", (0, FLOE[3], FLOE[1]))
for x, z, top in STONES3:
    A3.macro("macro_yellow_coin", (x, top + 40, z))
for sx, sz, sr, top in ISLANDS3:
    A3.macro("macro_coin_ring_horizontal", (sx + (200 if sx > 0 else -200), top, sz))
A3.macro("macro_coin_line_horizontal", (0, 0, -5000), yaw=90)
A3.macro("macro_coin_line_horizontal", (-3300, 0, -1300))
A3.macro("macro_coin_line_horizontal", (3300, 0, -1300))
A3.macro("macro_1up", (ISLANDS3[2][0], ISLANDS3[2][3] + 40, ISLANDS3[2][1]))

# ==========================================================================
# Custom models
# ==========================================================================
def rot_y(a):
    return lambda p: (p[0] * math.cos(a) + p[2] * math.sin(a), p[1], -p[0] * math.sin(a) + p[2] * math.cos(a))


lundi = Model("lundi")
BLACK, WHITE, ORANGE, RED, YELLOW, GREY = (28, 28, 38), (240, 240, 245), (245, 120, 30), (220, 60, 35), (250, 210, 60), (150, 150, 160)
FROST = (150, 210, 255)
lundi.ellipsoid("body", (0, 62, -5), (46, 50, 72), lambda v: BLACK if (v[1] > 8 or v[2] < -30) else WHITE)
lundi.ellipsoid("body", (0, 112, 48), (36, 36, 38), lambda v: BLACK if (v[1] > 20 or v[2] < -12) else (232, 232, 238))
lundi.ellipsoid("body", (0, 104, 92), (13, 24, 26),
                lambda v: RED if v[2] > 10 else (YELLOW if v[2] > -2 else GREY), slices=6, stacks=5)
for sx in (-1, 1):
    lundi.ellipsoid("body", (sx * 27, 118, 70), (7, 7, 6), lambda v: (10, 10, 15), slices=5, stacks=4)
    lundi.ellipsoid("body", (sx * 28, 119, 67), (9, 9, 4), lambda v: RED, slices=5, stacks=3)
    lundi.flat("body", [(sx * 18, 6, 10), (sx * 34, 2, 46), (sx * 6, 2, 44)], ORANGE, (0, 1, 0))
lundi.flat("body", [(-18, 52, -70), (18, 52, -70), (0, 66, -112)], BLACK, (0, 1, 0))


def wing(part, flap, sweep=0.0):
    """One wing pose, mirrored. flap raises the wing about the body's long
    axis; sweep folds it back along the flank (the tucked dive/perch pose)."""
    for sx in (-1, 1):
        a, b = math.radians(flap), math.radians(sweep)

        def P(lx, ly, lz):
            # sweep in the horizontal plane (tip toward the tail), then flap
            x0 = lx * math.cos(b) + lz * math.sin(b)
            z0 = -lx * math.sin(b) + lz * math.cos(b)
            x = x0 * math.cos(a) - ly * math.sin(a)
            y = x0 * math.sin(a) + ly * math.cos(a)
            return (sx * 38 + sx * x, 84 + y, z0 - 8)
        pts = [P(0, 0, 26), P(0, 0, -34), P(88, -6, -46), P(104, -9, -22), P(66, -3, 14)]
        lundi.flat(part, pts, BLACK, (0, 1, 0))
        lundi.flat(part, [P(88, -6, -46), P(104, -9, -22), P(120, -11, -40)], FROST, (0, 1, 0))


wing("wings0", 12, sweep=74)   # folded along the flanks: perched, diving
wing("wings1", 50, 6)          # up
wing("wings2", 8)              # level
wing("wings3", -28, -4)        # down
wing("wings4", 30, 3)          # half up
wing("wings5", -10, -2)        # half down

steam = Model("steam")
SEG, H = 10, 1600
for j in range(SEG):
    a0, a1 = math.tau * j / SEG, math.tau * (j + 1) / SEG
    for lvl in range(6):
        y0, y1 = H * lvl / 6, H * (lvl + 1) / 6
        r0 = 110 + 90 * (lvl / 6) ** 1.5
        r1 = 110 + 90 * ((lvl + 1) / 6) ** 1.5
        al0, al1 = int(210 * (1 - lvl / 6) ** 1.2), int(210 * (1 - (lvl + 1) / 6) ** 1.2)
        def V(a, r, y):
            return (math.sin(a) * r, y, math.cos(a) * r)
        quad = [V(a0, r0, y0), V(a1, r0, y0), V(a1, r1, y1), V(a0, r1, y1)]
        c0 = (235, 245, 255, al0)
        c1 = (235, 245, 255, al1)
        out = (math.sin((a0 + a1) / 2), 0, math.cos((a0 + a1) / 2))
        steam.tri("column", quad[0], quad[1], quad[2], c0, out, amb=0.9)
        steam.tri("column", quad[0], quad[2], quad[3], c1, out, amb=0.9)

# ==========================================================================
# Write everything
# ==========================================================================
lvl_dir = ROOT / "levels/ffj"
stats = {}
for idx, area in L.areas.items():
    stats[idx] = L.write_area(area, lvl_dir / f"areas/{idx}")
L.write_model(lundi, lvl_dir / "lundi/model.inc.c")
L.write_model(steam, lvl_dir / "steam/model.inc.c")
L.write_scroll_table(lvl_dir / "scroll.inc.c")

fmt = lambda p: "{ %.1ff, %.1ff, %.1ff }" % p
(lvl_dir / "layout.h").write_text("\n".join([
    "// Generated by tools/new64/gen_ffj.py. Do not edit.",
    "#ifndef FFJ_LAYOUT_H",
    "#define FFJ_LAYOUT_H",
    "",
    "// The Lundi star appears above the tallest sea stack.",
    f"#define FFJ_LUNDI_STAR_POS {fmt(LUNDI_STAR)}",
    "// The Big Chill Bully's star appears above the ice floe in the magma hall.",
    f"#define FFJ_CHILL_STAR_POS {fmt(CHILL_STAR)}",
    "// Below this the Big Chill Bully has fallen off the floe.",
    f"#define FFJ_CHILL_BULLY_DEATH_Y {FLOE[3] - 200:.1f}f",
    "// Where Mario lands in area 1 (MARIO_POS)",
    f"#define FFJ_SPAWN_Y {int(spawn[1])}",
    "",
    "#endif",
    ""]))

coin_vals = {"macro_yellow_coin": 1, "macro_coin_line_horizontal": 5, "macro_coin_ring_horizontal": 8,
             "macro_coin_ring_vertical": 8, "macro_red_coin": 2, "macro_box_ten_coins": 10}
coins = {i: sum(coin_vals.get(m[0], 0) for m in a.macros) for i, a in L.areas.items()}
for idx, (nvis, nv, nct) in stats.items():
    print(f"area {idx}: visual tris {nvis}, collision verts {nv} tris {nct}, macro coins {coins[idx]}")
print(f"total macro coins {sum(coins.values())} (+ enemy drops)")
print(f"rim {RIM_Y:.0f} crater lava {CRATER_LAVA_Y:.0f} lagoon water {lag_y:.0f} pool {pool_y:.0f}")

if len(sys.argv) > 2:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (NC * 6, NC * 6))
    d = ImageDraw.Draw(img)
    pal = {"lava": (255, 90, 20), "lavacrust": (200, 60, 20), "snow": (245, 250, 255), "icecrack": (200, 225, 255),
           "ice": (170, 210, 255), "blacksand": (60, 60, 70), "seabed": (40, 80, 120), "moss": (110, 150, 80),
           "grass": (120, 170, 90), "rock": (140, 140, 140), "basalt": (80, 85, 100), "ash": (70, 65, 65),
           "scoria": (150, 90, 80), "silica": (190, 230, 225), "snowpack": (220, 230, 240), "darkness": (0, 0, 0),
           "craterwall": (120, 80, 70)}
    for (i, k), c in G1.cells.items():
        mat = c["mat"]
        if c.get("region"):
            mat = c["region"](X0 + (i + 0.5) * CELL, Z0 + (k + 0.5) * CELL).mat
        col = pal.get(mat, (255, 0, 255))
        h = sum(c["floor"]) / 4
        if h < 0 and mat == "seabed":
            col = (30, 70 + int(h / 10), 120)
        d.rectangle((i * 6, k * 6, i * 6 + 5, k * 6 + 5), fill=col)
    for model, (x, y, z), *_ in A1.objects:
        px, pz = (x - X0) / CELL * 6, (z - Z0) / CELL * 6
        colr = (255, 220, 0) if "STAR" in model else (255, 0, 255) if "LUNDI" in model else (0, 255, 255) if "GEYSER" in model else None
        if colr:
            d.ellipse((px - 4, pz - 4, px + 4, pz + 4), fill=colr, outline=(0, 0, 0))
    img.save(sys.argv[2])
