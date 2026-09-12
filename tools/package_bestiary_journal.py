"""Package a verified Bestiary build and optionally install the local files.

The caller must ensure map and char services are stopped before --install.
The old map-server is preserved under a content-addressed backup filename.
This never starts/stops a process or modifies server configuration/GRF order.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
import pefile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def machine(path):
    parsed=pefile.PE(str(path),fast_load=True)
    try:return parsed.FILE_HEADER.Machine
    finally:parsed.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',type=Path,required=True)
    ap.add_argument('--game',type=Path,required=True)
    ap.add_argument('--server',type=Path,required=True)
    ap.add_argument('--install',action='store_true')
    ap.add_argument('--install-client',action='store_true',help='Install only the client; keep the running map server untouched')
    args=ap.parse_args()
    build=args.build.resolve();game=args.game.resolve();server=args.server.resolve()
    verification=json.loads((build/'journal-verification.json').read_text())
    result=json.loads((build/'build-result.json').read_text())
    assert verification['passed'] and result['build_passed']
    fit=json.loads((build/'native-fit-verification.json').read_text());assert fit['passed']
    native=json.loads((build/'native-manifest.json').read_text(encoding='utf-8'))['bestiary']
    version=native['layoutVersion']
    assert version == 9, 'This packager targets the initial V9 implementation'
    cache=None
    if version>=6:
        cache=json.loads((build/'cache-verification.json').read_text(encoding='utf-8'));assert cache['passed']
    client=build/'bestiary-preview.exe';assert digest(client)==result['target_sha256']
    protocol=native['protocolVersion'];encyclopedia=None;live_fixes=None
    if version>=8:
        live_fixes=json.loads((build/'live-fixes-verification.json').read_text(encoding='utf-8'));assert live_fixes['passed']
    if version>=7:
        encyclopedia=json.loads((build/'encyclopedia-verification.json').read_text(encoding='utf-8'));assert encyclopedia['passed']
        strict_yaml=json.loads((ROOT/'Outputs/Bestiary/verification/native/yaml-test/verification.json').read_text(encoding='utf-8'));assert strict_yaml['passed']
    research=None;char_backend=None
    if version>=9:
        from bestiary_release_support import require_stopped,migrate
        research=json.loads((build/'research-server-verification.json').read_text());assert research['passed']
        for relative,expected in research['server_sources'].items():assert digest(server/relative)==expected,relative+' changed after verification'
        for name,expected in research['binaries'].items():assert digest(server/'build/bestiary-v9/bin'/name)==expected,name+' changed after verification'
        assert json.loads((build/'research-native-verification.json').read_text())['passed']
        assert json.loads((build/'lifecycle-verification.json').read_text())['passed']
        assert digest(ROOT/'Scripts/Patches/BestiaryUI.qjs')==research['client_patch_sha256']
        char_backend=server/'build/bestiary-v9/bin/char-server.exe';assert machine(char_backend)==0x8664
    backend=server/f'build/bestiary-v{9 if version>=9 else protocol}/bin/map-server.exe' 
    assert machine(backend)==0x8664
    assert machine(client)==0x14c
    asset_root=ROOT/'Images/BestiaryUI/journal'
    assets=json.loads((asset_root/'manifest.json').read_text(encoding='utf-8'))
    manifest={'client':f'bestiary_20250716_journal_v{version}.exe','client_sha256':digest(client),
              'server':'map-server.exe','server_sha256':digest(backend),
              'window':[760,500],'minimum_game_viewport':[800,600],
              'protocol':f'BSUI v{protocol} (legacy v1/v2 responses supported)' ,'assets':{},'native_checks':verification['checks'],
              'native_fit_cases':[c['name'] for c in fit['cases']],'live_accepted':False}
    if research:
        manifest['char_server']='char-server.exe';manifest['char_server_sha256']=digest(char_backend)
        manifest['research']={'protocol':1,'account_wide':True,'definitions_sha256':digest(server/'db/bestiary_research.yml'),'checks':research['checks']}
    for name in assets['files']:
        source=asset_root/name;built=build/'data/texture/bestiary/journal'/name
        assert source.read_bytes()==built.read_bytes(),name
        manifest['assets']['data/texture/bestiary/journal/'+name]=digest(source)
    archive=ROOT/f'Outputs/Bestiary/bestiary-20250716-journal-v{version}.zip'
    if live_fixes:manifest['live_fix_checks']=live_fixes['checks']
    if cache:manifest['cache_checks']=cache['checks']
    if encyclopedia:manifest['encyclopedia_checks']=encyclopedia['checks']
    if research:
        readme=f'''Bestiary V9 - native 2025-07-16 client

Copy client/ into the existing game directory and launch {manifest['client']}.
Stop BOTH map and char services before installing server/map-server.exe and
server/char-server.exe. Apply the included additive SQL migration to the
character database first. Preserve db/import/bestiary_research.yml if present;
the archive supplies an empty import template. Both services require matching
research definitions and InnoDB mail tables.

V9 enables account-wide research, groups, favorites, tracking, journal points,
Claim/Claim All, account-bound utility mail, cosmetic titles and cabinet trophies.
Local thresholds are not advertised as official RO Origin Global values.
See Bestiary.md for rules, exclusions, durability and rollback.

V8 fixes are included: physical Escape routing, opaque minimaps, comma-separated
numbers and @reloadmobdb catalog invalidation. Catalog cache survives reopen;
research/claim updates never invalidate it. Research definition edits currently
require restarting both services. Native visual/live combat acceptance is pending.
'''
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(ROOT/'docs/bestiary.md','Bestiary.md')
        z.write(client,'client/'+manifest['client']);z.write(backend,'server/map-server.exe')
        if research:
            z.write(char_backend,'server/char-server.exe')
            z.write(server/'db/bestiary_research.yml','server/db/bestiary_research.yml')
            z.write(server/'db/import-tmpl/bestiary_research.yml','server/db/import-tmpl/bestiary_research.yml')
            z.write(server/'sql-files/upgrades/2026-09-12-bestiary-research.sql','server/sql-files/upgrades/2026-09-12-bestiary-research.sql')
            for name in ['research-server-verification.json','research-native-verification.json','lifecycle-verification.json','research-core-verification.json','research-sql-verification.json']:
                z.write(build/name,name)
            for name in ['journal-qa-tab1-detail0-popup0-view0.png','journal-qa-tab2-detail0-popup0-view1.png','journal-qa-tab2-detail0-popup0-view3.png']:
                z.write(build/name,name)
        for relative in manifest['assets']:z.write(build/relative,'client/'+relative)
        z.write(build/'native-fit-verification.json','native-fit-verification.json')
        if live_fixes:
            z.write(build/'live-fixes-verification.json','live-fixes-verification.json')
        if cache:z.write(build/'cache-verification.json','cache-verification.json')
        if encyclopedia:
            z.write(build/'encyclopedia-verification.json','encyclopedia-verification.json')
            z.write(ROOT/'Outputs/Bestiary/verification/native/yaml-test/verification.json','server-yaml-verification.json')
            z.write(server/'db/bestiary_lore.yml','server/db/bestiary_lore.yml')
            z.write(server/'db/import-tmpl/bestiary_lore.yml','server/db/import-tmpl/bestiary_lore.yml')
        z.write(build/'journal-qa-tab0-detail0-popup0.png','layout-preview-test-packets.png')
        z.writestr('README.txt',readme)
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
    if args.install:
        if research:
            require_stopped()
            manifest['sql_installation']=migrate(server,build)
            original_char=server/'char-server.exe';assert original_char.is_file()
            if digest(original_char)!=manifest['char_server_sha256']:
                backup=server/'build/bestiary-v9/backups'/('char-server.before-'+digest(original_char)+'.exe')
                backup.parent.mkdir(parents=True,exist_ok=True)
                if not backup.exists():shutil.copy2(original_char,backup)
                assert digest(backup)==digest(original_char)
                manifest['char_server_backup']=str(backup)
                shutil.copy2(char_backend,original_char)
            assert digest(original_char)==manifest['char_server_sha256']
            manifest['installed_char_server']=str(original_char)
        original=server/'map-server.exe';assert original.is_file()
        assert machine(original)==0x8664
        if digest(original)!=manifest['server_sha256']:
            backup=server/'build/bestiary-v1/backups'/('map-server.before-'+digest(original)+'.exe')
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():shutil.copy2(original,backup)
            assert digest(backup)==digest(original)
            manifest['server_backup']=str(backup)
        else:
            backups=sorted((server/'build/bestiary-v1/backups').glob('map-server.before-*.exe'))
            manifest['server_backups']=[str(p) for p in backups]
        if digest(original)!=manifest['server_sha256']:shutil.copy2(backend,original)
        assert digest(original)==manifest['server_sha256']
        manifest['installed_server']=str(original)
    if args.install or args.install_client:
        for relative,expected in manifest['assets'].items():
            target=game/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists() or digest(target)!=expected:shutil.copy2(build/relative,target)
            assert digest(target)==expected
        client_target=game/manifest['client']
        if client_target.exists() and digest(client_target)!=digest(client):
            old=build/('previous-client-'+digest(client_target)+'.exe');shutil.copy2(client_target,old)
        if not client_target.exists() or digest(client_target)!=manifest['client_sha256']:shutil.copy2(client,client_target)
        assert digest(client_target)==manifest['client_sha256']
        manifest['installed_client']=str(client_target)
    if digest(server/'map-server.exe')==manifest['server_sha256']:
        manifest['installed_server']=str(server/'map-server.exe');manifest['server_install_pending']=False
    else:manifest['server_install_pending']=True
    if research:
        manifest['char_server_install_pending']=digest(server/'char-server.exe')!=manifest['char_server_sha256']
    manifest['archive']=str(archive);manifest['archive_sha256']=digest(archive)
    (build/'release-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in manifest.items() if key not in ['assets','native_checks']},indent=2))


if __name__=='__main__':main()
