"""Shared level generator library for new64 courses.

A Level has several Areas. Each Area collects triangles per material (opaque
or translucent), collision triangles per surface type, water boxes, macro
objects and script objects, and writes them as decomp-style C.

Geometry is built from a few primitives:
  - Grid: a 2.5D terrain/cave grid. Every cell has its own floor (and optional
    ceiling) corner heights, so terraces, cliffs, lava pools and cave walls all
    come out of one routine.
  - boxes, prisms/cylinders, cones, sheets, decals.

Textures are referenced by their ROM symbol names (bin/*.c); sizes are read
from the ROM_ASSET_LOAD_TEXTURE lines so non-square textures work.
"""
import math
import random
import re
from pathlib import Path

SURFACE_DEFAULT = "SURFACE_DEFAULT"


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(v):
    m = math.sqrt(dot(v, v)) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


class Noise:
    """Small value-noise with fbm, deterministic per seed."""

    def __init__(self, seed):
        rng = random.Random(seed)
        self.p = list(range(256))
        rng.shuffle(self.p)
        self.p += self.p
        self.v = [rng.uniform(-1, 1) for _ in range(256)]

    def _h(self, x, z):
        return self.v[self.p[(self.p[x & 255] + z) & 255]]

    def value(self, x, z):
        x0, z0 = math.floor(x), math.floor(z)
        fx, fz = x - x0, z - z0
        sx, sz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
        a = lerp(self._h(x0, z0), self._h(x0 + 1, z0), sx)
        b = lerp(self._h(x0, z0 + 1), self._h(x0 + 1, z0 + 1), sx)
        return lerp(a, b, sz)

    def fbm(self, x, z, octaves=4):
        s, amp, f = 0.0, 1.0, 1.0
        for _ in range(octaves):
            s += amp * self.value(x * f, z * f)
            amp *= 0.5
            f *= 2.0
        return s


def load_texture_sizes(root):
    """symbol -> (fmt, width, height) from ROM_ASSET_LOAD_TEXTURE lines."""
    pat = re.compile(r'ROM_ASSET_LOAD_TEXTURE\((\w+),\s*"([^"]+)",\s*0x[0-9a-fA-F]+,\s*\d+,\s*0x[0-9a-fA-F]+,\s*(\d+)\)')
    out = {}
    for f in list(Path(root, "bin").glob("*.c")) + list(Path(root, "levels").glob("*/texture.inc.c")):
        for m in pat.finditer(f.read_text(errors="ignore")):
            name, fname, size = m.group(1), m.group(2), int(m.group(3))
            parts = fname.split(".")
            fmt = parts[-3] if len(parts) >= 3 else "rgba16"
            bpp = {"rgba16": 2, "ia16": 2, "ia8": 1, "i8": 1, "ia4": 0.5, "i4": 0.5, "rgba32": 4}.get(fmt, 2)
            px = int(size / bpp)
            w = 32 if px >= 32 * 32 or px % 32 == 0 else int(math.sqrt(px))
            if px == 64 * 64:
                w = 64
            out[name] = (fmt, w, px // w)
    return out


class Material:
    def __init__(self, name, tex, tint=(255, 255, 255), alpha=255, surface=SURFACE_DEFAULT,
                 world=256.0, glow=1.0, unlit=False, clamp=False):
        self.name, self.tex, self.tint, self.alpha = name, tex, tint, alpha
        self.surface = surface      # default collision type for this material
        self.world = world          # world units per texture repeat
        self.glow = glow            # how much area glow (lava light) affects it
        self.unlit = unlit          # ignore sun shading (lava, emissive)
        self.clamp = clamp

    @property
    def translucent(self):
        return self.alpha < 255


class Light:
    """Directional sun + ambient + optional point-ish glow function."""

    def __init__(self, sun=(0.35, 0.85, 0.4), ambient=0.55, sun_color=(1.0, 1.0, 1.0),
                 ambient_color=(1.0, 1.0, 1.0), glow=None):
        self.sun = norm(sun)
        self.ambient = ambient
        self.sun_color = sun_color
        self.ambient_color = ambient_color
        self.glow = glow            # fn(p) -> (r, g, b) additive, 0..1 scale

    def shade(self, p, n, mat, extra=1.0):
        if mat.unlit:
            c = [1.0, 1.0, 1.0]
        else:
            d = max(0.0, dot(n, self.sun))
            c = [self.ambient * self.ambient_color[i] + (1 - self.ambient) * d * self.sun_color[i] for i in range(3)]
        c = [v * extra for v in c]
        if self.glow and mat.glow > 0:
            g = self.glow(p)
            c = [c[i] + g[i] * mat.glow for i in range(3)]
        return tuple(max(0, min(255, int(mat.tint[i] * c[i]))) for i in range(3))


class Area:
    def __init__(self, level, index, light):
        self.level, self.index, self.light = level, index, light
        self.tris = {}          # material name -> [(verts, uvs, colors)]
        self.col = {}           # surface -> [(a, b, c)]
        self.water = []         # (x1, z1, x2, z2, y)
        self.macros = []
        self.objects = []
        self.footprints = []

    # -- low level --------------------------------------------------------
    def tri(self, mat, a, b, c, uv, want=None, shade=1.0, surface="mat", normals=None, alpha=None):
        """Add a triangle; winding is flipped to face `want` if given.
        surface: "mat" = material default, None = no collision, or a type."""
        m = self.level.mats[mat] if mat else None
        n = norm(cross(sub(b, a), sub(c, b)))
        if want is not None and dot(n, want) < 0:
            b, c = c, b
            uv = (uv[0], uv[2], uv[1])
            if normals:
                normals = (normals[0], normals[2], normals[1])
            n = (-n[0], -n[1], -n[2])
        if m is not None:
            ou = math.floor(min(u for u, _ in uv))
            ov = math.floor(min(v for _, v in uv))
            uv = tuple((u - ou, v - ov) for u, v in uv)
            ns = normals or (n, n, n)
            cols = tuple(self.light.shade(p, nn, m, shade) for p, nn in zip((a, b, c), ns))
            al = m.alpha if alpha is None else alpha
            if isinstance(al, (int, float)):
                al = (al, al, al)
            cols = tuple(col + (int(alp),) for col, alp in zip(cols, al))
            self.tris.setdefault(mat, []).append(((a, b, c), uv, cols))
        if surface == "mat":
            surface = m.surface if m else None
        if surface is not None:
            self.col.setdefault(surface, []).append((a, b, c))

    def quad(self, mat, a, b, c, d, uvs, want=None, shade=1.0, surface="mat", alpha=None):
        al = alpha if alpha is None or isinstance(alpha, (int, float)) else None
        if alpha is not None and not isinstance(alpha, (int, float)):
            self.tri(mat, a, b, c, (uvs[0], uvs[1], uvs[2]), want, shade, surface, alpha=(alpha[0], alpha[1], alpha[2]))
            self.tri(mat, a, c, d, (uvs[0], uvs[2], uvs[3]), want, shade, surface, alpha=(alpha[0], alpha[2], alpha[3]))
            return
        self.tri(mat, a, b, c, (uvs[0], uvs[1], uvs[2]), want, shade, surface, alpha=al)
        self.tri(mat, a, c, d, (uvs[0], uvs[2], uvs[3]), want, shade, surface, alpha=al)

    def wall_quad(self, mat, p, q, y0p, y1p, y0q, y1q, want, shade=0.9, surface="mat", u0=0.0):
        """Vertical-ish quad from edge p->q, bottom y0 to top y1 at each end."""
        w = self.level.mats[mat].world
        L = math.dist((p[0], p[1]), (q[0], q[1])) / w
        a, b = (p[0], y1p, p[1]), (q[0], y1q, q[1])
        c, d = (q[0], y0q, q[1]), (p[0], y0p, p[1])
        uvs = ((u0, -y1p / w), (u0 + L, -y1q / w), (u0 + L, -y0q / w), (u0, -y0p / w))
        self.quad(mat, a, b, c, d, uvs, want, shade, surface)

    # -- primitives -------------------------------------------------------
    def box(self, centre, size, yaw=0.0, top="stone", side=None, bottom=None, collide=True, shade=1.0):
        """centre = (x, top_y, z); size = (w, h, d) before yaw (deg, 0 = +z)."""
        side = side or top
        bottom = bottom or side
        cx, ty, cz = centre
        w, h, d = size
        r = math.radians(yaw)
        cs, sn = math.cos(r), math.sin(r)

        def rot(lx, lz):
            return (cx + lx * cs + lz * sn, cz - lx * sn + lz * cs)
        cs4 = [rot(-w / 2, -d / 2), rot(w / 2, -d / 2), rot(w / 2, d / 2), rot(-w / 2, d / 2)]
        T = [(x, ty, z) for x, z in cs4]
        B = [(x, ty - h, z) for x, z in cs4]
        tw = self.level.mats[top].world
        tuv = [(-w / 2 / tw, -d / 2 / tw), (w / 2 / tw, -d / 2 / tw), (w / 2 / tw, d / 2 / tw), (-w / 2 / tw, d / 2 / tw)]
        surf = "mat" if collide else None
        self.quad(top, T[0], T[1], T[2], T[3], tuv, (0, 1, 0), shade, surf)
        self.quad(bottom, B[0], B[1], B[2], B[3], tuv, (0, -1, 0), 0.6 * shade, surf)
        lens = [w, d, w, d]
        for i in range(4):
            j = (i + 1) % 4
            mid = ((T[i][0] + T[j][0]) / 2 - cx, 0, (T[i][2] + T[j][2]) / 2 - cz)
            self.wall_quad(side, cs4[i], cs4[j], ty - h, ty, ty - h, ty, mid, 0.9 * shade, surf)
        self.footprints.append(([c for c in cs4], top))

    def prism(self, cx, cz, r, y0, y1, sides=6, side="stone", cap="stone", yaw=0.0, collide=True,
              cap_r=None, bottom_cap=False, shade=1.0):
        """Upright n-gon prism (basalt column, tower, pillar)."""
        a0 = math.radians(yaw)
        pts = [(cx + math.sin(a0 + math.tau * i / sides) * r, cz + math.cos(a0 + math.tau * i / sides) * r)
               for i in range(sides)]
        surf = "mat" if collide else None
        u = 0.0
        w = self.level.mats[side].world
        for i in range(sides):
            j = (i + 1) % sides
            mid = ((pts[i][0] + pts[j][0]) / 2 - cx, 0, (pts[i][1] + pts[j][1]) / 2 - cz)
            self.wall_quad(side, pts[i], pts[j], y0, y1, y0, y1, mid, 0.92 * shade, surf, u)
            u += math.dist(pts[i], pts[j]) / w
        if cap:
            cr = cap_r or r
            cp = [(cx + math.sin(a0 + math.tau * i / sides) * cr, cz + math.cos(a0 + math.tau * i / sides) * cr)
                  for i in range(sides)]
            cw = self.level.mats[cap].world
            c = (cx, y1, cz)
            for i in range(sides):
                j = (i + 1) % sides
                a, b = (cp[i][0], y1, cp[i][1]), (cp[j][0], y1, cp[j][1])
                uv = lambda p: ((p[0] - cx) / cw, (p[2] - cz) / cw)
                self.tri(cap, c, a, b, (uv(c), uv(a), uv(b)), (0, 1, 0), shade, surf)
        if bottom_cap:
            c = (cx, y0, cz)
            for i in range(sides):
                j = (i + 1) % sides
                a, b = (pts[i][0], y0, pts[i][1]), (pts[j][0], y0, pts[j][1])
                self.tri(side, c, a, b, ((0, 0), (1, 0), (0, 1)), (0, -1, 0), 0.5, surf)
        self.footprints.append((pts, side))

    def cone(self, cx, cz, r, y_base, y_tip, sides=8, mat="stone", collide=False, down=False, shade=1.0, jitter=0.0, seed=0):
        """Stalactite (down=True, tip below) / stalagmite / spike."""
        rng = random.Random(seed)
        pts = [(cx + math.sin(math.tau * i / sides) * r * (1 + rng.uniform(-jitter, jitter)),
                cz + math.cos(math.tau * i / sides) * r * (1 + rng.uniform(-jitter, jitter))) for i in range(sides)]
        tip = (cx, y_tip, cz)
        surf = "mat" if collide else None
        w = self.level.mats[mat].world
        for i in range(sides):
            j = (i + 1) % sides
            a, b = (pts[i][0], y_base, pts[i][1]), (pts[j][0], y_base, pts[j][1])
            out = ((pts[i][0] + pts[j][0]) / 2 - cx, 0.3 if not down else -0.3, (pts[i][1] + pts[j][1]) / 2 - cz)
            L = math.dist(pts[i], pts[j]) / w
            h = abs(y_tip - y_base) / w
            self.tri(mat, a, b, tip, ((0, 0), (L, 0), (L / 2, h)), out, shade, surf)

    def sheet(self, pts, mat, uvs, want, alpha=None, surface=None, shade=1.0):
        """Free quad (waterfall, water surface, steam). No collision by default."""
        self.quad(mat, pts[0], pts[1], pts[2], pts[3], uvs, want, shade, surface, alpha)

    def water_plane(self, x1, z1, x2, z2, y, mat="water", box=True, step=2000.0):
        w = self.level.mats[mat].world
        nx = max(1, int(math.ceil((x2 - x1) / step)))
        nz = max(1, int(math.ceil((z2 - z1) / step)))
        for i in range(nx):
            for k in range(nz):
                ax, bx = x1 + (x2 - x1) * i / nx, x1 + (x2 - x1) * (i + 1) / nx
                az, bz = z1 + (z2 - z1) * k / nz, z1 + (z2 - z1) * (k + 1) / nz
                pts = [(ax, y, az), (bx, y, az), (bx, y, bz), (ax, y, bz)]
                uvs = [((p[0] - x1) / w % 64, (p[2] - z1) / w % 64) for p in pts]
                uvs = [(ax - x1, az - z1), (bx - x1, az - z1), (bx - x1, bz - z1), (ax - x1, bz - z1)]
                uvs = [(u / w, v / w) for u, v in uvs]
                self.sheet(pts, mat, uvs, (0, 1, 0))
        if box:
            self.water.append((int(x1), int(z1), int(x2), int(z2), int(y)))

    def decal(self, cx, cy, cz, r, mat, segments=12, seed=0, lift=2.0, alpha=None):
        rng = random.Random(seed)
        pts = []
        for i in range(segments):
            a = math.tau * i / segments
            rr = r * rng.uniform(0.75, 1.0)
            pts.append((cx + math.sin(a) * rr, cy + lift, cz + math.cos(a) * rr))
        c = (cx, cy + lift, cz)
        w = self.level.mats[mat].world
        uv = lambda p: ((p[0] - cx) / w, (p[2] - cz) / w)
        for i in range(segments):
            j = (i + 1) % segments
            self.tri(mat, c, pts[i], pts[j], (uv(c), uv(pts[i]), uv(pts[j])), (0, 1, 0), 1.0, None, alpha=alpha)

    def invisible_wall(self, p, q, y0, y1, want):
        a, b, c, d = (p[0], y1, p[1]), (q[0], y1, q[1]), (q[0], y0, q[1]), (p[0], y0, p[1])
        self.tri(None, a, b, c, ((0, 0),) * 3, want, surface=SURFACE_DEFAULT)
        self.tri(None, a, c, d, ((0, 0),) * 3, want, surface=SURFACE_DEFAULT)

    def death_plane(self, y, extent):
        a, b, c, d = (-extent, y, -extent), (extent, y, -extent), (extent, y, extent), (-extent, y, extent)
        self.tri(None, a, c, b, ((0, 0),) * 3, (0, 1, 0), surface="SURFACE_DEATH_PLANE")
        self.tri(None, a, d, c, ((0, 0),) * 3, (0, 1, 0), surface="SURFACE_DEATH_PLANE")

    # -- objects ----------------------------------------------------------
    def macro(self, preset, pos, yaw=0, param=None):
        self.macros.append((preset, yaw, pos, param))

    def obj(self, model, pos, beh, param=0, yaw=0, acts=None, pitch=0, roll=0):
        self.objects.append((model, pos, (pitch, yaw, roll), param, beh, acts))


class Grid:
    """2.5D grid for terrain and caves.

    cell(i, k) returns None for solid rock, or a dict:
      floor: (y00, y10, y11, y01) corner heights (or a float)
      ceil:  same, or None for open sky
      mat:   floor material; wall: wall material; ceilmat: ceiling material
      surface: optional collision override for the floor
    Corners are (x0,z0), (x1,z0), (x1,z1), (x0,z1).
    """

    def __init__(self, area, x0, z0, cell, nx, nz):
        self.a, self.x0, self.z0, self.cell, self.nx, self.nz = area, x0, z0, cell, nx, nz
        self.cells = {}

    def corner(self, i, k):
        return (self.x0 + i * self.cell, self.z0 + k * self.cell)

    def fill(self, fn):
        for i in range(self.nx):
            for k in range(self.nz):
                c = fn(i, k, *self.corner(i, k), *self.corner(i + 1, k + 1))
                if c is not None:
                    for key in ("floor", "ceil"):
                        v = c.get(key)
                        if isinstance(v, (int, float)):
                            c[key] = (v, v, v, v)
                    self.cells[(i, k)] = c

    def build(self, floor_normals=None, wall_mat_default="rock", skip_floor=None):
        a = self.a
        cs = self.cell
        # Edge index: 0 = -z (k), 1 = +x (i+1), 2 = +z (k+1), 3 = -x (i)
        edges = {0: ((0, 1), (0, -1)), 1: ((1, 2), (1, 0)), 2: ((2, 3), (0, 1)), 3: ((3, 0), (-1, 0))}
        for (i, k), c in self.cells.items():
            P = [self.corner(i, k), self.corner(i + 1, k), self.corner(i + 1, k + 1), self.corner(i, k + 1)]
            f = c["floor"]
            fm = c["mat"]
            w = a.level.mats[fm].world
            fp = [(P[j][0], f[j], P[j][1]) for j in range(4)]
            uv = [(p[0] / w, p[2] / w) for p in fp]
            surf = c.get("surface", "mat")
            ns = None
            if floor_normals:
                ns = [floor_normals(p[0], p[2]) for p in fp]
            if not (skip_floor and skip_floor(c)):
                # Split along the shorter diagonal for nicer slopes
                if abs(f[0] - f[2]) <= abs(f[1] - f[3]):
                    a.tri(fm, fp[0], fp[1], fp[2], (uv[0], uv[1], uv[2]), (0, 1, 0), 1.0, surf,
                          normals=(ns[0], ns[1], ns[2]) if ns else None)
                    a.tri(fm, fp[0], fp[2], fp[3], (uv[0], uv[2], uv[3]), (0, 1, 0), 1.0, surf,
                          normals=(ns[0], ns[2], ns[3]) if ns else None)
                else:
                    a.tri(fm, fp[0], fp[1], fp[3], (uv[0], uv[1], uv[3]), (0, 1, 0), 1.0, surf,
                          normals=(ns[0], ns[1], ns[3]) if ns else None)
                    a.tri(fm, fp[1], fp[2], fp[3], (uv[1], uv[2], uv[3]), (0, 1, 0), 1.0, surf,
                          normals=(ns[1], ns[2], ns[3]) if ns else None)
            ce = c.get("ceil")
            if ce is not None:
                cm = c.get("ceilmat", c.get("wall", wall_mat_default))
                cw = a.level.mats[cm].world
                cp = [(P[j][0], ce[j], P[j][1]) for j in range(4)]
                cuv = [(p[0] / cw, p[2] / cw) for p in cp]
                a.tri(cm, cp[0], cp[1], cp[2], (cuv[0], cuv[1], cuv[2]), (0, -1, 0), 0.75)
                a.tri(cm, cp[0], cp[2], cp[3], (cuv[0], cuv[2], cuv[3]), (0, -1, 0), 0.75)
            wm = c.get("wall", wall_mat_default)
            for e, ((j0, j1), (di, dk)) in edges.items():
                nb = self.cells.get((i + di, k + dk))
                p, q = P[j0], P[j1]
                out = (di, 0, dk)
                if nb is None:
                    # Solid neighbour: wall from floor up to ceiling (or a tall cliff)
                    top0 = ce[j0] if ce is not None else f[j0] + c.get("cliff", 0)
                    top1 = ce[j1] if ce is not None else f[j1] + c.get("cliff", 0)
                    if top0 > f[j0] + 1 or top1 > f[j1] + 1:
                        a.wall_quad(wm, p, q, f[j0], top0, f[j1], top1, (-di, 0, -dk))
                    continue
                # Open neighbour: step/cliff where floors disagree (draw from the higher side)
                nf = nb["floor"]
                # neighbour corner indices on the shared edge
                nmap = {0: (3, 2), 1: (0, 3), 2: (1, 0), 3: (2, 1)}[e]
                hn0, hn1 = nf[nmap[0]], nf[nmap[1]]
                if f[j0] > hn0 + 1 or f[j1] > hn1 + 1:
                    if f[j0] >= hn0 and f[j1] >= hn1:
                        a.wall_quad(wm, p, q, hn0, f[j0], hn1, f[j1], out)
                if ce is not None and nb.get("ceil") is not None:
                    nc = nb["ceil"]
                    hc0, hc1 = nc[nmap[0]], nc[nmap[1]]
                    if ce[j0] < hc0 - 1 or ce[j1] < hc1 - 1:
                        if ce[j0] <= hc0 and ce[j1] <= hc1:
                            a.wall_quad(wm, p, q, ce[j0], hc0, ce[j1], hc1, out)
                elif ce is not None and nb.get("ceil") is None:
                    pass


class Model:
    """A small vertex-coloured object model (no texture) built from ellipsoids
    and boxes; written as display lists for custom objects."""

    def __init__(self, name):
        self.name = name
        self.parts = {}          # part name -> [(verts, colors)]

    def tri(self, part, a, b, c, col, want=None, light=(0.3, 0.8, 0.5), amb=0.55):
        n = norm(cross(sub(b, a), sub(c, b)))
        if want is not None and dot(n, want) < 0:
            b, c = c, b
            n = (-n[0], -n[1], -n[2])
        L = norm(light)
        k = amb + (1 - amb) * max(0.0, dot(n, L))
        cc = tuple(max(0, min(255, int(v * k))) for v in col[:3]) + (col[3] if len(col) > 3 else 255,)
        self.parts.setdefault(part, []).append(((a, b, c), (cc, cc, cc)))

    def ellipsoid(self, part, centre, radii, color_fn, slices=8, stacks=6, rot=None):
        cx, cy, cz = centre
        rx, ry, rz = radii
        pts = {}
        for s in range(stacks + 1):
            th = math.pi * s / stacks
            for l in range(slices):
                ph = math.tau * l / slices
                x, y, z = math.sin(th) * math.sin(ph), math.cos(th), math.sin(th) * math.cos(ph)
                p = (x * rx, y * ry, z * rz)
                if rot:
                    p = rot(p)
                pts[(s, l)] = (cx + p[0], cy + p[1], cz + p[2])
        for s in range(stacks):
            for l in range(slices):
                l2 = (l + 1) % slices
                a, b, c, d = pts[(s, l)], pts[(s, l2)], pts[(s + 1, l2)], pts[(s + 1, l)]
                mid = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2, (a[2] + c[2]) / 2)
                col = color_fn(sub(mid, centre))
                out = sub(mid, centre)
                if s > 0:
                    self.tri(part, a, b, c, col, out)
                if s < stacks - 1:
                    self.tri(part, a, c, d, col, out)

    def flat(self, part, pts, col, want):
        for i in range(1, len(pts) - 1):
            self.tri(part, pts[0], pts[i], pts[i + 1], col, want)
            self.tri(part, pts[0], pts[i + 1], pts[i], col, (-want[0], -want[1], -want[2]))


class Level:
    def __init__(self, short, root):
        self.short = short
        self.root = Path(root)
        self.mats = {}
        self.areas = {}
        self.models = []
        self.tex_sizes = load_texture_sizes(root)

    def mat(self, name, tex, **kw):
        self.mats[name] = Material(name, tex, **kw)

    def area(self, index, light):
        self.areas[index] = Area(self, index, light)
        return self.areas[index]

    # -- writers ----------------------------------------------------------
    def _tex_info(self, tex):
        fmt, w, h = self.tex_sizes.get(tex, ("rgba16", 32, 32))
        return fmt, w, h

    def _material_dl(self, out, prefix, mat, tris):
        m = self.mats[mat]
        fmt, tw, th = self._tex_info(m.tex)
        vname = f"{prefix}_vtx_{mat}"
        out.append(f"static const Vtx {vname}[] = {{")
        for verts, uvs, cols in tris:
            for p, (u, v), c in zip(verts, uvs, cols):
                s, t = int(round(u * tw * 32)), int(round(v * th * 32))
                s = max(-32768, min(32767, s))
                t = max(-32768, min(32767, t))
                x, y, z = (int(round(k)) for k in p)
                out.append(f"    {{{{{{{x}, {y}, {z}}}, 0, {{{s}, {t}}}, {{{c[0]}, {c[1]}, {c[2]}, {c[3]}}}}}}},")
        out.append("};")
        out.append("")
        gfmt = {"rgba16": "G_IM_FMT_RGBA", "ia16": "G_IM_FMT_IA", "ia8": "G_IM_FMT_IA", "i8": "G_IM_FMT_I"}[fmt]
        gsiz = {"rgba16": "G_IM_SIZ_16b", "ia16": "G_IM_SIZ_16b", "ia8": "G_IM_SIZ_8b", "i8": "G_IM_SIZ_8b"}[fmt]
        ms, mt = int(math.log2(tw)), int(math.log2(th))
        wrap = "G_TX_CLAMP" if m.clamp else "G_TX_WRAP | G_TX_NOMIRROR"
        cc = "G_CC_MODULATERGBA, G_CC_MODULATERGBA" if m.translucent else "G_CC_MODULATERGB, G_CC_MODULATERGB"
        out.append(f"static const Gfx {prefix}_dl_{mat}[] = {{")
        out.append("    gsDPPipeSync(),")
        out.append(f"    gsDPSetCombineMode({cc}),")
        out.append("    gsSPClearGeometryMode(G_LIGHTING),")
        out.append(f"    gsDPLoadTextureBlock({m.tex}, {gfmt}, {gsiz}, {tw}, {th}, 0, {wrap}, {wrap}, {ms}, {mt}, G_TX_NOLOD, G_TX_NOLOD),")
        out.append("    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),")
        n = len(tris) * 3
        for base in range(0, n, 15):
            cnt = min(15, n - base)
            out.append(f"    gsSPVertex({vname} + {base}, {cnt}, 0),")
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
        return f"{prefix}_dl_{mat}"

    def write_area(self, area, adir):
        adir.mkdir(parents=True, exist_ok=True)
        p = f"{self.short}_area_{area.index}"
        out = ["// Generated by tools/new64. Do not edit.", ""]
        for mname in sorted({m for m in area.tris}):
            out.append(f"extern const u8 {self.mats[mname].tex}[];")
        out.append("")
        opaque, xlu = [], []
        for mname, tris in area.tris.items():
            if not tris:
                continue
            dl = self._material_dl(out, p, mname, tris)
            (xlu if self.mats[mname].translucent else opaque).append(dl)
        for label, dls in (("opaque", opaque), ("transparent", xlu)):
            out.append(f"const Gfx {p}_dl_{label}[] = {{")
            out += [f"    gsSPDisplayList({d})," for d in dls]
            out.append("    gsSPEndDisplayList(),")
            out.append("};")
            out.append("")
        (adir / "model.inc.c").write_text("\n".join(out))

        # collision
        verts, index = [], {}

        def vid(pt):
            key = tuple(int(round(k)) for k in pt)
            if key not in index:
                index[key] = len(verts)
                verts.append(key)
            return index[key]
        groups = []
        for surf, tris in area.col.items():
            idx = []
            for a, b, c in tris:
                t = (vid(a), vid(b), vid(c))
                if len(set(t)) == 3:
                    idx.append(t)
            groups.append((surf, idx))
        col = [f"const Collision {p}_collision[] = {{", "    COL_INIT(),", f"    COL_VERTEX_INIT({len(verts)}),"]
        col += [f"    COL_VERTEX({x}, {y}, {z})," for x, y, z in verts]
        for surf, idx in groups:
            col.append(f"    COL_TRI_INIT({surf}, {len(idx)}),")
            col += [f"    COL_TRI({a}, {b}, {c})," for a, b, c in idx]
        col.append("    COL_TRI_STOP(),")
        if area.water:
            col.append(f"    COL_WATER_BOX_INIT({len(area.water)}),")
            for i, (x1, z1, x2, z2, y) in enumerate(area.water):
                col.append(f"    COL_WATER_BOX({i}, {x1}, {z1}, {x2}, {z2}, {y}),")
        col += ["    COL_END(),", "};", ""]
        (adir / "collision.inc.c").write_text("// Generated by tools/new64. Do not edit.\n" + "\n".join(col))

        mac = [f"const MacroObject {p}_macro_objs[] = {{"]
        for preset, yaw, (x, y, z), param in area.macros:
            x, y, z = (int(round(k)) for k in (x, y, z))
            if param is None:
                mac.append(f"    MACRO_OBJECT(/*preset*/ {preset}, /*yaw*/ {yaw}, /*pos*/ {x}, {y}, {z}),")
            else:
                mac.append(f"    MACRO_OBJECT_WITH_BEH_PARAM(/*preset*/ {preset}, /*yaw*/ {yaw}, /*pos*/ {x}, {y}, {z}, /*behParam*/ 0x{param:02X}),")
        mac += ["    MACRO_OBJECT_END(),", "};", ""]
        (adir / "macro.inc.c").write_text("// Generated by tools/new64. Do not edit.\n" + "\n".join(mac))

        objs = [f"static const LevelScript {p}_objects[] = {{"]
        for model, (x, y, z), (pi, ya, ro), param, beh, acts in area.objects:
            x, y, z = (int(round(k)) for k in (x, y, z))
            ang = f"{int(pi)}, {int(ya)}, {int(ro)}"
            if acts:
                objs.append(f"    OBJECT_WITH_ACTS(/*model*/ {model}, /*pos*/ {x}, {y}, {z}, /*angle*/ {ang}, "
                            f"/*behParam*/ 0x{param:08X}, /*beh*/ {beh}, /*acts*/ {acts}),")
            else:
                objs.append(f"    OBJECT(/*model*/ {model}, /*pos*/ {x}, {y}, {z}, /*angle*/ {ang}, "
                            f"/*behParam*/ 0x{param:08X}, /*beh*/ {beh}),")
        objs += ["    RETURN(),", "};", ""]
        (adir / "objects.inc.c").write_text("// Generated by tools/new64. Do not edit.\n" + "\n".join(objs))
        nvis = sum(len(t) for t in area.tris.values())
        ncol = sum(len(i) for _, i in groups)
        return nvis, len(verts), ncol

    def write_model(self, model, path, layer_alpha=False):
        """Untextured, vertex-coloured model: one display list per part."""
        out = ["// Generated by tools/new64. Do not edit.", ""]
        for part, tris in model.parts.items():
            vname = f"{self.short}_{model.name}_{part}_vtx"
            out.append(f"static const Vtx {vname}[] = {{")
            for verts, cols in tris:
                for p, c in zip(verts, cols):
                    x, y, z = (int(round(k)) for k in p)
                    out.append(f"    {{{{{{{x}, {y}, {z}}}, 0, {{0, 0}}, {{{c[0]}, {c[1]}, {c[2]}, {c[3]}}}}}}},")
            out.append("};")
            out.append("")
            cc = "G_CC_SHADE, G_CC_SHADE"
            out.append(f"const Gfx {self.short}_{model.name}_{part}_dl[] = {{")
            out.append("    gsDPPipeSync(),")
            out.append(f"    gsDPSetCombineMode({cc}),")
            out.append("    gsSPClearGeometryMode(G_LIGHTING),")
            n = len(tris) * 3
            for base in range(0, n, 15):
                cnt = min(15, n - base)
                out.append(f"    gsSPVertex({vname} + {base}, {cnt}, 0),")
                k = 0
                while k + 6 <= cnt:
                    out.append(f"    gsSP2Triangles({k}, {k + 1}, {k + 2}, 0x0, {k + 3}, {k + 4}, {k + 5}, 0x0),")
                    k += 6
                if k + 3 <= cnt:
                    out.append(f"    gsSP1Triangle({k}, {k + 1}, {k + 2}, 0x0),")
            out.append("    gsDPPipeSync(),")
            out.append("    gsSPSetGeometryMode(G_LIGHTING),")
            out.append("    gsSPEndDisplayList(),")
            out.append("};")
            out.append("")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(out))
