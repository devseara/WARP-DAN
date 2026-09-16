"""Complete Archer exports with inspected attachments and exact accepted-frame retention."""
import argparse
import copy
import hashlib
import json
import math
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from package_clan_skin_assets import ROOT
from acolyte_neck_registration import ring_collars
from fix_archer_design_alignment import neck_point
from fit_acolyte_necks import ground, source_collar
from review_original_job_directions import native_context
from review_full_swordman_set import body, head, ORIGIN
from sprite_formats import read_spr, read_act, write_spr, write_act, Layer, anchor
from render_native_wing_anatomy import rgba
from spr_reader import Spr
from preview_clan_reference_revision import bake
from refine_clan_combat_necks import components

SOURCE = ROOT / 'Assets/ClanBodySkins/Archer/complete-v1'
ACCEPTED = SOURCE.parent / 'alignment-v3'
WORK = SOURCE.parent / 'complete-v4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_at(directory, sex, revision):
    stem = directory / 'assets' / f'{sex}-angel-archer-{revision}'
    return read_spr(stem.with_suffix('.spr').read_bytes()), read_act(stem.with_suffix('.act').read_bytes())


def inputs():
    approval = json.loads((ACCEPTED / 'user-review.json').read_text(encoding='utf8'))
    assert approval['status'] == 'accepted'
    for row in approval['files']:
        assert digest(ACCEPTED / row['path']) == row['sha256']
    plan = json.loads((SOURCE / 'art-plan.json').read_text(encoding='utf8'))
    refs = json.loads((SOURCE / 'head-neck-reference.json').read_text(encoding='utf8'))
    reports = {}
    for sex in ('male', 'female'):
        report = json.loads((SOURCE / (sex + '-verification.json')).read_text(encoding='utf8'))
        assert not report['missing_sheets'] and not report['stock_fallback_frames'] and not report['detached_artwork_flags']
        for row in report['files']:
            assert digest(SOURCE / row['path']) == row['sha256']
        reports[sex] = report
    return plan, refs, reports


def audit():
    WORK.mkdir(parents=True, exist_ok=True)
    plan, refs, reports = inputs()
    records = []
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)
    for sex in ('male', 'female'):
        pair = pair_at(SOURCE, sex, 'v1')
        _, spr, native, heads, ha = native_context('archer', sex)
        old = json.loads((ACCEPTED / (sex + '-verification.json')).read_text(encoding='utf8'))
        retained = {row['sprite'] for row in old['imports']}
        selected = []
        for batch in plan['batches']:
            if batch['sex'] != sex:
                continue
            for pose in batch['poses']:
                if pose['sprite'] in retained:
                    continue
                ai, fi = pose['representative_action'], pose['representative_frame']
                target = neck_point(refs, sex, native, heads, ha, ai, fi)
                image = body(sex, ai, fi, pair, job='archer')
                simple = ai // 8 in (0, 1, 2, 4, 6, 7, 9, 12)
                candidates = ring_collars(image, target, simple)
                point = candidates[0]['point'] if candidates else None
                method = 'Dark collar aperture'
                pink_point = None
                if simple:
                    data = np.asarray(image)
                    rgb = data[:, :, :3].astype(int)
                    top = image.getbbox()[1]
                    yy, xx = np.indices(data.shape[:2])
                    pink = ((rgb[:, :, 0] - rgb[:, :, 1] > 18) &
                            (np.abs(rgb[:, :, 1] - rgb[:, :, 2]) < 27) &
                            (rgb[:, :, 0] > 65) & (data[:, :, 3] > 128) &
                            (yy < top + 14) & (np.abs(xx - ORIGIN[0] - target[0]) < 100))
                    py, px = np.where(pink)
                    if len(px) >= 8:
                        pink_point = [float(px.mean()) + .5 - ORIGIN[0], float(py.mean()) + .5 - ORIGIN[1]]
                        if point is None or point[1] + ORIGIN[1] - top > 22 or np.linalg.norm(np.array(point) - pink_point) > 20:
                            point, method = pink_point, 'Top collar interior; inspect closed aperture'
                record = dict(sex=sex, sprite=pose['sprite'], action=ai, frame=fi,
                              batch=batch['name'], native_point=target.tolist(), collar_point=point,
                              method=method, pink_point=pink_point, candidates=candidates, reviewed=False)
                selected.append(record)
                records.append(record)
        for page in range(math.ceil(len(selected) / 20)):
            board = Image.new('RGB', (1200, 1100), '#283746')
            pen = ImageDraw.Draw(board)
            for cell, row in enumerate(selected[page * 20:(page + 1) * 20]):
                x, y = cell % 4 * 300, cell // 4 * 220
                ai, fi = row['action'], row['frame']
                pen.text((x + 4, y + 3), f"{row['sprite']:03} A{ai} F{fi} {row['batch']}", font=font, fill='white')
                center = np.array(row['native_point']) + ORIGIN
                box = (round(center[0] - 105), round(center[1] - 80), round(center[0] + 105), round(center[1] + 200))
                for col, custom in enumerate((False, True)):
                    image = body(sex, ai, fi, pair if custom else None, job='archer')
                    point = row['collar_point'] if custom else row['native_point']
                    if point is not None:
                        px, py = np.array(point) + ORIGIN
                        draw = ImageDraw.Draw(image)
                        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill='magenta' if custom else 'cyan')
                    image = image.crop(box).resize((146, 194), Image.Resampling.NEAREST)
                    board.paste(image, (x + col * 150, y + 24), image)
            board.save(WORK / f'{sex}-landmarks-{page}.png')
    pin_paths = [SOURCE / row['path'] for report in reports.values() for row in report['files']]
    pin_paths += [SOURCE.parent / 'native' / sex / (kind + ext) for sex in ('male', 'female')
                  for kind in ('body', 'head') for ext in ('.spr', '.act')]
    pin_paths.append(SOURCE / 'head-neck-reference.json')
    pins = [dict(path=p.relative_to(ROOT).as_posix(), sha256=digest(p)) for p in pin_paths]
    (WORK / 'landmark-source-pins.json').write_text(json.dumps(pins, indent=2), encoding='utf8')
    (WORK / 'landmark-proposals.json').write_text(json.dumps(records, indent=2), encoding='utf8')
    print(json.dumps(dict(records=len(records), missing=[(r['sex'], r['sprite']) for r in records if r['collar_point'] is None])))


def build():
    plan, refs, source_reports = inputs()
    for pin in json.loads((WORK / 'landmark-source-pins.json').read_text(encoding='utf8')):
        assert digest(ROOT / pin['path']) == pin['sha256'], ('Re-audit changed landmark source', pin['path'])
    rows = json.loads((WORK / 'landmark-proposals.json').read_text(encoding='utf8'))
    lookup = {(r['sex'], r['sprite']): r for r in rows}
    for row in json.loads((WORK / 'landmark-overrides.json').read_text(encoding='utf8')):
        lookup[row['sex'], row['sprite']].update(row)
    (WORK / 'assets').mkdir(exist_ok=True)
    all_files, proofs = [], []
    for sex in ('male', 'female'):
        source_images, source_act = pair_at(SOURCE, sex, 'v1')
        accepted_images, accepted_act = pair_at(ACCEPTED, sex, 'v3')
        accepted_report = json.loads((ACCEPTED / (sex + '-verification.json')).read_text(encoding='utf8'))
        fallback = {tuple(pair) for pair in accepted_report['stock_fallback_frames']}
        _, native_spr, native, heads, ha = native_context('archer', sex)
        by_action, geometry = {}, {}
        for key, row in lookup.items():
            if row['sex'] != sex:
                continue
            assert row['collar_point'] is not None
            ai, fi = row['action'], row['frame']
            original = body(sex, ai, fi, job='archer')
            custom = body(sex, ai, fi, (source_images, source_act), job='archer')
            target, collar = np.array(row['native_point']), np.array(row['collar_point'])
            axis = np.array([0., 1.])
            if ai // 8 == 8:
                yy, xx = np.where(np.asarray(original)[:, :, 3] > 128)
                axis = np.array([xx.mean() + .5 - ORIGIN[0], yy.mean() + .5 - ORIGIN[1]]) - target
                axis /= np.linalg.norm(axis)
            extents = []
            for image, center in ((original, target), (custom, collar)):
                yy, xx = np.where(np.asarray(image)[:, :, 3] > 128)
                points = np.column_stack((xx + .5 - ORIGIN[0], yy + .5 - ORIGIN[1]))
                extents.append(float((points @ axis).max() - center @ axis))
            assert min(extents) > 8, (key, 'Invalid collar-to-body extent', extents)
            ratio = extents[0] / extents[1]
            by_action.setdefault(ai, []).append(ratio)
            geometry[key] = dict(axis=axis, proposed_scale=ratio)
        scales = {ai: float(np.median(values)) for ai, values in by_action.items()}
        assert all(.45 < scale < 1.8 for scale in scales.values()), scales
        prepared, walking_x = {}, {}
        for ai, frames in enumerate(native.actions):
            for fi, frame in enumerate(frames):
                if (ai, fi) not in fallback:
                    continue
                index = frame.layers[0].index
                row = lookup[sex, index]
                scale = scales[row['action']]
                collar = source_collar(row, frame, native, native_spr)
                target = neck_point(refs, sex, native, heads, ha, ai, fi)
                original = body(sex, ai, fi, job='archer')
                custom = body(sex, ai, fi, (source_images, source_act), job='archer')
                pivot = collar + ORIGIN
                resized = custom.transform(custom.size, Image.Transform.AFFINE,
                    (1 / scale, 0, pivot[0] * (1 - 1 / scale), 0, 1 / scale, pivot[1] * (1 - 1 / scale)), Image.Resampling.NEAREST)
                axis = geometry[sex, index]['axis'].copy()
                if frame.layers[0].mirror:
                    axis[0] *= -1
                yy, xx = np.where(np.asarray(original)[:, :, 3] > 128)
                span = np.column_stack((xx, yy)) @ axis
                band = min(60., float(np.ptp(span)) * .28)
                shift = np.rint(ground(original, axis, band) - ground(resized, axis, band)).astype(int)
                prepared[ai, fi] = (resized, collar, target, shift, scale, index)
                if ai // 8 == 1:
                    walking_x.setdefault(ai, []).append(int(shift[0]))
        # Hold the lateral root fixed through a walk direction, rather than
        # moving the torso whenever the lowest foot changes ownership.
        walking_x = {ai: int(round(float(np.median(values)))) for ai, values in walking_x.items()}
        act, images, seen, frame_proofs = copy.deepcopy(native), [], {}, []
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                if (ai, fi) not in fallback:
                    old = accepted_act.actions[ai][fi]
                    frame = copy.deepcopy(old)
                    act.actions[ai][fi] = frame
                    image = accepted_images[old.layers[0].index].copy()
                    x, y = old.layers[0].x, old.layers[0].y
                    preserved, delta, scale = True, [0, 0], 1.
                    index = native.actions[ai][fi].layers[0].index
                else:
                    resized, collar, target, shift, scale, index = prepared[ai, fi]
                    shift = shift.copy()
                    if ai in walking_x:
                        shift[0] = walking_x[ai]
                    canvas = Image.new('RGBA', resized.size)
                    canvas.alpha_composite(resized, tuple(map(int, shift)))
                    collar = collar + shift
                    bounds = canvas.getbbox()
                    assert bounds and min(bounds[:2]) > 0 and max(bounds[2:]) < 640, (sex, ai, fi, 'Body clipped')
                    cropped = canvas.crop(bounds)
                    image, x, y = bake([(cropped, bounds[0] - ORIGIN[0], bounds[1] - ORIGIN[1])])
                    delta = np.rint((collar - target) / 4).astype(int).tolist()
                    before = anchor(frame)
                    raw = bytearray(frame.anchors[0])
                    struct.pack_into('<ii', raw, 4, before[0] + delta[0], before[1] + delta[1])
                    frame.anchors[0] = bytes(raw)
                    preserved = False
                key = image.size, image.tobytes()
                if key not in seen:
                    seen[key] = len(images)
                    images.append(image)
                frame.layers = [Layer(x, y, seen[key], sx=.25, sy=.25)]
                frame_proofs.append(dict(action=ai, frame=fi, native_sprite=index, accepted_v3_preserved=preserved,
                                         fixed_action_scale=scale, head_anchor_delta=delta))
        sb, ab = write_spr(images), write_act(act)
        decoded, reopened, independent = read_spr(sb), read_act(ab), Spr(sb)
        assert len(reopened.actions) == 104 and sum(map(len, reopened.actions)) == 456
        assert all(image.tobytes() == rgba(independent, i, 1).tobytes() for i, image in enumerate(decoded))
        issues = []
        for index, image in enumerate(decoded):
            data = np.asarray(image)
            assert not data[data[:, :, 3] == 0].any()
            sizes = sorted((len(group) for group in components(data[:, :, 3] > 0)), reverse=True)
            if len(sizes) != 1:
                issues.append(dict(sprite=index, components=sizes))
        for row in frame_proofs:
            ai, fi = row['action'], row['frame']
            actual = body(sex, ai, fi, (decoded, reopened), job='archer')
            if row['accepted_v3_preserved']:
                assert actual.tobytes() == body(sex, ai, fi, (accepted_images, accepted_act), job='archer').tobytes()
                assert head(sex, ai, fi, job='archer', pair=(decoded, reopened)).tobytes() == head(sex, ai, fi, job='archer', pair=(accepted_images, accepted_act)).tobytes()
            f, n = reopened.actions[ai][fi], native.actions[ai][fi]
            assert (f.ranges, f.sound) == (n.ranges, n.sound)
        assert reopened.speeds == native.speeds and reopened.tail == native.tail
        stem = WORK / 'assets' / f'{sex}-angel-archer-v4'
        sex_files = []
        for ext, raw in (('.spr', sb), ('.act', ab)):
            path = stem.with_suffix(ext)
            path.write_bytes(raw)
            entry = dict(path=path.relative_to(WORK).as_posix(), sha256=digest(path))
            sex_files.append(entry)
            all_files.append(dict(sex=sex, **entry))
        report = dict(source_reports[sex])
        report.update(status='Complete V4 candidate', files=sex_files, native_metadata_preserved=False,
                      timing_ranges_sound_preserved=True, head_anchor_policy='fit-to-painted-collar',
                      original_head_artwork_preserved=True, independent_decoder_match=True,
                      accepted_v3_frame_uses_preserved=sum(row['accepted_v3_preserved'] for row in frame_proofs),
                      fixed_action_scales=scales, walking_lateral_roots=walking_x,
                      detached_artwork_flags=issues, installed=False, frame_registration=frame_proofs)
        (WORK / (sex + '-verification.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
        proofs.append(dict(sex=sex, preserved=report['accepted_v3_frame_uses_preserved'], images=len(images), detached=issues, scales=scales))
    plan['head_attachment_policy'] = 'fit-to-painted-collar'
    (WORK / 'art-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf8')
    (WORK / 'full-build-verification.json').write_text(json.dumps(dict(status='complete_candidate', files=all_files, checks=proofs), indent=2), encoding='utf8')
    print(json.dumps(proofs))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit', 'build'))
    args = parser.parse_args()
    audit() if args.command == 'audit' else build()
