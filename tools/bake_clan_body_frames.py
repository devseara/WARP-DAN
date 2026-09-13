"""Bake approved Angel layers into one body layer, plus native UI copies.

World pixels retain the original 4x resolution and ACT scale 0.25. File X/Y
stay logical: the client loader already divides them by layer scale before
subtracting half the source image size. The geometry scales that loaded value
back. This two-stage conversion was verified against all 456 live male frames.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import sys
import struct
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "Outputs/angel-clan-swordman-20260908"
sys.path.insert(0, str(ART / "production-v02"))
from sprite_formats import read_spr, write_spr, read_act, write_act, Layer

# Native head coordinates are the reference; collar geometry is corrected in the artwork.
HEAD_ATTACHMENT_Y = {"male": 0, "female": 0}

def fitted_anchors(anchors, sex):
    result = []
    for anchor in anchors:
        raw = bytearray(anchor)
        struct.pack_into("<i", raw, 8, struct.unpack_from("<i", raw, 8)[0] + HEAD_ATTACHMENT_Y[sex])
        result.append(bytes(raw))
    return result



def composite(images, frame):
    layers = []
    for layer in frame.layers:
        assert layer.kind == 1 and layer.sx == layer.sy == 0.25
        assert layer.color == (255, 255, 255, 255)
        if layer.index < 0:
            continue
        image = images[layer.index]
        if layer.mirror:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if layer.angle:
            image = image.rotate(-layer.angle, Image.Resampling.NEAREST, expand=True)
        x, y = 4 * layer.x - image.width // 2, 4 * layer.y - image.height // 2
        layers.append((image, x, y))
    assert layers
    # Multiples of eight give even logical dimensions and integer ACT centers.
    left = math.floor(min(x for _, x, _ in layers) / 8) * 8
    top = math.floor(min(y for _, _, y in layers) / 8) * 8
    right = math.ceil(max(x + im.width for im, x, _ in layers) / 8) * 8
    bottom = math.ceil(max(y + im.height for im, _, y in layers) / 8) * 8
    result = Image.new("RGBA", (right - left, bottom - top))
    for image, x, y in layers:
        result.alpha_composite(image, (x - left, y - top))
    return result, (left + right) // 8, (top + bottom) // 8


def build():
    out = ROOT / "Outputs/clan-body-skins/native-collar-v8"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    contact = Image.new("RGB", (1280, 460), "#283545")
    pen = ImageDraw.Draw(contact)
    for row, (sex, korean, source) in enumerate([
        ("male", "남", ART / "production-v06-corrections/sprites/male/angel_swordman_male_DETAIL_V06"),
        ("female", "여", ART / "female-wing-repair-v08/sprites/angel_swordman_female_WING_V08"),
    ]):
        images = read_spr(source.with_suffix(".spr").read_bytes())
        from rebuild_angel_pose_collars import rebuild_pose_collars
        from spr_reader import Spr
        native = Spr((ART / f"production-v02/source/{sex}-body.spr").read_bytes())
        native_act = read_act((ART / f"production-v02/source/{sex}-body.act").read_bytes())
        head_base = ROOT / "Outputs/clan-body-skins/original-job-audit"
        heads = Spr((head_base / f"{sex}-head.spr").read_bytes())
        head_act = read_act((head_base / f"{sex}-head.act").read_bytes())
        images, masks, edits = rebuild_pose_collars(images, native, native_act, heads, head_act, sex=sex)
        (out / f"pose-collar-verification-{sex}.json").write_text(json.dumps(edits, indent=2), encoding="utf8")
        original = read_act(source.with_suffix(".act").read_bytes())
        world = copy.deepcopy(original)
        preview = copy.deepcopy(original)
        merged, small, seen = [], [], {}
        checked = 0
        for ai, frames in enumerate(original.actions):
            for fi, frame in enumerate(frames):
                image, x, y = composite(images, frame)
                key = (image.size, hashlib.sha256(image.tobytes()).hexdigest())
                if key not in seen:
                    seen[key] = len(merged)
                    merged.append(image)
                    small.append(image.convert("RGBa").resize((image.width // 4, image.height // 4), Image.Resampling.LANCZOS).convert("RGBA"))
                index = seen[key]
                # ACT load converts center positions to unscaled top-left values.
                # Do not apply inverse scale again in the exported file.
                world.actions[ai][fi].layers = [Layer(x, y, index, sx=0.25, sy=0.25)]
                preview.actions[ai][fi].layers = [Layer(x, y, index)]
                world.actions[ai][fi].anchors = fitted_anchors(frame.anchors, sex)
                preview.actions[ai][fi].anchors = fitted_anchors(frame.anchors, sex)
                # Independent full-canvas comparison verifies all source pixels
                # survive merging at the same coordinates, including rotations.
                before = Image.new("RGBA", (1600, 1600))
                for layer in frame.layers:
                    if layer.index < 0:
                        continue
                    part = images[layer.index]
                    if layer.mirror:
                        part = part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    if layer.angle:
                        part = part.rotate(-layer.angle, Image.Resampling.NEAREST, expand=True)
                    before.alpha_composite(part, (800 + layer.x * 4 - part.width // 2, 800 + layer.y * 4 - part.height // 2))
                after = Image.new("RGBA", before.size)
                wl = world.actions[ai][fi].layers[0]
                ul = preview.actions[ai][fi].layers[0]
                assert wl.x == ul.x and wl.y == ul.y
                assert image.width * wl.sx == small[index].width
                assert image.height * wl.sy == small[index].height
                # Verified live loader + geometry sequence. Checking geometry
                # alone previously introduced the rejected v3 double scaling.
                loaded_x = int(wl.x / wl.sx) - image.width // 2
                loaded_y = int(wl.y / wl.sy) - image.height // 2
                native_left, native_top = loaded_x * wl.sx, loaded_y * wl.sy
                assert native_left + image.width * wl.sx / 2 == ul.x
                assert native_top + image.height * wl.sy / 2 == ul.y
                after.alpha_composite(image, (800 + round(native_left * 4),
                                              800 + round(native_top * 4)))
                assert before.tobytes() == after.tobytes(), (sex, ai, fi)
                checked += 1
                if ai < 8 and fi == 0:
                    tile = Image.new("RGBA", (160, 210))
                    pic = small[index].resize((image.width // 2, image.height // 2), Image.Resampling.NEAREST)
                    tile.alpha_composite(pic, (80 + x * 2 - pic.width // 2, 185 + y * 2 - pic.height // 2))
                    contact.paste(tile, (ai * 160, row * 230 + 20), tile)
                    pen.text((ai * 160 + 8, row * 230 + 5), f"{sex} / {ai}", fill="white")
        assert checked == 456 and len(world.actions) == 104
        for variant, act, sprites in [("world", world, merged), ("preview", preview, small)]:
            folder = out / f"data/sprite/clan_skins/1/{'preview/' if variant == 'preview' else ''}인간족/몸통/{korean}"
            folder.mkdir(parents=True, exist_ok=True)
            stem = folder / f"검사_{korean}"
            raw_act, raw_spr = write_act(act), write_spr(sprites)
            stem.with_suffix(".act").write_bytes(raw_act)
            stem.with_suffix(".spr").write_bytes(raw_spr)
            decoded = read_act(raw_act)
            assert decoded.tail == original.tail
            for old_frames, new_frames in zip(original.actions, decoded.actions):
                assert len(old_frames) == len(new_frames)
                for old, new in zip(old_frames, new_frames):
                    assert (old.ranges, old.sound) == (new.ranges, new.sound)
                    assert new.anchors == fitted_anchors(old.anchors, sex)
                    assert len(new.layers) == 1 and new.layers[0].index >= 0
            restored = read_spr(raw_spr)
            assert all(a.size == b.size and a.tobytes() == b.tobytes() for a, b in zip(sprites, restored))
            rows.append({"sex": sex, "variant": variant, "images": len(sprites), "actions": 104, "frames": checked,
                         "spr_sha256": hashlib.sha256(raw_spr).hexdigest(), "act_sha256": hashlib.sha256(raw_act).hexdigest(),
                         "scale": act.actions[0][0].layers[0].sx, "head_attachment_delta_y": HEAD_ATTACHMENT_Y[sex], "native_offset_scale_verified": True, "max_image": max(im.width * im.height for im in sprites)})
        print(sex, checked, "frames: exact 4x composite and metadata checks passed", flush=True)
    contact.save(out / "idle-directions-body-wings.png")
    (out / "verification.json").write_text(json.dumps(rows, indent=2), encoding="utf8")
    print(out)
    return out


if __name__ == "__main__":
    build()
