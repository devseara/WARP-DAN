import csv
import sys
import math
sys.path.insert(0, 'tools/dual_weapon_formats')
from act_reader import parse_act

ACT_PATH = 'Inputs/DualWeaponAuthored/accepted-act/female-assassin-pair28-attack-body-guide.act'
CSV_PATH = 'Inputs/DualWeaponAuthored/poses/female-assassin-pair28.csv'

with open(ACT_PATH, 'rb') as f:
    act = parse_act(f.read())

with open(CSV_PATH, newline='') as f:
    rows = [r for r in csv.DictReader(f) if r['phase'] == 'attack']

assert len(rows) == 128, len(rows)

# CSV keyed by (direction, frame, hand)
csv_map = {}
for r in rows:
    direction = int(r['source_action']) - 80
    frame = int(r['target_frame'])
    hand = int(r['physical_hand'])
    csv_map[(direction, frame, hand)] = (int(r['x']), int(r['y']))

assert len(csv_map) == 128

# ACT: action = 88 + direction, layer1 = pair_guide, layer2 = off-hand(dagger,hand=1), layer3 = main-hand(sword,hand=0)
raw_act = {}
layer1_abs = {}
for direction in range(8):
    action = act['actions'][88 + direction]
    assert len(action.frames) == 8
    for frame in range(8):
        layers = action.frames[frame].layers
        l1 = layers[1]
        l2 = layers[2]  # dagger / off-hand / hand=1
        l3 = layers[3]  # sword / main-hand / hand=0
        layer1_abs[(direction, frame)] = (l1.x, l1.y)
        raw_act[(direction, frame, 1)] = (l2.x, l2.y)
        raw_act[(direction, frame, 0)] = (l3.x, l3.y)

results = []  # (direction, frame, hand, csv_abs, raw_abs, correction)
for direction in range(8):
    for frame in range(8):
        l1x, l1y = layer1_abs[(direction, frame)]
        for hand in (0, 1):
            csv_dx, csv_dy = csv_map[(direction, frame, hand)]
            csv_abs = (l1x + csv_dx, l1y + csv_dy)
            raw_abs = raw_act[(direction, frame, hand)]
            corr = (csv_abs[0] - raw_abs[0], csv_abs[1] - raw_abs[1])
            results.append((direction, frame, hand, csv_abs, raw_abs, corr))

# --- Print all 128 cells ---
print('direction frame hand | csv_abs        raw_abs        correction   |mag|')
for direction, frame, hand, csv_abs, raw_abs, corr in results:
    mag = math.hypot(*corr)
    print('%9d %5d %4d | (%4d,%4d)  (%4d,%4d)  (%4d,%4d)  %6.2f' % (
        direction, frame, hand, csv_abs[0], csv_abs[1], raw_abs[0], raw_abs[1], corr[0], corr[1], mag))

# --- 1. Basic distribution ---
zero_count = sum(1 for r in results if r[5] == (0, 0))
mags = [math.hypot(*r[5]) for r in results]
nonzero_mags = [m for m in mags if m > 0]
print()
print('=== 1. Basic distribution ===')
print('total cells:', len(results))
print('exactly (0,0):', zero_count)
print('nonzero:', len(nonzero_mags))
if nonzero_mags:
    print('nonzero mean magnitude: %.3f px' % (sum(nonzero_mags) / len(nonzero_mags)))
    print('nonzero max magnitude: %.3f px' % max(nonzero_mags))
    print('nonzero min magnitude: %.3f px' % min(nonzero_mags))
# histogram buckets
buckets = [0, 1, 2, 5, 10, 20, 40, 10**9]
labels = ['0', '(0,1]', '(1,2]', '(2,5]', '(5,10]', '(10,20]', '(20,40]', '(40,+)']
counts = [0] * (len(buckets) - 1)
zero_bucket = 0
for m in mags:
    if m == 0:
        zero_bucket += 1
        continue
    for i in range(len(buckets) - 1):
        if buckets[i] < m <= buckets[i+1] if i > 0 else 0 < m <= buckets[i+1]:
            counts[i] += 1
            break
print('histogram: 0px=%d' % zero_bucket, list(zip(labels[1:], counts[1:])))

# --- 2. Per-frame mean/std across directions, per hand ---
print()
print('=== 2. Per-frame stats across directions (per hand) ===')
for hand in (0, 1):
    print('-- hand %d (%s) --' % (hand, 'sword/main' if hand == 0 else 'dagger/off'))
    for frame in range(8):
        vecs = [r[5] for r in results if r[2] == hand and r[1] == frame]
        xs = [v[0] for v in vecs]
        ys = [v[1] for v in vecs]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        # population std
        std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs) / len(xs))
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys) / len(ys))
        mags_f = [math.hypot(*v) for v in vecs]
        print('  frame %d: vectors=%s  mean=(%.2f,%.2f) std=(%.2f,%.2f) mag_mean=%.2f mag_std=%.2f mag_range=[%.1f,%.1f]' % (
            frame, vecs, mean_x, mean_y, std_x, std_y, sum(mags_f)/len(mags_f),
            math.sqrt(sum((m - sum(mags_f)/len(mags_f))**2 for m in mags_f)/len(mags_f)),
            min(mags_f), max(mags_f)))

# --- 3. Quantized unique values ---
print()
print('=== 3. Quantized correction vectors (nearest 1px = exact ints already; try nearest 2px, 4px) ===')
for q in (1, 2, 4, 8):
    uniq = {}
    for r in results:
        dx, dy = r[5]
        qx = round(dx / q) * q
        qy = round(dy / q) * q
        uniq.setdefault((qx, qy), []).append((r[0], r[1], r[2]))
    print('quantization=%dpx -> %d unique vectors' % (q, len(uniq)))
    if q in (1, 4):
        for vec, cells in sorted(uniq.items(), key=lambda kv: -len(kv[1])):
            print('   %s : count=%d cells=%s' % (vec, len(cells), cells))

# --- 4. Correlate magnitude with known reach frames ---
print()
print('=== 4. Correction magnitude vs frame index (all directions combined per hand) ===')
for hand in (0, 1):
    print('-- hand %d --' % hand)
    for frame in range(8):
        mags_f = [math.hypot(*r[5]) for r in results if r[2] == hand and r[1] == frame]
        print('  frame %d: mean_mag=%.2f max_mag=%.2f n_nonzero=%d/%d' % (
            frame, sum(mags_f)/len(mags_f), max(mags_f), sum(1 for m in mags_f if m > 0), len(mags_f)))

# --- 5. raw ACT reach per frame (for correlation) for reference ---
print()
print('=== raw ACT reach (distance from layer1/pair_guide) per frame, per hand, mean across directions ===')
for hand in (0, 1):
    print('-- hand %d --' % hand)
    for frame in range(8):
        reaches = []
        for direction in range(8):
            l1x, l1y = layer1_abs[(direction, frame)]
            rx, ry = raw_act[(direction, frame, hand)]
            reaches.append(math.hypot(rx - l1x, ry - l1y))
        print('  frame %d: mean_reach=%.2f min=%.2f max=%.2f' % (frame, sum(reaches)/len(reaches), min(reaches), max(reaches)))
