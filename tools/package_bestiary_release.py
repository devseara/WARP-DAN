"""Package the verified Bestiary client/lore/backend and optionally install only client files.

Server activation remains a separate zero-player-gated maintenance operation.
Existing game executables are never overwritten; changed textures are backed up.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile,re
import pefile
from bestiary_paths import bestiary_texture_root
ROOT=Path(__file__).resolve().parents[1]
CLIENT_NAME='Banquet_Bestiary_Interactive_Rewards_20260913_Fixed.exe'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--client-build',type=Path,required=True);ap.add_argument('--server-build',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--install-client',action='store_true');ap.add_argument('--client-name',default=CLIENT_NAME);ap.add_argument('--titles',type=Path,help='Verified title-table output directory');ap.add_argument('--acceptance',type=Path,help='User acceptance record, requiring an exact EXE hash match');args=ap.parse_args()
    client_name=args.client_name;assert re.fullmatch(r'[A-Za-z0-9_. -]+\.exe',client_name)
    client=args.client_build.resolve();build=args.server_build.resolve();server=ROOT.parent/'BanquetOfHeroes';out=args.output.resolve();game=args.game.resolve();out.mkdir(parents=True,exist_ok=True)
    native=read(client/'native-manifest.json')['bestiary'];proof=read(client/'build-result.json');backend=read(build/'build-result.json')
    assert native['layoutVersion']==12 and native['personalPayload']['size']==2440 and native.get('menuButton')
    assert proof['build_passed'] and backend['passed'] and sha(client/'bestiary-preview.exe')==proof['target_sha256']
    assert all(sha(server/name)==value for name,value in backend['source_sha256'].items()),'Backend inputs changed after build'
    files={'client/'+client_name:client/'bestiary-preview.exe'}
    for name in ['journal','cache','encyclopedia','live-fixes','research-native','native-fit','rewards-preview-search','reward-item-interaction','mouse-dispatch','lifecycle']:
        path=client/(name+'-verification.json');assert read(path)['passed'];files['verification/client/'+path.name]=path
    if args.titles:
        title_dir=args.titles.resolve();title=read(title_dir/'title-verification.json');assert title['passed'] and title['title_db_sha256']==sha(server/'db/title_db.yml')
        assert title['research_definitions_sha256']==sha(server/'db/bestiary_research.yml')
        source=title_dir/title['client_key'];assert sha(source)==title['after_sha256'];files['client/'+title['client_key']]=source
        files['verification/titles.json']=title_dir/'title-verification.json';files['warp/tools/sync_bestiary_titles.py']=ROOT/'tools/sync_bestiary_titles.py'
    for part in ['research/core-test','research/sql-test','native/yaml-test']:
        path=ROOT/'Outputs/Bestiary/verification'/part/'verification.json';assert read(path)['passed'];files['verification/server/'+part.replace('/','-')+'.json']=path
    lore=ROOT/'Outputs/Bestiary/lore-rewards-20260913/content/lore-verification.json';assert read(lore)['passed'] and read(lore)['lore_sha256']==sha(server/'db/bestiary_lore.yml');files['verification/lore.json']=lore
    for row in backend['targets']:
        p=Path(row['binary']);assert sha(p)==row['sha256'];files['server/'+p.name]=p
    for name in ['db/bestiary_lore.yml','db/bestiary_lore_sources.json','db/bestiary_research.yml','db/title_db.yml','db/import-tmpl/bestiary_lore.yml','db/import-tmpl/bestiary_research.yml','sql-files/upgrades/2026-09-12-bestiary-research.sql','sql-files/upgrades/2026-09-13-bestiary-mail-innodb.sql']:
        files['server/'+name]=server/name
    for name in ['src/map/bestiary_research.cpp','src/map/bestiary_research.hpp','src/common/bestiary_definitions.hpp','src/char/int_bestiary.cpp','src/char/int_mail.cpp']:
        files['server-source/'+name]=server/name
    for name in ['BestiaryUI.qjs','ItemCollectionUI.qjs','ROGlobalZeroMenu.qjs','NewButtonVisibility.qjs']:
        p=ROOT/'Scripts/Patches'/name;assert p.read_bytes()==(client/'warp-fixture/Scripts/Patches'/name).read_bytes();files['warp/Scripts/Patches/'+name]=p
    for name in ['bestiary.md']:files['docs/'+name]=ROOT/'docs'/name
    for p in (ROOT/'tools/fixtures/bestiary/lore').glob('curated-*.json'):files['lore-inputs/'+p.name]=p
    for name in ['build_bestiary_lore.py','verify_bestiary_lore.py']:files['warp/tools/'+name]=ROOT/'tools'/name
    for p in (client/bestiary_texture_root(native)).rglob('*'):
        if p.is_file():files['client/'+p.relative_to(client).as_posix()]=p
    for name in ['journal-qa-tab0-detail2-popup0.png','journal-qa-tab2-detail0-popup0-view0.png','journal-qa-tab2-detail0-popup0-view3.png']:files['previews/'+name]=client/name
    files['verification/backend-build.json']=build/'build-result.json';files['verification/client-build.json']=client/'build-result.json'
    pe=pefile.PE(str(client/'bestiary-preview.exe'));assert pe.FILE_HEADER.Machine==0x14c
    imports=[entry for d in pe.DIRECTORY_ENTRY_IMPORT for entry in d.imports if entry.name==b'timeGetTime'];assert len(imports)==1 and imports[0].address==native['timeGetTimeIat']
    missing=[d.dll.decode() for d in pe.DIRECTORY_ENTRY_IMPORT if not any((root/d.dll.decode()).is_file() for root in [game,Path('C:/Windows/SysWOW64')])];assert not missing,missing
    custom=any(d.dll.lower()==b'bohcustoms.dll' for d in pe.DIRECTORY_ENTRY_IMPORT)
    if custom:
        from fix_custom_bridge_iats import BridgeIatFixer
        assert not BridgeIatFixer(client/'bestiary-preview.exe','bohcustoms.dll').find_fixes()
    pe.close()
    accepted=None
    if args.acceptance:
        accepted=read(args.acceptance);assert accepted['acceptance']['confirmed'] and accepted['client']['sha256']==proof['target_sha256'],'Acceptance belongs to a different EXE'
        files['verification/user-acceptance.json']=args.acceptance.resolve()
    manifest={'passed':True,'client':client_name,'client_sha256':proof['target_sha256'],'layout_version':native['layoutVersion'],'personal_snapshots':{'legacy':[9,2176],'item_previews':[10,2440],'opt_in_flag':2},'lore':read(lore),'files':{name:sha(p) for name,p in files.items()},'final_timer_iat_verified':True,'missing_import_dlls':missing,'custom_bridge_imported':custom,'live_game_accepted':accepted is not None,'acceptance':accepted['acceptance'] if accepted else None,'server_deployed_this_run':False,'client_installed':False}
    archive=out/(client_name[:-4]+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        z.writestr('README.txt',"Bestiary - local 2025-07-16 full saved profile\n\nLaunch client/"+client_name+" after copying the client folder into your existing game directory. Keep its existing DLLs and GRFs. The journal/menu textures use the requested native UI bestiary folder.\n\nReward icons support localized-name hover tooltips and right-click native information in V12. Inspecting an icon cannot claim its reward. See docs/bestiary.md#titles for title unlocks and client mappings.\n\nThe matching map backend enables reward search and up to five item icons with quantities. Existing 2176-byte personal snapshots remain supported. Claim All still claims every available reward.\n\nServer binaries are for this current local checkout. Activate through the approved zero-player maintenance procedure with binary/WAL/mail backups; never copy over running servers. Preserve all db/import files and account progress. The previous expansion's InnoDB mail prerequisite still applies; this update changes no research IDs or SQL schema.\n\nLore covers every loaded mob ID. See docs/bestiary.md#lore-sources for attribution and the distinction between sourced accounts and original field notes. Previews use synthetic packets.\n"+("This EXE matches the user-accepted build.\n" if accepted else "Live game acceptance remains pending.\n"))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in manifest['files'].items())
    manifest['archive']=str(archive);manifest['archive_sha256']=sha(archive)
    if args.install_client:
        target=game/client_name
        assert not target.exists() or sha(target)==manifest['client_sha256'],'Refusing to replace a different existing EXE'
        backups=[];installed=[]
        for name,p in files.items():
            if not name.startswith('client/'):continue
            relative=Path(name[len('client/'):]);dest=game/relative
            assert dest.resolve().is_relative_to(game),'Install target escapes game directory'
            if dest.exists() and sha(dest)!=sha(p):
                backup=out/'client-backup'/relative;backup.parent.mkdir(parents=True,exist_ok=True);assert not backup.exists();shutil.copy2(dest,backup);backups.append(str(backup))
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists() or sha(dest)!=sha(p):shutil.copy2(p,dest)
            assert sha(dest)==sha(p);installed.append(str(dest))
        manifest.update(client_installed=True,installed_exe=str(target),installed_files=len(installed),texture_backups=backups)
    (out/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ['passed','client','client_sha256','archive','archive_sha256','client_installed','live_game_accepted']},indent=2))
if __name__=='__main__':main()
