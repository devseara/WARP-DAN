"""Verify the published VIP install chain using an isolated Git index only.

Requires a full WARP clone containing upstream commit 9a10e8b. No worktree,
installed client, default Git index or player data is modified.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--warp',type=Path,required=True)
args=ap.parse_args()
package=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='vip-package-index-') as scratch:
    env=dict(os.environ,GIT_INDEX_FILE=str(Path(scratch)/'index'))
    def git(*parts):
        return subprocess.check_output(['git','-C',str(args.warp),*parts],env=env)
    git('read-tree','9a10e8b')
    for name in ('DevSeara-BattlePass-ChatUI-NPC-Gacha.diff',
                 'DevSeara-Announcement-Item-Icons.diff',
                 'DevSeara-VIP-UI.diff','DevSeara-VIP-UI-v2-upgrade.diff',
                 'DevSeara-VIP-UI-compact-regular-upgrade.diff'):
        patch=str(package/'install'/name)
        git('apply','--cached','--check',patch)
        git('apply','--cached','--whitespace=nowarn',patch)
        print('PASS isolated install:',name,flush=True)
    candidates=list((package/'Assets/VipUI').glob('*.png'))
    candidates+=list((package/'Inputs/VipUI').glob('runtime.*'))
    candidates+=[package/'Scripts/Patches/VipUI.qjs',package/'Scripts/Runtime/VipUI/runtime.cpp']
    for pattern in ('test_vip_*','build_vip_*','verify_vip_payload.py','render_vip_*',
                    'vip_design_contract.py','run_vip_redesign_checks.py'):
        candidates+=list((package/'tools').glob(pattern))
    for file in candidates:
        relative=file.relative_to(package).as_posix()
        actual=git('show',':'+relative)
        expected=file.read_bytes()
        if file.suffix in ('.py','.js','.qjs','.cpp','.json'):
            actual=actual.replace(b'\r\n',b'\n');expected=expected.replace(b'\r\n',b'\n')
        assert actual==expected,relative
    installed_art=git('ls-files','Assets/VipUI').decode().splitlines()
    assert len(installed_art)==63 and not any('readable_' in name for name in installed_art)
    print('PASS:',len(candidates),'installed VIP assets/source/test payloads match the published package; exactly 63 canonical images')
