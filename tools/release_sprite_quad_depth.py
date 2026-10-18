"""Release the hash-verified renderer upgrade with paired signing and rollback."""
from pathlib import Path
import json, os, shutil, subprocess, sys
import hd_sprite_release as r
from verify_floor_safe_sprite_depth import Image, emulate

WORK=r.ROOT/'Outputs/sprite-depth-crash-fix-20261018'
RELEASE=WORK/'deployment'
UPGRADE=WORK/'isolated-upgrade-r5/upgrade.json'
PREVIOUS=r.ROOT/'Outputs/sprite-depth-main-20261018/deployment'
REJECTED='601fa320dceb31f016649d8183f8f8604668901acc5f81caf25d0a15d6fcce00'

def closed():
    p=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name '*Ragexe*','*roid*' -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,creationflags=0x08000000)
    assert p.returncode==0 and p.stdout.strip()=='0','Close the game client before release.'

def install():
    closed();u=r.hd.base.load(UPGRADE)
    baseline=Path(u['source']);candidate=Path(u['candidate']);source=r.GAME/baseline.name
    assert u['status']=='candidate_verified' and u['all_other_existing_section_bytes_preserved'] and u['weather_player_draw_preserved']
    assert u['caves_outside_original_image'] and u['isolated_cave_section']=='.rhwfix'
    assert r.sha(baseline.read_bytes())==u['source_sha256'] and r.sha(candidate.read_bytes())==u['candidate_sha256']
    assert r.sha(source.read_bytes())==REJECTED,'Inspect changes since the rejected release before replacing it.'
    regression=r.hd.base.load(r.ROOT/'docs/evidence/sprite-depth-state-overlap-20261018/reset-then-render.json')
    assert regression['fixed']['passed'] and regression['fixed']['client_sha256']==u['candidate_sha256']
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
    previous=r.hd.base.load(PREVIOUS/'release.json')
    assert immutable==previous['immutable_files'],'Revalidate recovery files after unrelated asset changes.'
    recovery=PREVIOUS/'before'
    assert r.sha((recovery/r.CLIENT).read_bytes())==u['source_sha256']
    fields=dict(line.split('=',1) for line in (recovery/'riftlock-release.sig').read_text(encoding='ascii').splitlines())
    _,manifest=r.signing_modules()
    assert manifest.release_digest(recovery/r.CLIENT,r.GAME/'riftlock.dll',r.GAME/'libsodium.dll',recovery/'riftlock-assets-v1.txt').hex()==fields['digest']
    result=dict(status='prepared',client=r.CLIENT,source_sha256=u['source_sha256'],rejected_client_sha256=REJECTED,candidate_sha256=u['candidate_sha256'],signing_before=before_signature,backup=str(before),healthy_recovery=str(recovery),immutable_files=immutable,live_client_tested=False)
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
            shutil.copyfile(recovery/name,pending);os.replace(pending,r.GAME/name)
        r.verify_signature()
        result.update(status='restored_healthy_pre_upgrade_release',installed=False)
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
