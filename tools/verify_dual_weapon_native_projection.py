"""Verify raw ACT/native Layer normalization and execute the native rectangle producer.

Reads a captured live-resource report and the user's PE. It does not open or
modify the live process. Native C40C20 executes unmodified under Unicorn;
status effects are disabled and a synthetic on-screen origin is supplied.
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
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX,
    UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)
from verify_dual_weapon_compositor import Resources, ROOT
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.spr_reader import Spr


def normalized_layer(raw, image):
    """Raw ACT center -> native integer edge; ceil-half confirmed from live fields.

    This helper intentionally requires a valid image and does not invent the
    native sentinel behavior for invalid sprite indices.
    """
    return [raw.x - (image.width + 1) // 2, raw.y - (image.height + 1) // 2,
            raw.sprite_index, raw.mirror, int.from_bytes(bytes(raw.color), 'little'),
            raw.scale_x, raw.scale_y, raw.rotation, raw.sprite_type]


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


class NativeProjector:
    ENTRY, END = 0xC40C20, 0xC412C8

    def __init__(self, executable):
        self.executable = executable
        raw = executable.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        pe = pefile.PE(data=raw)
        assert pe.FILE_HEADER.Machine == 0x14c and pe.OPTIONAL_HEADER.ImageBase == 0x400000
        self.code = pe.get_data(self.ENTRY - 0x400000, self.END - self.ENTRY)
        assert self.code[:6] == bytes.fromhex('55 8b ec 83 ec 0c')
        assert self.code[-3:] == bytes.fromhex('c2 44 00')
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.u.mem_write(0x400000, pe.get_memory_mapped_image())
        self.base = 0x40000000
        self.u.mem_map(self.base, 0x10000)
        self.actor, self.layer, self.image = self.base, self.base + 0x1000, self.base + 0x1100
        self.packet, self.rect, self.color = self.base + 0x1200, self.base + 0x1300, self.base + 0x1400
        self.depth, self.viewport, self.stack = self.base + 0x1500, self.base + 0x1600, self.base + 0xE000
        self.stop = self.base + 0xF000
        self.w(0x12515F8, self.viewport)
        self.w(self.viewport + 0x28, 8192, 8192)
        assert struct.unpack('<d', self.u.mem_read(0xFD4420, 8))[0] == 1.0

    def w(self, address, *values):
        self.u.mem_write(address, struct.pack('<' + 'I' * len(values), *(x & 0xffffffff for x in values)))

    def project(self, layer, dimensions, unit=1.0, actor_scale=1.0,
                origin=(400.0, 300.0), offsets=(0, 0), extra_x=0.0, actor_angle=0):
        self.u.mem_write(self.actor, bytes(0x600))
        self.w(self.actor + 0x50, struct.unpack('<I', struct.pack('<f', actor_scale))[0])
        self.w(self.actor + 0x7C, actor_angle)
        self.w(self.actor + 0x98, 0xffffffff)
        # Native constant-depth path avoids unrelated camera/depth division.
        self.u.mem_write(self.actor + 0xA2, b'\1')
        self.u.mem_write(self.layer, struct.pack('<4iI2f2i', *layer))
        self.u.mem_write(self.image, struct.pack('<4h', *dimensions))
        self.u.mem_write(self.packet, bytes(48))
        bits = lambda x: struct.unpack('<I', struct.pack('<f', x))[0]
        args = [0, 0, bits(unit), self.layer, bits(origin[0]), bits(origin[1]),
                self.depth, bits(extra_x), self.depth + 16, self.depth + 20,
                self.image, self.packet, self.rect, self.color,
                offsets[0], offsets[1], 0]
        self.w(self.stack, self.stop, *args)
        registers = [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]
        for i, register in enumerate(registers):
            self.u.reg_write(register, 0x777000 + i * 16)
        self.u.reg_write(UC_X86_REG_ESP, self.stack)
        self.u.reg_write(UC_X86_REG_ECX, self.actor)
        self.u.emu_start(self.ENTRY, self.stop, count=10000)
        assert self.u.reg_read(UC_X86_REG_EIP) == self.stop
        assert self.u.reg_read(UC_X86_REG_ESP) == self.stack + 72, 'Native RET68 imbalance'
        assert self.u.reg_read(UC_X86_REG_EAX) & 255 == 1, 'Native packet was clipped'
        for i, register in enumerate(registers):
            assert self.u.reg_read(register) == 0x777000 + i * 16
        assert bytes(self.u.mem_read(self.layer, 36)) == struct.pack('<4iI2f2i', *layer)
        return struct.unpack('<6fIf', self.u.mem_read(self.packet, 32))


def expected_projection(layer, dimensions, unit, actor_scale, origin, offsets, extra_x):
    x, y, _, mirror, _, sx, sy, angle, _ = layer
    width, height, cols, rows = dimensions
    ux = f32(f32(f32(unit) * f32(sx)) * f32(actor_scale))
    uy = f32(f32(f32(unit) * f32(sy)) * f32(actor_scale))
    extent_x, extent_y = width * (cols + 1), height * (rows + 1)
    left = f32((x + offsets[0] + (extent_x if mirror else 0)) * ux + f32(origin[0]))
    right = f32((x + offsets[0] + (0 if mirror else extent_x)) * ux + f32(origin[0]) + 1)
    top = f32((y + offsets[1]) * uy + f32(origin[1]))
    bottom = f32((y + offsets[1] + extent_y) * uy + f32(origin[1]) + 1)
    return [top, f32(left + f32(extra_x)), bottom, f32(right + f32(extra_x)), float(angle)]


def audit_live(snapshot_path, resources):
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    compared, invalid, mismatches, anchors = [], [], [], []
    for live_act in snapshot['resources'].values():
        name = live_act['name']
        if not name.endswith('.act') or '_여_' not in name:
            continue
        stem = name.split('_여_')[-1][:-4]
        act = parse_act(resources.read(stem + '.act'))
        spr = Spr(resources.read(stem + '.spr'))
        images = {kind: [im for im in spr.images if im.is_indexed == (kind == 0)] for kind in (0, 1)}
        cells = {(int(a), 0): cell for a, cell in live_act.get('frames', {}).items()}
        cells.update({tuple(map(int, key.split(':'))): cell for key, cell in live_act.get('held_frames', {}).items()})
        for (action, frame), cell in sorted(cells.items()):
            raw_frame = act['actions'][action].frames[frame]
            assert len(raw_frame.layers) == len(cell['layers']), (name, action, frame, 'layer count')
            assert [list(a) for a in raw_frame.anchors] == cell['anchors'], (name, action, frame, 'anchors')
            anchors.append([name, action, frame, cell['anchors']])
            for index, live in enumerate(cell['layers']):
                raw = raw_frame.layers[index]
                item = {'name': name, 'action': action, 'frame': frame, 'layer': index, 'native': live}
                if raw.sprite_index < 0 or raw.sprite_index >= len(images[raw.sprite_type]):
                    # Record rather than infer an unprofiled sentinel transform.
                    invalid.append(item)
                    continue
                image = images[raw.sprite_type][raw.sprite_index]
                expected = normalized_layer(raw, image)
                item.update(raw_center=[raw.x, raw.y], dimensions=[image.width, image.height], expected_native=expected)
                compared.append(item)
                if expected != live:
                    mismatches.append(item)
    return {'snapshot_sha256': hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        'snapshot_exe_sha256': snapshot['sha256'], 'snapshot_atomic': snapshot['atomic_snapshot'],
        'visible_layer_count': len(compared), 'anchor_frame_count': len(anchors),
        'invalid_sprite_layers_not_normalized': invalid, 'mismatches': mismatches,
        'layers': compared, 'anchors': anchors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'docs/evidence/dual-weapon-live-pair28-20260905.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/dual_weapon_native_projection/report.json')
    args = parser.parse_args()
    resources = Resources(args.client)
    live = audit_live(args.snapshot, resources)
    assert not live['mismatches'], live['mismatches'][:3]
    native = NativeProjector(args.exe)
    cases = []
    for dimensions in [(26, 26, 0, 0), (53, 38, 0, 0), (62, 44, 0, 0), (16, 16, 1, 2)]:
        for unit in [0.5, 1.0, 2.3423]:
            for actor_scale in [1.0, 1.5]:
                for mirror in [0, 1]:
                    for sx, sy in [(1.0, 1.0), (0.75, 1.25)]:
                        for offsets in [(0, 0), (7, -13)]:
                            layer = [-20, -49, 0, mirror, 0xffffffff, sx, sy, 80, 0]
                            origin, extra_x = (400.25, 300.75), 3.25
                            output = native.project(layer, dimensions, unit, actor_scale, origin, offsets, extra_x)
                            expected = expected_projection(layer, dimensions, unit, actor_scale, origin, offsets, extra_x)
                            actual = list(output[:4]) + [output[7]]
                            assert all(abs(a - e) < 0.0001 for a, e in zip(actual, expected)), (actual, expected)
                            # Removing the far-edge +1 recovers exact native units
                            # for both mirror states, unlike abs(width)/imageWidth.
                            recovered_x = abs(output[3] - output[1] - 1) / (dimensions[0] * (dimensions[2] + 1) * abs(sx))
                            recovered_y = abs(output[2] - output[0] - 1) / (dimensions[1] * (dimensions[3] + 1) * abs(sy))
                            assert abs(recovered_x - unit * actor_scale) < 0.00001
                            assert abs(recovered_y - unit * actor_scale) < 0.00001
                            cases.append({'dimensions': dimensions, 'unit': unit, 'actor_scale': actor_scale,
                                'mirror': mirror, 'layer_scale': [sx, sy], 'offsets': offsets,
                                'native': actual, 'expected': expected, 'recovered_units': [recovered_x, recovered_y]})
    report = {'schema': 'dual_weapon_native_projection/v1', 'executable_sha256': native.sha256,
        'native_producer': {'start': hex(native.ENTRY), 'end_exclusive': hex(native.END),
            'bytes': len(native.code), 'sha256': hashlib.sha256(native.code).hexdigest()},
        'live_normalization': live, 'native_projection_cases': len(cases), 'cases': cases,
        'resources': resources.evidence, 'visual_acceptance': False,
        'limitations': ['Snapshot reads were not atomic.', 'Normalizer is checked against captured valid layers; invalid-sprite sentinel behavior is not inferred.',
            'Native C40C20 executes in full, with status effects disabled, constant-depth mode, and an explicit synthetic origin/attachment offset.',
            'This validates native layer/rectangle math, not the caller job-anchor calculation or live hand contact.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'visible_layer_count': live['visible_layer_count'], 'anchor_frame_count': live['anchor_frame_count'],
        'normalization_mismatches': len(live['mismatches']), 'native_projection_cases': len(cases)}))


if __name__ == '__main__':
    main()
