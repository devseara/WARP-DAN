"""Exercise runtime image-center registration beyond the two reference sprites.

Mutates native-layout source layers/images in an isolated Unicorn fixture.
Expected geometry comes from executed legacy packets and independent Python
trigonometry, not the generated header's dagger-only correction fields.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from verify_dual_weapon_compositor import Resources, ROOT
from verify_dual_weapon_native_basis import NativeLegacyMachine, NativeMachine, invoke_native
from verify_dual_weapon_native_projection import NativeProjector


def expected(reference, source, dimensions, target, new_dimensions):
    top, left, bottom, right, angle = reference['geometry']
    ux = abs(right - left) / (dimensions[0] * source[5])
    uy = abs(bottom - top) / (dimensions[1] * source[6])
    dx = (target[0] + new_dimensions[0] / 2) * target[5] - (source[0] + dimensions[0] / 2) * source[5]
    dy = (target[1] + new_dimensions[1] / 2) * target[6] - (source[1] + dimensions[1] / 2) * source[6]
    extra_mirror = (right < left) != bool(source[3])
    if extra_mirror:
        dx = -dx
    radians = math.radians(angle - source[7])
    cx = reference['center'][0] + math.cos(radians) * dx * ux - math.sin(radians) * dy * uy
    cy = reference['center'][1] + math.sin(radians) * dx * ux + math.cos(radians) * dy * uy
    width, height = new_dimensions[0] * target[5] * ux, new_dimensions[1] * target[6] * uy
    mirrored = bool(target[3]) != extra_mirror
    return [cy - height / 2, cx + (width if mirrored else -width) / 2,
            cy + height / 2, cx + (-width if mirrored else width) / 2, angle]


def run(client, executable, payload, output):
    resources, projector = Resources(client), NativeProjector(executable)
    legacy, current = NativeLegacyMachine(resources, payload), NativeMachine(resources, payload)
    cases, rejections = [], []
    max_error = 0.0
    # Odd/even dimensions, independent positive XY scales, source mirror,
    # native axis scale and actor rotation all vary independently.
    for unit, actor_angle in ((1.0, 0), (2.3423, 15), (2.3423, -90)):
        # Direction1 shares direction0 artwork without modifying the old
        # Compose branch's action32/frame0 family discriminator itself.
        for direction in (1, 2, 4, 6):
            for frame in (0, 3):
                action = 32 + direction
                reference = invoke_native(legacy, projector, legacy.stock, action, frame, unit, actor_angle=actor_angle)
                sword = next(d for d in reference['draws'] if d['resource'] == '13412')
                selected = [c for c in legacy.native_calls if c[0] == legacy.main['act']]
                assert len(selected) == 1
                _, source_action, source_frame = selected[0]
                old = legacy.native_layer(legacy.main, source_action, source_frame)
                old_image = legacy.main['images'][(old[8], old[2])][1]
                _, original, stock, _ = current.equip(26, 2, 2, off_only=True)
                ptr = original['layers'][(source_action, source_frame)][0]
                image_ptr = original['images'][(old[8], old[2])][0]
                layer_bytes, image_bytes = bytes(current.u.mem_read(ptr, 36)), bytes(current.u.mem_read(image_ptr, 8))
                for scales, mirror, dimensions in (((0.75, 1.5), 1 - old[3], (41, 28)),
                                                   ((1.25, 0.5), old[3], (26, 57))):
                    target = list(old)
                    target[0] += 7; target[1] -= 11
                    target[3], target[5], target[6] = mirror, *scales
                    current.u.mem_write(ptr, struct.pack('<4iI2f2i', *target))
                    current.u.mem_write(image_ptr, struct.pack('<HHhh', *dimensions, 0, 0))
                    actual = invoke_native(current, projector, stock, action, frame, unit, actor_angle=actor_angle)
                    assert actual['handled'] == 1 and len(actual['draws']) == 1, (unit, actor_angle, direction, frame, scales, source_action, source_frame, actual)
                    wanted = expected(sword, old, (old_image.width, old_image.height), target, dimensions)
                    got = actual['draws'][0]['geometry']
                    error = max(abs(a - b) for a, b in zip(got, wanted))
                    assert error < 0.001, (direction, frame, scales, wanted, got)
                    max_error = max(max_error, error)
                    cases.append({'unit': unit, 'actor_angle': actor_angle, 'direction': direction,
                                  'frame': frame, 'source_action_frame': [source_action, source_frame],
                                  'scale': scales, 'mirror': mirror, 'dimensions': dimensions,
                                  'expected': wanted, 'actual': got, 'max_error': error})
                current.u.mem_write(ptr, layer_bytes)
                current.u.mem_write(image_ptr, image_bytes)

    _, original, stock, _ = current.equip(26, 2, 2, off_only=True)
    ptr = original['layers'][(33, 0)][0]
    layer_bytes = bytes(current.u.mem_read(ptr, 36))
    layer = list(struct.unpack('<4iI2f2i', layer_bytes))
    mutations = [('nonzero_source_angle', 7, 30), ('zero_scale', 5, 0.0),
                 ('negative_scale', 5, -1.0), ('infinite_scale', 5, float('inf')),
                 ('nan_scale', 6, float('nan')), ('missing_selected_image', 2, -1)]
    for label, index, value in mutations:
        changed = layer.copy(); changed[index] = value
        current.u.mem_write(ptr, struct.pack('<4iI2f2i', *changed))
        result = invoke_native(current, projector, stock, 33, 0, 1.0)
        assert result == {'handled': 0, 'draws': []}, (label, result)
        rejections.append(label)
    current.u.mem_write(ptr, layer_bytes)

    vector = current.r(original['act'] + 0x110)
    frame_ptr = current.r(vector + 33 * 12)
    saved_vector = bytes(current.u.mem_read(frame_ptr + 0x20, 12))
    extra = current.alloc(72)
    second = layer.copy(); second[4] = 0  # Conservatively refuse even alpha-zero extra art.
    current.u.mem_write(extra, layer_bytes + struct.pack('<4iI2f2i', *second))
    current.w(frame_ptr + 0x20, extra, extra + 72, extra + 72)
    result = invoke_native(current, projector, stock, 33, 0, 1.0)
    assert result == {'handled': 0, 'draws': []}, result
    rejections.append('second_real_image_layer')
    second[2] = -1
    current.u.mem_write(extra + 36, struct.pack('<4iI2f2i', *second))
    result = invoke_native(current, projector, stock, 33, 0, 1.0)
    assert result['handled'] == 1 and len(result['draws']) == 1
    current.u.mem_write(frame_ptr + 0x20, saved_vector)

    result = {'schema': 'dual_weapon_general_registration/v1',
              'payload_sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
              'native_pe_sha256': projector.sha256, 'case_count': len(cases),
              'maximum_geometry_error': max_error, 'rejections': rejections,
              'blank_extra_layer_allowed': True, 'cases': cases,
              'limits': ['Source-layer mutations test arithmetic and guards, not the visual quality of real new weapon artwork.',
                         'Nonzero source angles and additional valid image layers are deliberately unsupported.',
                         'Reference body poses remain female Assassin; no male/job registration is inferred.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'limits')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/dual_weapon_general_registration/registration.json')
    args = parser.parse_args()
    run(args.client, args.exe, args.payload, args.output)
