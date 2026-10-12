"""Package only verified IDUI test outputs; do not replace running services."""
from pathlib import Path
import json,hashlib,shutil,zipfile,argparse,re
from datetime import date
ROOT=Path(__file__).resolve().parents[1];SERVER=ROOT.parent/'BanquetOfHeroes'
BASE=ROOT/'Outputs/ItemDescription'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--client',type=Path,required=True);ap.add_argument('--version',required=True);ap.add_argument('--date',default=date.today().strftime('%Y%m%d'));ap.add_argument('--client-only',action='store_true');args=ap.parse_args()
    assert re.fullmatch(r'\d{8}',args.date), 'Date must be YYYYMMDD'
    assert args.version.isalnum(), 'Version must be a filename-safe identifier'
    CLIENT=args.client.resolve();RELEASE=BASE/('release-'+args.version)
    assert not RELEASE.exists(), 'Use a new release directory'
    qa=json.loads((CLIENT/'release-verification.json').read_text(encoding='utf8'))
    server=json.loads((BASE/'server/build-result.json').read_text(encoding='utf8')) if not args.client_only else None
    assert qa['passed'] and (server is None or server['passed'])
    assert digest(CLIENT/'item-description.exe')==qa['client_sha256']
    if server:
        for name,value in server['source_sha256'].items():assert digest(SERVER/name)==value,'Stale server source: '+name
        for target in server['targets']:assert digest(Path(target['target']))==target['sha256']
    RELEASE.mkdir(parents=True,exist_ok=True)
    def copy(source,relative):
        p=RELEASE/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,p)
    copy(CLIENT/'item-description.exe','client/Banquet_ItemDescription_Test_'+args.version+'_'+args.date+'.exe')
    if not args.client_only:
        for name in ['map-server.exe','map-server-generator.exe']:copy(BASE/'server/bin'/name,'server/'+name)
        for name in ['db/item_description_db.yml','db/item_description_generated.yml','db/import/item_description_db.yml','db/import-tmpl/item_description_db.yml']:copy(SERVER/name,'server/'+name)
    for name in ['release-verification.json','native-verification.json','edge-verification.json','artwork-verification.json','comparison-verification.json','skin-verification.json','header-verification.json','header-style-preview.png','router-verification.json','journal-verification.json','iat-verification.log','native-body-preview.png']:
        copy(CLIENT/name,'verification/'+name)
    if not args.client_only:
        copy(BASE/'generated-data-report.json','verification/generated-data-report.json')
        copy(BASE/'server/build-result.json','verification/server-build.json')
        copy(BASE/'server-tests/verification.json','verification/server-tests.json')
    copy(ROOT/'docs/item-description.md','README.md')
    files={str(p.relative_to(RELEASE)).replace('\\','/'):digest(p)for p in RELEASE.rglob('*')if p.is_file() and p.name!='manifest.json'}
    manifest={'version':args.version,'client_build':20250716,'live_accepted':False,'services_restarted':False,'client_only':args.client_only,'server_requirement':'IDUI v3 or later' if args.client_only else 'included matching server','files':files}
    (RELEASE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    archive=BASE/('item-description-test-'+args.version+'-'+args.date+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        for p in sorted(RELEASE.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(RELEASE))
    print(json.dumps({'release':str(RELEASE),'archive':str(archive),'sha256':digest(archive),'files':len(files)+1,'live_accepted':False}))
if __name__=='__main__':main()
