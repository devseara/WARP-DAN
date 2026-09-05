"""Execute generalized class admission and exact-source guards in emitted x86.

The 23-class matrix intentionally reuses known dagger/sword ACT/SPR fixtures:
it proves the requested allowlist, rejection and hand ownership, not visual fit.
Real resource tests are separate and enumerate the installed compatible views.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from verify_dual_weapon_compositor import Machine, Resources, ROOT
from dual_weapon_formats.rig_tables import parse_rig_bytes


def run(client, payload, output, allowed):
    allowed=set(allowed)
    assert {1,2,6} <= allowed <= set(range(1,24))
    resources = Resources(client)
    machine = Machine(resources, payload)
    sword, dagger = machine.load('13412'), machine.load('1238')
    axe = machine.load('도끼')
    carriers = {name: (machine.load(name), machine.load(name+'_검광'))
                for name in ('검', '단검_검')}
    source = (ROOT/'Scripts/Patches/AllowDualCustomWeaponSprites.qjs').read_text(encoding='utf-8')
    rig = parse_rig_bytes(bytes.fromhex(re.findall(
        r'const DualWeaponAuthoredRigHex = "([0-9A-Fa-f ]+)";', source)[0]))
    poses = {(r['phase'], r['direction'], r['frame'], r['hand']): r['transform']
             for r in rig['records'] if not r['family'] and not r['gender'] and r['state'] == 9}

    def equip(main, off, mt, ot, carrier='단검_검', off_only=False, views=(45, 34)):
        stock, trail = carriers[carrier]
        machine.w(machine.slot+20, stock['spr'], trail['spr'])
        machine.w(machine.row, machine.actor,
                  0 if off_only else main['spr'], 0 if off_only else main['act'], 0, 0,
                  off['spr'], off['act'], 0, 0, stock['act'], trail['act'],
                  28 if carrier == '단검_검' else 2, 0 if off_only else mt, ot, 0)
        machine.w(machine.viewrow, 0 if off_only else views[0], views[1])
        machine.w(machine.actor+0x440, 0 if off_only else 1001, 1002)
        return stock, trail

    def selected(resource, phase, direction, frame, hand):
        pose = poses[phase, direction, frame, hand]
        if pose.metadata & 8:
            return None
        action = (80 if phase or pose.metadata & 32 else 32)+direction
        key = action, pose.flags & 31
        layer = resource['layers'][key][1]
        return resource['images'][layer.sprite_type, layer.sprite_index][0]

    class_cases, rejected_class_cases = [], []
    for mt in range(1, 24):
        for ot in range(1, 24):
            stock, _ = equip(sword, dagger, mt, ot)
            swap = (mt == 1 and ot in (2, 6)) or (mt == 2 and ot == 6)
            ordered = (dagger, sword) if swap else (sword, dagger)
            for phase, action in ((0, 32), (1, 88)):
                handled=machine.invoke(stock, action, 0)
                if mt not in allowed or ot not in allowed:
                    assert handled==0 and not machine.calls, ('out-of-scope class drawn', mt, ot, phase)
                    continue
                assert handled == 1, ('class admission', mt, ot, phase)
                got = Counter((c['palette'], c['image']) for c in machine.calls)
                expected = Counter((r['spr']+0x110, selected(r, phase, 0, 0, hand))
                                   for hand, r in enumerate(ordered))
                assert got == expected, ('class source ownership', mt, ot, phase)
            (class_cases if mt in allowed and ot in allowed else rejected_class_cases).append([mt, ot])
    off_cases, rejected_off_cases = [], []
    for ot in range(1, 24):
        stock, _ = equip(sword, dagger, 0, ot, carrier='검', off_only=True)
        for direction in range(8):
            handled=machine.invoke(stock, 32+direction, 0)
            if ot not in allowed:
                assert handled==0 and not machine.calls, ('out-of-scope off-only drawn', ot, direction)
                continue
            assert handled == 1, ('off admission', ot, direction)
            assert len(machine.calls) == 1
            assert machine.calls[0]['palette'] == dagger['spr']+0x110
            assert machine.calls[0]['image'] == selected(dagger, 0, direction, 0, 1 if ot == 1 else 0)
        (off_cases if ot in allowed else rejected_off_cases).append(ot)

    coverage_path = ROOT/'docs/evidence/dual-weapon-type-coverage.json'
    coverage = json.loads(coverage_path.read_text(encoding='utf-8'))
    views = coverage['summary']['female']['source_compatible_sword_role_views']
    assert views == coverage['summary']['female']['source_compatible_dagger_role_views']
    declared = {r['view']: r for r in coverage['views']+coverage['generic_types']}
    real = []
    for view in views:
        record = declared[view]
        resource = machine.load(record['resource_stem'])
        for role in (0, 1):
            row = {'view': view, 'resource': resource['name'], 'physical_role': role,
                   'pair28_target_cells': 0, 'sword_carrier_held_cells': 0,
                   'selected_original_image_checks': 0}
            for carrier in carriers:
                # Real dagger partner for physical hand0, real axe partner
                # for hand1: both preserve ordering without a fake class23.
                assert record['base_type'] in allowed
                main, off = (resource, dagger) if role == 0 else (axe, resource)
                mt, ot = (record['base_type'], 1) if role == 0 else (6, record['base_type'])
                main_view, off_view = (view, 34) if role == 0 else (6, view)
                stock, trail = equip(main, off, mt, ot, carrier, views=(main_view, off_view))
                phases = ((0, 32, 6), (1, 88, 8)) if carrier == '단검_검' else ((0, 32, 6),)
                for phase, action_base, frames in phases:
                    for direction in range(8):
                        for frame in range(frames):
                            original_image = selected(resource, phase, direction, frame, role)
                            draws = []
                            for current in (stock, trail):
                                result = machine.invoke(current, action_base+direction, frame)
                                if result is not None:
                                    assert result == 1, ('real exact source rejected', view, role, carrier, phase, direction, frame)
                                    draws.extend(machine.calls)
                            owned = [c for c in draws if c['palette'] == resource['spr']+0x110]
                            # For the same resource in both slots, distinguish
                            # original image ownership by a multiset oracle.
                            expected = Counter()
                            for hand, r in enumerate((main, off)):
                                im = selected(r, phase, direction, frame, hand)
                                if im is not None:
                                    expected[r['spr']+0x110, im] += 1
                            assert Counter((c['palette'], c['image']) for c in draws) == expected
                            if original_image is not None:
                                assert any(c['image'] == original_image for c in owned)
                                row['selected_original_image_checks'] += 1
                            row['pair28_target_cells' if carrier == '단검_검' else 'sword_carrier_held_cells'] += 1
            real.append(row)

    carrier_inventory = {}
    for name, (stock, trail) in carriers.items():
        data = {}
        for phase, base, frames in (('held', 32, 6), ('dual_attack', 88, 8)):
            data[phase] = []
            for direction in range(8):
                data[phase].append({'direction': direction, 'body': [f for f in range(frames)
                    if (base+direction, f) in stock['layers'] and
                    (stock['layers'][base+direction, f][1].sprite_type,
                     stock['layers'][base+direction, f][1].sprite_index) in stock['images']],
                    'trail': [f for f in range(frames) if (base+direction, f) in trail['layers'] and
                    (trail['layers'][base+direction, f][1].sprite_type,
                     trail['layers'][base+direction, f][1].sprite_index) in trail['images']]})
        carrier_inventory[name] = data
    assert all(not r['body'] and not r['trail'] for r in carrier_inventory['검']['dual_attack'])

    # Make the legacy route observable rather than leaving ctx19=0 for every
    # case. This is a dispatch sentinel, not a substitute for the separate
    # actual-legacy/native-geometry regression.
    legacy = machine.alloc(16)
    marker = 0x51A7C0DE
    machine.u.mem_write(legacy, b'\xB8'+struct.pack('<I', marker)+b'\xC2\x24\x00')
    machine.w(machine.ctx+19*4, legacy)
    legacy_dispatch = []
    for main, off, mt, ot, pair_views in ((sword, dagger, 2, 1, (45, 34)),
                                         (dagger, sword, 1, 2, (34, 45))):
        stock, _ = equip(main, off, mt, ot, views=pair_views)
        assert machine.invoke(stock, 32, 0) == marker and not machine.calls
        legacy_dispatch.append({'views': pair_views, 'legacy_called': True})
    for view in range(1, 24):
        stock, _ = equip(sword, dagger, view, 1, views=(view, 34))
        handled=machine.invoke(stock, 32, 0)
        assert handled == int(view in allowed) and len(machine.calls) == (2 if view in allowed else 0)
        legacy_dispatch.append({'views': [view, 34], 'legacy_called': False, 'handled':bool(handled)})
    machine.w(machine.ctx+19*4, 0)

    guards = []
    def rejected(label, address, replacement, action=32, frame=0, carrier='단검_검', wrap=False):
        stock, _ = equip(sword, dagger, 2, 1, carrier)
        before = bytes(machine.u.mem_read(address, len(replacement)))
        try:
            machine.u.mem_write(address, replacement)
            result = machine.invoke(stock, action, frame, frame_wrap=wrap)
            assert result == 0 and not machine.calls, (label, result, len(machine.calls))
        finally:
            machine.u.mem_write(address, before)
        guards.append(label)
    for offset, name in ((48, 'main'), (52, 'off')):
        for value in (0, 24, 0xFFFFFFFF):
            rejected(f'{name} type {value} rejected', machine.row+offset, struct.pack('<I', value))
    rejected('male profile rejected', machine.row+56, struct.pack('<I', 1))
    for name, resource in (('main', sword), ('off', dagger)):
        rejected(name+' foreign ACT family rejected', resource['act']+0x14, b'X')
        original = bytes(machine.u.mem_read(resource['act']+0x14, 0xE0))
        rejected(name+' filename at obsolete +0x10 rejected', resource['act']+0x10, original)
    act_vector = machine.r(sword['act']+0x110)
    held_frames = machine.r(act_vector+32*12)
    rejected('missing exact source action', sword['act']+0x114, struct.pack('<I', act_vector+32*12))
    rejected('missing exact source held frame', act_vector+32*12+4, struct.pack('<I', held_frames))
    attack_frames = machine.r(act_vector+80*12)
    rejected('missing selected attack frame4 does not wrap to frame0', act_vector+80*12+4,
             struct.pack('<I', attack_frames+4*68), action=88)
    layer_address = sword['layers'][32, 0][0]
    rejected('invalid selected image index', layer_address+8, struct.pack('<i', -1))
    rejected('unprofiled source rotation', layer_address+28, struct.pack('<i', 30))
    rejected('zero source scale', layer_address+20, struct.pack('<f', 0))
    rejected('nonfinite source scale', layer_address+20, struct.pack('<f', float('nan')))
    rejected('held target frame6 cannot wrap', machine.row+44, struct.pack('<I', 28), frame=6, wrap=True)
    rejected('dual compositor rejects native solo attack80 carrier', machine.row+44,
             struct.pack('<I', 2), action=80, carrier='검')

    result = {
        'schema': 'dual_weapon_all_type_compositor_execution/v2',
        'allowed_classes':sorted(allowed),
        'payload': str(payload), 'payload_sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
        'source_sha256': hashlib.sha256((ROOT/'CustomDLL/DualWeapon/compositor.c').read_bytes()).hexdigest(),
        'coverage_sha256': hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
        'class_admission_reused_fixtures': {'fixture_main': '13412', 'fixture_off': '1238',
            'combinations': class_cases, 'combination_count': len(class_cases),
            'rejected_combinations':rejected_class_cases, 'rejected_combination_count':len(rejected_class_cases),
            'checked_phases': ['held32/frame0', 'dual_attack88/frame0'],
            'off_only_classes': off_cases, 'rejected_off_only_classes':rejected_off_cases, 'off_only_directions_per_class': 8,
            'claim': 'class admission and source ownership only; no mace/staff/gun art is represented by these fixtures'},
        'real_resource_rows': real, 'real_view_count': len(views),
        'carrier_inventory': carrier_inventory, 'rejection_checks': guards,
        'legacy_dispatch_sentinel_cases': legacy_dispatch,
        'source_resources': resources.evidence,
        'limits': [
            'No game process, GPU draw or live visual acceptance is covered.',
            'Missing Assassin assets are not generated or replaced by the reused class-admission fixtures.',
            'Generic sword carrier has no visible body/trail layer in dual attack88..95; selector change alone cannot produce those packets.',
            'Native projection and packet arithmetic retain their separately verified fixture contract and are not re-proved here.',
            'Off-only non-held behavior retains its inherited native-resource/frame-zero fallback; these new strict source guards cover dual and held paths.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'class_combinations': len(class_cases), 'rejected_combinations':len(rejected_class_cases), 'off_only_classes': len(off_cases),
                      'real_views': len(views), 'real_resource_rows': len(real), 'rejection_checks': len(guards)}))
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, default=Path(r'D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes'))
    parser.add_argument('--payload', type=Path, default=ROOT/'Inputs/DualWeaponRuntime/compositor.dwcp')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/evidence/dual-weapon-supported-compositor-20260905.json')
    parser.add_argument('--allowed-classes', type=int, nargs='+', default=[1,2,6], help='Explicit expected contract; pass all23 only for archived all-type payloads')
    args = parser.parse_args()
    run(args.client, args.payload, args.output, args.allowed_classes)
