"""Shared female-Mage GRF release service. Configure paths through the versioned release entrypoint.

No standalone deployment command. Backups, atomic transactions and Riftlock
verification are retained from the proven release implementation.
"""
from pathlib import Path
import sys,json,hashlib,shutil,struct,subprocess,ctypes,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import first_job_hd_sprites as hd
import clan_grf_transaction as transaction
from dual_weapon_formats.grf_reader import GrfFile
GAME=Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes')
WORK=None  # Required from the versioned release entrypoint.
RELEASE=None  # Required from the versioned release entrypoint.
STEM='data/sprite/인간족/몸통/여/마법사_여'
SERVER=ROOT.parent/'BanquetOfHeroes'
CLIENT='2025-07-16_Ragexe_riftlock_classic_npc.exe'
RESOURCE_RECORD=None  # Required from the versioned release entrypoint.
INSTALLATION_RECORD=None  # Required from the versioned release entrypoint.
PATCH_FILENAME=None  # Required from the versioned release entrypoint.
def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf8')

def inspect():
    RELEASE.mkdir(parents=True,exist_ok=True)
    accepted=hd.base.load(ROOT/'Inputs/HDFirstJobs/accepted-v1.json')
    targets={r['entry'].lower() for r in accepted['resources']}|{STEM+e for e in ['.spr','.act']}
    resources=[];archives=[]
    for path in GAME.glob('*.grf'):
        archive=GrfFile(path)
        try:
            found=[]
            for name in targets:
                if name in archive.entries:
                    raw=archive.read(name);entry=archive.entries[name];row=dict(entry=name,bytes=len(raw),sha256=sha(raw),archive=path.name,flags=entry['flags'])
                    if name.endswith('.act'):
                        act=hd.base.read_act(raw);row.update(actions=len(act.actions),frame_uses=sum(map(len,act.actions)),scales=sorted(set(l.sx for fs in act.actions for f in fs for l in f.layers)))
                    found.append(row);resources.append(row)
            archives.append(dict(archive=path.name,format=archive.format,version=archive.version,records=archive.file_count,hd_body_resources=sum(r.get('scales')==[.5] for r in found),matching_resources=len(found),clan_sprite_resources=sum('clan_skins/' in k for k in archive.entries)))
        finally:archive.close()
    manifest=GAME/'riftlock-assets-v1.txt';prefixes={};protected=[]
    for line in manifest.read_text(encoding='utf8').splitlines():
        kind=line.partition('=')[0];prefixes[kind]=prefixes.get(kind,0)+1
        if kind in ['asset','resource','grf','entry']:
            fields=line.partition('=')[2].split('|')
            decoded=[]
            for field in fields:
                try:decoded.append(bytes.fromhex(field).decode('utf8'))
                except (ValueError,UnicodeError):decoded.append(field)
            if any('마법사_여' in x or 'maindata.grf' in x or 'sprite' in x for x in decoded):
                protected.append(dict(kind=kind,fields=decoded))
    report=dict(game=str(GAME),archives=archives,body_resources=resources,signed_manifest_kinds=prefixes,signed_sprite_samples=protected[:8],ini=(GAME/'DATA.INI').read_text(),target_resources=[STEM+'.spr',STEM+'.act'])
    save(RELEASE/'archive-discovery.json',report)
    print(json.dumps(dict(archives=archives,target=[r for r in resources if r['entry'].startswith(STEM)],manifest_kinds=prefixes,signed_samples=protected[:3]),ensure_ascii=True))

def desired():
    record=hd.base.load(RESOURCE_RECORD);result={}
    for row in record['files']:
        p=WORK/row['path'];raw=p.read_bytes();assert sha(raw)==row['sha256'];result[STEM+p.suffix]=raw
    assert len(result)==2
    return result

def signing_modules():
    sys.path.insert(0,str(SERVER/'tools'))
    import riftlock_release,riftlock_manifest
    return riftlock_release,riftlock_manifest

def verify_signature():
    release,manifest=signing_modules();fields=dict(line.split('=',1) for line in (GAME/'riftlock-release.sig').read_text(encoding='ascii').splitlines())
    assert fields['format']=='riftlock-release-signature-v1' and fields['build']=='1'
    digest=manifest.release_digest(GAME/CLIENT,GAME/'riftlock.dll',GAME/'libsodium.dll',GAME/'riftlock-assets-v1.txt');assert digest.hex()==fields['digest']
    signature=bytes.fromhex(fields['signature']);public=bytes.fromhex(fields['public_key']);assert public in (GAME/'riftlock.dll').read_bytes()
    sodium=manifest.load_sodium(SERVER/'libsodium.dll');assert sodium.sodium_init()>=0
    statement=release.release_statement(1,int(fields['release']),digest)
    assert sodium.crypto_sign_verify_detached((ctypes.c_ubyte*64).from_buffer_copy(signature),(ctypes.c_ubyte*len(statement)).from_buffer_copy(statement),ctypes.c_ulonglong(len(statement)),(ctypes.c_ubyte*32).from_buffer_copy(public))==0
    return dict(build=1,release=int(fields['release']),digest=digest.hex(),public_key=public.hex(),signature_verified=True)

def prepare():
    payloads=desired();RELEASE.mkdir(parents=True,exist_ok=True)
    assert not (RELEASE/'maindata-transaction.json').exists(),'Release already has a transaction; verify or roll back, do not overwrite it'
    sign=verify_signature()
    secret_path=SERVER/'conf/riftlock-server.key';assert secret_path.is_file()
    # Read only to check the configured identity, never print/copy secret bytes.
    secret=bytes.fromhex(secret_path.read_text(encoding='ascii').strip());assert len(secret)==64 and secret[32:].hex()==sign['public_key'];del secret
    archive=GrfFile(GAME/'maindata.grf')
    try:
        before={name:sha(archive.read(name)) for name in payloads}
        discovery=hd.base.load(RELEASE/'archive-discovery.json')
        assert before=={r['entry']:r['sha256'] for r in discovery['body_resources'] if r['archive']=='maindata.grf' and r['entry'] in payloads}
        for name in payloads:
            p=RELEASE/'before'/Path(name).name;p.parent.mkdir(exist_ok=True);p.write_bytes(archive.read(name))
    finally:archive.close()
    # Check every higher-priority archive and the loose resource path.
    from riftlock_assets import read_client_loader
    _,mode,order,_=read_client_loader(GAME/CLIENT,GAME);assert 'maindata.grf' in order
    for name in payloads:assert not (GAME/Path(name)).exists(),('Loose override',name)
    for filename in order[:order.index('maindata.grf')]:
        grf=GrfFile(GAME/filename)
        try:assert not (set(payloads)&set(grf.entries)),('Higher-priority override',filename)
        finally:grf.close()
    for e in ['.spr','.act']:
        p=RELEASE/'accepted'/f'mage-female{e}';p.parent.mkdir(exist_ok=True);p.write_bytes(payloads[STEM+e])
    from package_clan_skin_assets import pack_payloads
    pack_payloads(payloads,RELEASE/PATCH_FILENAME)
    for name in ['riftlock-assets-v1.txt','riftlock-release.sig']:shutil.copyfile(GAME/name,RELEASE/'before'/name)
    report=dict(status='prepared',game=str(GAME),archive='maindata.grf',before_archive_sha256=transaction.digest(GAME/'maindata.grf'),before_resources=before,loader_mode=mode,archive_order=order,signing_before=sign,resources=[dict(entry=k,sha256=sha(v)) for k,v in payloads.items()],user_acceptance=True,acceptance_date='2026-10-12',acceptance_basis='Versioned release entrypoint records explicit deployment authorization.',installed=False)
    save(RELEASE/'release.json',report)
    print(json.dumps(dict(status='prepared',archive='maindata.grf',resources=2,loader=mode,signing_identity_verified=True)))

def install():
    report=hd.base.load(RELEASE/'release.json');assert report['status']=='prepared'
    assert transaction.digest(GAME/'maindata.grf')==report['before_archive_sha256']
    assert not (RELEASE/'maindata.grf.before').exists();shutil.copyfile(GAME/'maindata.grf',RELEASE/'maindata.grf.before')
    assert transaction.digest(RELEASE/'maindata.grf.before')==report['before_archive_sha256']
    immutable={name:transaction.digest(GAME/name) for name in [CLIENT,'riftlock.dll','libsodium.dll','DATA.INI','update.grf','spritedata.grf','palettedata.grf']}
    receipt=RELEASE/'maindata-transaction.json'
    try:
        result=transaction.replace_records(GAME/'maindata.grf',desired(),receipt)
        signed=subprocess.run([sys.executable,str(SERVER/'tools/riftlock_release.py'),'--game-root',str(GAME),'--client-exe',CLIENT,'--build-id','1','--secret',str(SERVER/'conf/riftlock-server.key'),'--library',str(SERVER/'libsodium.dll')],capture_output=True,text=True,creationflags=0x08000000)
        (RELEASE/'signing.log').write_text(signed.stdout+'\n'+signed.stderr,encoding='utf8');assert signed.returncode==0,'Signing failed; see saved log'
        signature=verify_signature()
        for name,digest in immutable.items():assert transaction.digest(GAME/name)==digest,('Unrelated file changed',name)
        archive=GrfFile(GAME/'maindata.grf')
        try:
            for name,raw in desired().items():assert archive.read(name)==raw
        finally:archive.close()
    except Exception:
        if receipt.exists() and hd.base.load(receipt)['status']=='installed':transaction.rollback(receipt)
        for name in ['riftlock-assets-v1.txt','riftlock-release.sig']:
            temp=GAME/(name+'.hd-restore.pending');shutil.copyfile(RELEASE/'before'/name,temp);os.replace(temp,GAME/name)
        save(RELEASE/'failure-rollback.json',dict(archive_restored=transaction.digest(GAME/'maindata.grf')==report['before_archive_sha256']))
        raise
    report.update(status='installed',installed=True,after_archive_sha256=transaction.digest(GAME/'maindata.grf'),transaction=result,signing_after=signature,unchanged_game_files=immutable,post_install_live_client_observed=False)
    save(RELEASE/'release.json',report);save(INSTALLATION_RECORD,report)
    record=hd.base.load(RESOURCE_RECORD);record.update(status='user_accepted_installed',installed=True,user_acceptance=True,accepted_date='2026-10-12',installation_record=INSTALLATION_RECORD.relative_to(ROOT).as_posix());save(RESOURCE_RECORD,record)
    print(json.dumps(dict(status='installed',archive=str(GAME/'maindata.grf'),resources=2,unrelated_records_preserved=result['unrelated_records_preserved'],signature_verified=True,archive_sha256=report['after_archive_sha256'])))
