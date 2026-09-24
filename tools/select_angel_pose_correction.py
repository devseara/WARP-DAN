"""Select complete corrected drawings without shifting unaffected sheet cells."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from refine_clan_combat_necks import components
from import_full_swordman_art import extract


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path, batch):
    pixels = np.array(Image.open(path).convert('RGBA'))
    rgb = pixels[:, :, :3].astype(int)
    pink = (rgb[:, :, 0] > 160) & (rgb[:, :, 2] > 145) & (rgb[:, :, 1] < 120)
    marks = [g for g in components(pink & (pixels[:, :, 3] > 64)) if len(g) >= 20]
    assert len(marks) == batch['cells'], (path, 'marker count', len(marks))
    marks.sort(key=lambda g: float(g[:, 0].mean()))
    ordered = []
    cols = batch['columns']
    for i in range(0, len(marks), cols):
        ordered.extend(sorted(marks[i:i + cols], key=lambda g: float(g[:, 1].mean())))
    centers = np.array([[g[:, 1].mean(), g[:, 0].mean()] for g in ordered])
    expected = np.array([np.array(p['marker_in_cell']) + np.array([p['cell'] % cols, p['cell'] // cols]) * batch['tile_size'] + [0, 340] for p in batch['poses']])
    ex, got = expected.mean(axis=0), centers.mean(axis=0)
    scale = float(((expected - ex) * (centers - got)).sum() / ((expected - ex) ** 2).sum())
    residual = np.linalg.norm(centers - ((expected - ex) * scale + got), axis=1)
    green = (rgb[:, :, 1] > 95) & (rgb[:, :, 1] - rgb[:, :, 0] > 48) & (rgb[:, :, 1] - rgb[:, :, 2] > 48)
    clean = pixels.copy()
    clean[pink | green | (pixels[:, :, 3] <= 16)] = 0
    bodies = [g for g in components(clean[:, :, 3] > 0) if len(g) > 1000]
    assert len(bodies) == batch['cells'], (path, 'body count', len(bodies))
    row_y = [centers[i:i + cols, 1].mean() for i in range(0, len(centers), cols)]
    selected = {}
    for group in bodies:
        x, y = group[:, 1].mean(), group[:, 0].mean()
        row = int(np.searchsorted(row_y, y) - 1)
        assert 0 <= row < batch['rows']
        candidates = centers[row * cols:min((row + 1) * cols, len(centers))]
        cell = row * cols + int(np.argmin(abs(candidates[:, 0] - x)))
        assert cell not in selected
        selected[cell] = group
    assert set(selected) == set(range(batch['cells']))
    return pixels, clean, ordered, centers, scale, residual, selected


def run(work, sex, name, base_name, edited_name, cells):
    work = work.resolve()
    def local(name):
        path = (work / name).resolve()
        assert path.is_relative_to(work), path
        return path
    feedback = work / 'user-review.json'
    if feedback.exists():
        assert json.loads(feedback.read_text(encoding='utf8')).get('status') != 'accepted'
    plan = json.loads((work / 'art-plan.json').read_text(encoding='utf8'))
    batch = next(b for b in plan['batches'] if (b['sex'], b['name']) == (sex, name))
    base_path, edited_path = local(base_name), local(edited_name)
    base, _, base_marks, base_centers, base_scale, base_error, base_bodies = inspect(base_path, batch)
    _, edited, _, edited_centers, edited_scale, edit_error, edit_bodies = inspect(edited_path, batch)
    assert base_error.max() < 5, ('Base grid is not valid', base_error.tolist())
    assert set(cells) <= set(base_bodies)
    scale = base_scale / edited_scale
    assert .8 < scale < 1.25
    output = Image.fromarray(base.copy())
    details = []
    for cell in cells:
        original = base_bodies[cell]
        y0, x0 = original.min(axis=0)
        y1, x1 = original.max(axis=0) + 1
        erase = (max(0, int(x0) - 6), max(0, int(y0) - 6), min(output.width, int(x1) + 6), min(output.height, int(y1) + 6))
        output.paste((0, 0, 0, 0), erase)
        group = edit_bodies[cell]
        ey0, ex0 = group.min(axis=0)
        ey1, ex1 = group.max(axis=0) + 1
        cut = np.zeros((ey1 - ey0, ex1 - ex0, 4), np.uint8)
        yy, xx = group[:, 0], group[:, 1]
        cut[yy - ey0, xx - ex0] = edited[yy, xx]
        image = Image.fromarray(cut)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.NEAREST)
        corner = np.rint(base_centers[cell] - (edited_centers[cell] - [ex0, ey0]) * scale).astype(int)
        assert corner.min() >= 0 and corner[0] + image.width < output.width and corner[1] + image.height < output.height
        output.alpha_composite(image, tuple(corner.tolist()))
        details.append(dict(cell=cell, native_sprite=batch['poses'][cell]['sprite'], selected_source_bounds=[int(ex0), int(ey0), int(ex1), int(ey1)], placed_at=corner.tolist()))
    after = np.asarray(output)
    for cell, group in base_bodies.items():
        if cell not in cells:
            assert np.array_equal(after[group[:, 0], group[:, 1]], base[group[:, 0], group[:, 1]]), ('Unchanged body modified', cell)
    for group in base_marks:
        assert np.array_equal(after[group[:, 0], group[:, 1]], base[group[:, 0], group[:, 1]]), 'Guide changed'
    target = work / 'art' / sex / (name + '.png')
    output.save(target)
    _, checks = extract(batch, work)
    records_path = work / 'generation-records.json'
    records = json.loads(records_path.read_text(encoding='utf8'))
    row = next(r for r in records if (r['sex'], r['name']) == (sex, name))
    selection = dict(base=base_name, base_sha256=digest(base_path), edited=edited_name, edited_sha256=digest(edited_path),
                     uniform_source_resolution_ratio=scale, edited_marker_residual=edit_error.tolist(),
                     base_marker_residual=base_error.tolist(), unchanged_bodies_preserved=True, original_guides_preserved=True, selections=details)
    row.update(sha256=digest(target), pose_selection=selection)
    records_path.write_text(json.dumps(records, indent=2) + '\n', encoding='utf8')
    audit_path = work / 'import-audit.json'
    audit = json.loads(audit_path.read_text(encoding='utf8'))
    audit = [r for r in audit if (r['sex'], r['batch']) != (sex, name)]
    audit.append(dict(sex=sex, batch=name, status='registered', sha256=row['sha256'], checks=checks))
    audit_path.write_text(json.dumps(audit, indent=2) + '\n', encoding='utf8')
    (work / f'{sex}-{name}-pose-selection.json').write_text(json.dumps(selection, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(status='registered_selected_correction', sex=sex, batch=name, poses=len(checks), corrected_cells=cells, other_pose_pixels_preserved=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--sex', required=True, choices=('male', 'female'))
    parser.add_argument('--batch', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--edited', required=True)
    parser.add_argument('--cells', required=True)
    args = parser.parse_args()
    run(args.work, args.sex, args.batch, args.base, args.edited, [int(x) for x in args.cells.split(',')])
