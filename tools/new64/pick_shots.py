#!/usr/bin/env python3
"""Pick the last captured frame for each test pose and build a contact sheet.

Usage: pick_shots.py <shot dir> "x,y,z,yaw;..." [labels;...]
Reads <shot dir>/raw/index.txt written by the NEW64_SHOT_DIR frame dumper.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

out = Path(sys.argv[1])
poses = [tuple(float(v) for v in p.split(",")[:3]) for p in sys.argv[2].split(";") if p]
labels = sys.argv[3].split(";") if len(sys.argv) > 3 else [f"pose {i + 1}" for i in range(len(poses))]
rows = []
for line in (out / "raw/index.txt").read_text().splitlines():
    f, lvl, x, y, z = line.split()
    rows.append((f, float(x), float(y), float(z)))
picked = []
for i, (px, py, pz) in enumerate(poses):
    near = [r for r in rows if math.hypot(r[1] - px, r[3] - pz) < 700]
    if not near:
        print(f"pose {i + 1}: no frames")
        continue
    # Prefer frames where Mario has landed (lowest y seen near the pose)
    fr = near[-1][0]
    src = out / f"raw/frame_{fr}.png"
    if src.exists():
        picked.append((labels[i] if i < len(labels) else f"pose {i + 1}", Image.open(src)))
cols = 3
w, h = 480, 360
sheet = Image.new("RGB", (cols * w, ((len(picked) + cols - 1) // cols) * (h + 20)), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for i, (label, img) in enumerate(picked):
    x, y = (i % cols) * w, (i // cols) * (h + 20)
    sheet.paste(img.convert("RGB").resize((w, h)), (x, y + 20))
    d.text((x + 6, y + 4), label, fill=(255, 255, 255))
sheet.save(out / "sheet.png")
print(f"{len(picked)} shots -> {out / 'sheet.png'}")
