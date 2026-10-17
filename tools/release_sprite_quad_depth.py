"""Release the hash-verified renderer upgrade with paired signing and rollback."""
from pathlib import Path
import json, os, shutil, subprocess, sys
import hd_sprite_release as r
from verify_floor_safe_sprite_depth import Image, emulate

WORK=r.ROOT/'Outputs/sprite-depth-main-20261018'
RELEASE=WORK/'deployment'
UPGRADE=WORK/'current-client-upgrade-r3/upgrade.json'

def closed():
    p=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name '*Ragexe*','*roid*' -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,creationflags=0x08000000)
    assert p.returncode==0 and p.stdout.strip()=='0','Close the game client before release.'

def install():
    closed();u=r.hd.base.load(UPGRADE)
    source=Path(u['source']);candidate=Path(u['candidate'])
    assert source.parent.resolve()==r.GAME.resolve()
    assert u['status']=='candidate_verified' and u['all_other_existing_section_bytes_preserved'] and u['weather_player_draw_preserved']
    assert r.sha(source.read_bytes())==u['source_sha256'] and r.sha(candidate.read_bytes())==u['candidate_sha256']
    r.CLIENT=source.name;before_signature=r.verify_signature()
    key=r.SERVER/'conf/riftlock-server.key'
    secret=bytes.fromhex(key.read_text(encoding='ascii').strip())
    assert len(secret)==64 and secret[32:].hex()==before_signature['public_key'];del secret
    RELEASE.mkdir(parents=True,exist_ok=True)
    assert not (RELEASE/'release.json').exists(),'Release checkpoint already exists; verify instead.'
    names=[r.CLIENT,'riftlock-assets-v1.txt','riftlock-release.sig']
    before=RELEASE/'before';before.mkdir()
    for name in names:shutil.copyfile(r.GAME/name,before/name)
    immutable={p.name:r.transaction.digest(p) for p in list(r.GAME.glob('*.grf'))+[r.GAME/'riftlock.dll',r.GAME/'libsodium.dll',r.GAME/'DATA.INI']}
    result=dict(status='prepared',client=r.CLIENT,source_sha256=u['source_sha256'],candidate_sha256=u['candidate_sha256'],signing_before=before_signature,backup=str(before),immutable_files=immutable,live_client_tested=False)
    r.save(RELEASE/'release.json',result)
    closed()
    try:
        pending=source.with_name(source.name+'.sprite-depth.pending')
        assert not pending.exists()
        shutil.copyfile(candidate,pending);assert r.sha(pending.read_bytes())==u['candidate_sha256'];os.replace(pending,source)
        signed=subprocess.run([sys.executable,str(r.SERVER/'tools/riftlock_release.py'),'--game-root',str(r.GAME),'--client-exe',r.CLIENT,'--build-id','1','--secret',str(key),'--library',str(r.SERVER/'libsodium.dll')],capture_output=True,text=True,creationflags=0x08000000)
        (RELEASE/'signing.log').write_text(signed.stdout+'\n'+signed.stderr,encoding='utf-8')
        assert signed.returncode==0,'Signing failed; restoring the previous release.'
        signature=r.verify_signature()
        assert r.sha(source.read_bytes())==u['candidate_sha256']
        for name,digest in immutable.items():assert r.transaction.digest(r.GAME/name)==digest,('Unrelated game file changed',name)
        image=Image(source);assert image.read(0xC4A5B1,5).hex()=='0f1f440000'
        assert image.read(0xC4A63E,9).hex()=='8b45d80b8824010000'
        result.update(status='installed',installed=True,signing_after=signature,floor_emulation=emulate(source),uniform_rhw=True,legacy_clan_hook_removed=True,all_grfs_dlls_and_ini_unchanged=True)
        r.save(RELEASE/'release.json',result)
    except Exception:
        for name in names:
            pending=r.GAME/(name+'.sprite-depth-restore.pending')
            shutil.copyfile(before/name,pending);os.replace(pending,r.GAME/name)
        result.update(status='rolled_back',installed=False)
        r.save(RELEASE/'release.json',result)
        raise
    print(json.dumps(dict(status='installed',client=r.CLIENT,sha256=u['candidate_sha256'],signature_verified=True,all_grfs_unchanged=True)),flush=True)

def verify():
    result=r.hd.base.load(RELEASE/'release.json');assert result['status']=='installed'
    r.CLIENT=result['client'];assert r.sha((r.GAME/r.CLIENT).read_bytes())==result['candidate_sha256']
    for name,digest in result['immutable_files'].items():assert r.transaction.digest(r.GAME/name)==digest
    signature=r.verify_signature()
    manifest=RELEASE/'independent-manifest.txt'
    p=subprocess.run([sys.executable,str(r.SERVER/'tools/riftlock_assets.py'),'--game-root',str(r.GAME),'--client-exe',str(r.GAME/r.CLIENT),'--output',str(manifest)],capture_output=True,text=True,creationflags=0x08000000)
    (RELEASE/'independent-scan.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
    assert p.returncode==0 and manifest.read_bytes()==(r.GAME/'riftlock-assets-v1.txt').read_bytes()
    result.update(independent_manifest_match=True,signature_verified=signature['signature_verified'])
    r.save(RELEASE/'release.json',result)
    print('PASS: deployed anti-warp/depth hooks, immutable game assets and independent paired signing',flush=True)

if __name__=='__main__':
    for stage in sys.argv[1:]:
        assert stage in ['install','verify']
        globals()[stage]()
