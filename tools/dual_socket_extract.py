"""
dual_socket_extract.py

HISTORICAL PAIR-GUIDE EXPORT: these are weapon-center guide origins, NOT
anatomical hand sockets. This CSV is not used by the pixel-grip compositor.
See docs/dual-weapon-grip-placement-20260905.md.

Extracts a per-(family,gender,phase,direction,frame) "socket" position table
from the accepted-act dual-wield guide file, for the new
socket + fixed-per-view-hilt-landmark composition model.

Socket source layer
--------------------
The accepted-act file carries 4 layers per frame:
    layer 0 = body_guide   (torso/body anchor -- NOT used here)
    layer 1 = pair_guide   (the anchor the weapon layers are authored against)
    layer 2 = reference dagger sprite (reference_role=1, view=34; not invariant anatomy)
    layer 3 = reference sword sprite  (reference_role=0, view=45; not invariant anatomy)

Report 1 ("Dual-Wield Layer<->CSV Correspondence") established empirically
(bit-exact at frame 0/2 in all 4 sampled directions) that the pose CSV's
`packet_delta` x/y for both hands is `layer_weapon.(x,y) - layer1.(x,y)`,
i.e. the weapon position is authored as a delta *against layer 1
(pair_guide)*, not against layer 0 (body_guide). Layer 0 was shown in that
report to track the torso and sit persistently far from either weapon layer
or their midpoint.

The task description's own parenthetical ("body_guide layer, or whatever
the first report determined is the right source") explicitly defers to that
finding, so this script extracts layer 1 (pair_guide), NOT layer 0
(body_guide), as the per-cell socket position. This is a deliberate,
documented deviation from the literal "body_guide" wording, made because
report 1's numeric evidence points at layer 1.

Usage:
    python tools/dual_socket_extract.py
"""
import csv
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dual_weapon_formats'))
from act_reader import parse_act  # noqa: E402

ACT_PATH = os.path.join('Inputs', 'DualWeaponAuthored', 'accepted-act',
                         'female-assassin-pair28-attack-body-guide.act')
OUT_PATH = os.path.join('Inputs', 'DualWeaponAuthored', 'sockets',
                         'female-assassin-attack.csv')

ATTACK_ACTION_BASE = 88  # action 88+direction = attack action group for `direction`
SOCKET_LAYER_INDEX = 1   # layer 1 = pair_guide (see module docstring)
NUM_DIRECTIONS = 8
NUM_FRAMES = 8


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    act_path = os.path.join(repo_root, ACT_PATH)
    out_path = os.path.join(repo_root, OUT_PATH)

    with open(act_path, 'rb') as f:
        raw = f.read()
    source_sha256 = hashlib.sha256(raw).hexdigest()

    act = parse_act(raw)
    actions = act['actions']
    assert len(actions) >= ATTACK_ACTION_BASE + NUM_DIRECTIONS, (
        'expected at least %d actions, got %d' % (ATTACK_ACTION_BASE + NUM_DIRECTIONS, len(actions)))

    rows = []
    for direction in range(NUM_DIRECTIONS):
        action = actions[ATTACK_ACTION_BASE + direction]
        assert len(action.frames) == NUM_FRAMES, (
            'action %d: expected %d frames, got %d' % (
                ATTACK_ACTION_BASE + direction, NUM_FRAMES, len(action.frames)))
        for frame in range(NUM_FRAMES):
            layers = action.frames[frame].layers
            assert len(layers) >= 2, 'action %d frame %d: expected >=2 layers, got %d' % (
                ATTACK_ACTION_BASE + direction, frame, len(layers))
            socket_layer = layers[SOCKET_LAYER_INDEX]
            rows.append({
                'family': 0,
                'gender': 0,
                'phase': 'attack',
                'direction': direction,
                'frame': frame,
                'x': socket_layer.x,
                'y': socket_layer.y,
                'coordinate_mode': 'pair_guide_absolute',
                'provenance': 'female-assassin-pair28-attack-body-guide.act:action%d:frame%d:layer1(pair_guide)' % (
                    ATTACK_ACTION_BASE + direction, frame),
                'source_sha256': source_sha256,
            })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ['family', 'gender', 'phase', 'direction', 'frame', 'x', 'y',
                  'coordinate_mode', 'provenance', 'source_sha256']
    with open(out_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print('wrote %d socket rows to %s' % (len(rows), out_path))
    print('source sha256: %s' % source_sha256)


if __name__ == '__main__':
    main()
