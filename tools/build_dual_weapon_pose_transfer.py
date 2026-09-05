"""HISTORICAL, LIVE-REJECTED raw-ACT pose-transfer experiment.

Its raw coordinates and integer-rounded/mirrored center deltas do not preserve
the runtime packet basis. This generated rig is no longer a runtime input.
Use build_dual_weapon_native_basis.py for the corrected native representation.
"""
from __future__ import annotations
import argparse
import configparser
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

sys.dont_write_bytecode = True
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.grf_reader import GrfFile
from dual_weapon_formats.spr_reader import Spr
from dual_weapon_formats.rig_tables import (parse_rig_bytes, dense_index,
                                           DWR3_TRANSFORM, DWR3_HEADER)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'data/sprite/인간족/어세신/어세신_여_'


def build(client: Path):
    ini = configparser.ConfigParser()
    ini.read(client / 'DATA.INI')
    paths = [client / v for k, v in sorted(ini['Data'].items(), key=lambda x: int(x[0]))]
    grfs, evidence = {}, {}

    def resource(name):
        key = PREFIX + name
        path = client / key
        if path.is_file():
            data = path.read_bytes()
        else:
            data = None
            for path in paths:
                if path not in grfs:
                    grfs[path] = GrfFile(path)
                data = grfs[path].read(key.lower())
                if data is not None:
                    break
        if data is None:
            raise FileNotFoundError(key)
        evidence[key] = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}
        return data

    names = ['1238', '13412', '단검_검', '단검_검_검광']
    acts = {name: parse_act(resource(name + '.act')) for name in names}
    sprites = {name: Spr(resource(name + '.spr')) for name in names}

    def layer(name, action, frame):
        frames = acts[name]['actions'][action].frames
        if frame >= len(frames) or not frames[frame].layers:
            return None
        value = frames[frame].layers[0]
        count = sprites[name].n_indexed8 if value.sprite_type == 0 else sprites[name].n_bgra32
        return value if 0 <= value.sprite_index < count else None

    original = (ROOT / 'Inputs/DualWeaponAuthored/rigs/female-assassin-canonical.dwr3').read_bytes()
    rig = parse_rig_bytes(original)
    cells = {(r['family'], r['gender'], r['state'], r['phase'], r['direction'], r['frame'], r['hand']):
             tuple(vars(r['transform']).values()) for r in rig['records']}
    changes = []
    for record in rig['records']:
        if record['family'] or record['gender'] or record['state'] != 9:
            continue
        phase, direction, frame, hand = (record[k] for k in ('phase', 'direction', 'frame', 'hand'))
        t = record['transform']
        x, y = float(t.dx), float(t.dy)
        action = (80 if phase or t.metadata & 32 else 32) + direction
        source_frame = t.flags & 31
        delta = (0, 0)
        if not t.metadata & 8:
            # Reconstruct what the working current-resource compositor emits.
            # A native body packet owns replacement, otherwise a visible trail.
            if t.metadata & 16:
                base = layer('단검_검', 88 + direction, frame)
                if base is None:
                    base = layer('단검_검_검광', 88 + direction, frame)
                assert base is not None, (direction, frame)
                x += base.x
                y += base.y
            if hand == 0:
                dagger, sword = layer('1238', action, source_frame), layer('13412', action, source_frame)
                assert dagger and sword, (action, source_frame)
                # These exact native source cells use the same hand orientation.
                # Refuse an input variant requiring a different transform model.
                assert dagger.rotation == sword.rotation == 0
                assert dagger.scale_x == dagger.scale_y == sword.scale_x == sword.scale_y == 1
                assert dagger.mirror == sword.mirror
                dx, dy = dagger.x - sword.x, dagger.y - sword.y
                if t.flags & 64:
                    dx = -dx
                angle = math.radians(t.rotation)
                delta = (math.cos(angle)*dx - math.sin(angle)*dy,
                         math.sin(angle)*dx + math.cos(angle)*dy)
                x += delta[0]
                y += delta[1]
        # Actor targets remove dependence on the different pair25 guide center.
        nx, ny = round(x), round(y)
        assert -128 <= nx <= 127 and -128 <= ny <= 127
        value = (nx, ny, t.flags, t.metadata & ~16, t.rotation)
        cells[(0, 0, 6, phase, direction, frame, hand)] = value
        changes.append({'state': 6, 'phase': phase, 'direction': direction, 'frame': frame,
                        'hand': hand, 'source_action': action, 'source_frame': source_frame,
                        'reference_transform': vars(t), 'native_center_correction': delta,
                        'unrounded_actor_target': [x, y], 'output': value,
                        'status': 'derived_from_live_reference_pending_acceptance'})
        if phase == 0:
            # The user requests the same physical hand as in the working pair:
            # dagger uses pair28 hand1; sword uses pair28 hand0. Only held cells
            # are transferable: solo attack80 has a different body timeline.
            state = 0 if hand == 1 else 1
            value = (t.dx, t.dy, t.flags, t.metadata, t.rotation)
            assert not t.metadata & 16
            cells[(0, 0, state, 0, direction, frame, 0)] = value
            changes.append({'state': state, 'phase': 0, 'direction': direction, 'frame': frame,
                            'hand': 0, 'pair28_reference_hand': hand, 'output': value,
                            'status': 'exact_pair28_held_subset_pending_acceptance'})

    indices = [0] * rig['index_count']
    transforms, lookup = [], {}
    for key, value in sorted(cells.items()):
        if value not in lookup:
            transforms.append(value)
            lookup[value] = len(transforms)
        family, gender, state, phase, direction, frame, hand = key
        idx = dense_index(family, gender, state, 15, phase, direction, frame, hand)
        indices[idx] = lookup[value]
    payload = original[20:36] + struct.pack('<7680H', *indices)
    payload += b''.join(DWR3_TRANSFORM.pack(*t) for t in transforms)
    result = DWR3_HEADER.pack(b'DWR3', 3, 1, 15, 7680, len(transforms), zlib.crc32(payload)) + payload
    parsed = parse_rig_bytes(result)
    # Preserve every original cell except the explicitly replaced pair25 state.
    after = {(r['family'], r['gender'], r['state'], r['phase'], r['direction'], r['frame'], r['hand']):
             tuple(vars(r['transform']).values()) for r in parsed['records']}
    for r in rig['records']:
        key = tuple(r[k] for k in ('family', 'gender', 'state', 'phase', 'direction', 'frame', 'hand'))
        if key[2] != 6:
            assert after[key] == tuple(vars(r['transform']).values())
    output = ROOT / 'Inputs/DualWeaponAuthored/rigs/female-assassin-pair28-derived.dwr3'
    output.write_bytes(result)
    report = {'schema': 'pair28_pose_transfer/v1', 'base_sha256': hashlib.sha256(original).hexdigest(),
              'output_sha256': hashlib.sha256(result).hexdigest(), 'output_bytes': len(result),
              'resources': evidence, 'changed_cells': changes, 'live_acceptance': False,
              'status': 'live_rejected_historical_experiment_not_runtime_input',
              'checks': ['all original pair28 poses unchanged', 'all other dual-pair poses unchanged',
                         'all 96 visible main-dagger source cells valid with matching native orientation',
                         'pair25 packet deltas converted using the working pair28 native guide',
                         'off-only held is exact matching physical hand subset',
                         'solo attack timeline is not inferred from dual attack']}
    output.with_suffix('.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('output_sha256', 'output_bytes', 'checks')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    build(parser.parse_args().client)
