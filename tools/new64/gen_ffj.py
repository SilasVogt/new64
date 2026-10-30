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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from levelgen import Level, Light, Grid, Noise, Model, smoothstep, lerp, norm  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
L = Level("ffj", ROOT)

# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
L.mat("blacksand", "fire_09001800", tint=(105, 105, 115))
L.mat("seabed", "fire_09001800", tint=(80, 95, 105))
L.mat("moss", "fire_09002800", tint=(215, 240, 190))
L.mat("grass", "outside_09004000", tint=(190, 215, 160))
L.mat("rock", "fire_09002000", tint=(205, 205, 210))
L.mat("basalt", "fire_09005800", tint=(185, 190, 205))
L.mat("ash", "fire_09001800", tint=(85, 80, 82))
L.mat("scoria", "fire_0900A800", tint=(200, 150, 140))
L.mat("lava", "fire_09009000", tint=(255, 235, 220), unlit=True, glow=0.0, surface="SURFACE_BURNING", world=380.0)
L.mat("lavacrust", "fire_09009800", tint=(255, 230, 210), unlit=True, glow=0.0, surface="SURFACE_BURNING")
L.mat("snow", "snow_09008800", tint=(245, 250, 255))
L.mat("ice", "snow_09000800", tint=(215, 235, 255), surface="SURFACE_ICE")
L.mat("icewall", "snow_09002800", tint=(205, 228, 255), world=320.0)
L.mat("icecrack", "snow_09002000", tint=(225, 240, 255))
L.mat("icecrystal", "snow_09000800", tint=(200, 235, 255), alpha=200, unlit=True, surface=None)
L.mat("water", "water_09000000", tint=(120, 175, 215), alpha=170, surface=None, world=600.0)
L.mat("lagoon", "water_09000000", tint=(175, 240, 235), alpha=215, surface=None, world=500.0)
L.mat("fall", "water_09003800", tint=(255, 255, 255), alpha=180, surface=None, world=260.0, unlit=True, glow=0.0)
L.mat("silica", "snow_09006000", tint=(230, 245, 240))
L.mat("foam", "snow_09008800", tint=(255, 255, 255), alpha=170, surface=None, unlit=True, glow=0.0)
L.mat("wood", "grass_09006800", tint=(200, 160, 120))
L.mat("whitewall", "grass_09007000", tint=(250, 250, 245))
L.mat("redroof", "fire_0900A800", tint=(255, 120, 100))
L.mat("darkness", "fire_09005800", tint=(0, 0, 0), unlit=True, glow=0.0, surface=None)
L.mat("obsidian", "fire_09005800", tint=(120, 115, 130))
L.mat("tuberock", "fire_0900A800", tint=(150, 110, 100))
L.mat("snowpack", "snow_09006000", tint=(215, 230, 245))

N1 = Noise(1)
N2 = Noise(2)
N3 = Noise(3)

# ==========================================================================
# Area 1: the highlands
# ==========================================================================
X0, Z0, CELL, NC = -11200, -11200, 320, 70
EDGE = X0 + CELL * NC

VOLC = (5200, -5600)
V_R, V_H, RC, LR = 6200.0, 4300.0, 1350.0, 1050.0
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


def base(x, z):
    s = shore(x)
    if z > s:
        h = max(-700.0, -(z - s) * 0.35)
    elif z > s - 1300:
        h = 40 + (s - z) * 0.03
    else:
        d = (s - 1300) - z
        h = 80 + d * 0.085 + 160 * N2.fbm(x / 2500, z / 2500)
    # Mountains around the north, east and west edges keep Mario in.
    edge = min(x - X0, EDGE - x, z - Z0 + 2000)
    if z < s - 1300:
        h += 3800 * (1 - smoothstep(0, 2200, edge))
    return h


def cone(r):
    return V_H * max(0.0, 1 - r / V_R) ** 1.15


RIM_Y = base(*VOLC) + cone(RC)
CRATER_LAVA_Y = RIM_Y - 700


def volcano(x, z):
    r = math.dist((x, z), VOLC)
    if r >= V_R:
        return None
    b = base(x, z)
    if r >= RC:
        return b + cone(r) + 60 * N3.fbm(x / 900, z / 900) * (1 - r / V_R)
    if r < LR:
        return CRATER_LAVA_Y
    return lerp(CRATER_LAVA_Y + 60, RIM_Y, (r - LR) / (RC - LR))


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


def cell_area1(i, k, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    cls = classify(cx, cz)
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    f = [corner_h(cls, x, z) for x, z in corners]
    h = sum(f) / 4
    slope = (max(f) - min(f)) / CELL
    c = {"floor": tuple(f), "mat": "moss", "wall": "rock", "cls": cls}
    rv = math.dist((cx, cz), VOLC)
    if cls == "lowland":
        lava_river = dist_to_river(cx, cz) < RIVER_W and rv > RC
        lava_pool = math.dist((cx, cz), LAVA_POOL[:2]) < LAVA_POOL[2]
        if lava_river or lava_pool:
            c["floor"] = tuple(v - 90 for v in f)
            c["mat"] = "lavacrust" if N3.value(cx / 400, cz / 400) > 0.35 else "lava"
            c["wall"] = "basalt"
        elif rv < LR:
            c["mat"] = "lava"
            c["wall"] = "scoria"
        elif rv < RC + 250:
            c["mat"] = "scoria"
        elif h < -30:
            c["mat"] = "seabed"
        elif cz > shore(cx) - 1450 and h < 170:
            c["mat"] = "blacksand"
        elif math.dist((cx, cz), LAGOON[:2]) < LAGOON[2] + 120:
            c["mat"] = "silica"
        elif math.dist((cx, cz), POOL[:2]) < POOL[2] + 100:
            c["mat"] = "rock"
        elif rv < V_R * 0.92:
            c["mat"] = "basalt" if slope > 0.75 else ("ash" if N1.value(cx / 700, cz / 700) > -0.1 else "basalt")
        elif slope > 0.7 or h > 3200:
            c["mat"] = "snow" if h > 2900 else "rock"
        else:
            c["mat"] = "grass" if N2.fbm(cx / 2200, cz / 2200) > 0.15 and h < 900 else "moss"
    elif cls == "plateau":
        c["mat"] = "snow" if N3.value(cx / 900, cz / 900) > -0.45 else "icecrack"
        c["wall"] = "icewall"
    elif cls == "fall_ledge":
        c["mat"] = "moss"
        c["wall"] = "basalt"
    elif cls == "tongue":
        _, d = tongue_t(cx, cz)
        c["mat"] = "snow" if d < TONGUE_W * 0.32 else "icecrack"
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
    g += 0.55 * max(0.0, 1 - dr / 1300) ** 2
    g += 0.6 * max(0.0, 1 - math.dist((p[0], p[2]), LAVA_POOL[:2]) / 1600) ** 2
    rv = math.dist((p[0], p[2]), VOLC)
    if rv < RC + 300 and p[1] > CRATER_LAVA_Y - 50:
        g += 0.8 * max(0.0, 1 - (p[1] - CRATER_LAVA_Y) / 900)
    return (g * 1.0, g * 0.45, g * 0.12)


A1 = L.area(1, Light(sun=(-0.45, 0.55, 0.7), ambient=0.52, sun_color=(1.0, 0.95, 0.85),
                     ambient_color=(0.85, 0.9, 1.05), glow=area1_glow))
G1 = Grid(A1, X0, Z0, CELL, NC, NC)
G1.fill(cell_area1)


def ground1(x, z):
    i, k = int((x - X0) // CELL), int((z - Z0) // CELL)
    c = G1.cells.get((i, k))
    if c is None:
        return lowland(x, z)
    fx, fz = (x - (X0 + i * CELL)) / CELL, (z - (Z0 + k * CELL)) / CELL
    f = c["floor"]
    return lerp(lerp(f[0], f[1], fx), lerp(f[3], f[2], fx), fz)


def terrain_normal(x, z):
    e = 60.0
    hx = lowland(x + e, z) - lowland(x - e, z)
    hz = lowland(x, z + e) - lowland(x, z - e)
    return norm((-hx, 2 * e, -hz))


G1.build(floor_normals=terrain_normal)

# Sea and water
A1.water_plane(X0, 3800, EDGE, EDGE, 0, "water", box=True, step=2800)
lag_y = lowland(LAGOON[0], LAGOON[1] - LAGOON[2]) - 70
A1.water_plane(LAGOON[0] - LAGOON[2], LAGOON[1] - LAGOON[2], LAGOON[0] + LAGOON[2], LAGOON[1] + LAGOON[2],
               lag_y, "lagoon", box=True, step=900)
pool_y = lowland(POOL[0], POOL[1] + POOL[2]) - 60
A1.water_plane(POOL[0] - POOL[2], POOL[1] - POOL[2] + 200, POOL[0] + POOL[2], POOL[1] + POOL[2],
               pool_y, "lagoon", box=True, step=800)

# Waterfall in front of the alcove: two layers for depth
fall_top = plateau_h(-7800, FALL_Z1) + 10
for dz, al in ((10, 205), (30, 150), (55, 110)):
    zf = FALL_Z1 + dz
    A1.sheet([(FALL_X[0] - 60, fall_top, zf), (FALL_X[1] + 60, fall_top, zf),
              (FALL_X[1] + 60, pool_y - 20, zf), (FALL_X[0] - 60, pool_y - 20, zf)],
             "fall", [(0, 0), (2.3, 0), (2.3, (fall_top - pool_y) / 300), (0, (fall_top - pool_y) / 300)],
             (0, 0, 1), alpha=(al, al, al, al))
# Spray at the bottom of the falls
A1.decal(-7800, pool_y, FALL_Z1 + 220, 560, "foam", 14, seed=9, lift=6, alpha=170)
A1.decal(-7800, pool_y, FALL_Z1 + 160, 330, "foam", 10, seed=10, lift=10, alpha=210)

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

# Volcano crater: stepping stones from just under the rim to the central spire.
# The inner crater wall is too steep to walk, so the first stone sits above it.
CRATER_DIR = norm((-0.82, 0.0, 0.57))
crater_steps = []
for r, dh in ((1170, 420), (930, 380), (690, 360), (450, 380)):
    x, z = VOLC[0] + CRATER_DIR[0] * r, VOLC[1] + CRATER_DIR[2] * r
    top = CRATER_LAVA_Y + dh
    crater_steps.append((x, z, top))
    A1.prism(x, z, 125, CRATER_LAVA_Y - 300, top, 6, side="basalt", cap="basalt", yaw=r % 37)
CRATER_SPIRE_TOP = CRATER_LAVA_Y + 520
A1.prism(VOLC[0], VOLC[1], 240, CRATER_LAVA_Y - 300, CRATER_SPIRE_TOP, 6, side="basalt", cap="scoria")

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


def cave2_cell(i, k, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]

    def info(x, z):
        best = None
        r = math.dist((x, z), HALL[:2])
        if r < HALL[2]:
            fl = 0 if r < LAKE_R else 50 * smoothstep(LAKE_R, HALL[2], r)
            ce = 1550 - 850 * (r / HALL[2]) ** 2
            best = (fl, ce, "lake" if r < LAKE_R else "shore")
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
    ci = info(cx, cz)
    if ci is None:
        return None
    fl, ce, kind = ci
    f, cc = [], []
    for x, z in corners:
        v = info(x, z)
        if v is None:
            v = ci
        f.append(v[0])
        cc.append(max(v[1], v[0] + 300))
    mat = {"lake": "ice", "shore": "snowpack", "room": "snowpack", "gallery": "ice",
           "entry": "snowpack", "maze": "icecrack", "ramp": "snowpack", "slide": "ice"}[kind]
    c = {"floor": tuple(f), "ceil": tuple(cc), "mat": mat, "wall": "icewall", "ceilmat": "icewall", "kind": kind}
    if kind == "slide":
        c["surface"] = "SURFACE_VERY_SLIPPERY"
    return c


def area2_glow(p):
    # Cold blue light filtering through the ice
    return (0.0, 0.08, 0.22)


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
             side="icecrystal", cap="icecrystal", collide=True, yaw=j * 20)
A2.prism(0, 0, 170, -20, 260, 6, side="icecrystal", cap="ice", collide=True)
for (rx, rz), rr, fl, hh in ROOMS2:
    for j in range(3):
        a = j * 2.1 + rx
        x, z = rx + math.sin(a) * rr * 0.6, rz + math.cos(a) * rr * 0.6
        A2.cone(x, z, 60, fl, fl + 240 + 60 * j, 6, "icecrystal", collide=True, seed=j)

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


def cave3_cell(i, k, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]

    def info(x, z):
        r = math.dist((x, z), HALL3[:2])
        d, t = caps(x, z, *TUBE[0], *TUBE[1])
        best = None
        if d < TUBE[2]:
            stream = abs(x) < 130 and z < 4300
            fl = -60 if stream else 0
            best = (fl, 820 - 220 * (d / TUBE[2]) ** 2, "stream" if stream else "tube")
        if r < HALL3[2]:
            ce = 2600 - 1300 * (r / HALL3[2]) ** 2
            if r > HALL3[2] - 450:
                best = (0, ce, "rim")
            elif math.dist((x, z), FLOE[:2]) < FLOE[2]:
                best = (FLOE[3], ce, "floe")
            else:
                isl = [s for s in ISLANDS3 if math.dist((x, z), s[:2]) < s[2]]
                if isl:
                    best = (isl[0][3], ce, "island")
                elif best is None:
                    best = (MAGMA_Y, ce, "magma")
        return best
    ci = info(cx, cz)
    if ci is None:
        return None
    f, cc = [], []
    for x, z in corners:
        v = info(x, z)
        if v is None or v[2] != ci[2]:
            v = (ci[0], info(x, z)[1] if info(x, z) else ci[1], ci[2])
        f.append(v[0])
        cc.append(max(v[1], v[0] + 350))
    kind = ci[2]
    mat = {"tube": "obsidian", "stream": "lava", "rim": "obsidian", "floe": "ice", "island": "basalt",
           "magma": "lava"}[kind]
    if kind == "magma" and N3.value(cx / 500, cz / 500) > 0.3:
        mat = "lavacrust"
    return {"floor": tuple(f), "ceil": tuple(cc), "mat": mat,
            "wall": "icewall" if kind == "floe" else "tuberock", "ceilmat": "tuberock", "kind": kind}


def area3_glow(p):
    g = max(0.0, 1 - (p[1] - MAGMA_Y) / 2200)
    return (0.75 * g, 0.32 * g, 0.08 * g)


A3 = L.area(3, Light(sun=(0.0, -1.0, 0.2), ambient=0.38, sun_color=(1.0, 0.5, 0.2),
                     ambient_color=(0.75, 0.55, 0.55), glow=area3_glow))
G3 = Grid(A3, X3, Z3, C3, N3C, N3C)
G3.fill(cave3_cell)
G3.build()

for x, z, top in STONES3:
    A3.prism(x, z, 150, MAGMA_Y - 200, top, 6, side="basalt", cap="basalt", yaw=x % 30)
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


def wing(part, angle):
    for sx in (-1, 1):
        a = math.radians(angle)  # same pose both sides; x is mirrored below
        def P(lx, ly, lz):
            # pivot at the shoulder; rotate about the body's long axis
            x = lx * math.cos(a) - ly * math.sin(a)
            y = lx * math.sin(a) + ly * math.cos(a)
            return (sx * 40 + sx * x, 82 + y, lz)
        pts = [P(0, 0, 30), P(0, 0, -40), P(95, -8, -55), P(110, -12, -20), P(70, -4, 20)]
        lundi.flat(part, pts, BLACK, (0, 1, 0))
        lundi.flat(part, [P(95, -8, -55), P(110, -12, -20), P(128, -14, -40)], FROST, (0, 1, 0))


wing("wings0", -82)   # folded / tucked for a dive
wing("wings1", 52)    # up
wing("wings2", 8)     # level
wing("wings3", -38)   # down

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
           "scoria": (150, 90, 80), "silica": (190, 230, 225), "snowpack": (220, 230, 240), "darkness": (0, 0, 0)}
    for (i, k), c in G1.cells.items():
        col = pal.get(c["mat"], (255, 0, 255))
        h = sum(c["floor"]) / 4
        if h < 0 and c["mat"] == "seabed":
            col = (30, 70 + int(h / 10), 120)
        d.rectangle((i * 6, k * 6, i * 6 + 5, k * 6 + 5), fill=col)
    for model, (x, y, z), *_ in A1.objects:
        px, pz = (x - X0) / CELL * 6, (z - Z0) / CELL * 6
        colr = (255, 220, 0) if "STAR" in model else (255, 0, 255) if "LUNDI" in model else (0, 255, 255) if "GEYSER" in model else None
        if colr:
            d.ellipse((px - 4, pz - 4, px + 4, pz + 4), fill=colr, outline=(0, 0, 0))
    img.save(sys.argv[2])
