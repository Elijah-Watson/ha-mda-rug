"""Reproduce the integration's simple rug icon using the Python standard library."""

import colorsys
import struct
import zlib
from pathlib import Path


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def main():
    size = 256
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            fringe = (y < 16 or y >= 240) and 20 <= x < 236 and (x - 20) % 24 < 8
            body = 16 <= y < 240
            if fringe:
                pixel = (60, 70, 90, 255)
            elif body:
                edge = x < 10 or x >= 246 or y < 26 or y >= 230
                if edge:
                    rgb = colorsys.hsv_to_rgb((x + y) / 512, 0.8, 1)
                    pixel = (*[int(v * 255) for v in rgb], 255)
                elif abs(x - 128) + abs(y - 128) < 55:
                    pixel = (92, 205, 225, 255)
                else:
                    pixel = (28, 37, 55, 255)
            else:
                pixel = (0, 0, 0, 0)
            rows.extend(pixel)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    target = Path(__file__).resolve().parents[1] / "custom_components/mda_rug/brand/icon.png"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(png)


if __name__ == "__main__":
    main()
