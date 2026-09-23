"""Build Acolyte V3 with native head motion and anatomically registered bodies.

The head never follows a detected costume feature. Collar landmarks belong to
unique native drawings, so repeated/held drawings cannot get independent fits.
Sequence scales are fixed, and sole corrections leave the collar/upper body and
boot shapes rigid. All placement changes are exported, not reviewer-only offsets.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from review_original_job_directions import native_context
from review_full_swordman_set import ORIGIN, body, head, joined
from fit_acolyte_necks import source_collar
from acolyte_neck_registration import native_neck_target
from preview_clan_reference_revision import bake
from sprite_formats import Layer, anchor, read_act, read_spr, write_act, write_spr
from spr_reader import Spr
from refine_clan_combat_necks import components

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'Assets/ClanBodySkins/Acolyte'
V1, V2, WORK = BASE / 'complete-v1', BASE / 'registration-v2', BASE / 'motion-v3'
GROUPS = ['Idle', 'Walk', 'Sit', 'Pickup', 'Attack 1', 'Attack 2', 'Hit',
          'Native action 7', 'Death', 'Standby', 'Attack 3', 'Attack 4', 'Cast']


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_pair(directory, sex, revision):
    path = directory / 'assets' / f'{sex}-angel-acolyte-{revision}'
    return read_spr(path.with_suffix('.spr').read_bytes()), read_act(path.with_suffix('.act').read_bytes())


def extract_redraws():
    """Select complete alpha components, including boots across grid boundaries."""
    specs = [
        ('male-attack-redraw.png', (1200, 400), 4, [('male', n) for n in (70, 71, 72, 73)]),
        ('pickup-redraw-source.png', (1200, 800), 4,
         [(sex, n) for sex in ('male', 'female') for n in (50, 51, 52, 53)]),
        ('female-attack-redraw.png', (900, 1200), 3, [('female', n) for n in range(82, 91)]),
    ]
    records = []
    for name, size, columns, entries in specs:
        source = Image.open(WORK / name).convert('RGBA').resize(size, Image.Resampling.NEAREST)
        pixels = np.array(source)
        pixels[pixels[:, :, 3] < 128] = 0
        pixels[pixels[:, :, 3] >= 128, 3] = 255
        groups = [g for g in components(pixels[:, :, 3] > 0) if len(g) > 1000]
        assert len(groups) == len(entries), (name, len(groups))
        selected = {}
        for group in groups:
            yy, xx = group[:, 0], group[:, 1]
            cell = int(yy.mean() // 400) * columns + int(xx.mean() // 300)
            assert cell not in selected and cell < len(entries), (name, cell)
            selected[cell] = group
        for cell, (sex, sprite) in enumerate(entries):
            yy, xx = selected[cell][:, 0], selected[cell][:, 1]
            canvas = np.zeros((640, 640, 4), np.uint8)
            tx = xx + 170 - cell % columns * 300
            ty = yy + 100 - cell // columns * 400
            assert tx.min() >= 0 and tx.max() < 640 and ty.min() >= 0 and ty.max() < 640
            canvas[ty, tx] = pixels[yy, xx]
            path = WORK / 'redraw-poses' / f'{sex}-{sprite:03}.png'
            Image.fromarray(canvas).save(path)
            records.append(dict(source=name, cell=cell, sex=sex, native_sprite=sprite,
                                path=path.relative_to(WORK).as_posix(), sha256=sha(path.read_bytes()),
                                complete_component_pixels=len(yy), imported_without_cell_clipping=True))
    # The deep female pickup has a separate locked native-pose correction.
    raw = Image.open(WORK / 'female-deep-pickup-redraw.png').convert('RGBA').resize((300, 320), Image.Resampling.NEAREST)
    pixels = np.array(raw)
    pixels[pixels[:, :, 3] < 128] = 0
    pixels[pixels[:, :, 3] >= 128, 3] = 255
    canvas = Image.new('RGBA', (640, 640))
    canvas.alpha_composite(Image.fromarray(pixels), (170, 180))
    path = WORK / 'redraw-poses/female-053.png'
    canvas.save(path)
    records = [r for r in records if (r['sex'], r['native_sprite']) != ('female', 53)]
    records.append(dict(source='female-deep-pickup-redraw.png', sex='female', native_sprite=53,
                        path=path.relative_to(WORK).as_posix(), sha256=sha(path.read_bytes()),
                        imported_without_cell_clipping=True))
    save(WORK / 'redraw-import.json', records)


def prepare():
    """Freeze the inspected landmarks, replacements and scale calibration."""
    extract_redraws()
    points = load(WORK / 'collar-points.json')
    replacements = {
        ('male', 70): [10., -234.], ('male', 71): [7., -236.],
        ('male', 72): [-43., -195.], ('male', 73): [-46., -191.],
        ('male', 50): [-18., -161.], ('male', 51): [-5., -133.],
        ('male', 52): [8., -166.], ('male', 53): [8., -141.],
        ('female', 50): [-26., -185.], ('female', 51): [-11.5, -173.5],
        ('female', 52): [-27., -212.], ('female', 53): [-54., -174.],
        ('female', 83): [11.5, -234.5], ('female', 84): [8.5, -213.5],
        ('female', 85): [-.5, -215.5],
    }
    for row in points:
        key = row['sex'], row['sprite']
        current_target = native_neck_target(row['sex'], row['action'], row['frame']).tolist()
        if row['native_point'] != current_target:
            row['previous_native_point'] = row['native_point']
            row['native_point'] = current_target
        if key in replacements:
            row['v1_collar_point'] = row['collar_point']
            row['collar_point'] = replacements[key]
            row['replacement'] = f'redraw-poses/{key[0]}-{key[1]:03}.png'
            row['landmark_basis'] = 'Anatomical opening inspected in redraw-0/1; not the detector score'
        else:
            row['landmark_basis'] = 'Anatomical opening inspected in original pose sheets, with explicit corrections'
    paths = [ROOT / 'tools/fix_acolyte_motion.py', WORK / 'collar-points.json',
             V2 / 'head-neck-reference.json', V2 / 'registration-verification.json',
             V2 / 'landmark-proposals.json', V2 / 'landmark-overrides.json']
    for sex in ('male', 'female'):
        for revision, directory in [('v1', V1), ('v2', V2)]:
            for suffix in ('.spr', '.act'):
                paths.append(directory / 'assets' / f'{sex}-angel-acolyte-{revision}{suffix}')
    paths += [ROOT / row['path'] for row in load(V2 / 'native-reference-pins.json')]
    paths += [WORK / row['replacement'] for row in points if 'replacement' in row]
    paths += [WORK / name for name in ('male-attack-redraw.png', 'pickup-redraw-source.png', 'female-attack-redraw.png', 'female-deep-pickup-redraw.png')]
    pins = [dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p.read_bytes())) for p in paths]
    config = dict(status='review_candidate', points=points, source_pins=pins, scales={},
                  policy='native head ACT anchors; one scale per canonical action/view; fixed collar per native drawing; local sole fitting only')
    for sex in ('male', 'female'):
        pair = read_pair(V1, sex, 'v1')
        ratios = {}
        for row in points:
            if row['sex'] != sex or row['action'] // 8 in (7, 8):
                continue
            ai, fi = row['action'], row['frame']
            source = (Image.open(WORK / row['replacement']).convert('RGBA') if 'replacement' in row else
                      body(sex, ai, fi, pair, job='acolyte'))
            ny = body(sex, ai, fi, job='acolyte').getbbox()[3] - ORIGIN[1]
            sy = source.getbbox()[3] - ORIGIN[1]
            ratios.setdefault(ai, []).append((ny - row['native_point'][1]) / (sy - row['collar_point'][1]))
        config['scales'][sex] = {str(ai): float(np.median(values)) for ai, values in ratios.items()}
    save(WORK / 'calibration.json', config)
    print('Saved calibration for', len(points), 'native drawings and', len(replacements), 'replacement poses')


def render_source(row, sex, ai, fi, pair, native, native_spr):
    if 'replacement' not in row:
        return body(sex, ai, fi, pair, job='acolyte')
    image = Image.open(WORK / row['replacement']).convert('RGBA')
    first = native.actions[row['action']][row['frame']].layers[0]
    layer = native.actions[ai][fi].layers[0]
    raw = native_spr.images[layer.index]
    assert first.index == layer.index and not first.mirror
    dy = (layer.y - first.y) * 4
    if layer.mirror:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        dx = (first.x + layer.x - 2 * (raw.width // 2) + raw.width) * 4
    else:
        dx = (layer.x - first.x) * 4
    canvas = Image.new('RGBA', image.size)
    canvas.alpha_composite(image, (dx, dy))
    return canvas


def fit_sole(image, collar_y, destination_bottom):
    """Rigid upper body and boots, monotone continuous lower-body registration.

    This does not change the head or translate the whole body toward whichever
    foot is lowest. The upper region stays identical; the terminal boot region
    undergoes a rigid translation. Only the connecting cloth/leg span deforms.
    """
    bottom = image.getbbox()[3]
    delta = float(destination_bottom - bottom)
    upper = collar_y + min(80., max(36., (bottom - collar_y) * .38))
    lower = float(bottom - 24)
    if lower - upper < 40:
        upper = lower - 40
    # Keep the inverse mapping one-to-one even for a compressed bent pose.
    if delta < 0:
        upper = min(upper, lower - abs(delta) * 2.6)
    assert upper > collar_y + 12, ('Insufficient torso/leg span', delta, upper, collar_y)
    source_y = np.linspace(0, image.height - 1, image.height * 16)
    t = np.clip((source_y - upper) / (lower - upper), 0, 1)
    destination_y = source_y + delta * t * t * (3 - 2 * t)
    derivative = np.diff(destination_y) / np.diff(source_y)
    assert derivative.min() > .35, ('Folded pose fit', derivative.min())
    inverse = np.interp(np.arange(image.height), destination_y, source_y)
    source_indices = np.rint(inverse).astype(int)
    pixels = np.asarray(image)[np.clip(source_indices, 0, image.height - 1)].copy()
    result = Image.fromarray(pixels)
    preserved_to = max(0, int(np.floor(upper)))
    assert np.array_equal(pixels[:preserved_to], np.asarray(image)[:preserved_to])
    assert abs(result.getbbox()[3] - destination_bottom) <= 1
    return result, dict(sole_delta_native=delta / 4, rigid_upper_end_native=(upper - ORIGIN[1]) / 4,
                        rigid_boot_height_native=6, min_vertical_derivative=float(derivative.min()),
                        upper_pixels_preserved=True)


def build():
    config = load(WORK / 'calibration.json')
    for pin in config['source_pins']:
        if pin['path'] == 'tools/fix_acolyte_motion.py':
            continue  # The immutable artwork inputs are checked; code hash is recorded on export.
        assert sha((ROOT / pin['path']).read_bytes()) == pin['sha256'], pin['path']
    points = {(r['sex'], r['sprite']): r for r in config['points']}
    checks, files = [], []
    (WORK / 'assets').mkdir(exist_ok=True)
    for sex in ('male', 'female'):
        pair = read_pair(V1, sex, 'v1')
        prior = read_pair(V2, sex, 'v2')
        _, native_spr, native, _, _ = native_context('acolyte', sex)
        act = copy.deepcopy(pair[1])
        images, cache = [], {}
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                nf = native.actions[ai][fi]
                row = points[sex, nf.layers[0].index]
                source = render_source(row, sex, ai, fi, pair, native, native_spr)
                collar = source_collar(row, nf, native, native_spr)
                target = source_collar(dict(row, collar_point=row['native_point']), nf, native, native_spr)
                scale = config['scales'][sex].get(str(row['action']), 1.)
                assert .7 < scale < 1.3
                c, t = collar + ORIGIN, target + ORIGIN
                fitted = source.transform(source.size, Image.Transform.AFFINE,
                    (1 / scale, 0, c[0] - t[0] / scale, 0, 1 / scale, c[1] - t[1] / scale), Image.Resampling.NEAREST)
                sole = dict(sole_delta_native=0., upper_pixels_preserved=True)
                if ai // 8 not in (7, 8):
                    original = body(sex, ai, fi, job='acolyte')
                    fitted, sole = fit_sole(fitted, t[1], original.getbbox()[3])
                box = fitted.getbbox()
                assert box and min(box[:2]) > 0 and max(box[2:]) < 640
                image, x, y = bake([(fitted.crop(box), box[0] - ORIGIN[0], box[1] - ORIGIN[1])])
                key = image.size, sha(image.tobytes())
                index = cache.get(key)
                if index is None:
                    index = len(images)
                    images.append(image)
                    cache[key] = index
                frame.layers = [Layer(x, y, index, sx=.25, sy=.25)]
                frame.anchors = copy.deepcopy(nf.anchors)
                assert (frame.ranges, frame.sound) == (nf.ranges, nf.sound)
                new_pair = images, act
                rendered = body(sex, ai, fi, new_pair, job='acolyte')
                assert rendered.tobytes() == fitted.tobytes(), (sex, ai, fi, 'Bake changed registration')
                h = head(sex, ai, fi, job='acolyte', pair=new_pair)
                assert h.tobytes() == head(sex, ai, fi, job='acolyte').tobytes()
                tx, ty = np.rint(t).astype(int)
                region = (slice(max(0, ty - 16), min(640, ty + 17)), slice(max(0, tx - 24), min(640, tx + 25)))
                contact = int(np.count_nonzero((np.asarray(h)[:, :, 3] > 0)[region] & (np.asarray(rendered)[:, :, 3] > 0)[region]))
                assert contact > 0, (sex, ai, fi, 'Collar detached')
                checks.append(dict(sex=sex, action=ai, frame=fi, native_sprite=nf.layers[0].index,
                    replacement_pose=row.get('replacement'), fixed_sequence_scale=scale, native_head_identical=True,
                    previous_head_residual=(np.array(anchor(prior[1].actions[ai][fi])) - anchor(nf)).tolist(),
                    head_residual=[0, 0], collar_target_4x=target.tolist(), neck_contact_pixels=contact, **sole))
        assert act.speeds == native.speeds and act.tail == pair[1].tail
        spr_raw, act_raw = write_spr(images), write_act(act)
        independent = Spr(spr_raw)
        assert len(images) == len(independent.images)
        for image, raw in zip(images, independent.images):
            pixels = np.frombuffer(raw.pixels, np.uint8).reshape(raw.height, raw.width, 4)
            assert image.tobytes() == pixels[::-1, :, [3, 2, 1, 0]].copy().tobytes()
        for index, image in enumerate(images):
            groups = sorted(components(np.asarray(image)[:, :, 3] > 128), key=len, reverse=True)
            assert not any(len(g) > 16 for g in groups[1:]), (sex, index, 'Detached sprite fragment')
        for ext, raw in (('.spr', spr_raw), ('.act', act_raw)):
            path = WORK / 'assets' / f'{sex}-angel-acolyte-v3{ext}'
            path.write_bytes(raw)
            files.append(dict(sex=sex, path=path.relative_to(WORK).as_posix(), sha256=sha(raw), bytes=len(raw)))
        reopened = read_pair(WORK, sex, 'v3')
        assert len(reopened[1].actions) == 104 and sum(map(len, reopened[1].actions)) == 456
        for ai, frames in enumerate(reopened[1].actions):
            for fi, frame in enumerate(frames):
                assert frame.anchors == native.actions[ai][fi].anchors
                assert body(sex, ai, fi, reopened, job='acolyte').tobytes() == body(sex, ai, fi, (images, act), job='acolyte').tobytes()
    result = dict(status='candidate_export_verified_pending_visual_review', installed=False, user_accepted=False,
                  actions=208, frame_uses=len(checks), native_head_renders_identical=912,
                  timing_ranges_sounds_preserved=True, independent_spr_decoder_match=True, detached_major_components=[],
                  max_extra_head_step_native=0., fixed_scale_per_sequence=True,
                  source_tool_sha256=sha(Path(__file__).read_bytes()), files=files, checks=checks)
    save(WORK / 'verification.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'frame_uses', 'native_head_renders_identical', 'max_extra_head_step_native')}))


def review():
    """Share identical rendered comparisons across actions."""
    image_dir = WORK / 'review/images'
    image_dir.mkdir(parents=True, exist_ok=True)
    data, count = {}, 0
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 12)
    for sex in ('male', 'female'):
        previous, candidate = read_pair(V2, sex, 'v2'), read_pair(WORK, sex, 'v3')
        data[sex] = []
        for ai, frames in enumerate(candidate[1].actions):
            records = []
            for fi in range(len(frames)):
                paths = []
                for pair in (None, previous, candidate):
                    im = joined(sex, ai, fi, pair, job='acolyte')
                    encoded = io.BytesIO()
                    im.save(encoded, format='PNG')
                    raw = encoded.getvalue()
                    path = image_dir / (sha(raw) + '.png')
                    if not path.exists():
                        path.write_bytes(raw)
                    paths.append(path.relative_to(WORK).as_posix())
                records.append(paths)
                count += 1
            data[sex].append(dict(ms=round(candidate[1].speeds[ai] * 25), frames=records))
        for ai in (0, 4, 8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 24, 26, 32, 34, 40, 42, 80, 82, 84, 96, 98):
            frames = candidate[1].actions[ai]
            board = Image.new('RGB', (180 * len(frames), 765), '#283746')
            pen = ImageDraw.Draw(board)
            for fi in range(len(frames)):
                for k, pair in enumerate((None, previous, candidate)):
                    image = joined(sex, ai, fi, pair, job='acolyte').crop((140, 40, 500, 520)).resize((180, 240), Image.Resampling.NEAREST)
                    board.paste(image, (fi * 180, k * 255 + 15), image)
                    pen.text((fi * 180 + 2, k * 255), f'{sex} A{ai} F{fi} ' + ['Native', 'V2 installed', 'V3 candidate'][k], font=font, fill='white')
            board.save(WORK / f'{sex}-A{ai}-compare.png')
    template = (ROOT / 'tools/acolyte_motion_review.html').read_text(encoding='utf8')
    template = template.replace('__DATA__', json.dumps(data, separators=(',', ':'))).replace('__GROUPS__', json.dumps(GROUPS))
    (WORK / 'review.html').write_text(template, encoding='utf8', newline='\n')
    save(WORK / 'review-coverage.json', dict(frame_uses=count, variants=3, all_eight_directions=True,
                                           rendered_from_reopened_exports=True, common_origin=list(ORIGIN)))
    print('Rendered', count, 'native/installed/corrected frame comparisons')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'build', 'review'))
    args = parser.parse_args()
    globals()[args.stage]()
