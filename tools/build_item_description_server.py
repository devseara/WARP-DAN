"""Build map and generator targets into IDUI's isolated directory, without deployment."""
from pathlib import Path
import argparse,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');args=ap.parse_args()
    server=args.server.resolve();out=ROOT/'Outputs/ItemDescription/server';(out/'bin').mkdir(parents=True,exist_ok=True)
    names=['src/common/item_description_wire.hpp','src/map/item_description.cpp','src/map/item_description.hpp','src/map/clif.cpp','src/map/itemdb.cpp','src/map/pc.hpp','src/config/renewal.hpp','db/item_description_db.yml','db/item_description_generated.yml','db/import/item_description_db.yml']
    hashes={name:hashlib.sha256((server/name).read_bytes()).hexdigest()for name in names}
    msbuild='C:/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe';results=[]
    for project in ['map-server','map-server-generator']:
        print('BUILD '+project,flush=True);log=out/(project+'.log')
        cmd=[msbuild,str(server/f'src/map/{project}.vcxproj'),'/t:Build','/m:2','/nologo','/verbosity:minimal','/p:Configuration=Release','/p:Platform=x64','/p:BuildProjectReferences=false','/p:SolutionDir='+str(server)+'\\','/p:OutDir='+str(out/'bin')+'\\','/p:IntDir='+str(out/'obj'/project)+'\\']
        with log.open('w',encoding='utf8')as f:result=subprocess.run(cmd,cwd=server,stdout=f,stderr=subprocess.STDOUT)
        target=out/'bin'/(project+'.exe')
        if result.returncode or not target.exists():raise RuntimeError(log.read_text(encoding='utf8',errors='replace')[-5500:])
        results.append({'target':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'passed':True});print(project+' PASS',flush=True)
    assert all(hashlib.sha256((server/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items()),'Sources changed while building'
    report={'passed':True,'deployed':False,'source_sha256':hashes,'targets':results};(out/'build-result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
