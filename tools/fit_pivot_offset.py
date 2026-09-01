"""
Fit a fixed (ox, oy) pivot offset relative to body_guide (layer0) such that
pivot(direction, frame) = body_absolute(direction, frame) + (ox, oy)
minimizes the across-direction variance of
dist(direction, frame, hand) = |hand_absolute(direction, frame, hand) - pivot(direction, frame)|,
averaged/summed over the 8 attack frames. Fit hand0 (main-hand) and hand1
(off-hand) separately. Compare against the null hypothesis offset (0,0)
(i.e. pivot == body_guide itself), and compare a single joint-across-frames
fit against 8 independent per-frame fits.

hand_absolute(direction, frame, hand) = layer1_absolute(direction, frame)
                                         + CSV(direction, frame, hand).x/y
(the CSV-reconstruction rule -- never the raw ACT layer2/layer3 value).
"""
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "dual_weapon_formats"))
from act_reader import parse_act  # noqa: E402

ROOT = Path(__file__).parent.parent
ACT_PATH = ROOT / "Inputs/DualWeaponAuthored/accepted-act/female-assassin-pair28-attack-body-guide.act"
CSV_PATH = ROOT / "Inputs/DualWeaponAuthored/poses/female-assassin-pair28.csv"

N_DIR = 8
N_FRAME = 8
ACT_ACTION_BASE = 88  # act_action = 88 + direction (established mapping)
CSV_SOURCE_ACTION_BASE = 80  # csv source_action = 80 + direction


def load_act_layers():
    data = ACT_PATH.read_bytes()
    act = parse_act(data)
    # body_absolute[dir][frame] = (x, y) of layer0
    # pair_absolute[dir][frame] = (x, y) of layer1
    body_absolute = np.zeros((N_DIR, N_FRAME, 2))
    pair_absolute = np.zeros((N_DIR, N_FRAME, 2))
    for d in range(N_DIR):
        action = act["actions"][ACT_ACTION_BASE + d]
        assert len(action.frames) == N_FRAME, (d, len(action.frames))
        for f in range(N_FRAME):
            layers = action.frames[f].layers
            l0 = layers[0]
            l1 = layers[1]
            body_absolute[d, f] = (l0.x, l0.y)
            pair_absolute[d, f] = (l1.x, l1.y)
    return body_absolute, pair_absolute


def load_csv_deltas():
    # csv_delta[hand][dir][frame] = (x, y)  from coordinate_mode=packet_delta rows
    csv_delta = np.zeros((2, N_DIR, N_FRAME, 2))
    seen = np.zeros((2, N_DIR, N_FRAME), dtype=bool)
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["coordinate_mode"] != "packet_delta":
                continue
            src_action = int(row["source_action"])
            if not (CSV_SOURCE_ACTION_BASE <= src_action < CSV_SOURCE_ACTION_BASE + N_DIR):
                continue
            d = src_action - CSV_SOURCE_ACTION_BASE
            f = int(row["target_frame"])
            hand = int(row["physical_hand"])
            csv_delta[hand, d, f] = (float(row["x"]), float(row["y"]))
            seen[hand, d, f] = True
    assert seen.all(), f"missing csv rows: {np.argwhere(~seen)}"
    return csv_delta


def objective_sum_variance(offset, body_absolute, hand_absolute):
    """Sum over frames of (variance across directions of dist), for one offset applied to all frames."""
    ox, oy = offset
    pivot = body_absolute + np.array([ox, oy])  # (N_DIR, N_FRAME, 2)
    dist = np.linalg.norm(hand_absolute - pivot, axis=2)  # (N_DIR, N_FRAME)
    per_frame_var = dist.var(axis=0)  # (N_FRAME,)
    return per_frame_var.sum(), dist


def grid_search(body_absolute, hand_absolute, lo=-60, hi=60, coarse_step=1.0, refine_steps=(0.2, 0.02)):
    best = None
    xs = np.arange(lo, hi + 1e-9, coarse_step)
    ys = np.arange(lo, hi + 1e-9, coarse_step)
    for ox in xs:
        for oy in ys:
            val, _ = objective_sum_variance((ox, oy), body_absolute, hand_absolute)
            if best is None or val < best[0]:
                best = (val, ox, oy)
    _, bx, by = best
    for step in refine_steps:
        span = step * 15
        xs = np.arange(bx - span, bx + span + 1e-9, step)
        ys = np.arange(by - span, by + span + 1e-9, step)
        for ox in xs:
            for oy in ys:
                val, _ = objective_sum_variance((ox, oy), body_absolute, hand_absolute)
                if val < best[0]:
                    best = (val, ox, oy)
        _, bx, by = best
    return best  # (objective_value, ox, oy)


def fit_single_frame_offset(body_f, hand_f, lo=-60, hi=60, coarse_step=1.0, refine_steps=(0.2, 0.02)):
    """Fit offset minimizing variance across directions for a single frame (body_f, hand_f: (N_DIR,2))."""
    best = None
    xs = np.arange(lo, hi + 1e-9, coarse_step)
    ys = np.arange(lo, hi + 1e-9, coarse_step)
    for ox in xs:
        for oy in ys:
            pivot = body_f + np.array([ox, oy])
            dist = np.linalg.norm(hand_f - pivot, axis=1)
            val = dist.var()
            if best is None or val < best[0]:
                best = (val, ox, oy)
    _, bx, by = best
    for step in refine_steps:
        span = step * 15
        xs = np.arange(bx - span, bx + span + 1e-9, step)
        ys = np.arange(by - span, by + span + 1e-9, step)
        for ox in xs:
            for oy in ys:
                pivot = body_f + np.array([ox, oy])
                dist = np.linalg.norm(hand_f - pivot, axis=1)
                val = dist.var()
                if val < best[0]:
                    best = (val, ox, oy)
        _, bx, by = best
    return best


def report_for_hand(hand_name, hand_idx, body_absolute, pair_absolute, csv_delta):
    hand_absolute = pair_absolute + csv_delta[hand_idx]  # (N_DIR, N_FRAME, 2)

    print(f"\n{'=' * 70}\nHAND: {hand_name} (physical_hand={hand_idx})\n{'=' * 70}")

    # --- NULL hypothesis: offset = (0,0), i.e. pivot == body_guide itself ---
    null_val, null_dist = objective_sum_variance((0.0, 0.0), body_absolute, hand_absolute)
    print("\n-- NULL offset (0,0) == plain body_guide --")
    print(f"{'frame':>5} {'mean_dist':>10} {'std_dist':>9} {'var_dist':>9}")
    for f in range(N_FRAME):
        d = null_dist[:, f]
        print(f"{f:5d} {d.mean():10.3f} {d.std():9.3f} {d.var():9.3f}")
    print(f"sum of per-frame variances (objective): {null_val:.3f}")

    # --- General fixed joint offset, fit across all 8 frames simultaneously ---
    joint_val, jox, joy = grid_search(body_absolute, hand_absolute)
    _, joint_dist = objective_sum_variance((jox, joy), body_absolute, hand_absolute)
    print(f"\n-- JOINT fitted offset (single ox,oy for all frames): ox={jox:.3f}, oy={joy:.3f} --")
    print(f"{'frame':>5} {'mean_dist':>10} {'std_dist':>9} {'var_dist':>9}")
    for f in range(N_FRAME):
        d = joint_dist[:, f]
        print(f"{f:5d} {d.mean():10.3f} {d.std():9.3f} {d.var():9.3f}")
    print(f"sum of per-frame variances (objective): {joint_val:.3f}")
    improvement = (1 - joint_val / null_val) * 100 if null_val else float("nan")
    print(f"Improvement over null: {improvement:.1f}% reduction in summed per-frame variance")

    # --- Independent per-frame fits (upper bound on how good a "pivot" could plausibly be) ---
    print("\n-- INDEPENDENT per-frame fitted offsets (different ox,oy per frame) --")
    per_frame_vals = []
    per_frame_offsets = []
    for f in range(N_FRAME):
        val, fox, foy = fit_single_frame_offset(body_absolute[:, f, :], hand_absolute[:, f, :])
        per_frame_vals.append(val)
        per_frame_offsets.append((fox, foy))
        print(f"  frame {f}: ox={fox:7.3f} oy={foy:7.3f}  var={val:8.3f}  std={val ** 0.5:7.3f}")
    per_frame_sum = sum(per_frame_vals)
    print(f"sum of per-frame variances at per-frame-optimal offsets: {per_frame_sum:.3f}")

    print("\n-- SUMMARY for this hand --")
    print(f"  null (0,0):                 sum_var={null_val:10.3f}  avg_std={np.sqrt(null_val / N_FRAME):7.3f}")
    print(f"  joint fit  (ox={jox:.2f},oy={joy:.2f}): sum_var={joint_val:10.3f}  avg_std={np.sqrt(joint_val / N_FRAME):7.3f}")
    print(f"  per-frame fits (8 offsets): sum_var={per_frame_sum:10.3f}  avg_std={np.sqrt(per_frame_sum / N_FRAME):7.3f}")
    gap = (1 - per_frame_sum / joint_val) * 100 if joint_val else float("nan")
    print(f"  joint fit is worse than per-frame-optimal by: {joint_val - per_frame_sum:.3f} sum_var "
          f"({(joint_val / per_frame_sum - 1) * 100 if per_frame_sum else float('nan'):.1f}% relatively)")
    ox_spread = [o[0] for o in per_frame_offsets]
    oy_spread = [o[1] for o in per_frame_offsets]
    print(f"  per-frame offset spread: ox in [{min(ox_spread):.2f},{max(ox_spread):.2f}], "
          f"oy in [{min(oy_spread):.2f},{max(oy_spread):.2f}]  "
          f"(vs joint ox={jox:.2f},oy={joy:.2f})")

    return {
        "null_val": null_val,
        "joint_val": joint_val,
        "joint_offset": (jox, joy),
        "per_frame_sum": per_frame_sum,
        "per_frame_offsets": per_frame_offsets,
    }


def main():
    body_absolute, pair_absolute = load_act_layers()
    csv_delta = load_csv_deltas()

    print("Loaded ACT:", ACT_PATH.name)
    print("Loaded CSV:", CSV_PATH.name)
    print(f"directions={N_DIR} frames={N_FRAME}")

    results = {}
    results["hand0_main"] = report_for_hand("hand0 (main-hand, sword, layer3)", 0, body_absolute, pair_absolute, csv_delta)
    results["hand1_off"] = report_for_hand("hand1 (off-hand, dagger, layer2)", 1, body_absolute, pair_absolute, csv_delta)

    print(f"\n{'=' * 70}\nOVERALL\n{'=' * 70}")
    for name, r in results.items():
        print(f"{name}: null_sum_var={r['null_val']:.2f} -> joint_sum_var={r['joint_val']:.2f} "
              f"(offset={r['joint_offset'][0]:.2f},{r['joint_offset'][1]:.2f})  "
              f"per_frame_best_sum_var={r['per_frame_sum']:.2f}")


if __name__ == "__main__":
    main()
