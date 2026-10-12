"""Replace the male idle master's closed neck cap using native Swordman pixels.

Only the collar region of body image 0 changes. The native alpha silhouette and
neck/garment boundaries supply geometry; skin keeps the native color ramp and
clothing gets Angel gold/ivory. No head-coordinate or whole-body offset change.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "Outputs/angel-clan-swordman-20260908"
sys.path.insert(0, str(ROOT / "tools/dual_weapon_formats"))
sys.path.insert(0, str(ART / "production-v02"))
from spr_reader import Spr
from sprite_formats import read_spr

GOLD = ["fff5cd", "f8dfa0", "e6c374", "cf9f50", "ad793a", "87542e", "623c2d", "402a32"]
IVORY = ["fff9e9", "f1e9d8", "dad6c9", "bec1bd", "9ea9af", "7c8c9e", "5d6d85", "3b485f"]


def rebuild(image, native_spr):
    native = native_spr.images[0]
    assert image.size == (native.width * 4, native.height * 4)
    indices = np.frombuffer(native.pixels, np.uint8).reshape(native.height, native.width)
    palette = np.array(native_spr.palette, dtype=np.uint8)
    patch = palette[indices].copy()
    gold = np.array([tuple(bytes.fromhex(c)) + (255,) for c in GOLD], np.uint8)
    ivory = np.array([tuple(bytes.fromhex(c)) + (255,) for c in IVORY], np.uint8)
    yy, xx = np.indices(indices.shape)
    # The neck itself follows the native shape. Its upper shaded mass sits
    # behind the head; the native exposed neck pixels emerge below the chin.
    light = (indices >= 8) & (indices < 16)
    neck = light & (xx >= 16) & (xx <= 25) & (yy <= 6)
    patch[neck] = palette[72 + (indices[neck] - 8)]
    trim = (indices >= 112) & (indices < 120)
    patch[trim] = gold[indices[trim] - 112]
    patch[light & ~neck] = ivory[indices[light & ~neck] - 8]
    patch[(indices >= 40) & (indices < 48)] = (58, 61, 81, 255)
    patch[indices == 2] = (64, 42, 50, 255)
    patch[indices == 0] = 0
    # Bounded replacement removes the complete closed oval and keeps the blue
    # jewel, shoulder engraving and all torso/limb pixels outside this region.
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).polygon([(48, 0), (112, 0), (112, 20), (104, 28),
                                 (100, 36), (92, 40), (60, 40), (52, 28), (48, 20)], fill=255)
    native_patch = Image.fromarray(patch).resize(image.size, Image.Resampling.NEAREST)
    before = np.array(image)
    after = before.copy()
    selection = np.array(mask) != 0
    after[selection] = np.array(native_patch)[selection]
    assert np.array_equal(after[~selection], before[~selection])
    return Image.fromarray(after), mask


def build():
    out = ROOT / "Outputs/clan-body-skins/native-collar-v7"
    out.mkdir(parents=True, exist_ok=True)
    source = ART / "production-v06-corrections/sprites/male/angel_swordman_male_DETAIL_V06.spr"
    images = read_spr(source.read_bytes())
    native = Spr((ART / "production-v02/source/male-body.spr").read_bytes())
    result, mask = rebuild(images[0], native)
    result.save(out / "male-front-body.png")
    mask.save(out / "collar-edit-mask.png")
    report = {"body_image": 0, "affected_action_frames": [[0, 0], [0, 1], [0, 2]],
              "native_neck_source": str((ART / "production-v02/source/male-body.spr").relative_to(ROOT)),
              "native_source_sha256": hashlib.sha256((ART / "production-v02/source/male-body.spr").read_bytes()).hexdigest(),
              "before_rgba_sha256": hashlib.sha256(images[0].tobytes()).hexdigest(),
              "after_rgba_sha256": hashlib.sha256(result.tobytes()).hexdigest(),
              "outside_collar_unchanged": True,
              "changed_pixels": int(np.count_nonzero(np.any(np.array(result) != np.array(images[0]), axis=2))),
              "head_attachment_delta": [0, 0]}
    (out / "collar-redraw.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(report))
    return result


if __name__ == "__main__":
    build()
