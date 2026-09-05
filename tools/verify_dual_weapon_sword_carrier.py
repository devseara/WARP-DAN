"""Verify held pair28 reference reconstruction from a native generic sword packet.

Both packet inputs execute native C40C20. The expected output executes the
accepted legacy core with the genuine pair28 resources. The actual output uses
the current compositor with generic sword channel 5 as its owned stock resource.
Origin/attachment inputs are common explicit fixtures; this is not live visual
acceptance or proof that a new weapon's grip has been registered correctly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from verify_dual_weapon_compositor import Resources, ROOT
from verify_dual_weapon_native_basis import (
    NativeLegacyMachine, NativeMachine, invoke_native, same_geometry,
)
from verify_dual_weapon_native_projection import NativeProjector


def run(client, executable, payload, output):
    resources = Resources(client)
    projector = NativeProjector(executable)
    reference = NativeLegacyMachine(resources, payload)
    current = NativeMachine(resources, payload)
    current.equip(28, 2, 1)
    carrier = current.load('검')
    # Only the native carrier changes. Original retained source art remains
    # the accepted 13412/1238 pair so this isolates carrier reconstruction.
    current.w(current.row + 36, carrier['act'])
    current.w(current.slot + 20, carrier['spr'])
    cases = []
    maximum = 0.0
    for unit in (1.0, 2.3423):
        for actor_angle in (0, 15, -90):
            for direction in range(8):
                for frame in range(6):
                    action = 32 + direction
                    expected = invoke_native(reference, projector, reference.stock,
                                             action, frame, unit, actor_angle=actor_angle)
                    actual = invoke_native(current, projector, carrier,
                                           action, frame, unit, actor_angle=actor_angle)
                    assert expected and expected['handled'] == 1, expected
                    assert actual and actual['handled'] == 1, actual
                    assert len(actual['draws']) == len(expected['draws']) == 2
                    for a, e in zip(actual['draws'], expected['draws']):
                        assert same_geometry(a, e), (direction, frame, unit, actor_angle, a, e)
                        maximum = max(maximum, *(abs(x-y) for x, y in zip(a['geometry'], e['geometry'])))
                    cases.append({'unit': unit, 'actor_angle': actor_angle,
                                  'direction': direction, 'frame': frame,
                                  'actual_native_carrier_layer': list(current.native_layer(carrier, action, frame)),
                                  'expected_legacy_pair28': expected['draws'],
                                  'actual_from_sword_carrier': actual['draws']})
    report = {
        'schema': 'dual_weapon_sword_carrier/v1',
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'native_pe_sha256': projector.sha256,
        'payload': str(payload.resolve()),
        'payload_sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
        'case_count': len(cases), 'all_cases_passed': True,
        'maximum_geometry_error': maximum, 'resources': resources.evidence,
        'cases': cases,
        'limits': [
            'Native projection origin is explicitly supplied equally for both carriers; no live camera/body attachment is emulated.',
            'Only held actions 32 through 39 and frames 0 through 5 are tested. Native phase 80 is not substituted with phase 88.',
            'Accepted reference original art remains 13412/1238; this isolates packet-carrier independence, not a new weapon grip.',
            'The native selector and resource loading owner are outside this fixture.',
            'No executable, client asset or live process is modified.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('native_pe_sha256', 'payload_sha256', 'case_count', 'all_cases_passed', 'maximum_geometry_error')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/evidence/dual-weapon-sword-carrier-20260905.json')
    args = parser.parse_args()
    run(args.client, args.exe, args.payload, args.output)
