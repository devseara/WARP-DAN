"""Compare emitted canonical geometry with the embedded legacy x86 compositor.

This is a transform regression, not a reconstruction of the native packet
producer or visual acceptance. Both cores receive the same synthetic packet
origin and real client SPR/ACT layer/image data. The legacy family discriminator
alone receives its expected (-20, -49) layer. See the report's fixture caveats.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP,
    UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP)

from verify_dual_weapon_compositor import Machine, Resources, ROOT
from verify_dual_weapon_scope import CORE_SHA256, payload


class LegacyMachine(Machine):
    def __init__(self, resources, runtime):
        super().__init__(resources, runtime, native_layout=False)
        self.main, self.off, self.stock, self.trail = self.equip(28, 2, 1)
        # The legacy core requires nonnull body AND trail owners even for held
        # draws. Held cells use only the body resources retained here.
        self.w(self.row + 12, self.main['spr'], self.main['act'])
        self.w(self.row + 28, self.off['spr'], self.off['act'])
        source = (ROOT / 'Scripts/Patches/AllowDualCustomWeaponSprites.qjs').read_text(encoding='utf-8')
        original = payload(source, 'DualWeaponAuthoredCore')
        assert hashlib.sha256(original).hexdigest() == CORE_SHA256, 'Re-profile changed legacy core'
        core = bytearray(original)
        self.legacy_base = 0x400000
        relocs = json.loads(re.search(r'const DualWeaponAuthoredCoreRelocs = (\[.*?\]);', source)[1])
        for offset, target in relocs:
            struct.pack_into('<I', core, offset, self.legacy_base + target)
        self.u.mem_write(self.legacy_base, bytes(core))
        self.entry = self.legacy_base
        rig = payload(source, 'DualWeaponAuthoredRig')
        rig_address = self.alloc(len(rig))
        self.u.mem_write(rig_address, rig)
        self.capture = self.alloc(128)
        self.frame_getter, self.layer_getter = 0x110200, 0x110220
        self.w(self.ctx + 4, self.capture, rig_address, self.frame_getter, self.layer_getter)
        self.u.mem_write(self.frame_getter, b'\xc2\x08\x00')
        self.u.mem_write(self.layer_getter, b'\xc2\x04\x00')
        self.act_map = {v['act']: v for v in self.loaded.values()}
        self.family_frame, self.family_layer = self.alloc(68), self.alloc(36)
        self.w(self.family_frame + 0x20, self.family_layer, self.family_layer + 36)
        self.w(self.family_layer, -20, -49, 0, 0, 0xffffffff, 0x3f800000, 0x3f800000, 0, 0)
        self.native_calls = []
        self.u.hook_add(UC_HOOK_CODE, self.native_hook)

    def native_hook(self, uc, address, size, _):
        if address == self.frame_getter:
            esp = uc.reg_read(UC_X86_REG_ESP)
            action, frame = self.r(esp + 4), self.r(esp + 8)
            act = uc.reg_read(UC_X86_REG_ECX)
            self.native_calls.append((act, action, frame))
            result = 0
            resource = self.act_map.get(act)
            if resource and action < len(resource['parsed']['actions']):
                vector = self.r(act + 0x110)
                begin, end = self.r(vector + action * 12), self.r(vector + action * 12 + 4)
                result = begin + (frame if frame < (end - begin) // 68 else 0) * 68
            if act == self.stock['act']:
                # This getter call only validates the legacy's historical
                # resource family. Actual packet/captured layer stay unchanged.
                assert (action, frame) == (32, 0)
                result = self.family_frame
            uc.reg_write(UC_X86_REG_EAX, result)
        elif address == self.layer_getter:
            frame = uc.reg_read(UC_X86_REG_ECX)
            uc.reg_write(UC_X86_REG_EAX, self.r(frame + 0x20) if frame else 0)


def invoke(machine, resource, action, frame):
    machine.calls = []
    layer_address, layer = resource['layers'][(action, frame)]
    image_address, image = resource['images'][(layer.sprite_type, layer.sprite_index)]
    # Explicit synthetic coordinate contract. ACT attachment anchors and body
    # attachment transforms are intentionally outside this arithmetic test.
    cx, cy = 400 + layer.x, 300 + layer.y
    width = image.width * layer.scale_x * (-1 if layer.mirror else 1)
    height = image.height * layer.scale_y
    packet = struct.pack('<6fIf3II', cy - height/2, cx - width/2,
        cy + height/2, cx + width/2, 0.5, 0.5, 0xffffffff,
        float(layer.rotation), 0, 0, 0, image_address)
    machine.u.mem_write(machine.packet, packet)
    machine.w(machine.actor + 0x38, action, frame)
    if isinstance(machine, LegacyMachine):
        machine.native_calls = []
        machine.w(machine.capture, machine.actor, 5, image_address, layer_address)
    esp = 0x2f00000
    machine.w(esp, machine.stop, machine.actor, machine.packet,
        resource['spr'] + 0x110, 0x123, 0, 0, 0x456, machine.ctx, machine.draw)
    registers = [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]
    for i, register in enumerate(registers):
        machine.u.reg_write(register, 0x777000 + i * 16)
    machine.u.reg_write(UC_X86_REG_ESP, esp)
    machine.u.emu_start(machine.entry, machine.stop, count=1000000)
    assert machine.u.reg_read(UC_X86_REG_EIP) == machine.stop
    assert machine.u.reg_read(UC_X86_REG_ESP) == esp + 40, 'RET 36 stack imbalance'
    for i, register in enumerate(registers):
        assert machine.u.reg_read(register) == 0x777000 + i * 16
    assert bytes(machine.u.mem_read(machine.packet, 48)) == packet, 'Input packet mutated'
    assert machine.u.reg_read(UC_X86_REG_EAX) == 1
    assert len(machine.calls) == 2
    if isinstance(machine, LegacyMachine):
        assert machine.native_calls[0] == (machine.stock['act'], 32, 0)
        assert len(machine.native_calls) == 3
        assert {c[0] for c in machine.native_calls[1:]} == {machine.main['act'], machine.off['act']}
    return [semantic_draw(machine, call) for call in machine.calls]


def semantic_draw(machine, call):
    owners = [r for r in machine.loaded.values() if call['palette'] == r['spr'] + 0x110]
    assert len(owners) == 1
    owner = owners[0]
    images = [key for key, value in owner['images'].items() if value[0] == call['image']]
    assert len(images) == 1
    assert call['actor'] == machine.actor
    return {'resource': owner['name'], 'image': images[0], 'packet_without_image_pointer': call['packet'][:11]}


def compare(client, runtime):
    resources = Resources(client)
    legacy = LegacyMachine(resources, runtime)
    current = Machine(resources, runtime, native_layout=False)
    _, _, stock, _ = current.equip(28, 2, 1)
    cases, mismatches = [], []
    for direction in range(8):
        for frame in range(6):
            old = invoke(legacy, legacy.stock, 32 + direction, frame)
            new = invoke(current, stock, 32 + direction, frame)
            cases.append({'direction': direction, 'frame': frame,
                          'legacy': old, 'current': new, 'equal': old == new})
            for order, (left, right) in enumerate(zip(old, new)):
                if left != right:
                    flipped = dict(left)
                    packet = list(left['packet_without_image_pointer'])
                    packet[1], packet[3] = packet[3], packet[1]
                    flipped['packet_without_image_pointer'] = tuple(packet)
                    mismatches.append({'direction': direction, 'frame': frame,
                                       'draw_order': order, 'mirror_only': flipped == right,
                                       'legacy': left, 'current': right})
    return {'schema': 'dual_weapon_legacy_transform/v1',
        'runtime_sha256': hashlib.sha256(runtime.read_bytes()).hexdigest(),
        'legacy_core_sha256': CORE_SHA256, 'case_count': len(cases), 'draw_count': len(cases) * 2,
        'mismatched_draws': len(mismatches), 'mismatches': mismatches, 'cases': cases,
        'resources': resources.evidence, 'visual_acceptance': False,
        'fixture_caveats': [
            'Both cores receive a synthetic origin (400,300) plus native ACT layer offsets; native attachment calculation is not exercised.',
            'Actual active client GRF SPR/ACT layers, image sizes and source resource identities are used.',
            'Only the legacy family-discriminator getter is supplied its historical (-20,-49,index0,mirror0) layer.',
            'Legacy unused held trail slots contain body resources to satisfy its mandatory-resource presence checks.',
            'Held action32..39/frame0..5 only; no attack geometry or live placement acceptance is claimed.'],
        'assertions': ['RET36', 'callee-save registers', 'input packet unchanged',
                       'two original resource draws', 'draw order and all packet fields compared',
                       'legacy discriminator and source getter calls are explicitly checked']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--payload', type=Path, default=ROOT / 'Inputs/DualWeaponRuntime/compositor.dwcp')
    parser.add_argument('--expect-mismatches', type=int, default=0,
                        help='Negative control: the unfixed payload produces 48 mirrored-direction draw mismatches')
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/dual_weapon_legacy_transform/report.json')
    args = parser.parse_args()
    report = compare(args.client, args.payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    assert report['mismatched_draws'] == args.expect_mismatches, (
        report['mismatched_draws'], args.expect_mismatches, str(args.output))
    if args.expect_mismatches == 48:
        assert all(x['mirror_only'] and 4 <= x['direction'] <= 7 for x in report['mismatches']), (
            'Negative control changed beyond the known canonical mirror regression', str(args.output))
    print(json.dumps({k: report[k] for k in ('runtime_sha256', 'case_count', 'draw_count', 'mismatched_draws')}))


if __name__ == '__main__':
    main()
