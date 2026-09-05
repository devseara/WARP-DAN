"""Audit native held registration and export original pixels for hilt inspection.

Requires Pillow (available in the bundled workspace Python). This verifies ACT
relationships, not anatomical hilt locations or live rendering acceptance.
"""
from __future__ import annotations
import argparse
import configparser
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont, ImageOps
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.grf_reader import GrfFile
from dual_weapon_formats.spr_reader import Spr

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "data/sprite/인간족/"
NAMES = {
    "body": PREFIX + "몸통/여/어쌔신크로스_여",
    "13412": PREFIX + "어세신/어세신_여_13412",
    "1238": PREFIX + "어세신/어세신_여_1238",
}


def audit(client, out):
    out.mkdir(parents=True, exist_ok=True)
    ini = configparser.ConfigParser()
    ini.read(client / "DATA.INI")
    paths = [client / value for _, value in sorted(ini["Data"].items(), key=lambda x: int(x[0]))]
    archives, sources = {}, {}

    def read(key):
        loose = client / Path(key)
        raw, source = (loose.read_bytes(), loose) if loose.is_file() else (None, None)
        if raw is None:
            for path in paths:
                if path not in archives:
                    archives[path] = GrfFile(path)
                raw = archives[path].read(key.lower())
                if raw is not None:
                    source = path
                    break
        if raw is None:
            raise FileNotFoundError(key)
        sources[key] = {"source": str(source), "sha256": hashlib.sha256(raw).hexdigest()}
        return raw

    assets = {name: (parse_act(read(key + ".act")), Spr(read(key + ".spr")))
              for name, key in NAMES.items()}
    for archive in archives.values():
        archive.close()

    def cell(name, direction, frame):
        act, spr = assets[name]
        layer = act["actions"][32 + direction].frames[frame].layers[0]
        rgba, width, height = spr.get_rgba(layer.sprite_index, layer.sprite_type)
        return layer, Image.frombytes("RGBA", (width, height), rgba)

    records = []
    for direction in range(8):
        for frame in range(6):
            row = {"direction": direction, "frame": frame, "weapons": {}}
            layers = []
            for name in ("13412", "1238"):
                layer, image = cell(name, direction, frame)
                assert layer.rotation == 0 and layer.scale_x == layer.scale_y == 1
                layers.append(layer)
                width, height = image.size
                loaded = [layer.x - (width + 1) // 2, layer.y - (height + 1) // 2]
                # Keep this explicitly conditional until the consumer contract
                # is proven: an extent of dimension+1 shifts even dimensions .5.
                center_plus_one = [loaded[0] + (width + 1) / 2,
                                   loaded[1] + (height + 1) / 2]
                row["weapons"][name] = {
                    "image": [layer.sprite_type, layer.sprite_index],
                    "dimensions": [width, height], "raw_ACT_xy": [layer.x, layer.y],
                    "loaded_ACT_xy": loaded, "mirror": layer.mirror,
                    "angle": layer.rotation, "scale": [layer.scale_x, layer.scale_y],
                    "center_if_native_extent_is_dimension_plus_one": center_plus_one,
                    "RGBA_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                }
            assert layers[0].mirror == layers[1].mirror
            row["raw_dagger_minus_sword"] = [layers[1].x - layers[0].x, layers[1].y - layers[0].y]
            a, b = [row["weapons"][name]["center_if_native_extent_is_dimension_plus_one"]
                    for name in ("13412", "1238")]
            row["delta_if_native_extent_is_dimension_plus_one"] = [b[0] - a[0], b[1] - a[1]]
            records.append(row)
    for direction in range(8):
        group = [r for r in records if r["direction"] == direction]
        assert all(r["raw_dagger_minus_sword"] == group[0]["raw_dagger_minus_sword"] for r in group)
        for name in ("13412", "1238"):
            assert all(r["weapons"][name]["RGBA_sha256"] == group[0]["weapons"][name]["RGBA_sha256"] for r in group)

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    sheet = Image.new("RGB", (1250, 700), (235, 235, 235))
    pen = ImageDraw.Draw(sheet)
    for k, (name, direction) in enumerate((("13412", 0), ("13412", 2), ("1238", 0), ("1238", 2))):
        layer, image = cell(name, direction, 0)
        width, height = image.size
        x, y, scale = 35 + k % 2 * 625, 45 + k // 2 * 350, 5
        pen.text((x, y - 30), f"{name} sprite{layer.sprite_index}, {width}x{height}, top-left pixel coordinates", font=font, fill="black")
        large = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
        sheet.paste(large, (x, y), large)
        for p in range(0, width + 1, 5):
            pen.line((x + p * scale, y, x + p * scale, y + height * scale), fill=(200, 200, 200))
            pen.text((x + p * scale, y + height * scale + 5), str(p), font=font, fill="black")
        for p in range(0, height + 1, 5):
            pen.line((x, y + p * scale, x + width * scale, y + p * scale), fill=(200, 200, 200))
            pen.text((x + width * scale + 5, y + p * scale), str(p), font=font, fill="black")
        image.save(out / f"{name}-sprite{layer.sprite_index}.png")
    sheet.save(out / "held-sources-grid.png")

    for group in range(2):
        sheet = Image.new("RGB", (1440, 760), (235, 235, 235))
        pen = ImageDraw.Draw(sheet)
        for column in range(4):
            direction = group * 4 + column
            for row, name in enumerate(("13412", "1238")):
                board = Image.new("RGBA", (120, 110), (220, 230, 235, 255))
                for key in ("body", name):
                    layer, image = cell(key, direction, 0)
                    if layer.mirror:
                        image = ImageOps.mirror(image)
                    width, height = image.size
                    board.alpha_composite(image, (60 + layer.x - (width + 1) // 2,
                                                   95 + layer.y - (height + 1) // 2))
                sheet.paste(board.resize((360, 330), Image.Resampling.NEAREST), (column * 360, row * 380 + 30))
                pen.text((column * 360 + 8, row * 380 + 5),
                         f"D{direction}/F0 {name}: ACT preview; no native depth", font=font, fill="black")
        sheet.save(out / f"body-held-directions-{group * 4}-{group * 4 + 3}.png")

    result = {
        "schema": "dual_weapon_held_grip_audit/v1", "sources": sources,
        "cells_checked": len(records), "all_held_frame_deltas_constant_per_direction": True,
        "same_image_per_weapon_within_each_held_direction": True,
        "anatomical_hilt_point_verified": False, "live_acceptance": False,
        "finding": "ACT registration and mirror/angle/scale consistency are verified; no unique hilt pixel is encoded by these assets.",
        "limits": ["Offline body previews draw weapon above body and omit native projection/depth/pixel expansion.",
                   "Matching ACT center deltas does not independently prove matching physical hilt locations.",
                   "Dimension+1 center columns are conditional calculations, not a native consumer verification."],
        "records": records,
    }
    (out / "grip-landmark-audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("sources", "records")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "Outputs/dual_weapon_grip_audit")
    args = parser.parse_args()
    audit(args.client, args.out)
