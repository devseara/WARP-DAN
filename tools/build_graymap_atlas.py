"""Generate the deterministic runtime GrayMap tile atlas (no map replacements)."""
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def build():
    width, height, tile, cell = 512, 256, 64, 32
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            variant = (y // tile) * 8 + x // tile
            mask, grid = variant & 15, bool(variant & 16)
            tx, ty = x % tile, y % tile
            bit = (ty // cell) * 2 + tx // cell
            blocked = bool(mask & (1 << bit))
            # Uniform tactical floor and continuous dark obstacles. No
            # per-cell checker motif or bright squares inside blocked regions.
            base = (43, 50, 58) if blocked else (160, 171, 181)
            delta = 2 if blocked and (tx + ty) % 8 < 2 else 0
            rgb = tuple(c + delta for c in base)
            if grid and not blocked and (tx % cell == 0 or ty % cell == 0):
                rgb = (193, 204, 214)
            pixels.extend((rgb[2], rgb[1], rgb[0], 255))
    # Top-origin BGRA; native texture loader handles the file orientation.
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 0x28)
    path = ROOT / 'Assets/GrayMap/cells.tga'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + pixels)
    print(f'{path}: {width}x{height}, 32 material variants')


if __name__ == '__main__':
    build()
