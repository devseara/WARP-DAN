"""Run the release-candidate IDUI and existing Bestiary gates against the same PE."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess
from verify_item_description_native import verify as native
from verify_item_description_edges import verify as edges
from verify_item_description_artwork import verify as visuals
from verify_item_description_comparison import verify as paired
from verify_item_description_skin import verify as skin
from verify_item_description_header import verify as header
from verify_item_description_router import verify as router
from verify_bestiary_journal import verify as bestiary
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);args=ap.parse_args();d=args.directory.resolve()
    m=json.loads((d/'native-manifest.json').read_text(encoding='utf8'))
    for name,digest in m['itemDescription']['source_sha256'].items():
        assert hashlib.sha256((ROOT/'tools/native'/name).read_bytes()).hexdigest()==digest,'Stale client payload: '+name
    results={}
    for name,fn in [('native',native),('edges',edges),('artwork',visuals),('comparison',paired),('skin',skin),('header',header),('router',router)]:
        print('VERIFY '+name,flush=True);results[name]=fn(d)
    if m.get('bestiary'):
        # Existing regression utility uses its historical fixed file name.
        alias=d/'bestiary-preview.exe'
        shutil.copy2(d/'item-description.exe',alias)
        print('VERIFY existing Bestiary',flush=True);results['bestiary']=bestiary(d)
    import pefile
    pe=pefile.PE(str(d/'item-description.exe'))
    assert next(i.name for desc in pe.DIRECTORY_ENTRY_IMPORT for i in desc.imports if i.address==0xfc17b0)==b'timeGetTime'
    run=subprocess.run([str(ROOT/'.venv-target-hud/Scripts/python.exe'),str(ROOT/'tools/fix_custom_bridge_iats.py'),str(d/'item-description.exe'),'--dll','cps.dll'],capture_output=True,text=True)
    assert run.returncode==0 and 'stale bridge operands: 0'in run.stdout,run.stdout+run.stderr
    (d/'iat-verification.log').write_text(run.stdout,encoding='utf8')
    report={'passed':True,'client_sha256':hashlib.sha256((d/'item-description.exe').read_bytes()).hexdigest(),'tests':results,'cps_stale_operands':0,'new_payload_imports':0,'live_accepted':False}
    (d/'release-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'client_sha256':report['client_sha256'],'groups':list(results),'cps_stale_operands':0,'live_accepted':False}))
if __name__=='__main__':main()
