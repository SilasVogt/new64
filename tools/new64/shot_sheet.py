#!/usr/bin/env python3
"""Contact sheets for tools/new64/testmods/shots.lua runs.

  shot_sheet.py <run dir>                     -> <run dir>/sheet.png
  shot_sheet.py --compare <before> <after> <out prefix>
                                              -> <out prefix>-1.png, -2.png, ...

A run dir is what testrun.sh writes (game.log and raw/ with index.txt). The
mod logs its plan ("new64-shot: plan <n> <x> <z> <label>"); each shot is the
last frame of the run of frames where Mario stands at that shot's spot.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H, BAR = 480, 360, 22


def load_run(run):
    run = Path(run)
    plan = []
    for line in (run / "game.log").read_text(errors="ignore").splitlines():
        m = re.search(r"new64-shot: plan (\d+) (-?\d+) (-?\d+) (.*)$", line)
        if m:
            plan.append((int(m.group(2)), int(m.group(3)), m.group(4).strip()))
    rows = []
    for line in (run / "raw/index.txt").read_text().splitlines():
        fr, _lvl, x, _y, z = line.split()
        rows.append((fr, float(x), float(z)))
    shots, pos = [], 0
    for x, z, label in plan:
        frames = []
        while pos < len(rows) and not (abs(rows[pos][1] - x) < 3 and abs(rows[pos][2] - z) < 3):
            pos += 1
        while pos < len(rows) and abs(rows[pos][1] - x) < 3 and abs(rows[pos][2] - z) < 3:
            frames.append(rows[pos][0])
            pos += 1
        # The camera is locked from the first frame, but the last few may
        # already be fading out for a warp: start 60% in and skip black ones.
        img = None
        for fr in reversed(frames[: max(1, len(frames) * 3 // 5)]):
            f = run / f"raw/frame_{fr}.png"
            if f.exists():
                im = Image.open(f).convert("RGB")
                if max(hi for _, hi in im.getextrema()) > 40:
                    img = im.resize((W, H))
                    break
        shots.append((label, img))
    return shots


def blank(text):
    img = Image.new("RGB", (W, H), (40, 0, 0))
    ImageDraw.Draw(img).text((10, H // 2), text, fill=(255, 255, 255))
    return img


def single(run):
    shots = load_run(run)
    cols = 3
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W, rows * (H + BAR)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for n, (label, img) in enumerate(shots):
        x, y = (n % cols) * W, (n // cols) * (H + BAR)
        sheet.paste(img or blank("no frame"), (x, y + BAR))
        d.text((x + 6, y + 5), f"{n + 1}. {label}", fill=(255, 255, 255))
    out = Path(run) / "sheet.png"
    sheet.save(out)
    print(f"{len(shots)} shots -> {out}")


def compare(before, after, prefix, per_page=6):
    a, b = load_run(before), load_run(after)
    n = max(len(a), len(b))
    pages = []
    for p in range(0, n, per_page):
        rows = range(p, min(n, p + per_page))
        sheet = Image.new("RGB", (2 * W + 10, len(rows) * (H + BAR) + BAR), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        d.text((6, 5), "before", fill=(255, 200, 120))
        d.text((W + 16, 5), "after", fill=(140, 255, 160))
        for r, k in enumerate(rows):
            y = BAR + r * (H + BAR)
            label = (b[k][0] if k < len(b) else a[k][0])
            d.text((6, y + 5), f"{k + 1}. {label}", fill=(255, 255, 255))
            sheet.paste((a[k][1] if k < len(a) else None) or blank("no frame"), (0, y + BAR))
            sheet.paste((b[k][1] if k < len(b) else None) or blank("no frame"), (W + 10, y + BAR))
        out = Path(f"{prefix}-{len(pages) + 1}.png")
        sheet.save(out)
        pages.append(out)
    for out in pages:
        print(out)


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        compare(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        single(sys.argv[1])
