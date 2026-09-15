"""Check the user-accepted Battle Pass/Gacha source baseline without modifying it.

Text hashes normalize CRLF to LF for Git portability; binary assets are exact.
This detects changes, not gameplay correctness. New builds also need native
regression tests and live acceptance before replacing a working installation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(data, mode):
    if mode == 'text-lf':
        data = data.replace(b'\r\n', b'\n')
    elif mode != 'binary':
        raise ValueError(f'Unknown hash mode: {mode}')
    return hashlib.sha256(data).hexdigest()


def verify(root, manifest, installed=False):
    root = root.resolve()
    failures = []
    files = dict(manifest['files'])
    if installed:
        files.update(manifest.get('installed_files', {}))
    for relative, entry in files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f'Baseline path escapes repository: {relative}')
        if not path.is_file():
            failures.append(f'MISSING {relative}')
        elif digest(path.read_bytes(), entry['mode']) != entry['sha256']:
            failures.append(f'CHANGED {relative}')
    if not manifest['files']:
        raise ValueError('Empty baseline is not a valid preservation check')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--installed', action='store_true', help='Also verify shared WARP helper installed by the diff')
    parser.add_argument('--client', type=Path, help='Also run native combined-client regression suite (Windows)')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    failures = verify(args.root, manifest, args.installed)
    if failures:
        print('\n'.join(failures))
        print('STOP: accepted feature files changed. Review the diff, run both feature suites,')
        print('and obtain live acceptance before updating the baseline or deploying.')
        return 1
    print(f'PASS: {manifest["baseline"]}: {len(manifest["files"])} protected files match', flush=True)
    if args.client:
        if manifest['component'] != 'client':
            parser.error('--client is only supported with the client manifest')
        exe = args.client.resolve()
        root = args.root.resolve()
        for name, extra in [
            ('test_battlepass_plain_name.py', []),
            ('test_packet_0bf6_route.py', ['--expect', 'bpui,gcha']),
            ('test_gacha_capture.py', []), ('test_gacha_surface.py', []),
            ('test_gacha_v16_layout.py', []), ('test_gacha_featured.py', []),
            ('test_gacha_ui.py', [])
        ]:
            subprocess.run([sys.executable, '-u', str(root / 'tools' / name), str(exe), *extra],
                           cwd=root, check=True)
        print('PASS: combined-client offline suite. Live acceptance is still required for new builds.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
