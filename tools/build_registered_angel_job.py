"""Export reviewed whole-pose paint layers using their locked native canvases."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from import_full_swordman_art import extract
from review_original_job_directions import native_context
from review_full_swordman_set import ORIGIN, body, head, joined, main as render_review
from fix_archer_design_alignment import neck_point
from acolyte_neck_registration import ring_collars
from fit_acolyte_necks import source_collar
from refine_clan_combat_necks import components
from preview_clan_reference_revision import bake
from sprite_formats import Layer, read_spr, read_act, write_spr, write_act
from spr_reader import Spr

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=lambda v: v.tolist() if isinstance(v, np.ndarray) else v.item()) + '\n', encoding='utf8', newline='\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def opaque(image):
    pixels = np.array(image.convert('RGBA'))
    pixels[pixels[:, :, 3] < 128] = 0
    pixels[pixels[:, :, 3] >= 128, 3] = 255
    groups = sorted(components(pixels[:, :, 3] > 0), key=len, reverse=True)
    assert groups
    major = [len(g) for g in groups[1:] if len(g) > 8]
    assert not major, ('Detached source pieces', major)
    removed = sum(len(g) for g in groups[1:])
    for group in groups[1:]:
        pixels[group[:, 0], group[:, 1]] = 0
    return Image.fromarray(pixels), removed


def top_collar(image):
    pixels = np.asarray(image)
    yy, xx = np.where(pixels[:, :, 3] > 0)
    band = yy < yy.min() + 12
    return [float(xx[band].mean() + .5 - ORIGIN[0]), float(yy.min() + 5.5 - ORIGIN[1])]


def propose(image, target, action):
    top = top_collar(image)
    if action // 8 in (0, 1, 2, 4, 6, 7, 9):
        return top, 'top collar silhouette; requires visual verification', []
    candidates = ring_collars(image, target)
    for row in candidates:
        row['distance_to_native'] = float(np.linalg.norm(np.array(row['point']) - target))
        row['selection_score'] = row['score'] - row['distance_to_native'] * .85
    candidates.sort(key=lambda row: row['selection_score'], reverse=True)
    return (candidates[0]['point'] if candidates else top,
            'proposed aperture; verify neck rather than hand/belt', candidates[:6])


def landmark_boards(job, work, points):
    out = work / 'landmark-review'
    out.mkdir(exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 12)
    for sex in ('male', 'female'):
        selected = [r for r in points if r['sex'] == sex]
        for page in range((len(selected) + 11) // 12):
            board = Image.new('RGB', (1440, 1040), '#283746')
            pen = ImageDraw.Draw(board)
            for i, row in enumerate(selected[page * 12:(page + 1) * 12]):
                x, y = i % 3 * 480, i // 3 * 260
                ai, fi = row['action'], row['frame']
                target = np.array(row['native_point'])
                box_world = [int(target[0] - 115), int(target[1] - 75), int(target[0] + 115), int(target[1] + 145)]
                row['review_crop_world'] = box_world
                box = tuple(np.array(box_world) + np.array([*ORIGIN, *ORIGIN]))
                original = joined(sex, ai, fi, job=job).crop(box)
                source = Image.open(work / row['source_pose']).convert('RGBA').crop(box)
                draw = ImageDraw.Draw(source)
                for gx in range(0, source.width, 20):
                    draw.line((gx, 0, gx, source.height), fill=(105, 130, 145, 75))
                for gy in range(0, source.height, 20):
                    draw.line((0, gy, source.width, gy), fill=(105, 130, 145, 75))
                px, py = np.array(row['collar_point']) - np.array(box_world[:2])
                draw.ellipse((px - 4, py - 4, px + 4, py + 4), outline='magenta', width=1)
                draw.line((px - 2, py, px + 2, py), fill='magenta')
                board.paste(original, (x, y + 24), original)
                board.paste(source, (x + 240, y + 24), source)
                pen.text((x + 3, y + 2), f"{sex} SPR {row['sprite']} / A{ai} F{fi} / {row['batch']}", font=font, fill='white')
                pen.text((x + 242, y + 245), f"origin {box_world[:2]} / point {[round(float(v), 1) for v in row['collar_point']]}", font=font, fill='white')
            board.save(out / f'{sex}-{page}.png')


def prepare(job, work):
    plan_path = work / 'art-plan.json'
    plan = load(plan_path)
    assert plan['job'] == job
    refs_path = work / 'refs/head-neck-reference.json'
    if not refs_path.exists():
        source = ROOT / 'Assets/ClanBodySkins/Acolyte/registration-v2/head-neck-reference.json'
        refs_path.write_bytes(source.read_bytes())
    refs = load(refs_path)
    previous_path = work / 'neck-landmarks.json'
    previous = {(r['sex'], r['sprite']): r for r in load(previous_path)} if previous_path.exists() else {}
    points, pins, imports = [], [], []
    for sex in ('male', 'female'):
        src, spr, native, heads, ha = native_context(job, sex)
        for name in ('head.spr', 'head.act'):
            assert (src / name).read_bytes() == (ROOT / 'Assets/ClanBodySkins/Acolyte/native' / sex / name).read_bytes(), 'Head reference differs'
        for name in ('body.spr', 'body.act', 'head.spr', 'head.act'):
            path = src / name
            pins.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=digest(path)))
        seen = set()
        for batch in plan['batches']:
            if batch['sex'] != sex:
                continue
            art_path = work / 'art' / sex / (batch['name'] + '.png')
            assert art_path.is_file(), ('Missing sheet', sex, batch['name'])
            assert digest(src / 'body.spr') == batch['source_spr_sha256']
            assert digest(src / 'body.act') == batch['source_act_sha256']
            drawings, evidence = extract(batch, work)
            imports.extend(dict(row, sex=sex, batch=batch['name']) for row in evidence)
            pins.append(dict(path=art_path.relative_to(ROOT).as_posix(), sha256=digest(art_path)))
            for record in batch['poses']:
                index, ai, fi = record['sprite'], record['representative_action'], record['representative_frame']
                assert index not in seen
                seen.add(index)
                nf = native.actions[ai][fi]
                active = [l for l in nf.layers if l.index >= 0]
                assert len(active) == 1 and active[0].index == index and not active[0].mirror
                layer = active[0]
                raw = spr.images[index]
                image, offset = drawings[index]
                image, removed = opaque(image)
                canvas = Image.new('RGBA', (640, 640))
                xy = (np.array([layer.x - raw.width // 2, layer.y - raw.height // 2]) * 4 + offset + ORIGIN).astype(int)
                canvas.alpha_composite(image, tuple(xy.tolist()))
                assert np.count_nonzero(np.asarray(canvas)[:, :, 3]) == np.count_nonzero(np.asarray(image)[:, :, 3]), (sex, index, 'Source clipped')
                path = work / 'source-poses' / sex / f'{index:03}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                canvas.save(path)
                target = neck_point(refs, sex, native, heads, ha, ai, fi).tolist()
                point, method, candidates = propose(canvas, np.array(target), ai)
                row = dict(sex=sex, sprite=index, action=ai, frame=fi, batch=batch['name'], source_pose=path.relative_to(work).as_posix(),
                           source_pose_sha256=digest(path), native_point=target, collar_point=point, method=method,
                           candidates=candidates, reviewed=False, removed_quantization_specks=removed)
                old = previous.get((sex, index))
                if old and old['source_pose_sha256'] == row['source_pose_sha256'] and old['native_point'] == target:
                    for key in ('collar_point', 'method', 'reviewed', 'review_note'):
                        if key in old:
                            row[key] = old[key]
                points.append(row)
                pins.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=digest(path)))
        used = {l.index for fs in native.actions for f in fs for l in f.layers if l.index >= 0}
        assert seen == used, (sex, 'Missing native drawings', sorted(used - seen))
    landmark_boards(job, work, points)
    save(previous_path, points)
    pins += [dict(path=p.relative_to(ROOT).as_posix(), sha256=digest(p)) for p in (plan_path, refs_path)]
    save(work / 'source-pins.json', pins)
    save(work / 'complete-import.json', dict(job=job, sheets=len(plan['batches']), poses=len(points), imports=imports))
    print(json.dumps(dict(job=job, source_poses=len(points), unreviewed=sum(not r['reviewed'] for r in points), boards=str(work / 'landmark-review'))))


def render_source(image, row, frame, native, sprite):
    first = native.actions[row['action']][row['frame']].layers[0]
    layer = frame.layers[0]
    raw = sprite.images[layer.index]
    assert first.index == layer.index and not first.mirror
    dy = (layer.y - first.y) * 4
    if layer.mirror:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        dx = (first.x + layer.x - 2 * (raw.width // 2) + raw.width) * 4
    else:
        dx = (layer.x - first.x) * 4
    canvas = Image.new('RGBA', (640, 640))
    canvas.alpha_composite(image, (dx, dy))
    return canvas


def build(job, work, revision, review_only=False):
    points = load(work / 'neck-landmarks.json')
    from native_sprite_tracing import reviewed_trace
    traced = reviewed_trace(job, work, points, allow_pending=review_only)
    for pin in load(work / 'source-pins.json'):
        assert digest(ROOT / pin['path']) == pin['sha256'], pin['path']
    refs = load(work / 'refs/head-neck-reference.json')
    rows = {(r['sex'], r['sprite']): r for r in points}
    pending, all_checks = [], []
    for sex in ('male', 'female'):
        _, spr, native, heads, ha = native_context(job, sex)
        art = {r['sprite']: Image.open(work / traced[sex, r['sprite']]['paint_layer']).convert('RGBA') for r in points if r['sex'] == sex}
        act, images, cache, checks = copy.deepcopy(native), [], {}, []
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                nf = native.actions[ai][fi]
                active = [l for l in nf.layers if l.index >= 0]
                assert len(active) == 1 and active[0] is nf.layers[0]
                index = active[0].index
                row = rows[sex, index]
                source = render_source(art[index], row, nf, native, spr)
                target = source_collar(dict(row, collar_point=row['native_point']), nf, native, spr)
                canonical_neck = neck_point(refs, sex, native, heads, ha, row['action'], row['frame'])
                assert np.allclose(canonical_neck, row['native_point']), (sex, index, 'Stale native neck point')
                # Artwork already occupies the native canvas. Only replay the
                # original ACT translation/mirror; never resize or warp a pose.
                fitted = source
                fitted, removed = opaque(fitted)
                box = fitted.getbbox()
                assert box and min(box[:2]) > 0 and max(box[2:]) < 640, (sex, ai, fi, 'Clipped')
                image, x, y = bake([(fitted.crop(box), box[0] - ORIGIN[0], box[1] - ORIGIN[1])])
                key = image.size, hashlib.sha256(image.tobytes()).hexdigest()
                output_index = cache.get(key)
                if output_index is None:
                    output_index = len(images)
                    images.append(image)
                    cache[key] = output_index
                frame.layers = [Layer(x, y, output_index, sx=.25, sy=.25)]
                pair = images, act
                rendered = body(sex, ai, fi, pair, job=job)
                assert rendered.tobytes() == fitted.tobytes(), 'Bake changed registration'
                h = head(sex, ai, fi, job=job, pair=pair)
                assert h.tobytes() == head(sex, ai, fi, job=job).tobytes(), 'Native head changed'
                fresh = neck_point(refs, sex, native, heads, ha, ai, fi) + ORIGIN
                tx, ty = np.rint(fresh).astype(int)
                region = (slice(max(0, ty - 16), min(640, ty + 17)), slice(max(0, tx - 24), min(640, tx + 25)))
                contact = int(np.count_nonzero((np.asarray(h)[:, :, 3] > 0)[region] & (np.asarray(rendered)[:, :, 3] > 0)[region]))
                native_body = body(sex, ai, fi, job=job)
                native_contact = int(np.count_nonzero((np.asarray(h)[:, :, 3] > 0)[region] & (np.asarray(native_body)[:, :, 3] > 0)[region]))
                # Some original pickup poses join at an edge outside this
                # sampled overlap region. Do not demand overlap stock lacks.
                assert native_contact == 0 or contact > 0, (sex, ai, fi, index, 'Lost native head/collar contact')
                assert (frame.anchors, frame.ranges, frame.sound) == (nf.anchors, nf.ranges, nf.sound)
                checks.append(dict(sex=sex, action=ai, frame=fi, native_sprite=index, native_canvas_scale=1.,
                                   native_head_identical=True, collar_target_4x=target.tolist(), neck_contact_pixels=contact, native_neck_contact_pixels=native_contact,
                                   removed_quantization_specks=removed, native_frame_replayed=True, local_deformation=False))
        assert len(act.actions) == 104 and sum(map(len, act.actions)) == 456
        sb, ab = write_spr(images), write_act(act)
        reopened, independent = read_spr(sb), Spr(sb)
        for image, other in zip(reopened, independent.images):
            raw = np.frombuffer(other.pixels, np.uint8).reshape(other.height, other.width, 4)
            assert image.tobytes() == raw[::-1, :, [3, 2, 1, 0]].copy().tobytes()
        parsed = read_act(ab)
        assert parsed.tail == native.tail and parsed.speeds == native.speeds
        for ai, frames in enumerate(parsed.actions):
            for fi, frame in enumerate(frames):
                assert (frame.anchors, frame.ranges, frame.sound) == (native.actions[ai][fi].anchors, native.actions[ai][fi].ranges, native.actions[ai][fi].sound)
                assert body(sex, ai, fi, (reopened, parsed), job=job).tobytes() == body(sex, ai, fi, (images, act), job=job).tobytes()
        pending.append((sex, sb, ab, len(art), len(images), checks))
        all_checks.extend(checks)
    out = work / 'assets'
    out.mkdir(exist_ok=True)
    files = []
    for sex, sb, ab, native_count, image_count, checks in pending:
        sex_files = []
        for suffix, raw in (('.spr', sb), ('.act', ab)):
            path = out / f'{sex}-angel-{job}-{revision}{suffix}'
            row = dict(sex=sex, path=path.relative_to(work).as_posix(), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            feedback = work / 'user-review.json'
            if feedback.exists() and load(feedback).get('status') == 'accepted':
                assert any(r['path'] == row['path'] and r['sha256'] == row['sha256'] for r in load(feedback)['files']), 'Changed accepted export: use a new revision'
            path.write_bytes(raw)
            sex_files.append(row)
            files.append(row)
        save(work / f'{sex}-verification.json', dict(job=job, sex=sex, status='review_only' if review_only else 'complete_candidate', landmark_annotations_complete=all(r['reviewed'] for r in traced.values()), actions=104, frame_uses=456,
            unique_drawings=native_count, exported_images=image_count, stock_fallback_frames=[], missing_sheets=[], detached_artwork_flags=[],
            native_metadata_preserved=True, timing_ranges_sound_preserved=True, head_anchor_policy='native', independent_decoder_match=True,
            native_head_renders_identical=456, files=sex_files, checks=checks))
    save(work / 'registration-verification.json', dict(job=job, status='review_only' if review_only else 'complete_candidate_awaiting_visual_review', installed=False, landmark_annotations_complete=all(r['reviewed'] for r in traced.values()),
         actions=208, frame_uses=912, native_heads_identical=912, extra_head_motion_native=0, independent_decoder_match=True,
         native_canvas_scale=1., local_deformation=False, trace_manifest_sha256=digest(work / 'native-trace.json'),
         paint_inputs=[dict(path=r['paint_layer'], sha256=digest(work / r['paint_layer'])) for r in traced.values()], files=files, checks=all_checks, source_tool_sha256=digest(Path(__file__))))
    print(json.dumps(dict(job=job, status='review_only' if review_only else 'complete_candidate', actions=208, frames=912, files=files)))


def registered_review(job, work, revision):
    render_review(False, work, job, '{sex}-angel-' + job + '-' + revision)
    path=work/'full-action-review.html'
    html=path.read_text(encoding='utf8')
    html=html.replace('This is the complete body artwork review;', 'This is a corrected native-pose review candidate;')
    html=html.replace('<div class="controls">', '<p><a href="native-trace-review.html">Original canvas overlay</a></p><div class="controls">', 1)
    html += """<script>
const poseParams=new URLSearchParams(location.search);
if(poseParams.has('action')){const ai=Math.max(0,Math.min(103,Number(poseParams.get('action'))||0));document.getElementById('group').value=String(Math.floor(ai/8));document.getElementById('dir').value=String(ai%8);document.getElementById('group').dispatchEvent(new Event('change'));}
if(poseParams.get('play')==='1')document.getElementById('play').click();
document.body.dataset.reviewCandidate='true';
</script>"""
    path.write_text(html,encoding='utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'boards', 'build', 'review'))
    parser.add_argument('--job', choices=('merchant', 'thief'), default='merchant')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--revision', default='v1')
    parser.add_argument('--review-only', action='store_true', help='Write complete SPR/ACT for visual review; keep annotation/release approval pending')
    args = parser.parse_args()
    work = (args.work or ROOT / 'Assets/ClanBodySkins' / args.job.title() / ('complete-' + args.revision)).resolve()
    if args.stage == 'prepare':
        prepare(args.job, work)
    elif args.stage == 'boards':
        points = load(work / 'neck-landmarks.json')
        landmark_boards(args.job, work, points)
        save(work / 'neck-landmarks.json', points)
    elif args.stage == 'build':
        build(args.job, work, args.revision, args.review_only)
    else:
        registered_review(args.job, work, args.revision)
