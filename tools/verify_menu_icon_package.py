"""Check release bytes and optionally reconstruct the full-WARP update in an isolated index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
RELEASE = PACKAGE / 'updates/vip-battlepass-menu'


def verify(warp=None):
    manifest = json.loads((RELEASE / 'manifest.json').read_text(encoding='utf-8'))
    files = RELEASE / 'files'
    actual_paths = {p.relative_to(files).as_posix() for p in files.rglob('*') if p.is_file()}
    assert actual_paths == set(manifest['files']), 'Release inventory differs from the manifest'
    for relative, expected in manifest['files'].items():
        path = Path(relative)
        assert not path.is_absolute() and '..' not in path.parts
        assert path.parts[0] in ('Assets', 'Patches', 'Scripts', 'docs', 'tools'), relative
        assert path.suffix.lower() not in ('.exe', '.dll', '.pdb'), relative
        raw = (files / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected['sha256'], relative
        if path.suffix == '.qjs':
            assert raw.startswith(b'/*') and b'\n' not in raw.replace(b'\r\n', b''), relative
    patch = PACKAGE / manifest['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == manifest['patch_sha256']
    for directory, stem in (('VipUI', 'vip'), ('BattlepassUI', 'battlepass')):
        menu = files / 'Assets' / directory / 'menuicon'
        icons = json.loads((menu / 'manifest.json').read_text(encoding='utf-8'))['files']
        assert len(icons) == 12
        assert {p.name for p in menu.glob('*.bmp')} == set(icons)
        for name, spec in icons.items():
            raw = (menu / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == spec['sha256'], name
            assert raw[:2] == b'BM' and struct.unpack_from('<H', raw, 28)[0] == 24, name
            assert list(struct.unpack_from('<ii', raw, 18)) == spec['size'], name
            assert tuple(spec['size']) == ((32, 34) if '_old_' in name else (45, 41)), name
        assert (menu / f'bt_{stem}_press.bmp').read_bytes() == (menu / f'bt_{stem}_pressed.bmp').read_bytes()
        assert (menu / f'bt_{stem}_old_disabled.bmp').read_bytes() == (menu / f'bt_{stem}_old_normal.bmp').read_bytes()
    print(f'PASS: {len(actual_paths)} source/artwork/test files, both 12-icon families and installation diff')
    if warp:
        with tempfile.TemporaryDirectory(prefix='menu-icons-index-') as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
            def git(*args):
                return subprocess.check_output(['git', '-C', str(warp), *args], env=env)
            git('read-tree', manifest['base_commit'])
            git('apply', '--cached', '--check', str(patch))
            git('apply', '--cached', '--whitespace=nowarn', str(patch))
            assert git('write-tree').decode().strip() == manifest['result_tree']
            changed = git('diff', '--cached', '--name-only', manifest['base_commit']).decode().splitlines()
            assert changed == manifest['changed_paths']
            for relative, expected in manifest['files'].items():
                assert git('rev-parse', ':' + relative).decode().strip() == expected['git_blob'], relative
            print('PASS: isolated installation matches every published source blob and expected result tree')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--warp', type=Path, help='Full WARP clone containing the declared base commit')
    verify(parser.parse_args().warp)
