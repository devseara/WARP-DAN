"""Build a chat-icon regression candidate in an isolated WARP fixture.

Never changes saved user profiles, source clients, or the installed game.
Requires an explicit source profile and a new output directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--without', action='append', default=[], choices=['BattlepassUI', 'GachaUI'])
    ap.add_argument('--reverse-feature-order', action='store_true')
    ap.add_argument('--with-notice', action='store_true', help='Select stock announcement item icons (legacy NoticeMarquee ID), staged profile only')
    ap.add_argument('--with-vip', action='store_true', help='Select independent native VIP UI, staged profile only')
    args = ap.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / 'warp-fixture'
    fixture.mkdir()
    # WARP's OUTDIR is relative to its fixture, not the profile's target EXE.
    (fixture / 'Outputs').mkdir()
    for name in ('win32', 'Scripts', 'Tables', 'Patches', 'Inputs', 'Languages', 'Styles', 'Assets', 'Images'):
        shutil.copytree(ROOT / name, fixture / name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    target = output / 'Ragnarok-chat-test.exe'
    saved = args.profile.read_text(encoding='utf-8-sig')
    if args.with_vip and not re.search(r'^\s+- VipUI\s*$', saved, re.M):
        saved, added = re.subn(r'^( +)- ChatItemIcons([ \t]*\r?)$', r'\1- ChatItemIcons\2\n\1- VipUI', saved, flags=re.M)
        assert added == 1, 'Expected one ChatItemIcons selection'
    if args.with_notice and not re.search(r'^\s+- NoticeMarquee\s*$', saved, re.M):
        saved, added = re.subn(r'^( +)- ChatItemIcons([ \t]*\r?)$', r'\1- ChatItemIcons\2\n\1- NoticeMarquee', saved, flags=re.M)
        assert added == 1, 'Expected one ChatItemIcons selection'
    assert re.search(r'^\s+- ChatItemIcons\s*$', saved, re.M), 'Profile must select ChatItemIcons'
    saved, count = re.subn(r'^to:[^\n]*', lambda _: 'to: ' + json.dumps(target.as_posix()), saved, flags=re.M)
    assert count == 1, 'Expected exactly one output field'
    for name in args.without:
        saved = re.sub(r'^ +-[ ]+' + name + r'[ \t]*\r?\n', '', saved, flags=re.M)
    if args.reverse_feature_order:
        names = re.findall(r'^ +-[ ]+(BattlepassUI|GachaUI)[ \t]*\r?$', saved, re.M)
        assert len(names) == 2, names
        replacement = iter(reversed(names))
        saved = re.sub(r'^( +-[ ]+)(BattlepassUI|GachaUI)([ \t]*\r?)$',
                       lambda m: m[1] + next(replacement) + m[3], saved, flags=re.M)
    profile = output / 'build-profile.yml'
    profile.write_text(saved, encoding='utf-8')
    run = subprocess.run([str(fixture / 'win32/WARP_console.exe'), '-using', str(profile)],
                         cwd=fixture, capture_output=True, timeout=240)
    log = run.stdout + run.stderr
    (output / 'build.log').write_bytes(log)
    if run.returncode or b'-E-' in log or not target.is_file():
        raise RuntimeError(f'WARP build failed ({run.returncode}); see {output / "build.log"}')
    skipped = fixture / 'SkippedPatches.log'
    if skipped.is_file() and skipped.read_text(encoding='utf-8-sig').strip():
        raise RuntimeError(f'WARP skipped patches; see {skipped}')
    assert b'ChatItemIcons.v3\0' in target.read_bytes(), 'Fresh chat helpers missing'
    print(json.dumps({'candidate': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                      'installed': False, 'live_accepted': False}, indent=2))


if __name__ == '__main__':
    main()
