"""Build, review and save a complete original Angel job candidate."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from package_clan_skin_assets import ROOT, pack_payloads
from build_mage_pose_set import build
from review_full_swordman_set import main as review, joined
from sprite_formats import read_spr, read_act
from sprite_review_animation import save_review_animation
from refine_clan_combat_necks import components
from save_accepted_clan_work import source_closure
from prepare_angel_job_sources import JOBS


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(job, work, revision='v1'):
    pairs = {}
    files, checks, payloads = [], [], {}
    for sex, key in [('male', '남'), ('female', '여')]:
        report = json.loads((work / (sex + '-verification.json')).read_text(encoding='utf8'))
        assert not report['missing_sheets'] and not report['stock_fallback_frames']
        assert not report['detached_artwork_flags']
        paths = [work / row['path'] for row in report['files']]
        for path, row in zip(paths, report['files']):
            assert digest(path) == row['sha256']
            files.append(dict(sex=sex, path=row['path'], bytes=path.stat().st_size, sha256=row['sha256']))
            payloads[f'data/sprite/clan_skins/1/인간족/몸통/{key}/{JOBS[job]}_{key}{path.suffix}'] = path.read_bytes()
        images, act = read_spr(paths[0].read_bytes()), read_act(paths[1].read_bytes())
        assert len(act.actions) == 104 and sum(map(len, act.actions)) == 456
        for index, image in enumerate(images):
            data = np.asarray(image)
            mask = data[:, :, 3] > 0
            rgb = data[:, :, :3].astype(int)
            assert not data[~mask].any(), (sex, index, 'transparent RGB residue')
            assert not (mask & (rgb[:, :, 1] > 95) & (rgb[:, :, 1] - rgb[:, :, 0] > 48)
                        & (rgb[:, :, 1] - rgb[:, :, 2] > 48)).any(), (sex, index, 'green key')
            assert not (mask & (rgb[:, :, 0] > 160) & (rgb[:, :, 2] > 145)
                        & (rgb[:, :, 1] < 120)).any(), (sex, index, 'registration key')
            assert len(components(mask)) == 1, (sex, index, 'detached component')
        pairs[sex] = images, act
        checks.append(dict(sex=sex, actions=104, frame_uses=456, unique_native_drawings=report['unique_drawings'],
                           exported_images=len(images), original_metadata_preserved=report.get('native_metadata_preserved',True),
                           timing_ranges_sound_preserved=report.get('timing_ranges_sound_preserved',True),
                           head_anchor_policy=report.get('head_anchor_policy','native'),
                           independent_decoder_match=report['independent_decoder_match'],
                           single_connected_body=True, key_and_transparent_rgb_checks=True))

    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)
    loops = work / 'review/walk-loops'
    loops.mkdir(parents=True, exist_ok=True)
    for direction in range(8):
        frames = []
        for fi in range(8):
            frame = Image.new('RGB', (880, 290), '#283746')
            pen = ImageDraw.Draw(frame)
            for col, (sex, original) in enumerate([('male', True), ('male', False), ('female', True), ('female', False)]):
                image = joined(sex, 8 + direction, fi, None if original else pairs[sex], job=job)
                image = image.crop((100, 40, 540, 560)).resize((220, 260), Image.Resampling.NEAREST)
                frame.paste(image, (col * 220, 22), image)
                pen.text((col * 220 + 5, 3), sex.title() + (' / Original' if original else ' / Angel'), font=font, fill='white')
            frames.append(frame)
        ms = round(pairs['male'][1].speeds[8 + direction] * 25)
        save_review_animation(frames, loops / f'direction-{direction}.gif', ms, loops / f'direction-{direction}.png')

    overview = Image.new('RGB', (1200, 620), '#283746')
    pen = ImageDraw.Draw(overview)
    for row, sex in enumerate(('male', 'female')):
        for col, (label, ai, fi) in enumerate([('Idle', 0, 0), ('Front walk', 8, 2), ('Side walk', 10, 3),
                                               ('Rear walk', 12, 2), ('Attack', 40, 0), ('Cast', 96, 2)]):
            image = joined(sex, ai, fi, pairs[sex], job=job).crop((120, 40, 520, 580)).resize((200, 270), Image.Resampling.NEAREST)
            overview.paste(image, (col * 200, row * 310 + 28), image)
            pen.text((col * 200 + 5, row * 310 + 5), sex.title() + ' / ' + label, font=font, fill='white')
    overview.save(work / 'overview.png')

    patch = work / f'angel-{job}-{revision}-review.grf'
    pack_payloads(payloads, patch)
    result = dict(status='complete_candidate_awaiting_visual_review', job=job, files=files, checks=checks,
                  installed=False, accepted=False, review='full-action-review.html', overview='overview.png',
                  grf=dict(path=patch.name, sha256=digest(patch)),
                  prompt_records='generation-records.json', tool='Built-in image generation plus native-pose import')
    feedback=work/'user-review.json'
    if feedback.exists():
        user_review=json.loads(feedback.read_text(encoding='utf8'))
        reviewed={row['path']:row['sha256'] for row in user_review.get('files',[])}
        if reviewed == {row['path']:row['sha256'] for row in files}:
            result['status']=user_review['status']
            result['accepted']=user_review['status']=='accepted'
            result['visual_acceptance_date']=user_review.get('date')
    installation = work / 'installation.json'
    if result['accepted'] and installation.exists():
        installed = json.loads(installation.read_text(encoding='utf8'))
        pinned = {row['path']: row['sha256'] for row in installed.get('files', [])}
        if installed.get('status') == 'installed' and pinned == {row['path']: row['sha256'] for row in files}:
            result['installed'] = True
            result['installation_record'] = installation.name
    (work / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    sources = source_closure([ROOT / 'tools/angel_job_pipeline.py', ROOT / 'tools/import_angel_job_art.py'])
    sources.update((ROOT / 'tools/dual_weapon_formats').glob('*.py'))
    selected = sources | {p for p in work.rglob('*') if p.is_file() and p.suffix not in ('.grf', '.zip')
                          and 'review' not in p.relative_to(work).parts and p.name != 'delivery.json'}
    selected.update(p for p in (work.parent / 'native').rglob('*') if p.is_file())
    selected.update(p for p in (work.parent / 'design').rglob('*') if p.is_file())
    for next_job in JOBS:
        for folder in ('native', 'design'):
            selected.update(p for p in (ROOT / 'Assets/ClanBodySkins' / next_job.title() / folder).rglob('*') if p.is_file())
    evidence=ROOT / 'Inputs/ClanBodySkins/records' / ('clan-' + job + '-' + revision + '.json')
    if evidence.exists():
        selected.add(evidence)
    spec_path=work/'build-spec.json'
    if spec_path.exists():
        spec=json.loads(spec_path.read_text(encoding='utf8'))
        selected.update(source_closure([ROOT/name for name in spec['source_tools']]))
        for name in spec['inputs']:
            path=ROOT/name
            if not path.is_file():
                raise FileNotFoundError('Missing rebuild input: '+name)
            selected.add(path)
    selected.add(ROOT / 'docs/clan-body-skins.md')
    archive = work.parent / (job.title() + '-' + revision + '-SPR-ACT-work.zip')
    inventory = []
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(selected):
            raw = path.read_bytes()
            relative = path.relative_to(ROOT).as_posix()
            output.writestr(relative, raw)
            inventory.append(dict(path=relative, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        output.writestr('saved-work-files.json', json.dumps(inventory, indent=2))
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for record in inventory:
            assert hashlib.sha256(output.read(record['path'])).hexdigest() == record['sha256']
    result['archive'] = dict(path=archive.name, sha256=digest(archive), bytes=archive.stat().st_size, files=len(inventory))
    (work / 'delivery.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({key: result[key] for key in ('status', 'job', 'archive', 'grf')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, choices=JOBS)
    parser.add_argument('--stage', choices=('build', 'review', 'package', 'all'), default='all')
    parser.add_argument('--work',type=Path)
    parser.add_argument('--revision',default='v1')
    args = parser.parse_args()
    work = args.work.resolve() if args.work else ROOT / 'Assets/ClanBodySkins' / args.job.title() / 'complete-v1'
    if args.revision!='v1' and args.stage in ('build','all'):
        parser.error('Use the revision build-spec command before review/package')
    if args.stage in ('build', 'all'):
        for sex in ('male', 'female'):
            build(sex, False, args.job, work)
    if args.stage in ('review', 'all'):
        review(False, work, args.job, '{sex}-angel-' + args.job + '-' + args.revision)
    if args.stage in ('package', 'all'):
        package(args.job, work, args.revision)
