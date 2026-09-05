"""Compare corrected poses with real legacy geometry using native-normalized ACTs.

Input rectangles come from the actual PE's C40C20. The legacy family check is
executed against normalized resources without a discriminator stub. This is
arithmetic/ABI proof; camera/job origin and attachment offsets remain explicit
fixture inputs and do not constitute live hand-contact acceptance.
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
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX,
    UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)
from verify_dual_weapon_compositor import Machine, Resources, ROOT
from verify_dual_weapon_legacy_transform import LegacyMachine, semantic_draw
from verify_dual_weapon_native_projection import NativeProjector, normalized_layer


class NativeLayout:
    def load(self, name):
        resource = super().load(name)
        if resource.get('native_normalized'):
            return resource
        for (action, frame), (address, raw) in resource['layers'].items():
            image = resource['images'].get((raw.sprite_type, raw.sprite_index))
            if image:
                native = normalized_layer(raw, image[1])
                self.u.mem_write(address, struct.pack('<4iI2f2i', *native))
            anchors = resource['parsed']['actions'][action].frames[frame].anchors
            vector = self.r(resource['act'] + 0x110)
            frame_address = self.r(vector + action * 12) + frame * 68
            if anchors:
                begin = self.alloc(12 * len(anchors))
                for i, anchor in enumerate(anchors):
                    self.w(begin + i * 12, *anchor)
                self.w(frame_address + 0x34, begin, begin + len(anchors) * 12,
                       begin + len(anchors) * 12, len(anchors))
        resource['native_normalized'] = True
        return resource

    def native_layer(self, resource, action, frame):
        return struct.unpack('<4iI2f2i', self.u.mem_read(resource['layers'][(action, frame)][0], 36))


class NativeMachine(NativeLayout, Machine):
    pass


class NativeLegacyMachine(NativeLayout, LegacyMachine):
    def __init__(self, resources, runtime):
        super().__init__(resources, runtime)
        # These exact retained generic trail names are recorded in the live
        # pair28 owner row, alongside the original 13412/1238 body resources.
        mt, ot = self.load('검_검광'), self.load('단검_검광')
        self.w(self.row + 12, mt['spr'], mt['act'])
        self.w(self.row + 28, ot['spr'], ot['act'])
        self.act_map = {v['act']: v for v in self.loaded.values()}
        assert self.native_layer(self.stock, 32, 0)[:4] == (-20, -49, 0, 0)

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
            uc.reg_write(UC_X86_REG_EAX, result)
        elif address == self.layer_getter:
            frame = uc.reg_read(UC_X86_REG_ECX)
            index = self.r(uc.reg_read(UC_X86_REG_ESP) + 4)
            begin, end = self.r(frame + 0x20), self.r(frame + 0x24)
            assert index < (end - begin) // 36
            uc.reg_write(UC_X86_REG_EAX, begin + index * 36)


def invoke_native(machine, projector, resource, action, frame, unit, channel=5, actor_angle=0):
    info = resource['layers'].get((action, frame))
    if not info:
        return None
    layer = machine.native_layer(resource, action, frame)
    image = resource['images'].get((layer[8], layer[2]))
    if not image:
        return None
    pointer, bitmap = image
    native = projector.project(layer, (bitmap.width, bitmap.height, 0, 0), unit,
                               origin=(960.0, 495.0), actor_angle=actor_angle)
    packet = struct.pack('<6fIf3II', *native, 0, 0, 0, pointer)
    machine.u.mem_write(machine.packet, packet)
    machine.w(machine.actor + 0x38, action, frame)
    machine.calls = []
    if isinstance(machine, LegacyMachine):
        machine.native_calls = []
        machine.w(machine.capture, machine.actor, channel, pointer, info[0])
    esp = 0x2f00000
    machine.w(esp, machine.stop, machine.actor, machine.packet,
              resource['spr'] + 0x110, 0x123, 0, 0, 0x456, machine.ctx, machine.draw)
    registers = [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]
    for i, register in enumerate(registers):
        machine.u.reg_write(register, 0x777000 + i * 16)
    machine.u.reg_write(UC_X86_REG_ESP, esp)
    machine.u.emu_start(machine.entry, machine.stop, count=1000000)
    assert machine.u.reg_read(UC_X86_REG_EIP) == machine.stop
    assert machine.u.reg_read(UC_X86_REG_ESP) == esp + 40
    for i, register in enumerate(registers):
        assert machine.u.reg_read(register) == 0x777000 + i * 16
    assert bytes(machine.u.mem_read(machine.packet, 48)) == packet
    draws = []
    for call in machine.calls:
        semantic = semantic_draw(machine, call)
        values = semantic.pop('packet_without_image_pointer')
        semantic['geometry'] = list(values[:4]) + [values[7]]
        semantic['center'] = [(values[1] + values[3]) / 2, (values[0] + values[2]) / 2]
        # Actual native z/color remain current-packet owned, so they must be
        # preserved rather than compared to the hypothetical reference packet.
        assert values[4:7] == native[4:7]
        draws.append(semantic)
    return {'handled': machine.u.reg_read(UC_X86_REG_EAX), 'draws': draws}


def same_geometry(left, right, tolerance=0.001):
    return (left['resource'] == right['resource'] and left['image'] == right['image'] and
            all(abs(a - b) < tolerance for a, b in zip(left['geometry'], right['geometry'])))


def dagger_reference(legacy, reference):
    """Register dagger bitmap centers to the accepted legacy sword transform.

    Derives from executed legacy packet/source calls and raw sprite dimensions,
    independently of the generated native_basis.h or C prepare_reference.
    """
    expected = []
    for draw in reference['draws']:
        if draw['resource'] == '1238':
            expected.append(draw)
            continue
        assert draw['resource'] == '13412'
        calls = [call for call in legacy.native_calls if call[0] == legacy.main['act']]
        assert len(calls) == 1
        _, action, frame = calls[0]
        sword = legacy.native_layer(legacy.main, action, frame)
        dagger = legacy.native_layer(legacy.off, action, frame)
        sword_image = legacy.main['images'][(sword[8], sword[2])][1]
        dagger_image = legacy.off['images'][(dagger[8], dagger[2])][1]
        assert sword[5:8] == dagger[5:8] == (1.0, 1.0, 0)
        assert sword[3] == dagger[3]
        dx = dagger[0] + dagger_image.width/2 - sword[0] - sword_image.width/2
        dy = dagger[1] + dagger_image.height/2 - sword[1] - sword_image.height/2
        top, left, bottom, right, angle = draw['geometry']
        mirror = right < left
        if mirror != bool(sword[3]):
            dx = -dx
        # Native final draw rotates the already-scaled rectangle. Transform
        # the bitmap-center difference in that same order: R * diag(Ux, Uy).
        # The final packet angle includes the current actor's extra rotation.
        radians = math.radians(angle - sword[7])
        ux, uy = abs(right-left)/sword_image.width, abs(bottom-top)/sword_image.height
        rx = math.cos(radians) * dx * ux - math.sin(radians) * dy * uy
        ry = math.sin(radians) * dx * ux + math.cos(radians) * dy * uy
        cx = draw['center'][0] + rx
        cy = draw['center'][1] + ry
        w, h = dagger_image.width * ux, dagger_image.height * uy
        expected.append({'resource': '1238', 'image': (dagger[8], dagger[2]),
            'geometry': [cy-h/2, cx+(w if mirror else -w)/2,
                         cy+h/2, cx+(-w if mirror else w)/2, angle],
            'center': [cx, cy], 'source_action_frame': [action, frame],
            'native_center_delta': [dx, dy], 'rotated_delta': [rx, ry]})
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--payload', type=Path, default=ROOT / 'Inputs/DualWeaponRuntime/compositor.dwcp')
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/dual_weapon_native_basis/report.json')
    parser.add_argument('--allow-differences', action='store_true', help='Write a negative-control report without asserting equality')
    args = parser.parse_args()
    resources, projector = Resources(args.client), NativeProjector(args.exe)
    legacy = NativeLegacyMachine(resources, args.payload)
    current = NativeMachine(resources, args.payload)
    off_cases, dd_cases, differences = [], [], []
    combinations = [(unit, actor_angle, phase, action_base, frames)
                    for unit in [1.0, 2.3423] for actor_angle in [0, 15, -90]
                    for phase, action_base, frames in [(0, 32, 6), (1, 88, 8)]]
    for unit, actor_angle, phase, action_base, frames in combinations:
        for direction in range(8):
            for frame in range(frames):
                action = action_base + direction
                channel = 6 if phase and frame in (3, 4, 6, 7) else 5
                reference_resource = legacy.trail if channel == 6 else legacy.stock
                reference = invoke_native(legacy, projector, reference_resource, action, frame, unit, channel, actor_angle)
                assert reference and reference['handled'] == 1
                by_name = {d['resource']: d for d in reference['draws']}
                for kind, name in ([(1, '1238'), (2, '13412')] if phase == 0 else []):
                    _, _, stock, _ = current.equip(25 if kind == 1 else 26, kind, kind, off_only=True)
                    actual = invoke_native(current, projector, stock, action, frame, unit, actor_angle=actor_angle)
                    equal = bool(actual and actual['handled'] == 1 and len(actual['draws']) == 1 and
                                 same_geometry(actual['draws'][0], by_name[name]))
                    case = {'unit': unit, 'actor_angle': actor_angle, 'direction': direction, 'frame': frame, 'weapon': name,
                            'equal': equal, 'reference': by_name[name], 'actual': actual}
                    off_cases.append(case)
                    if not equal:
                        differences.append({'kind': 'off_only', **case})
                expected_draws = dagger_reference(legacy, reference)
                _, _, stock, _ = current.equip(25, 1, 1)
                actual = invoke_native(current, projector, stock, action, frame, unit, actor_angle=actor_angle)
                equal = bool(actual and actual['handled'] == 1 and len(actual['draws']) == len(expected_draws) and
                             all(same_geometry(a, e) for a, e in zip(actual['draws'], expected_draws)))
                case = {'unit': unit, 'actor_angle': actor_angle, 'phase': phase, 'direction': direction, 'frame': frame, 'equal': equal,
                        'expected_draws': expected_draws, 'reference': reference, 'actual': actual}
                dd_cases.append(case)
                if not equal:
                    differences.append({'kind': 'dagger_dagger', **case})
    report = {'schema': 'dual_weapon_native_basis/v1', 'native_pe_sha256': projector.sha256,
        'runtime_sha256': hashlib.sha256(args.payload.read_bytes()).hexdigest(),
        'off_only_cases': off_cases, 'dagger_dagger_cases': dd_cases, 'differences': differences,
        'resources': resources.evidence, 'visual_acceptance': False,
        'limitations': ['Native actor origin is explicitly supplied; live camera/body attachment calculation is outside this fixture.',
            'True normalized resource family passes the legacy discriminator; no family stub is used.',
            'Native C40C20 supplies packet corners including scale, mirroring and the +1 far-edge pixel.',
            'Current packet depth/color ownership is preserved; geometry is compared against the legacy reference.',
            'Off-only held follows the same visible legacy hand; off-only attack has a separate body timeline and is outside this matrix.',
            'Dagger/dagger covers held and dual attack, with bitmap-center registration derived from executed legacy source-frame calls; visual hand contact remains unaccepted.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'off_only_cases': len(off_cases), 'dagger_dagger_cases': len(dd_cases),
                      'differences': len(differences)}))
    if not args.allow_differences:
        assert not differences, str(args.output)


if __name__ == '__main__':
    main()
