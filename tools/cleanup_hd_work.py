"""Prune explicit superseded HD experiments; retain sources and scoped rollback.

Run plan first, inspect Outputs/cleanup-20261019, then apply. No game mutations.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Outputs/cleanup-20261019'
ART = ROOT / 'Assets/HDFirstJobs/animation-audit-v1'
KEEP = {
    'female-mage-gripping-v48',
    'female-mage-mounted-attachments-v45',
    'female-mage-proportion-redraw-v44',
    'female-mage-grounded-preparation-v16',
    'female-mage-complete-fit-v2',
}
RETIRED = [
    'build_mage_planted_review.py',
    'build_mounted_mage_knife.py',
    'package_mage_mount_review.py',
    'investigate_mage_mounted_v45.py',
    'release_all_riding_combat.py',
    'release_mage_mounted_v45.py',
    'release_mage_renderer_v46.py',
    'release_mage_mount_lifecycle_v47.py',
    'verify_mounted_mage_attachments.py',
]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


def bounded(path, root):
    assert path.is_file() and path.resolve().is_relative_to(root.resolve())
    assert not path.is_symlink()
    current = path
    while True:
        assert not (current.lstat().st_file_attributes & 1024), 'Unexpected reparse point'
        if current == root:
            break
        current = current.parent


def plan():
    rows = []
    for p in ART.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(ART)
        if rel.parts[0] in KEEP or not rel.parts[0].startswith('female-mage-'):
            continue
        if p.suffix == '.actproj' and not any(
            x in p.name.lower() for x in ['native', 'reference', 'accepted']
        ):
            rows.append(
                dict(
                    path=p.relative_to(ROOT).as_posix(),
                    bytes=p.stat().st_size,
                    reason='superseded editable experiment; accepted/current embedded sources retained',
                )
            )
        elif p.suffix in ['.act', '.spr'] and 'candidate' in rel.parts:
            rows.append(
                dict(
                    path=p.relative_to(ROOT).as_posix(),
                    bytes=p.stat().st_size,
                    reason='superseded export; current projects and installed resources retained',
                )
            )
    save(WORK / 'asset-plan.json', rows)
    print(
        f'Plan: {len(rows)} obsolete files, {sum(r["bytes"] for r in rows)/2**30:.2f} GiB; review PNGs/recipes retained.'
    )


def apply():
    # The current projects carry their own ACT/SPR artwork, not pointers into
    # the experiments being removed. Keep their complete directories untouched.
    pins = {}
    for rel in [
        'female-mage-proportion-redraw-v44/mage-fox-proportion-v44-r3.actproj',
        'female-mage-mounted-attachments-v45/mage-fox-equipped-v45-final.actproj',
        'female-mage-grounded-preparation-v16/mage-grounded-final.actproj',
        'female-mage-gripping-v48/knife-gripping.actproj',
        'female-mage-gripping-v48/rod-gripping.actproj',
    ]:
        p = ART / rel
        data = json.loads(p.read_text(encoding='utf-8'))
        assert data['Act'] and data['Spr'] and data['Layers']
        pins[p.relative_to(ROOT).as_posix()] = sha(p)
    rows = json.loads((WORK / 'asset-plan.json').read_text())
    for row in rows:
        p = ROOT / row['path']
        bounded(p, ART)
        assert p.relative_to(ART).parts[0] not in KEEP
        assert p.stat().st_size == row['bytes']
        row['sha256'] = sha(p)
    recovery = ROOT / 'Assets/HDFirstJobs/cleanup-history/20261019'
    recovery.mkdir(parents=True, exist_ok=True)
    old = [ROOT / 'tools' / name for name in RETIRED]
    old.append(ROOT / 'docs/all-riding-combat.md')
    assert all(p.exists() for p in old)
    archive = recovery / 'retired-tools-and-doc.zip'
    assert not archive.exists()
    archived = old + [ROOT / 'docs/hd-sprites.md']
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in archived:
            z.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        for p in archived:
            assert z.read(p.relative_to(ROOT).as_posix()) == p.read_bytes()
    # Replace historical whole-archive rollback copies with the exact resources
    # they changed. Keep the newest full backup as a separate recovery point.
    sys.path.insert(0, str(ROOT / 'tools'))
    from dual_weapon_formats.grf_reader import GrfFile

    backups = []
    for p in sorted((ROOT / 'Assets/HDFirstJobs/releases').glob('*/maindata.grf.before')):
        if p.parent.name == 'female-mage-fox-v44-r3-20261018':
            continue
        receipt = json.loads((p.parent / 'maindata-transaction.json').read_text())
        assert sha(p) == receipt['before_sha256']
        names = receipt['replaced'] + receipt['removed']
        target = p.parent / 'scoped-rollback.zip'
        assert not target.exists()
        grf = GrfFile(p)
        try:
            payload = {name: grf.read(name) for name in names}
        finally:
            grf.close()
        meta = dict(
            whole_archive_removed=True,
            original_sha256=receipt['before_sha256'],
            restore_resources={n: hashlib.sha256(b).hexdigest() for n, b in payload.items()},
            remove_on_rollback=receipt['added'],
            policy='Apply only named resources to a fresh guarded transaction; regenerate signing. Never restore historical signatures over current assets.',
        )
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            for n, b in payload.items():
                z.writestr(n, b)
            z.writestr('rollback.json', json.dumps(meta, indent=2))
        with zipfile.ZipFile(target) as z:
            assert z.testzip() is None
            for n, b in payload.items():
                assert z.read(n) == b
        backups.append(
            dict(
                path=p.relative_to(ROOT).as_posix(),
                bytes=p.stat().st_size,
                sha256=receipt['before_sha256'],
                replacement=target.relative_to(ROOT).as_posix(),
                replacement_bytes=target.stat().st_size,
            )
        )
    # Freeze the full deletion list before unlinking anything.
    record = dict(
        status='prepared',
        source_pins=pins,
        assets=rows,
        backups=backups,
        retired=[
            dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in old
        ],
        recovery_archive=archive.relative_to(ROOT).as_posix(),
    )
    save(recovery / 'manifest.json', record)
    for row in rows + backups + record['retired']:
        p = ROOT / row['path']
        bounded(p, ROOT)
        p.unlink()
    assert all(sha(ROOT / n) == h for n, h in pins.items())
    record['status'] = 'complete'
    record['bytes_reclaimed'] = (
        sum(r['bytes'] for r in rows + backups + record['retired'])
        - sum(r['replacement_bytes'] for r in backups)
        - archive.stat().st_size
    )
    save(recovery / 'manifest.json', record)
    print(
        f'PASS cleanup: {record["bytes_reclaimed"]/2**30:.2f} GiB reclaimed; current source hashes unchanged.'
    )


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'apply'])
    globals()[p.parse_args().action]()
