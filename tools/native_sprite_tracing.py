"""Locked native canvases and reviewed paint layers for new Angel job artwork."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from build_registered_angel_job import ROOT, load, save, digest, render_source
from review_original_job_directions import native_context
from review_full_swordman_set import ORIGIN, body, head
from prepare_full_swordman_art import LABELS
from fix_archer_design_alignment import neck_point

LANDMARKS = ('neck', 'left_shoulder', 'right_shoulder', 'left_elbow',
    'right_elbow', 'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
    'left_knee', 'right_knee', 'left_ankle', 'right_ankle', 'left_sole', 'right_sole')


def prepare(job, work):
    points = load(work / 'neck-landmarks.json')
    lookup = {(r['sex'], r['sprite']): r for r in points}
    manifest_path = work / 'native-trace.json'
    existing = load(manifest_path) if manifest_path.exists() else None
    old = {(r['sex'], r['sprite']): r for r in existing['poses']} if existing else {}
    refs = load(work / 'refs/head-neck-reference.json')
    rows, data, pins = [], {}, []
    images_dir = work / 'trace-reference/images'
    images_dir.mkdir(parents=True, exist_ok=True)

    def reference(image):
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        content = buffer.getvalue()
        sha = hashlib.sha256(content).hexdigest()
        path = images_dir / (sha + '.png')
        if path.exists():
            assert path.read_bytes() == content, ('Native reference changed', path)
        else:
            path.write_bytes(content)
        return path.relative_to(work).as_posix(), sha

    for sex in ('male', 'female'):
        src, spr, native, heads, ha = native_context(job, sex)
        for name in ('body.spr', 'body.act', 'head.spr', 'head.act'):
            pins.append(dict(path=(src / name).relative_to(ROOT).as_posix(), sha256=digest(src / name)))
        native_poses, by_index = {}, {}
        for point in (r for r in points if r['sex'] == sex):
            index, ai, fi = point['sprite'], point['action'], point['frame']
            original = body(sex, ai, fi, job=job)
            native_poses[index] = original
            path, sha = reference(original)
            paint = work / 'paint-layers' / sex / f'{index:03}.png'
            paint.parent.mkdir(parents=True, exist_ok=True)
            if not paint.exists():
                paint.write_bytes((work / point['source_pose']).read_bytes())
            landmarks = {key: dict(visibility='unmarked', native=None, paint=None, note='') for key in LANDMARKS}
            target = neck_point(refs, sex, native, heads, ha, ai, fi).tolist()
            landmarks['neck'].update(visibility='visible', native=target, paint=point['collar_point'])
            row = dict(sex=sex, sprite=index, action=ai, frame=fi,
                native_canvas=path, native_sha256=sha, paint_layer=paint.relative_to(work).as_posix(),
                landmarks=landmarks, reviewed=False, reviewed_paint_sha256=None,
                adjacent_frames_reviewed=False, volume_and_occlusion_reviewed=False, review_note='')
            previous = old.get((sex, index))
            if previous:
                assert previous['native_sha256'] == sha, (sex, index, 'Native canvas changed; create a new candidate')
                for key in ('landmarks', 'reviewed', 'reviewed_paint_sha256', 'adjacent_frames_reviewed', 'volume_and_occlusion_reviewed', 'review_note'):
                    row[key] = previous[key]
                if previous['reviewed_paint_sha256'] != digest(paint):
                    row['reviewed'] = row['adjacent_frames_reviewed'] = row['volume_and_occlusion_reviewed'] = False
            rows.append(row)
            by_index[index] = row
        actions = []
        for ai, frames in enumerate(native.actions):
            frame_rows = []
            for fi, frame in enumerate(frames):
                active = [l for l in frame.layers if l.index >= 0]
                assert len(active) == 1
                layer = active[0]
                assert layer.sx == layer.sy == 1 and layer.angle == 0, ('Unprofiled native transform', sex, ai, fi)
                row, point = by_index[layer.index], lookup[sex, layer.index]
                # Prove outfit placement replays native pixels exactly, including
                # mirrored odd-width images. No crop recentering or per-frame fit.
                replay = render_source(native_poses[layer.index], point, frame, native, spr)
                original = body(sex, ai, fi, job=job)
                assert replay.tobytes() == original.tobytes(), (sex, ai, fi, 'Native replay differs')
                first = native.actions[row['action']][row['frame']].layers[0]
                raw = spr.images[layer.index]
                dx = ((first.x + layer.x - 2*(raw.width//2) + raw.width) if layer.mirror else layer.x-first.x)*4
                native_path, _ = reference(original)
                head_path, _ = reference(head(sex, ai, fi, job=job))
                frame_rows.append(dict(sprite=layer.index, native=native_path, head=head_path,
                    canonical_native=row['native_canvas'], paint=row['paint_layer'],
                    mirror=bool(layer.mirror), dx=dx, dy=(layer.y-first.y)*4, reviewed=row['reviewed']))
            actions.append(dict(action=ai, group=LABELS[ai//8], ms=round(native.speeds[ai]*25), frames=frame_rows))
        data[sex] = dict(actions=actions)
    if existing:
        assert existing['native_pins'] == pins, 'Native inputs changed; create a new candidate'
    save(manifest_path, dict(schema=1, job=job, method='locked_native_canvas_redress',
        canvas_size=[640, 640], origin=list(ORIGIN), output_pixels_per_native_pixel=4,
        anatomical_tolerance_native=.5, native_pins=pins, poses=rows))
    template = (ROOT / 'tools/native_sprite_trace_review.html').read_text(encoding='utf8')
    (work / 'native-trace-review.html').write_text(template.replace('__JOB__', job.title()).replace('__DATA__', json.dumps(data)), encoding='utf8')
    proof = dict(job=job, status='native_reference_replay_verified', installed=False,
        unique_native_canvases=len(rows), frame_uses=sum(len(a['frames']) for sex in data.values() for a in sex['actions']),
        native_replay_pixel_identical=sum(len(a['frames']) for sex in data.values() for a in sex['actions']),
        fully_annotated_poses=sum(r['reviewed'] for r in rows), exporter_adjusts_scale=False, reviewer='native-trace-review.html')
    save(work / 'native-trace-verification.json', proof)
    print(json.dumps(proof))


def reviewed_trace(job, work, points, allow_pending=False):
    trace = load(work / 'native-trace.json')
    assert trace['job'] == job and trace['method'] == 'locked_native_canvas_redress'
    for pin in trace['native_pins']:
        assert digest(ROOT / pin['path']) == pin['sha256'], ('Native source changed', pin['path'])
    mapped = {(r['sex'], r['sprite']): r for r in trace['poses']}
    assert set(mapped) == {(r['sex'], r['sprite']) for r in points}
    missing = [key for key, row in mapped.items() if not row['reviewed']]
    if missing and not allow_pending and (work / 'user-review.json').exists():
        approval = load(work / 'user-review.json')
        export = load(work / 'registration-verification.json')
        approved = {r['path']: r['sha256'] for r in approval.get('files', [])}
        exported = {r['path']: r['sha256'] for r in export.get('files', [])}
        if approval.get('status') == 'accepted' and len(exported) == 4 and approved == exported:
            assert all(digest(work / name) == sha for name, sha in exported.items()), 'Approved exports changed'
            inputs = export.get('paint_inputs', [])
            assert len(inputs) == len(mapped), 'Approved paint input pins missing'
            assert {r['path'] for r in inputs} == {r['paint_layer'] for r in mapped.values()}
            assert all(digest(work / r['path']) == r['sha256'] for r in inputs), 'Paint changed since accepted export'
            # User acceptance of the exact complete SPR/ACT takes precedence
            # over optional authoring-landmark annotation completion.
            allow_pending = True
    if not allow_pending:
        assert not missing, ('Trace and review complete poses before export', missing)
    for point in points:
        key = point['sex'], point['sprite']
        row = mapped[key]
        if allow_pending and not row['reviewed']:
            assert digest(work / row['native_canvas']) == row['native_sha256'], (key, 'Locked native canvas changed')
            with Image.open(work / row['paint_layer']) as image:
                assert image.size == (640,640) and image.mode == 'RGBA', (key, 'Paint canvas changed')
            continue
        assert row['reviewed_paint_sha256'] == digest(work / row['paint_layer']), (key, 'Paint changed since pose review')
        assert digest(work / row['native_canvas']) == row['native_sha256'], (key, 'Locked native canvas changed')
        assert row['adjacent_frames_reviewed'] and row['volume_and_occlusion_reviewed'] and row['review_note'], (key, 'Motion/volume/occlusion review missing')
        assert set(row['landmarks']) == set(LANDMARKS)
        for name, mark in row['landmarks'].items():
            if mark['visibility'] == 'occluded':
                assert name != 'neck' and mark['note'] and mark['native'] is None and mark['paint'] is None, (key, name, 'Explain genuinely hidden anatomy')
                continue
            assert mark['visibility'] == 'visible', (key, name, 'Unmarked anatomical point')
            source, target = np.array(mark['paint'], float), np.array(mark['native'], float)
            assert source.shape == target.shape == (2,) and np.isfinite([source, target]).all()
            assert np.linalg.norm(source-target) <= 2., (key, name, 'Painted pose does not follow native canvas')
        assert np.allclose(row['landmarks']['neck']['native'], point['native_point']), (key, 'Stale native neck point')
        with Image.open(work / row['paint_layer']) as image:
            assert image.size == (640, 640) and image.mode == 'RGBA', (key, 'Paint layer canvas changed')
    return mapped


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', choices=('merchant', 'thief'), default='merchant')
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    prepare(args.job, (args.work or ROOT / 'Assets/ClanBodySkins' / args.job.title() / 'complete-v1').resolve())
