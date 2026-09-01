"""
Independent re-verification script (written from scratch, does NOT import
tools/dual_weapon_formats/act_reader.py or correction_analysis.py).

Parses the ACT file directly against the standard RO ACT binary layout and
the pose CSV directly with csv.DictReader, then recomputes
correction(direction, frame, hand) = CSV_hand_absolute - raw_ACT_hand_absolute
for a spot-check sample plus the full 128-cell table, and checks the prior
agent's specific numeric/structural claims against it.
"""
import csv
import struct
import math

ACT_PATH = 'Inputs/DualWeaponAuthored/accepted-act/female-assassin-pair28-attack-body-guide.act'
CSV_PATH = 'Inputs/DualWeaponAuthored/poses/female-assassin-pair28.csv'


def parse_act_actions(data):
    assert data[0:2] == b'AC'
    ver_minor, ver_major = data[2], data[3]
    version = ver_major + ver_minor / 10.0
    action_count, = struct.unpack_from('<H', data, 4)
    pos = 16
    actions = []
    for _ai in range(action_count):
        frame_count, = struct.unpack_from('<i', data, pos)
        pos += 4
        frames = []
        for _fi in range(frame_count):
            pos += 32  # two range rects (attack/attack range boxes), 8 ints
            layer_count, = struct.unpack_from('<i', data, pos)
            pos += 4
            layers = []
            for _li in range(layer_count):
                x, y, sprite_index, mirror_raw = struct.unpack_from('<iiii', data, pos)
                pos += 16
                if version >= 2.0:
                    pos += 4  # RGBA color
                    pos += 4  # scale_x float
                    if version >= 2.4:
                        pos += 4  # scale_y float
                    pos += 4  # rotation int
                    pos += 4  # sprite_type int
                    if version >= 2.5:
                        pos += 8  # width, height ints
                layers.append((x, y, sprite_index, mirror_raw))
            if version >= 2.0:
                pos += 4  # sound_id
            # not loading anchors; we don't need them and this ACT's actions
            # of interest (88-95) frames are checked to have consistent
            # layer counts below, so anchor skipping would only matter if
            # version>=2.3 has anchors -- handle that to keep pos correct.
            if version >= 2.3:
                anchor_count, = struct.unpack_from('<i', data, pos)
                pos += 4
                pos += 16 * anchor_count
            frames.append(layers)
        actions.append(frames)
    return actions, version


def main():
    with open(ACT_PATH, 'rb') as f:
        act_data = f.read()
    actions, version = parse_act_actions(act_data)
    print('ACT version:', version, 'action_count:', len(actions))

    with open(CSV_PATH, newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['phase'] == 'attack']
    print('attack rows:', len(rows))
    assert len(rows) == 128

    csv_map = {}
    for r in rows:
        direction = int(r['source_action']) - 80
        frame = int(r['target_frame'])
        hand = int(r['physical_hand'])
        csv_map[(direction, frame, hand)] = (int(r['x']), int(r['y']))
    assert len(csv_map) == 128

    # Build raw ACT absolute positions per (direction, frame, hand) and
    # layer1 (pair guide) absolute per (direction, frame).
    layer1_abs = {}
    raw_act = {}
    for direction in range(8):
        action_idx = 88 + direction
        frames = actions[action_idx]
        assert len(frames) == 8, (direction, len(frames))
        for frame in range(8):
            layers = frames[frame]
            assert len(layers) >= 4, (direction, frame, len(layers))
            l1 = layers[1]
            l2 = layers[2]  # hand=1 (dagger/off-hand) per prior agent's claim
            l3 = layers[3]  # hand=0 (sword/main-hand) per prior agent's claim
            layer1_abs[(direction, frame)] = (l1[0], l1[1])
            raw_act[(direction, frame, 1)] = (l2[0], l2[1])
            raw_act[(direction, frame, 0)] = (l3[0], l3[1])

    results = {}
    for direction in range(8):
        for frame in range(8):
            l1x, l1y = layer1_abs[(direction, frame)]
            for hand in (0, 1):
                cdx, cdy = csv_map[(direction, frame, hand)]
                csv_abs = (l1x + cdx, l1y + cdy)
                raw_abs = raw_act[(direction, frame, hand)]
                corr = (csv_abs[0] - raw_abs[0], csv_abs[1] - raw_abs[1])
                results[(direction, frame, hand)] = (csv_abs, raw_abs, corr)

    # ---- Print full table ----
    print()
    print('dir frame hand | csv_abs        raw_abs        correction   |mag|')
    for direction in range(8):
        for frame in range(8):
            for hand in (0, 1):
                csv_abs, raw_abs, corr = results[(direction, frame, hand)]
                mag = math.hypot(*corr)
                print('%3d %5d %4d | (%4d,%4d)  (%4d,%4d)  (%4d,%4d)  %6.2f' % (
                    direction, frame, hand, csv_abs[0], csv_abs[1],
                    raw_abs[0], raw_abs[1], corr[0], corr[1], mag))

    # ---- Basic distribution ----
    zero = sum(1 for v in results.values() if v[2] == (0, 0))
    nonzero_mags = [math.hypot(*v[2]) for v in results.values() if v[2] != (0, 0)]
    print()
    print('=== distribution ===')
    print('total', len(results), 'zero', zero, 'nonzero', len(nonzero_mags))
    if nonzero_mags:
        print('nonzero mean %.3f max %.3f min %.3f' % (
            sum(nonzero_mags) / len(nonzero_mags), max(nonzero_mags), min(nonzero_mags)))

    # ---- distinct exact vectors ----
    uniq = {}
    for k, v in results.items():
        uniq.setdefault(v[2], []).append(k)
    print()
    print('distinct exact correction vectors:', len(uniq))

    # ---- frame 0/1/2 all-zero check ----
    f012_nonzero = [(k, v[2]) for k, v in results.items() if k[1] in (0, 1, 2) and v[2] != (0, 0)]
    print('frames 0,1,2 nonzero cells:', f012_nonzero)

    # ---- direction pairing check {0,1}{2,3}{4,5}{6,7} for hand1, frames 3-7 ----
    print()
    print('=== direction-pair check (hand=1) frames 3-7 ===')
    pairs = [(0, 1), (2, 3), (4, 5), (6, 7)]
    for frame in range(3, 8):
        for (da, db) in pairs:
            ca = results[(da, frame, 1)][2]
            cb = results[(db, frame, 1)][2]
            print('frame %d pair(%d,%d) hand1: %s vs %s match=%s' % (
                frame, da, db, ca, cb, ca == cb))

    # ---- hand0 vs hand1 identical check at frames 6,7 ----
    print()
    print('=== hand0 vs hand1 identical check, frames 6-7, all directions ===')
    for frame in (6, 7):
        for direction in range(8):
            c0 = results[(direction, frame, 0)][2]
            c1 = results[(direction, frame, 1)][2]
            print('dir %d frame %d: hand0=%s hand1=%s match=%s' % (direction, frame, c0, c1, c0 == c1))

    # ---- reach correlation, hand0 and hand1, using layer1 distance ----
    print()
    print('=== reach vs correction magnitude, per hand, per frame (mean across directions) ===')
    for hand in (0, 1):
        reach_by_frame = {}
        mag_by_frame = {}
        for frame in range(8):
            reaches = []
            mags = []
            for direction in range(8):
                l1x, l1y = layer1_abs[(direction, frame)]
                rx, ry = raw_act[(direction, frame, hand)]
                reaches.append(math.hypot(rx - l1x, ry - l1y))
                mags.append(math.hypot(*results[(direction, frame, hand)][2]))
            reach_by_frame[frame] = sum(reaches) / len(reaches)
            mag_by_frame[frame] = sum(mags) / len(mags)
        print('hand', hand)
        for frame in range(8):
            print('  frame %d: mean_reach=%.2f mean_corr_mag=%.2f' % (frame, reach_by_frame[frame], mag_by_frame[frame]))

        # Pearson r across all 64 cells (direction,frame) for this hand
        xs = []
        ys = []
        for direction in range(8):
            for frame in range(8):
                l1x, l1y = layer1_abs[(direction, frame)]
                rx, ry = raw_act[(direction, frame, hand)]
                reach = math.hypot(rx - l1x, ry - l1y)
                mag = math.hypot(*results[(direction, frame, hand)][2])
                xs.append(reach)
                ys.append(mag)
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
        sy = math.sqrt(sum((y - my) ** 2 for y in ys))
        r = cov / (sx * sy) if sx > 0 and sy > 0 else float('nan')
        print('  Pearson r (reach vs |correction|), hand %d, n=%d: %.3f' % (hand, n, r))


if __name__ == '__main__':
    main()
