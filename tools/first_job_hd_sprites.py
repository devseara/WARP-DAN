"""Maintain the frozen, user-accepted first-job HD release.

Rebuilds must match the accepted SPR/ACT bytes. Authoring experiments and
one-off repairs are archived; this tool never regenerates or refits artwork.
"""
from pathlib import Path
from functools import lru_cache
import argparse
import configparser
import copy
import json
import math

import numpy as np
from PIL import Image

import novice_hd_common as base
from clan_grf_transaction import digest, replace_records
from dual_weapon_formats.grf_reader import GrfFile
from package_hd_job_ui_grf import write_grf

ROOT = base.ROOT
RECORD = ROOT / 'Inputs/HDFirstJobs/accepted-v1.json'
CANVAS = (320, 320)
ORIGIN = (160, 240)
JOBS = {'swordman': 'Swordman', 'mage': 'Mage', 'archer': 'Archer',
        'acolyte': 'Acolyte', 'merchant': 'Merchant', 'thief': 'Thief'}
GROUPS = ['idle', 'walk', 'sit', 'pickup', 'combat1', 'combat2', 'hit',
          'pose7', 'death', 'standby', 'combat3', 'combat4', 'cast']


def accepted():
    record = base.load(RECORD)
    assert record['status'] == 'user_accepted' and record['user_acceptance']
    work = ROOT / record['work']
    assert digest(work / record['source_plan']) == record['source_plan_sha256']
    return record, work, base.load(work / record['source_plan'])


@lru_cache(maxsize=12)
def context(job, sex):
    _, work, _ = accepted()
    folder = work / 'native' / job / sex
    head = work / 'native/heads' / sex
    return (
        [im.convert('RGBA') for im in base.decode_spr((folder / 'body.spr').read_bytes())[0]],
        base.read_act((folder / 'body.act').read_bytes()),
        [im.convert('RGBA') for im in base.decode_spr((head / 'head.spr').read_bytes())[0]],
        base.read_act((head / 'head.act').read_bytes()),
    )


def native_body(job, sex, ai, fi):
    images, act, _, _ = context(job, sex)
    canvas = Image.new('RGBA', CANVAS)
    for layer in act.actions[ai][fi].layers:
        if layer.index < 0:
            continue
        assert layer.kind == 0 and layer.sx == layer.sy == 1 and layer.angle == 0
        image = images[layer.index]
        if layer.mirror:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        canvas.alpha_composite(image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST),
            (ORIGIN[0] + 2 * (layer.x - image.width // 2), ORIGIN[1] + 2 * (layer.y - image.height // 2)))
    return canvas


def native_head(job, sex, ai, fi):
    _, act, images, heads = context(job, sex)
    frame = act.actions[ai][fi]
    head = heads.actions[ai][min(fi, len(heads.actions[ai]) - 1)]
    bx, by = base.anchor(frame)
    hx, hy = base.anchor(head)
    canvas = Image.new('RGBA', CANVAS)
    for layer in head.layers:
        if layer.index < 0:
            continue
        image = images[layer.index]
        if layer.mirror:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST)
        if layer.angle:
            image = image.rotate(-layer.angle, Image.Resampling.NEAREST, expand=True)
        canvas.alpha_composite(image, (int(ORIGIN[0] + (layer.x + bx - hx) * 2 - image.width // 2),
                                       int(ORIGIN[1] + (layer.y + by - hy) * 2 - image.height // 2)))
    return canvas


def replay(image, row, frame, originals):
    first_x, first_y = row['native_layer']
    layer = frame.layers[0]
    raw = originals[layer.index]
    if layer.mirror:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        # Native odd-width mirrored sprites are not centered on the same edge.
        dx = (first_x + layer.x - 2 * (raw.width // 2) + raw.width) * 2
    else:
        dx = (layer.x - first_x) * 2
    canvas = Image.new('RGBA', CANVAS)
    canvas.alpha_composite(image, (dx, (layer.y - first_y) * 2))
    return canvas


def bake(image):
    # Encoding must preserve every alpha pixel and compensate the cropped origin.
    # This is not anatomical fitting; new collar/sole measurements use alpha>=128.
    bounds = image.getbbox()
    assert bounds
    x, y = bounds[0] // 2 * 2, bounds[1] // 2 * 2
    width = math.ceil((bounds[2] - x) / 4) * 4
    height = math.ceil((bounds[3] - y) / 4) * 4
    lx = (x + width // 2 - ORIGIN[0]) // 2
    ly = (y + height // 2 - ORIGIN[1]) // 2
    assert ORIGIN[0] + 2 * lx - width // 2 == x
    assert ORIGIN[1] + 2 * ly - height // 2 == y
    return image.crop((x, y, x + width, y + height)), lx, ly


def render_export(images, frame):
    canvas = Image.new('RGBA', CANVAS)
    for layer in frame.layers:
        assert layer.kind == 1 and layer.sx == layer.sy == 0.5
        assert not layer.mirror and not layer.angle
        image = images[layer.index]
        canvas.alpha_composite(image, (ORIGIN[0] + 2 * layer.x - image.width // 2,
                                       ORIGIN[1] + 2 * layer.y - image.height // 2))
    return canvas


def resource_map(record):
    return {(r['job'], r['sex'], Path(r['path']).suffix): r for r in record['resources']}


def verify_sources(record, work, plan):
    for pin in plan['native_files']:
        assert digest(work / pin['path']) == pin['sha256'], pin['path']
    for pose in plan['poses']:
        assert digest(work / pose['paint']) == pose['sha256'], pose['paint']
    for resource in record['resources']:
        assert digest(work / resource['path']) == resource['sha256'], resource['path']


def audit_pair(job, sex, images, act, originals, native, rows, paints):
    assert act.sounds == native.sounds and act.speeds == native.speeds and act.tail == native.tail
    assert len(act.actions) == len(native.actions)
    uses = 0
    for ai, frames in enumerate(native.actions):
        assert len(act.actions[ai]) == len(frames)
        for fi, frame in enumerate(frames):
            got = act.actions[ai][fi]
            assert (got.anchors, got.ranges, got.sound) == (frame.anchors, frame.ranges, frame.sound)
            index = frame.layers[0].index
            expected = replay(paints[index], rows[index], frame, originals)
            assert render_export(images, got).tobytes() == expected.tobytes(), (job, sex, ai, fi)
            uses += 1
    return uses


def independent_decode(blob):
    images = base.decode_spr(blob)[0]
    independent = base.Spr(blob)
    assert len(images) == len(independent.images)
    for image, raw in zip(images, independent.images):
        values = np.frombuffer(raw.pixels, np.uint8).reshape(raw.height, raw.width, 4)
        assert image.tobytes() == values[::-1, :, [3, 2, 1, 0]].copy().tobytes()
    return images


def verify(installed=False):
    record, work, plan = accepted()
    verify_sources(record, work, plan)
    resources = resource_map(record)
    coverage = []
    for pair in plan['pairs']:
        job, sex = pair['job'], pair['sex']
        originals, native, _, _ = context(job, sex)
        rows = {p['sprite']: p for p in plan['poses'] if (p['job'], p['sex']) == (job, sex)}
        paints = {i: Image.open(work / p['paint']).convert('RGBA') for i, p in rows.items()}
        images = independent_decode((work / resources[(job, sex, '.spr')]['path']).read_bytes())
        act = base.read_act((work / resources[(job, sex, '.act')]['path']).read_bytes())
        uses = audit_pair(job, sex, images, act, originals, native, rows, paints)
        assert uses == pair['frame_uses']
        coverage.append(dict(job=job, sex=sex, actions=len(act.actions), frame_uses=uses))
    result = dict(status='verified_accepted_resources',pairs=coverage,
                  resource_hashes_verified=len(record['resources']),source_pose_hashes_verified=len(plan['poses']))
    if installed:
        target = Path(record['installed_archive'])
        desired = {r['entry']:(work / r['path']).read_bytes() for r in record['resources']}
        check_priority(target, desired)
        archive = GrfFile(target)
        try:
            for name, data in desired.items():
                assert archive.read(name) == data, name
        finally:
            archive.close()
        result['installed_resources_match'] = True
        result['installed_archive_sha256'] = digest(target)
        result['whole_archive_matches_acceptance'] = result['installed_archive_sha256'] == record['installed_archive_sha256']
    base.save(work / 'verification/current.json', result)
    print(json.dumps(dict(status=result['status'],first_job_pairs=len(coverage),
                          frame_uses=sum(r['frame_uses'] for r in coverage),installed=installed)))
    return result


def build():
    record, work, plan = accepted()
    verify_sources(record, work, plan)
    resources = resource_map(record)
    output = work / 'rebuilt'
    output.mkdir(exist_ok=True)
    proof = []
    for pair in plan['pairs']:
        job, sex = pair['job'], pair['sex']
        originals, native, _, _ = context(job, sex)
        rows = {p['sprite']: p for p in plan['poses'] if (p['job'], p['sex']) == (job, sex)}
        paints = {i: Image.open(work / p['paint']).convert('RGBA') for i, p in rows.items()}
        act, images, dedup = copy.deepcopy(native), [], {}
        for ai, frames in enumerate(native.actions):
            for fi, frame in enumerate(frames):
                index = frame.layers[0].index
                canvas = replay(paints[index], rows[index], frame, originals)
                alpha = np.asarray(canvas)[:, :, 3]
                assert not np.any(alpha[[0, -1]]) and not np.any(alpha[:, [0, -1]])
                crop, x, y = bake(canvas)
                key = (crop.size, base.sha(crop.tobytes()))
                if key not in dedup:
                    dedup[key] = len(images)
                    images.append(crop)
                act.actions[ai][fi].layers = [base.Layer(x, y, dedup[key], sx=.5, sy=.5)]
        blobs = {'.spr': base.write_spr(images), '.act': base.write_act(act)}
        decoded = independent_decode(blobs['.spr'])
        reopened = base.read_act(blobs['.act'])
        audit_pair(job, sex, decoded, reopened, originals, native, rows, paints)
        for ext, blob in blobs.items():
            expected = resources[(job, sex, ext)]['sha256']
            assert base.sha(blob) == expected, ('Rebuild changed accepted bytes', job, sex, ext)
            path = output / f'{job}-{sex}{ext}'
            path.write_bytes(blob)
            proof.append(dict(job=job, sex=sex, path=path.relative_to(work).as_posix(),
                              sha256=expected, byte_identical=True))
    base.save(work / 'verification/rebuild.json', dict(status='byte_identical',files=proof))
    print(json.dumps(dict(status='byte_identical',first_job_pairs=len(plan['pairs']),files=len(proof))))


def package():
    record, work, _ = accepted()
    desired = {}
    for resource in record['resources']:
        data = (work / resource['path']).read_bytes()
        assert base.sha(data) == resource['sha256']
        desired[resource['entry']] = data
    destination = work / record['distribution']['path']
    write_grf(desired, destination)
    assert digest(destination) == record['distribution']['sha256']
    print(json.dumps(dict(status='accepted_package_verified',resources=len(desired),path=str(destination))))


def check_priority(target, desired):
    game = target.resolve().parent
    config = configparser.ConfigParser()
    config.read(game / 'DATA.INI', encoding='utf8')
    order = [name for _, name in sorted(config.items('Data'), key=lambda r: int(r[0]))]
    assert order.count(target.name) == 1
    for name in order:
        assert (game / name).resolve().parent == game
    for name in order[:order.index(target.name)]:
        archive = GrfFile(game / name)
        try:
            assert not set(desired).intersection(archive.entries), ('Higher-priority override', name)
        finally:
            archive.close()
    for name in desired:
        assert not (game / name).exists(), ('Loose override', name)


def deploy():
    record, work, plan = accepted()
    verify_sources(record, work, plan)
    target = Path(record['installed_archive']).resolve()
    desired = {r['entry']:(work / r['path']).read_bytes() for r in record['resources']}
    check_priority(target, desired)
    # Never overwrite the acceptance transaction receipt. Later installs get their own receipt.
    receipt = work / 'recovery' / ('reinstall-from-' + digest(target)[:16] + '.json')
    assert not receipt.exists(), 'Inspect the previous transaction before retrying this archive version'
    result = replace_records(target, desired, receipt)
    verify(installed=True)
    print(json.dumps(dict(status=result['status'],resources=len(desired),target=str(target))))


def review():
    record, work, plan = accepted()
    verify_sources(record, work, plan)
    resources = resource_map(record)
    directory = work / 'review/images'
    directory.mkdir(parents=True, exist_ok=True)
    def put(image):
        import io
        stream = io.BytesIO()
        image.save(stream, format='PNG')
        data = stream.getvalue()
        path = directory / (base.sha(data) + '.png')
        if not path.exists():
            path.write_bytes(data)
        return path.relative_to(work).as_posix()
    data = []
    for job, title in JOBS.items():
        for sex in ['male', 'female']:
            pending = (job, sex, '.spr') not in resources
            originals, native, _, _ = context(job, sex)
            if not pending:
                images = independent_decode((work / resources[(job, sex, '.spr')]['path']).read_bytes())
                act = base.read_act((work / resources[(job, sex, '.act')]['path']).read_bytes())
            actions = []
            for ai, frames in enumerate(native.actions):
                entries = []
                for fi, frame in enumerate(frames):
                    original = native_body(job, sex, ai, fi)
                    body = original if pending else render_export(images, act.actions[ai][fi])
                    head = native_head(job, sex, ai, fi)
                    touching = (np.asarray(original)[:, :, 3] > 128) & (np.asarray(head)[:, :, 3] > 128)
                    yy, xx = np.where(touching)
                    focus = [round(float(np.median(xx))), round(float(np.median(yy)))+3] if len(xx) else [160,130]
                    entries.append(dict(native=put(original),hd=put(body),head=put(head),
                        sprite=frame.layers[0].index,neck_focus=focus))
                actions.append(dict(action=ai,direction=ai % 8,group=GROUPS[ai // 8],
                                    ms=round(native.speeds[ai]*25),frames=entries))
            data.append(dict(job=job,title=title,sex=sex,pending=pending,actions=actions))
    template = (ROOT / 'tools/first_job_hd_review.html').read_text(encoding='utf8')
    (work / 'review.html').write_text(template.replace('__DATA__',json.dumps(data,separators=(',',':'))),encoding='utf8')
    print(json.dumps(dict(review=str(work / 'review.html'),accepted_pairs=11,pending_pairs=1)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['verify','build','package','review','deploy'])
    parser.add_argument('--installed', action='store_true', help='Also verify the installed GRF without writing it')
    args = parser.parse_args()
    if args.stage == 'verify':
        verify(installed=args.installed)
    else:
        assert not args.installed, '--installed applies to verify only'
        {'build':build,'package':package,'review':review,'deploy':deploy}[args.stage]()
