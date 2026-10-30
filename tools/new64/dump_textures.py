#!/usr/bin/env python3
"""Dump ROM textures referenced by ROM_ASSET_LOAD_TEXTURE lines to PNGs.

Usage: dump_textures.py <baserom.us.z64> <out_dir> <source.c>...

Writes one PNG per texture plus contact.png, a labelled sheet. Width is a
guess (square, else 32 or 64 wide) because the C files only carry byte sizes.
"""
import re
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

LINE = re.compile(r'ROM_ASSET_LOAD_TEXTURE\((\w+),\s*"([^"]+)",\s*(0x[0-9a-fA-F]+),\s*(\d+),\s*(0x[0-9a-fA-F]+),\s*(\d+)\)')


def mio0(rom, off):
    if rom[off:off + 4] != b"MIO0":
        return None
    size, comp_off, raw_off = struct.unpack(">III", rom[off + 4:off + 16])
    ctrl, comp, raw = off + 16, off + comp_off, off + raw_off
    out = bytearray()
    bits = left = 0
    while len(out) < size:
        if left == 0:
            bits = struct.unpack(">I", rom[ctrl:ctrl + 4])[0]
            ctrl += 4
            left = 32
        if bits & 0x80000000:
            out.append(rom[raw])
            raw += 1
        else:
            p = struct.unpack(">H", rom[comp:comp + 2])[0]
            comp += 2
            n, back = (p >> 12) + 3, (p & 0xFFF) + 1
            for _ in range(n):
                out.append(out[-back])
        bits = (bits << 1) & 0xFFFFFFFF
        left -= 1
    return bytes(out)


def decode(data, fmt):
    px = []
    if fmt == "rgba16":
        for i in range(0, len(data) - 1, 2):
            v = (data[i] << 8) | data[i + 1]
            px.append(((v >> 11 & 31) * 255 // 31, (v >> 6 & 31) * 255 // 31, (v >> 1 & 31) * 255 // 31, 255 if v & 1 else 0))
    elif fmt == "ia16":
        for i in range(0, len(data) - 1, 2):
            px.append((data[i], data[i], data[i], data[i + 1]))
    elif fmt == "ia8":
        for b in data:
            i, a = (b >> 4) * 17, (b & 15) * 17
            px.append((i, i, i, a))
    elif fmt == "i8":
        px = [(b, b, b, 255) for b in data]
    elif fmt == "ia4":
        for b in data:
            for n in (b >> 4, b & 15):
                i = (n >> 1) * 255 // 7
                px.append((i, i, i, 255 if n & 1 else 0))
    elif fmt == "i4":
        for b in data:
            for n in (b >> 4, b & 15):
                px.append((n * 17,) * 3 + (255,))
    else:
        return None
    n = len(px)
    side = int(n ** 0.5)
    w = side if side * side == n else (32 if n % 32 == 0 and n // 32 >= 32 else 64)
    h = n // w
    img = Image.new("RGBA", (w, h))
    img.putdata(px[:w * h])
    return img


def main():
    rom = Path(sys.argv[1]).read_bytes()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cache, tiles = {}, []
    for src in sys.argv[3:]:
        for m in LINE.finditer(Path(src).read_text()):
            name, fname, phys, _, seg, size = m.groups()
            phys, seg, size = int(phys, 16), int(seg, 16), int(size)
            if phys not in cache:
                cache[phys] = mio0(rom, phys) or rom[phys:]
            data = cache[phys][seg:seg + size]
            fmt = fname.split(".")[-3] if fname.count(".") >= 3 else ""
            img = decode(data, fmt)
            if img is None:
                continue
            img.save(out / f"{name}.png")
            tiles.append((name, fmt, img))
    cols, cell = 8, 140
    sheet = Image.new("RGB", (cols * cell, ((len(tiles) + cols - 1) // cols) * cell), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for i, (name, fmt, img) in enumerate(tiles):
        x, y = (i % cols) * cell, (i // cols) * cell
        t = img.resize((96, int(96 * img.height / img.width)) if img.width >= img.height else (int(96 * img.width / img.height), 96), Image.NEAREST)
        sheet.paste(t, (x + 22, y + 4), t)
        d.text((x + 4, y + 112), name[-14:], fill=(255, 255, 255))
        d.text((x + 4, y + 124), fmt, fill=(180, 180, 180))
    sheet.save(out / "contact.png")
    print(f"{len(tiles)} textures -> {out}")


if __name__ == "__main__":
    main()
