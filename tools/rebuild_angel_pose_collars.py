"""Transfer the original Swordman's neck geometry across posed images."""
import struct
import numpy as np
from PIL import Image, ImageFilter
from rebuild_angel_front_collar import rebuild, GOLD, IVORY


def rebuild_pose_collars(images, native_spr, body_act, head_spr, head_act, sex="male"):
    assert sex in ("male", "female")
    count = len(native_spr.images)
    contacts = [np.zeros((p.height, p.width), bool) for p in native_spr.images]
    uses = [[] for _ in range(count)]
    for ai, frames in enumerate(body_act.actions):
        for fi, frame in enumerate(frames):
            body = frame.layers[0]
            assert body.sx == body.sy == 1 and body.angle == 0
            if body.index < 0:
                continue
            native = native_spr.images[body.index]
            body_alpha = np.frombuffer(native.pixels, np.uint8).reshape(native.height, native.width) != 0
            if body.mirror:
                body_alpha = body_alpha[:, ::-1]
            hf = head_act.actions[ai][min(fi, len(head_act.actions[ai]) - 1)]
            bx, by = struct.unpack_from("<ii", frame.anchors[0], 4)
            hx, hy = struct.unpack_from("<ii", hf.anchors[0], 4)
            head_mask = Image.new("L", (native.width, native.height))
            for head in hf.layers:
                if head.index < 0:
                    continue
                assert head.sx == head.sy == 1 and head.angle == 0
                hi = head_spr.images[head.index]
                alpha = np.frombuffer(hi.pixels, np.uint8).reshape(hi.height, hi.width) != 0
                if head.mirror:
                    alpha = alpha[:, ::-1]
                alpha = Image.fromarray((alpha * 255).astype(np.uint8))
                x = head.x + bx - hx - hi.width // 2 - body.x + native.width // 2
                y = head.y + by - hy - hi.height // 2 - body.y + native.height // 2
                head_mask.paste(alpha, (x, y), alpha)
            contact = body_alpha & (np.array(head_mask) != 0)
            if body.mirror:
                contact = contact[:, ::-1]
            contacts[body.index] |= contact
            uses[body.index].append([ai, fi])

    palette = np.array(native_spr.palette, np.uint8)
    gold = np.array([tuple(bytes.fromhex(c)) + (255,) for c in GOLD], np.uint8)
    ivory = np.array([tuple(bytes.fromhex(c)) + (255,) for c in IVORY], np.uint8)
    result, records, masks = list(images), [], []
    for index in range(count):
        if sex == "male" and index == 0:
            result[index], mask = rebuild(images[index], native_spr)
        else:
            native = native_spr.images[index]
            assert images[index].size == (native.width * 4, native.height * 4)
            contact = contacts[index]
            if uses[index] and not np.any(contact):
                raise ValueError(f"Native head/body contact is empty for body {index}")
            mask = Image.fromarray((contact * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7 if sex == "male" else 5))
            assert np.count_nonzero(np.array(mask)) < native.width * native.height * 0.3, index
            mask = mask.resize(images[index].size, Image.Resampling.NEAREST)
            indices = np.frombuffer(native.pixels, np.uint8).reshape(native.height, native.width)
            patch = palette[indices].copy()
            light = (indices >= 8) & (indices < 16)
            patch[light] = ivory[indices[light] - 8]
            if sex == "male":
                patch[light & contact] = palette[72 + indices[light & contact] - 8]
            # Female skin uses the original 168..175 ramp. Retain it exactly;
            # use the native shirt-edge pixels as the low gold collar trim.
            else:
                shirt_edge = (indices >= 120) & (indices < 128)
                patch[shirt_edge] = gold[indices[shirt_edge] - 120]
            trim = (indices >= 112) & (indices < 120)
            patch[trim] = gold[indices[trim] - 112]
            patch[(indices >= 40) & (indices < 48)] = (58, 61, 81, 255)
            patch[indices == 2] = (64, 42, 50, 255)
            patch[indices == 0] = 0
            patch = Image.fromarray(patch).resize(images[index].size, Image.Resampling.NEAREST)
            after = np.array(images[index])
            selection = np.array(mask) != 0
            after[selection] = np.array(patch)[selection]
            result[index] = Image.fromarray(after)
        before, after = np.array(images[index]), np.array(result[index])
        selection = np.array(mask) != 0
        assert np.array_equal(before[~selection], after[~selection])
        masks.append(mask)
        records.append({"image": index, "frames": uses[index], "mask_bounds_4x": mask.getbbox(),
                        "changed_pixels": int(np.count_nonzero(np.any(before != after, axis=2))),
                        "outside_neck_unchanged": True})
    return result, masks, records
