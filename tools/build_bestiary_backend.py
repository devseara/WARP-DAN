"""Build matching Bestiary map, generator and char binaries without deployment."""
from pathlib import Path
import argparse,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--msbuild',type=Path,default=Path('C:/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe'))
    args=ap.parse_args();server=args.server.resolve();out=args.output.resolve();(out/'bin').mkdir(parents=True,exist_ok=True)
    names=['src/common/bestiary_definitions.hpp','src/common/bestiary_research_types.hpp','src/map/bestiary_research.cpp','src/map/bestiary_research.hpp','src/map/bestiary_journal.cpp','src/map/bestiary_ui.cpp','src/map/bestiary_catalog.inc','src/char/int_bestiary.cpp','src/char/int_mail.cpp','src/map/clif.cpp','src/map/achievement.cpp','db/bestiary_research.yml','db/bestiary_lore.yml','db/bestiary_lore_sources.json','db/import/bestiary_lore.yml','db/import/bestiary_research.yml','db/title_db.yml']
    sources={n:hashlib.sha256((server/n).read_bytes()).hexdigest() for n in names}
    results=[]
    for project in ['src/char/char-server.vcxproj','src/map/map-server.vcxproj','src/map/map-server-generator.vcxproj']:
        name=Path(project).stem;print('BUILD '+name,flush=True)
        command=[str(args.msbuild),str(server/project),'/t:Build','/m:2','/nologo','/verbosity:minimal','/p:Configuration=Release','/p:Platform=x64','/p:BuildProjectReferences=false',
                 '/p:SolutionDir='+str(server)+'\\','/p:OutDir='+str(out/'bin')+'\\','/p:IntDir='+str(out/'obj'/name)+'\\']
        log=out/(name+'.log')
        with log.open('w',encoding='utf-8') as stream:
            result=subprocess.run(command,cwd=server,stdout=stream,stderr=subprocess.STDOUT)
        target=out/'bin'/(name+'.exe')
        if result.returncode or not target.exists():
            print(log.read_text(encoding='utf-8',errors='replace')[-6500:]);raise RuntimeError(name+' build failed; '+str(log))
        row={'project':project,'binary':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'log':str(log),'passed':True}
        results.append(row);print(json.dumps(row),flush=True)
    assert all(hashlib.sha256((server/n).read_bytes()).hexdigest()==digest for n,digest in sources.items()), 'Source changed during build'
    report={'passed':True,'deployed':False,'server':str(server),'targets':results,'source_sha256':sources}
    (out/'build-result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('All three Bestiary backend targets built; running services were not modified.',flush=True)

if __name__=='__main__':main()
