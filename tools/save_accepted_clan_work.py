"""Save current pinned exports and authoring sources without review duplicates."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile
from release_accepted_clan_sprites import ROOT, RELEASE, CONFIG, current_payloads


def source_closure(seeds):
    found, queue = set(), list(seeds)
    while queue:
        path = queue.pop()
        if path in found or not path.is_file():
            continue
        found.add(path)
        if path.suffix != '.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf8'))
        for node in ast.walk(tree):
            names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            if isinstance(node, ast.Import):
                names += [alias.name for alias in node.names]
            for name in names:
                queue.append(ROOT / 'tools' / (name.replace('.', '/') + '.py'))
    return found


def main():
    current_payloads()  # Verify pinned current sources before saving.
    seeds = CONFIG['authoring_tools'] + ['release_accepted_clan_sprites.py', 'save_accepted_clan_work.py']
    missing = [name for name in seeds if not (ROOT / 'tools' / name).is_file()]
    if missing:
        raise FileNotFoundError('Restore the authoring source bundle before archiving: ' + ', '.join(missing))
    files = source_closure([ROOT / 'tools' / name for name in seeds])
    files.update((ROOT / 'tools/dual_weapon_formats').glob('*.py'))
    bases = {'Swordman/accepted-walk-v8', 'Swordman/complete-v9',
             'Mage/male-gait-v3', 'Mage/female-gait-v7',
             'Mage/walk-repair-v2', 'Mage/female-gait-v6',
             'Mage/female-gait-v8', 'Mage/female-gait-v9'}
    assets = ROOT / 'Assets/ClanBodySkins'
    for job in ('Swordman', 'Mage'):
        for path in (assets / job).rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(assets)
            parts = relative.parts
            if 'review' in parts or path.suffix == '.zip':
                continue
            selected = (path.suffix == '.json'
                        or 'native' in parts
                        or ('art' in parts or 'refs' in parts or 'design' in parts) and path.suffix == '.png'
                        or '/'.join(parts[:2]) in bases and 'assets' in parts)
            if selected:
                files.add(path)
    files.update(ROOT / row['source'] for row in CONFIG['resources'])
    files.add(ROOT / 'docs/clan-body-skins.md')
    files.update((ROOT / 'docs/evidence').glob('clan-*.json'))
    files.update(RELEASE.glob('*transaction.json'))
    for path in (RELEASE / 'verification.json', assets / 'releases/cleanup-manifest.json'):
        if path.is_file():
            files.add(path)
    archive = RELEASE / 'current-work.zip'
    rows = []
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(files):
            relative = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            rows.append(dict(path=relative, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            output.writestr(relative, raw)
        output.writestr('saved-work-files.json', json.dumps(rows, indent=2))
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for row in rows:
            assert hashlib.sha256(output.read(row['path'])).hexdigest() == row['sha256']
    report = dict(status='saved_and_verified', archive=archive.name,
                  sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  bytes=archive.stat().st_size, files=len(rows),
                  source_files=sum(row['path'].startswith('tools/') for row in rows),
                  excludes=['review renders', 'previous ZIP copies'], manifest=rows)
    (RELEASE / 'saved-work.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'manifest'}), flush=True)


if __name__ == '__main__':
    main()
