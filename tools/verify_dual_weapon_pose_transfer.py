"""Historical verifier of the LIVE-REJECTED raw-ACT pose-transfer experiment.

Its synthetic packet basis and disabled legacy core cannot prove native
placement. This is not a current acceptance gate. Run
verify_dual_weapon_native_basis.py for the corrected native projection tests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

from verify_dual_weapon_compositor import Machine, Resources, ROOT
from dual_weapon_formats.rig_tables import parse_rig_bytes


def summary(call, resource):
    packet = call['packet']
    index = next(key for key, value in resource['images'].items() if value[0] == call['image'])
    return {'resource': resource['name'], 'image': list(index),
            'center': [(packet[1]+packet[3])/2-400, (packet[0]+packet[2])/2-300],
            'size': [abs(packet[3]-packet[1]), abs(packet[2]-packet[0])],
            'angle': packet[7], 'mirror': packet[3]<packet[1]}


def capture(machine, stock, trail, action, frame):
    calls = []
    for resource in (stock, trail):
        result = machine.invoke(resource, action, frame, frame_wrap=True)
        if result is not None:
            assert result == 1
            calls.extend(machine.calls)
    return calls


def verify(client, baseline):
    resources = Resources(client)
    before, now, dual, solo = [Machine(resources, p) for p in (baseline, None, None, None)]
    sword, dagger, stock, trail = before.equip(28, 2, 1)
    nsword, ndagger, nstock, ntrail = now.equip(28, 2, 1)
    _, ddagger, dstock, dtrail = dual.equip(25, 1, 1)
    rig = parse_rig_bytes((ROOT/'Inputs/DualWeaponAuthored/rigs/female-assassin-canonical.dwr3').read_bytes())
    poses = {(r['phase'], r['direction'], r['frame'], r['hand']): r['transform']
             for r in rig['records'] if r['family']==r['gender']==0 and r['state']==9}
    records, pair28_checks, dd_checks = [], 0, 0
    max_error = 0.0
    off_checks, old_off_mismatches = 0, 0
    for phase, actionbase, frames in ((0,32,6),(1,88,8)):
        for direction in range(8):
            for frame in range(frames):
                action = actionbase + direction
                reference = capture(before, stock, trail, action, frame)
                current = capture(now, nstock, ntrail, action, frame)
                old = [summary(c, sword if c['palette']==sword['spr']+0x110 else dagger) for c in reference]
                new = [summary(c, nsword if c['palette']==nsword['spr']+0x110 else ndagger) for c in current]
                assert old == new, ('working pair28 changed', action, frame)
                pair28_checks += len(old)
                actual = [summary(c, ddagger) for c in capture(dual, dstock, dtrail, action, frame)]
                assert len(actual) == len(old)
                for expected, got in zip(old, actual):
                    hand = 0 if expected['resource']=='13412' else 1
                    pose = poses[(phase,direction,frame,hand)]
                    sa = (80 if phase or pose.metadata&32 else 32)+direction
                    sf = pose.flags&31
                    source = dagger['layers'][(sa,sf)][1]
                    cx, cy = expected['center']
                    if hand == 0:
                        ref = sword['layers'][(sa,sf)][1]
                        # Independent from generated rig/report: derive the
                        # expected offset directly from the original ACTs and
                        # working emitted packet, using native clockwise rotation.
                        dx, dy = source.x-ref.x, source.y-ref.y
                        if pose.flags&64:
                            dx = -dx
                        angle = math.radians(pose.rotation)
                        cx += dx*math.cos(angle)-dy*math.sin(angle)
                        cy += dx*math.sin(angle)+dy*math.cos(angle)
                    error = max(abs(got['center'][0]-cx), abs(got['center'][1]-cy))
                    assert error <= 0.5001, (action,frame,hand,got,[cx,cy])
                    max_error = max(max_error,error)
                    assert got['angle']==expected['angle'] and got['mirror']==expected['mirror']
                    assert got['image']==[source.sprite_type,source.sprite_index]
                    image = dagger['images'][(source.sprite_type,source.sprite_index)][1]
                    assert got['size']==[image.width*source.scale_x,image.height*source.scale_y]
                    dd_checks += 1
                    records.append({'phase':phase,'direction':direction,'frame':frame,'hand':hand,
                                    'expected_center_unrounded':[cx,cy],'output':got,'error':error})
                if phase == 0:
                    for weapon_type, name in ((1,'1238'),(2,'13412')):
                        _, original, solo_stock, solo_trail = solo.equip(25,weapon_type,weapon_type,off_only=True)
                        # Solo transition changes resource bindings, not body
                        # held action/frame. It must be the exact pair28 subset.
                        output = capture(solo,solo_stock,solo_trail,action,frame)
                        result = [summary(c,original) for c in output]
                        target = [entry for entry in old if entry['resource']==name]
                        assert result == target, ('off-only differs from working hand',action,frame,name,result,target)
                        off_checks += len(result)
    # Demonstrate that the old off-only transfer does NOT satisfy this oracle.
    for weapon_type, name in ((1,'1238'),(2,'13412')):
        legacy = Machine(resources,baseline)
        _, original, solo_stock, solo_trail = legacy.equip(25,weapon_type,weapon_type,off_only=True)
        output = capture(legacy,solo_stock,solo_trail,32,0)
        reference = capture(before,stock,trail,32,0)
        target = [summary(c,sword if name=='13412' else dagger) for c in reference
                  if c['palette']==(sword if name=='13412' else dagger)['spr']+0x110]
        old_off_mismatches += [summary(c,original) for c in output] != target
    assert old_off_mismatches == 2 and off_checks == 96
    assert pair28_checks == dd_checks == 208
    result = {'baseline_payload_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
              'payload_sha256':hashlib.sha256((ROOT/'Inputs/DualWeaponRuntime/compositor.dwcp').read_bytes()).hexdigest(),
              'method':'Emitted x86 vs working emitted pair28; native ACT source-center correspondence',
              'pair28_draws_unchanged':pair28_checks,'dagger_dagger_draws_verified':dd_checks,
              'off_only_held_draws_exactly_matching_reference':off_checks,
              'old_off_only_types_rejected_by_geometry_oracle':old_off_mismatches,
              'maximum_center_quantization_error_px':max_error,'live_acceptance':False,
              'off_only_solo_attack':'native transfer unchanged; dual attack timeline not transplanted',
              'checks':['source image index','center','angle','mirror','dimensions','draw order','hidden cells',
                        'working pair28 output unchanged','original image/palette identity'], 'records':records}
    path=ROOT/'docs/evidence/dual-weapon-pose-transfer-20260905.json'
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,default=ROOT/'Outputs/dual_weapon_resource_build/before-placement-fix/compositor.dwcp')
    args=parser.parse_args()
    verify(args.client,args.baseline)
