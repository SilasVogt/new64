#!/usr/bin/env python3
"""Generate Sky Garden Isles (levels/sgi) from the layout below.

Writes the level's display lists, collision, macro objects, script objects
and a small layout header, plus an optional top-down map preview.

Usage: gen_level.py <repo root> [map.png]

Everything that has to agree (island heights, where coins and stars sit,
the King Bob-omb star position) comes from the one LAYOUT here, so moving an
island moves everything on it.
"""
import math
import random
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Materials: ROM textures (all 32x32 RGBA16) + a base tint for vertex colours
# --------------------------------------------------------------------------
MATERIALS = {
    "grass":     ("outside_09004000", (255, 255, 255)),
    "grassedge": ("grass_09005000",   (255, 255, 255)),
    "dirt":      ("grass_09004800",   (200, 190, 180)),
    "rock":      ("grass_09003000",   (190, 180, 175)),
    "wood":      ("grass_09006800",   (255, 240, 220)),
    "brick":     ("grass_09007000",   (255, 250, 240)),
    "flag":      ("grass_09008000",   (255, 255, 255)),
    "stone":     ("mountain_09000000", (255, 255, 250)),
    "starstone": ("outside_09003000", (255, 245, 210)),
    "flowers":   ("grass_09002000",   (255, 255, 255)),
}
TEX_WORLD = 256.0          # world units per texture repeat
SUN = (0.35, 0.85, 0.40)   # light direction (normalised below)
AMBIENT = 0.62

# Surface types (include/surface_terrains.h)
SURFACE_DEFAULT = "SURFACE_DEFAULT"
SURFACE_DEATH_PLANE = "SURFACE_DEATH_PLANE"


def norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


SUN = norm(SUN)


class Level:
    def __init__(self):
        self.tris = {m: [] for m in MATERIALS}   # material -> [(verts, uvs, cols)]
        self.col = {}                             # surface -> [(a, b, c)]
        self.macros = []
        self.objects = []
        self.footprints = []                      # for the preview map

    # -- geometry ---------------------------------------------------------
    def tri(self, mat, a, b, c, uv, want=None, shade=1.0, surface=SURFACE_DEFAULT):
        """Add a triangle. `want` is the outward direction; winding is fixed to
        face it (SM64 uses the right-hand normal for both culling and collision)."""
        n = norm(cross(sub(b, a), sub(c, b)))
        if want is not None and dot(n, want) < 0:
            b, c = c, b
            uv = (uv[0], uv[2], uv[1])
            n = (-n[0], -n[1], -n[2])
        light = AMBIENT + (1.0 - AMBIENT) * max(0.0, dot(n, SUN))
        light *= shade
        # Textures repeat, so shift each triangle by whole repeats to keep the
        # fixed-point coordinates small.
        ou, ov = math.floor(min(u for u, _ in uv)), math.floor(min(v for _, v in uv))
        uv = tuple((u - ou, v - ov) for u, v in uv)
        tint = MATERIALS[mat][1]
        col = tuple(max(0, min(255, int(t * light))) for t in tint)
        if mat is not None:
            self.tris[mat].append(((a, b, c), uv, (col, col, col)))
        if surface is not None:
            self.col.setdefault(surface, []).append((a, b, c))

    def quad(self, mat, a, b, c, d, uvs, want, shade=1.0, surface=SURFACE_DEFAULT):
        self.tri(mat, a, b, c, (uvs[0], uvs[1], uvs[2]), want, shade, surface)
        self.tri(mat, a, c, d, (uvs[0], uvs[2], uvs[3]), want, shade, surface)

    def island(self, cx, cy, cz, radius, depth, seed, top="grass", side="grassedge",
               under="rock", segments=28, wobble=0.12, band=160):
        rng = random.Random(seed)
        phases = [rng.uniform(0, math.tau) for _ in range(3)]
        ring = []
        for i in range(segments):
            a = math.tau * i / segments
            r = radius * (1 + wobble * (0.6 * math.sin(2 * a + phases[0])
                                        + 0.3 * math.sin(3 * a + phases[1])
                                        + 0.2 * math.sin(5 * a + phases[2])))
            ring.append((a, r))
        pts = [(cx + math.sin(a) * r, cy, cz + math.cos(a) * r) for a, r in ring]
        centre = (cx, cy, cz)
        up = (0, 1, 0)
        # Top: fan, planar UVs relative to the centre
        def puv(p):
            return ((p[0] - cx) / TEX_WORLD, (p[2] - cz) / TEX_WORLD)
        for i in range(segments):
            p, q = pts[i], pts[(i + 1) % segments]
            self.tri(top, centre, p, q, (puv(centre), puv(p), puv(q)), up)
        # Side band (walls) with the grass edge at the top of the texture
        perim = 0.0
        for i in range(segments):
            p, q = pts[i], pts[(i + 1) % segments]
            seg = math.dist((p[0], p[2]), (q[0], q[2]))
            u0, u1 = perim / TEX_WORLD, (perim + seg) / TEX_WORLD
            perim += seg
            pb, qb = (p[0], cy - band, p[2]), (q[0], cy - band, q[2])
            mid = ((p[0] + q[0]) / 2 - cx, 0, (p[2] + q[2]) / 2 - cz)
            v1 = band / TEX_WORLD * 1.6
            self.quad(side, p, q, qb, pb, ((u0, 0), (u1, 0), (u1, v1), (u0, v1)), mid, 0.95)
        # Underside: shrinking rings down to a point (visual only)
        levels = 4
        prev = [(x, cy - band, z) for x, _, z in pts]
        for k in range(1, levels + 1):
            f = k / levels
            shrink = 1 - f ** 0.8 * 0.92
            y = cy - band - depth * f
            jitter = [rng.uniform(0.85, 1.1) for _ in range(segments)]
            cur = [(cx + (x - cx) * shrink * jitter[i], y, cz + (z - cz) * shrink * jitter[i])
                   for i, (x, _, z) in enumerate(pts)]
            if k == levels:
                cur = [(cx, cy - band - depth * 1.15, cz)] * segments
            vt0 = (k - 1) * depth / levels / TEX_WORLD
            vt1 = k * depth / levels / TEX_WORLD
            perim = 0.0
            for i in range(segments):
                j = (i + 1) % segments
                seg = math.dist((prev[i][0], prev[i][2]), (prev[j][0], prev[j][2]))
                u0, u1 = perim / TEX_WORLD, (perim + seg) / TEX_WORLD
                perim += seg
                out = (prev[i][0] - cx, -0.6, prev[i][2] - cz)
                shade = 0.85 - 0.35 * f
                if k == levels:
                    self.tri(under, prev[i], prev[j], cur[i], ((u0, vt0), (u1, vt0), ((u0 + u1) / 2, vt1)),
                             out, shade, None)
                else:
                    self.quad(under, prev[i], prev[j], cur[j], cur[i],
                              ((u0, vt0), (u1, vt0), (u1, vt1), (u0, vt1)), out, shade, None)
            prev = cur
        self.footprints.append(("island", [(p[0], p[2]) for p in pts], top))
        return pts

    def obox(self, centre, size, yaw_deg, top="wood", side="wood", bottom="dirt",
             collide_bottom=True):
        """Oriented box. centre = (x, top_y, z); size = (width_x, height, depth_z)
        before rotation by yaw (degrees, SM64 convention: 0 faces +z)."""
        cx, ty, cz = centre
        w, h, d = size
        yaw = math.radians(yaw_deg)
        cs, sn = math.cos(yaw), math.sin(yaw)

        def rot(lx, lz):
            return (cx + lx * cs + lz * sn, cz - lx * sn + lz * cs)

        corners = [rot(-w / 2, -d / 2), rot(w / 2, -d / 2), rot(w / 2, d / 2), rot(-w / 2, d / 2)]
        T = [(x, ty, z) for x, z in corners]
        B = [(x, ty - h, z) for x, z in corners]
        tuv = [(-w / 2 / TEX_WORLD, -d / 2 / TEX_WORLD), (w / 2 / TEX_WORLD, -d / 2 / TEX_WORLD),
               (w / 2 / TEX_WORLD, d / 2 / TEX_WORLD), (-w / 2 / TEX_WORLD, d / 2 / TEX_WORLD)]
        self.quad(top, T[0], T[1], T[2], T[3], tuv, (0, 1, 0))
        self.quad(bottom, B[0], B[1], B[2], B[3], tuv, (0, -1, 0), 0.6,
                  SURFACE_DEFAULT if collide_bottom else None)
        lens = [w, d, w, d]
        for i in range(4):
            j = (i + 1) % 4
            mid = ((T[i][0] + T[j][0]) / 2 - cx, 0, (T[i][2] + T[j][2]) / 2 - cz)
            L = lens[i] / TEX_WORLD
            v = h / TEX_WORLD
            self.quad(side, T[i], T[j], B[j], B[i], ((0, 0), (L, 0), (L, v), (0, v)), mid, 0.9)
        self.footprints.append(("box", corners, top))

    def beam(self, p0, p1, width, thick, top="wood", side="wood"):
        """Sloped plank strip from p0 to p1 (both top-surface points)."""
        dx, dz = p1[0] - p0[0], p1[2] - p0[2]
        L = math.hypot(dx, dz)
        px, pz = -dz / L * width / 2, dx / L * width / 2
        T = [(p0[0] + px, p0[1], p0[2] + pz), (p0[0] - px, p0[1], p0[2] - pz),
             (p1[0] - px, p1[1], p1[2] - pz), (p1[0] + px, p1[1], p1[2] + pz)]
        B = [(x, y - thick, z) for x, y, z in T]
        lu = math.dist(p0, p1) / TEX_WORLD
        wu = width / TEX_WORLD
        self.quad(top, T[0], T[1], T[2], T[3], ((0, 0), (wu, 0), (wu, lu), (0, lu)), (0, 1, 0))
        self.quad("dirt", B[0], B[1], B[2], B[3], ((0, 0), (wu, 0), (wu, lu), (0, lu)), (0, -1, 0), 0.6, None)
        for i, j in ((0, 3), (2, 1)):
            mid = (((T[i][0] + T[j][0]) / 2) - (p0[0] + p1[0]) / 2, 0,
                   ((T[i][2] + T[j][2]) / 2) - (p0[2] + p1[2]) / 2)
            v = thick / TEX_WORLD
            self.quad(side, T[i], T[j], B[j], B[i], ((0, 0), (lu, 0), (lu, v), (0, v)), mid, 0.85)
        self.footprints.append(("box", [(x, z) for x, _, z in T], top))

    def cylinder(self, cx, cz, r, y0, y1, segments=20, side="brick", cap="starstone", cap_r=None):
        pts = [(cx + math.sin(math.tau * i / segments) * r, cz + math.cos(math.tau * i / segments) * r)
               for i in range(segments)]
        circ = math.tau * r
        for i in range(segments):
            j = (i + 1) % segments
            a, b = pts[i], pts[j]
            u0, u1 = circ * i / segments / TEX_WORLD, circ * (i + 1) / segments / TEX_WORLD
            v = (y1 - y0) / TEX_WORLD
            mid = ((a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz)
            self.quad(side, (a[0], y1, a[1]), (b[0], y1, b[1]), (b[0], y0, b[1]), (a[0], y0, a[1]),
                      ((u0, 0), (u1, 0), (u1, v), (u0, v)), mid, 0.95)
        if cap:
            cr = cap_r or r
            cpts = [(cx + math.sin(math.tau * i / segments) * cr, cz + math.cos(math.tau * i / segments) * cr)
                    for i in range(segments)]
            c = (cx, y1, cz)
            for i in range(segments):
                j = (i + 1) % segments
                a, b = (cpts[i][0], y1, cpts[i][1]), (cpts[j][0], y1, cpts[j][1])
                uv = lambda p: ((p[0] - cx) / 280.0, (p[2] - cz) / 280.0)
                self.tri(cap, c, a, b, (uv(c), uv(a), uv(b)), (0, 1, 0))
            if cap_r and cap_r > r:
                # Overhanging cap: underside ring + rim wall
                rim = 60
                for i in range(segments):
                    j = (i + 1) % segments
                    a, b = cpts[i], cpts[j]
                    mid = ((a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz)
                    self.quad(side, (a[0], y1, a[1]), (b[0], y1, b[1]), (b[0], y1 - rim, b[1]),
                              (a[0], y1 - rim, a[1]), ((0, 0), (1, 0), (1, 0.25), (0, 0.25)), mid, 0.9)
                    ia, ib = pts[i], pts[j]
                    self.quad(side, (a[0], y1 - rim, a[1]), (b[0], y1 - rim, b[1]), (ib[0], y1 - rim, ib[1]),
                              (ia[0], y1 - rim, ia[1]), ((0, 0), (1, 0), (1, 1), (0, 1)), (0, -1, 0), 0.6)
        self.footprints.append(("cyl", [(p[0], p[1]) for p in pts], side))

    def decal(self, cx, cy, cz, r, mat="flowers", segments=12, seed=0):
        """Flat patch 2 units above a floor (visual only)."""
        rng = random.Random(seed)
        pts = []
        for i in range(segments):
            a = math.tau * i / segments
            rr = r * rng.uniform(0.75, 1.0)
            pts.append((cx + math.sin(a) * rr, cy + 2, cz + math.cos(a) * rr))
        c = (cx, cy + 2, cz)
        uv = lambda p: ((p[0] - cx) / TEX_WORLD * 2, (p[2] - cz) / TEX_WORLD * 2)
        for i in range(segments):
            j = (i + 1) % segments
            self.tri(mat, c, pts[i], pts[j], (uv(c), uv(pts[i]), uv(pts[j])), (0, 1, 0), 1.0, None)

    def death_plane(self, y, extent):
        a, b, c, d = (-extent, y, -extent), (extent, y, -extent), (extent, y, extent), (-extent, y, extent)
        self.col.setdefault(SURFACE_DEATH_PLANE, [])
        for t in ((a, c, b), (a, d, c)):
            n = norm(cross(sub(t[1], t[0]), sub(t[2], t[1])))
            if n[1] < 0:
                t = (t[0], t[2], t[1])
            self.col[SURFACE_DEATH_PLANE].append(t)

    # -- objects ----------------------------------------------------------
    def macro(self, preset, pos, yaw=0, param=None):
        self.macros.append((preset, yaw, pos, param))

    def obj(self, model, pos, beh, param=0, yaw=0, acts=None):
        self.objects.append((model, pos, yaw, param, beh, acts))


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
def build():
    L = Level()
    lay = {}

    # Islands: name -> (x, top y, z, radius, underside depth)
    S = (0, 0, 4800, 1400, 1500)       # spawn isle
    C = (0, 200, 0, 1900, 2200)        # central garden with the tower
    K = (5400, 1100, -700, 1500, 1800)  # King Bob-omb's arena
    N = (-300, 800, -5600, 900, 1100)  # north isle past the bridge
    Lonely = (3200, 2000, -5200, 700, 900)  # only reachable by cannon (lob, ~75 deg pitch)
    W = [(-3100, 400, 900, 520, 700), (-4300, 600, -300, 480, 650), (-5000, 800, -1800, 480, 650),
         (-4100, 1000, -3200, 520, 700), (-2600, 1150, -3700, 600, 800)]

    L.island(*S, seed=1)
    L.island(*C, seed=2, segments=32)
    L.island(*K, seed=3, top="flag", side="stone", under="rock", wobble=0.05)
    L.island(*N, seed=4)
    L.island(*Lonely, seed=5, segments=18)
    for i, w in enumerate(W):
        L.island(*w, seed=10 + i, segments=18)

    # Flower patches
    for i, (x, y, z, r) in enumerate([(-500, 0, 5300, 260), (700, 0, 4500, 220), (-1100, 200, 600, 300),
                                       (900, 200, 1100, 260), (500, 800, -5300, 240), (-3100, 400, 900, 200)]):
        L.decal(x, y, z, r, seed=40 + i)

    # Spawn -> central: sloped plank bridge
    L.beam((0, 0, 3480), (0, 200, 1780), 380, 50)

    # Sky tower in the middle of the central isle, spiral steps around it
    tower_top = 3000
    L.cylinder(0, 0, 380, 120, tower_top, side="brick", cap="starstone", cap_r=560)
    steps = []
    for i in range(18):
        a = math.radians(i * 26)
        x, z = math.sin(a) * 650, math.cos(a) * 650
        y = 330 + i * 150
        L.obox((x, y, z), (240, 80, 300), math.degrees(a) + 90, top="wood", side="wood")
        steps.append((x, y, z))
    lay["tower_top"] = tower_top

    # Central -> arena: rising stone blocks
    blocks = [(2300, 380, -60), (2720, 560, -160), (3140, 740, -260), (3560, 920, -380)]
    for b in blocks:
        L.obox(b, (320, 120, 320), 0, top="stone", side="stone", bottom="stone")

    # Central -> west chain of islets, with a stepping block in each gap
    wblocks = [(-2250, 300, 450), (-3700, 500, 300), (-4650, 700, -1050), (-4550, 900, -2500), (-3350, 1080, -3450)]
    for b in wblocks:
        L.obox(b, (280, 100, 280), 30, top="wood", side="wood")
    # Pillar on W3 holding a red coin
    w3 = W[2]
    L.cylinder(w3[0] - 150, w3[2] - 150, 110, w3[1] - 20, w3[1] + 300, segments=10, side="stone", cap="stone")

    # Central -> north: two bridge spans with a wide platform between
    plat = (-150, 400, -3050)
    L.beam((0, 200, -1820), (-110, 400, -2700), 300, 50)
    L.obox(plat, (700, 80, 700), 0, top="wood", side="wood")
    L.beam((-170, 400, -3400), (-290, 800, -4730), 260, 50)
    # Pillars on the north isle
    L.cylinder(-700, -5900, 140, N[1] - 20, N[1] + 420, segments=10, side="stone", cap="stone")
    L.cylinder(200, -6100, 120, N[1] - 20, N[1] + 220, segments=10, side="stone", cap="stone")
    # A pillar on the spawn isle to hop on
    L.cylinder(-900, 5500, 130, -20, 260, segments=10, side="stone", cap="stone")

    # Cannon pedestal on the central isle: a hollow stone frame (240 wide pit,
    # like vanilla cannon holes) with two steps up from the south.
    cx, cz, rim = 900, -1250, 600
    h = rim - C[1]
    for (ox, oz, w, d) in ((0, -220, 640, 200), (0, 220, 640, 200), (220, 0, 200, 240), (-220, 0, 200, 240)):
        L.obox((cx + ox, rim, cz + oz), (w, h, d), 0, top="stone", side="stone", bottom="stone", collide_bottom=False)
    L.obox((cx, 470, cz + 440), (300, 270, 240), 0, top="stone", side="stone", bottom="stone", collide_bottom=False)
    L.obox((cx, 340, cz + 680), (300, 140, 240), 0, top="stone", side="stone", bottom="stone", collide_bottom=False)
    lay["cannon"] = (cx, rim, cz)

    L.death_plane(-3000, 14000)

    # ---------------- objects ----------------
    # Mario entry (warp node 0x0A)
    L.obj("MODEL_NONE", (0, 600, 5700), "bhvSpinAirborneWarp", 0x000A0000, yaw=180)
    lay["spawn"] = (0, 0, 5700)

    # Trees
    for x, y, z in [(-700, 0, 4300), (850, 0, 4100), (-1300, 200, -800), (1250, 200, 900),
                    (-600, 200, 1500), (300, 800, -5900), (-3250, 400, 1100), (1500, 200, -900),
                    (Lonely[0] - 250, Lonely[1], Lonely[2] + 200)]:  # cannon shots can grab this one
        L.obj("MODEL_BOB_BUBBLY_TREE", (x, y, z), "bhvTree")

    # Star 1 (index 0): King Bob-omb, act 1 only. His star appears above the arena.
    L.obj("MODEL_KING_BOBOMB", (K[0], K[1], K[2]), "bhvKingBobomb", 0x00000000, yaw=-90, acts="ACT_1")
    lay["king_star"] = (K[0], K[1] + 500, K[2])

    # Star 2 (index 1): top of the tower
    L.obj("MODEL_STAR", (0, tower_top + 250, 0), "bhvStar", 0x01000000)

    # Star 3 (index 2): eight red coins, star appears on the last islet
    w5 = W[4]
    L.obj("MODEL_NONE", (w5[0], w5[1] + 250, w5[2]), "bhvHiddenRedCoinStar", 0x02000000)
    reds = [(W[0][0] + 200, W[0][1], W[0][2] - 100), (wblocks[1][0], wblocks[1][1], wblocks[1][2]),
            (W[1][0], W[1][1], W[1][2]), (w3[0] - 150, w3[1] + 300, w3[2] - 150),
            (wblocks[3][0], wblocks[3][1], wblocks[3][2]), (W[3][0] + 250, W[3][1], W[3][2]),
            (W[3][0] - 250, W[3][1], W[3][2] + 150), (wblocks[0][0], wblocks[0][1], wblocks[0][2])]
    for x, y, z in reds:
        L.macro("macro_red_coin", (x, y, z))

    # Star 4 (index 3): the lonely isle, only reachable by cannon
    L.obj("MODEL_STAR", (Lonely[0], Lonely[1] + 200, Lonely[2]), "bhvStar", 0x03000000)
    L.macro("macro_1up", (Lonely[0] + 200, Lonely[1], Lonely[2] + 150))
    # The cannon's yaw comes from the 2nd behParam byte (<< 8), and its swivel
    # animation ends 90 deg past that: 0x2A (59 deg) + 90 = 149 deg, pointing at
    # the lonely isle. The player can turn +-90 deg from there.
    L.macro("macro_cannon_closed", lay["cannon"], param=0x2A)
    L.macro("macro_bobomb_buddy_opens_cannon", (550, 200, -1050))

    # Star 5 (index 4): five secrets, star appears in the central garden
    L.obj("MODEL_NONE", (-900, 600, 1000), "bhvHiddenStar", 0x04000000)
    secrets = [(0, 260, -560), (0, 60, 6000), (-700, N[1] + 440, -5900), (6750, K[1] + 60, K[2]),
               (steps[11][0], steps[11][1] + 60, steps[11][2])]
    for p in secrets:
        L.macro("macro_hidden_star_trigger", p)

    # Star 6 (index 5): exclamation box above the bridge platform. 400 up is
    # out of reach of a single jump (~220) but not a double jump (~340).
    L.obj("MODEL_EXCLAMATION_BOX", (plat[0], plat[1] + 400, plat[2]), "bhvExclamationBox", 0x000E0000)

    # Enemies
    for x, y, z in [(-400, 0, 4000), (500, 0, 5100), (-900, 200, -300), (700, 200, 400),
                    (-200, 200, 1300), (-500, 800, -5500), (100, 800, -5200), (w5[0] + 250, w5[1], w5[2])]:
        L.macro("macro_goomba", (x, y, z))

    # Coins (100+ needed for the 100-coin star; total is printed below)
    L.macro("macro_coin_ring_horizontal", (0, 0, 4250))
    L.macro("macro_coin_line_horizontal", (-650, 0, 5000), yaw=0)
    L.macro("macro_coin_line_horizontal", (0, 100, 2650), yaw=0)
    L.macro("macro_coin_ring_horizontal", (-1050, 200, 250))
    L.macro("macro_coin_ring_horizontal", (1050, 200, -350))
    L.macro("macro_coin_line_horizontal", (1300, 200, 300), yaw=90)
    L.macro("macro_coin_line_horizontal", (-300, 200, -1300), yaw=90)
    for x, y, z in steps:
        L.macro("macro_yellow_coin", (x, y + 40, z))
    for x, y, z in blocks:
        L.macro("macro_yellow_coin", (x, y + 40, z))
    L.macro("macro_coin_ring_horizontal", (K[0] + 600, K[1], K[2] + 500))
    L.macro("macro_coin_line_horizontal", (K[0] - 300, K[1], K[2] - 700), yaw=90)
    L.macro("macro_coin_line_horizontal", (W[1][0], W[1][1], W[1][2] - 50), yaw=90)
    L.macro("macro_coin_line_horizontal", (w5[0], w5[1], w5[2] + 200), yaw=90)
    for i in (2, 4):
        x, y, z = wblocks[i]
        L.macro("macro_yellow_coin", (x, y + 40, z))
    L.macro("macro_coin_line_horizontal", (-50, 300, -2250), yaw=0)
    L.macro("macro_coin_line_horizontal", (-230, 600, -4050), yaw=0)
    L.macro("macro_coin_ring_horizontal", (-300, 800, -5800))
    coin_values = {"macro_yellow_coin": 1, "macro_coin_line_horizontal": 5, "macro_coin_ring_horizontal": 8,
                   "macro_red_coin": 2, "macro_goomba": 1}
    lay["coins"] = sum(coin_values.get(m[0], 0) for m in L.macros)
    return L, lay


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def fixed_uv(u, v):
    s, t = int(round(u * 32 * 32)), int(round(v * 32 * 32))
    assert -32768 <= s <= 32767 and -32768 <= t <= 32767, (u, v)
    return s, t


def write_model(L, path):
    out = ["// Generated by tools/new64/gen_level.py. Do not edit.", ""]
    for mat, (tex, _) in MATERIALS.items():
        out.append(f"extern const u8 {tex}[];")
    out.append("")
    dl_names = []
    for mat, tris in L.tris.items():
        if not tris:
            continue
        tex = MATERIALS[mat][0]
        out.append(f"static const Vtx sgi_vtx_{mat}[] = {{")
        for verts, uvs, cols in tris:
            for p, uv, c in zip(verts, uvs, cols):
                s, t = fixed_uv(*uv)
                x, y, z = (int(round(k)) for k in p)
                out.append(f"    {{{{{{{x}, {y}, {z}}}, 0, {{{s}, {t}}}, {{{c[0]}, {c[1]}, {c[2]}, 0xFF}}}}}},")
        out.append("};")
        out.append("")
        out.append(f"static const Gfx sgi_dl_{mat}[] = {{")
        out.append("    gsDPPipeSync(),")
        out.append("    gsDPSetCombineMode(G_CC_MODULATERGB, G_CC_MODULATERGB),")
        out.append("    gsSPClearGeometryMode(G_LIGHTING),")
        out.append(f"    gsDPLoadTextureBlock({tex}, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, "
                   "G_TX_WRAP | G_TX_NOMIRROR, G_TX_WRAP | G_TX_NOMIRROR, 5, 5, G_TX_NOLOD, G_TX_NOLOD),")
        out.append("    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),")
        n = len(tris) * 3
        for base in range(0, n, 15):
            cnt = min(15, n - base)
            out.append(f"    gsSPVertex(sgi_vtx_{mat} + {base}, {cnt}, 0),")
            k = 0
            while k + 6 <= cnt:
                out.append(f"    gsSP2Triangles({k}, {k + 1}, {k + 2}, 0x0, {k + 3}, {k + 4}, {k + 5}, 0x0),")
                k += 6
            if k + 3 <= cnt:
                out.append(f"    gsSP1Triangle({k}, {k + 1}, {k + 2}, 0x0),")
        out.append("    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_OFF),")
        out.append("    gsDPPipeSync(),")
        out.append("    gsSPSetGeometryMode(G_LIGHTING),")
        out.append("    gsDPSetCombineMode(G_CC_SHADE, G_CC_SHADE),")
        out.append("    gsSPEndDisplayList(),")
        out.append("};")
        out.append("")
        dl_names.append(f"sgi_dl_{mat}")
    out.append("const Gfx sgi_dl_area_1_opaque[] = {")
    for n in dl_names:
        out.append(f"    gsSPDisplayList({n}),")
    out.append("    gsSPEndDisplayList(),")
    out.append("};")
    path.write_text("\n".join(out) + "\n")
    return sum(len(t) for t in L.tris.values())


def write_collision(L, path):
    verts, index = [], {}

    def vid(p):
        key = tuple(int(round(k)) for k in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(key)
        return index[key]

    groups = []
    for surf, tris in L.col.items():
        idx = []
        for a, b, c in tris:
            ia, ib, ic = vid(a), vid(b), vid(c)
            if len({ia, ib, ic}) == 3:
                idx.append((ia, ib, ic))
        groups.append((surf, idx))
    out = ["// Generated by tools/new64/gen_level.py. Do not edit.",
           "const Collision sgi_area_1_collision[] = {", "    COL_INIT(),", f"    COL_VERTEX_INIT({len(verts)}),"]
    out += [f"    COL_VERTEX({x}, {y}, {z})," for x, y, z in verts]
    for surf, idx in groups:
        out.append(f"    COL_TRI_INIT({surf}, {len(idx)}),")
        out += [f"    COL_TRI({a}, {b}, {c})," for a, b, c in idx]
    out += ["    COL_TRI_STOP(),", "    COL_END(),", "};", ""]
    path.write_text("\n".join(out))
    return len(verts), sum(len(i) for _, i in groups)


def write_macros(L, path):
    out = ["// Generated by tools/new64/gen_level.py. Do not edit.", "const MacroObject sgi_area_1_macro_objs[] = {"]
    for preset, yaw, (x, y, z), param in L.macros:
        x, y, z = (int(round(k)) for k in (x, y, z))
        if param is None:
            out.append(f"    MACRO_OBJECT(/*preset*/ {preset}, /*yaw*/ {yaw}, /*pos*/ {x}, {y}, {z}),")
        else:
            out.append(f"    MACRO_OBJECT_WITH_BEH_PARAM(/*preset*/ {preset}, /*yaw*/ {yaw}, /*pos*/ {x}, {y}, {z}, /*behParam*/ 0x{param:02X}),")
    out += ["    MACRO_OBJECT_END(),", "};", ""]
    path.write_text("\n".join(out))


def write_objects(L, path):
    out = ["// Generated by tools/new64/gen_level.py. Do not edit.",
           "static const LevelScript sgi_area_1_objects[] = {"]
    for model, (x, y, z), yaw, param, beh, acts in L.objects:
        x, y, z = (int(round(k)) for k in (x, y, z))
        if acts:
            out.append(f"    OBJECT_WITH_ACTS(/*model*/ {model}, /*pos*/ {x}, {y}, {z}, /*angle*/ 0, {yaw}, 0, "
                       f"/*behParam*/ 0x{param:08X}, /*beh*/ {beh}, /*acts*/ {acts}),")
        else:
            out.append(f"    OBJECT(/*model*/ {model}, /*pos*/ {x}, {y}, {z}, /*angle*/ 0, {yaw}, 0, "
                       f"/*behParam*/ 0x{param:08X}, /*beh*/ {beh}),")
    out += ["    RETURN(),", "};", ""]
    path.write_text("\n".join(out))


def write_layout(lay, path):
    k = lay["king_star"]
    path.write_text("\n".join([
        "// Generated by tools/new64/gen_level.py. Do not edit.",
        "#ifndef SGI_LAYOUT_H",
        "#define SGI_LAYOUT_H",
        "",
        "// Where King Bob-omb's star flies to in Sky Garden Isles.",
        f"#define SGI_KING_STAR_POS {{ {k[0]:.1f}f, {k[1]:.1f}f, {k[2]:.1f}f }}",
        "",
        "#endif",
        ""]))


def write_map(L, lay, path):
    from PIL import Image, ImageDraw
    size, extent = 900, 8000
    img = Image.new("RGB", (size, size), (150, 200, 240))
    d = ImageDraw.Draw(img)
    colours = {"grass": (90, 170, 70), "flag": (190, 180, 160), "wood": (170, 120, 70),
               "stone": (140, 150, 140), "brick": (230, 220, 190)}

    def P(x, z):
        return ((x + extent) / (2 * extent) * size, (z + extent) / (2 * extent) * size)
    for kind, pts, mat in L.footprints:
        d.polygon([P(*p) for p in pts], fill=colours.get(mat, (120, 120, 120)), outline=(40, 40, 40))
    for model, (x, y, z), *_ in L.objects:
        if "STAR" in model or "Star" in model or "KING" in model or "EXCLAMATION" in model:
            cx, cz = P(x, z)
            d.ellipse((cx - 6, cz - 6, cx + 6, cz + 6), fill=(255, 220, 0), outline=(0, 0, 0))
    for preset, _, (x, y, z), _ in L.macros:
        cx, cz = P(x, z)
        col = (230, 30, 30) if "red" in preset else (255, 255, 120) if "coin" in preset else (120, 60, 20)
        d.ellipse((cx - 2, cz - 2, cx + 2, cz + 2), fill=col)
    d.text((10, 10), f"Sky Garden Isles - top view (north up), coins: {lay['coins']}", fill=(0, 0, 0))
    img.save(path)


def main():
    root = Path(sys.argv[1])
    L, lay = build()
    area = root / "levels/sgi/areas/1"
    area.mkdir(parents=True, exist_ok=True)
    ntri = write_model(L, area / "model.inc.c")
    nv, nct = write_collision(L, area / "collision.inc.c")
    write_macros(L, area / "macro.inc.c")
    write_objects(L, area / "objects.inc.c")
    write_layout(lay, root / "levels/sgi/layout.h")
    if len(sys.argv) > 2:
        write_map(L, lay, sys.argv[2])
    print(f"visual tris {ntri}, collision verts {nv} tris {nct}, coins {lay['coins']}")


if __name__ == "__main__":
    main()
