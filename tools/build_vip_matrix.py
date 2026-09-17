"""Reuse an isolated WARP fixture to build VIP/accepted-feature order variants.

Takes the successful build_chat_item_icons.py --with-vip output directory.
Does not edit installed WARP, saved user profiles or a live client.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

def main():
    ap=argparse.ArgumentParser();ap.add_argument('build',type=Path);args=ap.parse_args()
    build=args.build.resolve();fixture=build/'warp-fixture'
    source=(build/'build-profile.yml').read_text(encoding='utf8')
    assert all(re.search(r'^\s+- '+name+r'\s*$',source,re.M) for name in ('VipUI','BattlepassUI','GachaUI'))
    for name,remove,reverse in [('reverse',[],True),('bp-only',['GachaUI'],False),
                                 ('gacha-only',['BattlepassUI'],False),('vip-only',['BattlepassUI','GachaUI'],False)]:
        output=build.parent/name;output.mkdir(exist_ok=False)
        saved=source
        for patch in remove:saved=re.sub(r'^ +-[ ]+'+patch+r'[ \t]*\r?\n','',saved,flags=re.M)
        if reverse:
            names=re.findall(r'^ +-[ ]+(VipUI|BattlepassUI|GachaUI)[ \t]*\r?$',saved,re.M)
            replacement=iter(reversed(names))
            saved=re.sub(r'^( +-[ ]+)(VipUI|BattlepassUI|GachaUI)([ \t]*\r?)$',lambda m:m[1]+next(replacement)+m[3],saved,flags=re.M)
        target=output/'Ragnarok-vip-test.exe'
        saved,count=re.subn(r'^to:[^\n]*',lambda _:'to: '+json.dumps(target.as_posix()),saved,flags=re.M);assert count==1
        profile=output/'build-profile.yml';profile.write_text(saved,encoding='utf8')
        run=subprocess.run([str(fixture/'win32/WARP_console.exe'),'-using',str(profile)],cwd=fixture,capture_output=True,timeout=240)
        log=run.stdout+run.stderr;(output/'build.log').write_bytes(log)
        assert not run.returncode and b'-E-' not in log and target.is_file(),(name,log.decode(errors='replace'))
        skipped=fixture/'SkippedPatches.log'
        assert not skipped.is_file() or not skipped.read_text(encoding='utf-8-sig').strip()
        data=target.read_bytes();assert b'VipUI.v2\0' in data
        for patch,marker in [('BattlepassUI',b'BattlepassUI.'),('GachaUI',b'GachaUI.v20\0')]:
            if patch in remove:assert marker not in data,(name,'unexpected',patch)
            else:assert marker in data,(name,'missing',patch)
        print('PASS staged variant',name,target,flush=True)

if __name__=='__main__':main()
