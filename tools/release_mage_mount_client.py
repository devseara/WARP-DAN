"""Guarded client-only death/GrayMap update; no GRF or server mutation.

Current state and acceptance boundaries: docs/hd-sprites.md.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import hd_sprite_release as release

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Outputs/mage-death-graymap-v49-r2'
CHECKPOINT = WORK / 'installation'
CLIENT = '2025-07-16_Ragexe_175220998_clientinfo_patched.exe'
ATLAS = 'data/texture/graymap/cells.tga'
NAMES = [CLIENT, 'riftlock-assets-v1.txt', 'riftlock-release.sig', ATLAS]
SOURCE_SHA = '17f8e579cd0a54f1d043e43a216041ade391088d00223d864cc8e15f8c09f891'
release.CLIENT = CLIENT


def digest(path):
    return release.transaction.digest(path)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def closed():
    p = subprocess.run(
        [
            'powershell',
            '-NoProfile',
            '-Command',
            "@(Get-Process -Name '*Ragexe*','*roid*' -ErrorAction SilentlyContinue).Count",
        ],
        capture_output=True,
        text=True,
        creationflags=0x08000000,
    )
    assert p.returncode == 0 and p.stdout.strip() == '0', 'Close Ragnarok before replacement.'


def prepare():
    assert not CHECKPOINT.exists(), 'Inspect the existing checkpoint instead of overwriting it.'
    assert digest(release.GAME / CLIENT) == SOURCE_SHA
    build = load(WORK / 'preservation.json')
    candidate = Path(build['candidate'])
    assert digest(candidate) == build['candidate_sha256']
    assert build['imports_preserved'] and build['overlay_preserved']
    for name in [
        'death-dispatch.json',
        'compositor-verification.json',
        'mount-lifecycle-verification.json',
        'graymap-verification.json',
        'graymap-ui-verification.json',
    ]:
        report = load(WORK / name)
        assert report['passed'], name
        if 'client_sha256' in report:
            assert report['client_sha256'] == build['candidate_sha256']
    assert load(WORK / 'depth-verification.json')['passed']
    assert digest(WORK / 'release' / ATLAS) == digest(ROOT / 'Assets/GrayMap/cells.tga')
    signature = release.verify_signature()
    before = {}
    for name in NAMES:
        p = release.GAME / name
        before[name] = digest(p) if p.exists() else None
        if p.exists():
            backup = CHECKPOINT / 'before' / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, backup)
    immutable = {
        p.name: digest(p)
        for p in list(release.GAME.glob('*.grf'))
        + [release.GAME / 'riftlock.dll', release.GAME / 'libsodium.dll', release.GAME / 'DATA.INI']
    }
    save(
        CHECKPOINT / 'release.json',
        dict(
            status='ready',
            candidate=str(candidate),
            candidate_sha256=build['candidate_sha256'],
            before=before,
            immutable=immutable,
            signature_before=signature,
            live_accepted=False,
        ),
    )
    print('Prepared death routing + GrayMap; game files unchanged.')


def verify():
    r = load(CHECKPOINT / 'release.json')
    assert digest(release.GAME / CLIENT) == r['candidate_sha256']
    assert digest(release.GAME / ATLAS) == digest(ROOT / 'Assets/GrayMap/cells.tga')
    assert all(digest(release.GAME / n) == h for n, h in r['immutable'].items())
    signature = release.verify_signature()
    independent = CHECKPOINT / 'independent-manifest.txt'
    p = subprocess.run(
        [
            sys.executable,
            str(release.SERVER / 'tools/riftlock_assets.py'),
            '--game-root',
            str(release.GAME),
            '--client-exe',
            str(release.GAME / CLIENT),
            '--output',
            str(independent),
        ],
        capture_output=True,
        creationflags=0x08000000,
    )
    assert p.returncode == 0
    assert independent.read_bytes() == (release.GAME / 'riftlock-assets-v1.txt').read_bytes()
    result = dict(
        passed=True,
        client_sha256=r['candidate_sha256'],
        signature_verified=signature['signature_verified'],
        independent_manifest_match=True,
        all_grfs_and_dlls_unchanged=True,
        graymap_atlas_verified=True,
        live_accepted=False,
    )
    save(CHECKPOINT / 'installed-verification.json', result)
    return result


def install():
    r = load(CHECKPOINT / 'release.json')
    assert r['status'] == 'ready'
    closed()
    assert all(
        (digest(release.GAME / n) if (release.GAME / n).exists() else None) == h
        for n, h in r['before'].items()
    ), 'Game files changed since preparation.'
    assert digest(Path(r['candidate'])) == r['candidate_sha256']
    assert all(digest(release.GAME / n) == h for n, h in r['immutable'].items())
    try:
        for name, source in [(CLIENT, Path(r['candidate'])), (ATLAS, WORK / 'release' / ATLAS)]:
            target = release.GAME / name
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_name(target.name + '.mount-update.pending')
            assert not pending.exists()
            shutil.copyfile(source, pending)
            assert digest(pending) == digest(source)
            closed()
            os.replace(pending, target)
        p = subprocess.run(
            [
                sys.executable,
                str(release.SERVER / 'tools/riftlock_release.py'),
                '--game-root',
                str(release.GAME),
                '--client-exe',
                CLIENT,
                '--build-id',
                '1',
                '--secret',
                str(release.SERVER / 'conf/riftlock-server.key'),
                '--library',
                str(release.SERVER / 'libsodium.dll'),
            ],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
        )
        (CHECKPOINT / 'signing.log').write_text(p.stdout + p.stderr, encoding='utf-8')
        assert p.returncode == 0, 'Release signing failed.'
        verify()
    except BaseException:
        assert digest(release.GAME / CLIENT) in [
            SOURCE_SHA,
            r['candidate_sha256'],
        ], 'External client change; inspect checkpoint.'
        for name, sha in r['before'].items():
            dest = release.GAME / name
            if sha is None:
                if dest.exists():
                    dest.unlink()
            else:
                temp = dest.with_name(dest.name + '.mount-restore.pending')
                shutil.copyfile(CHECKPOINT / 'before' / name, temp)
                os.replace(temp, dest)
        r['status'] = 'rolled_back'
        save(CHECKPOINT / 'release.json', r)
        release.verify_signature()
        raise
    r['status'] = 'installed_for_live_testing'
    save(CHECKPOINT / 'release.json', r)
    print('PASS installed death routing + GrayMap; GRFs/server unchanged; signature verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'install', 'verify'])
    globals()[parser.parse_args().action]()
