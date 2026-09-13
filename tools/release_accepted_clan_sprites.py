"""Build pinned current world pairs and install them with native ACT UI."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import numpy as np
from sprite_formats import read_spr, read_act
from package_clan_skin_assets import pack_payloads
from clan_grf_transaction import digest, replace_records, finish, rollback
from grf_reader import GrfFile
from spr_reader import Spr

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/evidence/clan-sprites-current.json'
CONFIG = json.loads(MANIFEST.read_text(encoding='utf8'))
assert re.fullmatch(r'[a-z0-9-]+', CONFIG['release_id'])
RELEASE = ROOT / 'Assets/ClanBodySkins/releases' / CONFIG['release_id']
PATCH = RELEASE / ('angel-' + CONFIG['release_id'] + '.grf')
GAME = Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes')


def validate_active_release(manifest, state):
    """Do not let a historical manifest overwrite the active correction."""
    if state.get('status') not in ('prepared_requested_correction', 'deployed_requested_correction', 'accepted_pending_installation', 'accepted_installed'):
        return
    current = {row['entry']: row['sha256'] for row in manifest['resources']}
    active = state.get('resources', [])
    if not active or any(current.get(row['entry']) != row['sha256'] for row in active):
        tool = state.get('package_tool', 'the active correction packager')
        raise ValueError('Release manifest would downgrade the active correction. Use ' + tool + ' or update the pinned current manifest.')


def current_payloads():
    manifest = CONFIG
    assert manifest['status'] in ('accepted', 'installed_correction')
    correction = ROOT / 'Assets/ClanBodySkins/Mage/installed-correction.json'
    if correction.exists():
        validate_active_release(manifest, json.loads(correction.read_text(encoding='utf8')))
    result = {}
    for row in manifest['resources']:
        path = ROOT / row['source']
        if not path.is_file():
            raise FileNotFoundError('Restore the sprite source/work bundle before packaging: ' + str(path))
        assert digest(path) == row['sha256'], path
        result[row['entry']] = path.read_bytes()
    assert len(result) == 8 and not any('/preview/' in name for name in result)
    return result


# Compatibility for locally archived authoring scripts.
accepted_payloads = current_payloads


def build():
    payloads = current_payloads()
    pairs = []
    for name, raw in payloads.items():
        if not name.endswith('.spr'):
            continue
        images, independent = read_spr(raw), Spr(raw)
        assert not independent.n_indexed8 and len(images) == len(independent.images)
        for image, other in zip(images, independent.images):
            # Independent parser supplies raw bottom-up ABGR storage.
            pixels = np.frombuffer(other.pixels, np.uint8).reshape(other.height, other.width, 4)
            assert image.size == (other.width, other.height)
            assert image.tobytes() == pixels[::-1, :, [3, 2, 1, 0]].copy().tobytes()
        act = read_act(payloads[name[:-4] + '.act'])
        assert len(act.actions) == 104 and sum(map(len, act.actions)) == 456
        for frames in act.actions:
            for frame in frames:
                assert len(frame.layers) == 1
                layer = frame.layers[0]
                assert layer.kind == 1 and layer.sx == layer.sy == .25 and layer.angle == 0
                assert 0 <= layer.index < len(images)
        pairs.append(dict(entry=name, actions=104, frame_uses=456, independent_decoder_match=True))
    pack_payloads(payloads, PATCH)
    report = dict(status=CONFIG['status'], visual_acceptance=CONFIG['visual_acceptance'], patch=str(PATCH.relative_to(ROOT)),
                  sha256=digest(PATCH), entries=8, pairs=pairs,
                  previews='NativeActJobPreviews consumes these same world SPR/ACT pairs',
                  generated_preview_entries=0)
    (RELEASE / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return payloads


def install(payloads, game):
    main, update = game / 'maindata.grf', game / 'update.grf'
    legacy = {row['entry']: row['sha256'] for row in CONFIG['legacy_update_resources']}
    assert len(legacy) == 16
    a, b = GrfFile(main), GrfFile(update)
    try:
        duplicates = {name for name in legacy if name in b.entries}
        # Remove only verified copies of the exact previous release. Every
        # removed name must already exist safely in the destination archive.
        for name in duplicates:
            assert hashlib.sha256(b.read(name)).hexdigest() == legacy[name], ('Modified update resource', name)
            assert name in a.entries
            expected = {legacy[name]}
            if name in payloads:
                expected.add(hashlib.sha256(payloads[name]).hexdigest())
            assert hashlib.sha256(a.read(name)).hexdigest() in expected, ('Modified maindata resource', name)
    finally:
        a.close()
        b.close()
    main_result = replace_records(main, payloads, RELEASE / 'maindata-transaction.json')
    installed = GrfFile(main)
    try:
        for name, raw in payloads.items():
            assert installed.read(name) == raw
        for name in duplicates - set(payloads):
            assert hashlib.sha256(installed.read(name)).hexdigest() == legacy[name]
    finally:
        installed.close()
    update_result = replace_records(update, {}, RELEASE / 'update-dedup-transaction.json', remove=duplicates)
    a, b = GrfFile(main), GrfFile(update)
    try:
        for name, raw in payloads.items():
            assert name not in b.entries and a.read(name) == raw
    finally:
        a.close()
        b.close()
    report = dict(status='installed', authoritative_archive=str(main),
                  maindata_sha256=digest(main), update_sha256=digest(update),
                  patch_sha256=digest(PATCH), world_entries=8,
                  duplicate_update_entries_removed=len(duplicates),
                  archive_priority_verified=True, exe_modified=False,
                  maindata_transaction=main_result, update_transaction=update_result)
    # Keep completed transaction evidence on an idempotent verification run.
    receipt = RELEASE / 'installation.json'
    if not receipt.exists() or main_result['status'] != 'already_current' or update_result['status'] != 'already_current':
        receipt.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('_transaction')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--install', action='store_true')
    group.add_argument('--finish', type=Path, metavar='RECEIPT')
    group.add_argument('--rollback', type=Path, metavar='RECEIPT')
    parser.add_argument('--game', type=Path, default=GAME)
    args = parser.parse_args()
    if args.finish:
        finish(args.finish)
    elif args.rollback:
        rollback(args.rollback)
    else:
        payloads = build()
        if args.install:
            install(payloads, args.game)
