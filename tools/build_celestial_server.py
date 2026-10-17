"""Build matching WENV map and generator binaries into an isolated staging folder."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def relink_without_pdb(server,out,project,log,dependencies_root=None):
    """Link the compiled Release objects when the local PDB installation fails."""
    ns={'m':'http://schemas.microsoft.com/developer/msbuild/2003'}
    tree=ET.parse(server/f'src/map/{project}.vcxproj')
    groups=[g for g in tree.findall('m:ItemDefinitionGroup',ns) if "Release|x64" in g.get('Condition','')]
    assert len(groups)==1
    dependencies=groups[0].find('m:Link/m:AdditionalDependencies',ns).text
    dependencies=dependencies.replace('$(SolutionDir)',str(dependencies_root or server)+'\\').replace('$(Platform)','x64').replace('%(AdditionalDependencies)','')
    objects=sorted((out/'obj'/project).rglob('*.obj'))
    assert len(objects)>80,'Production object set is incomplete'
    vs=Path('C:/Program Files/Microsoft Visual Studio/18/Community')
    version=(vs/'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
    vc=vs/'VC/Tools/MSVC'/version;sdk=Path(os.environ['ProgramFiles(x86)'])/'Windows Kits/10'
    sdk_version=sorted(p.name for p in (sdk/'Lib').iterdir() if p.is_dir())[-1]
    env=os.environ.copy();env['LIB']=';'.join(str(p) for p in [vc/'lib/x64',sdk/'Lib'/sdk_version/'ucrt/x64',sdk/'Lib'/sdk_version/'um/x64'])
    target=out/'bin'/(project+'.exe')
    command=['/NOLOGO','/MACHINE:X64','/SUBSYSTEM:CONSOLE','/OUT:'+str(target),'/DEBUG:NONE','/LTCG','/OPT:REF','/OPT:ICF','/DYNAMICBASE','/NXCOMPAT']
    # Microsoft.Cpp's inherited Windows default libraries follow the explicit project list.
    command += [str(p) for p in objects]+[p for p in dependencies.split(';') if p]
    command += ['kernel32.lib','user32.lib','gdi32.lib','winspool.lib','comdlg32.lib','advapi32.lib',
                'shell32.lib','ole32.lib','oleaut32.lib','uuid.lib','odbc32.lib','odbccp32.lib']
    response=out/(project+'-no-pdb.rsp')
    response.write_text('\n'.join('"'+p+'"' for p in command)+'\n',encoding='utf-16')
    with log.open('a',encoding='utf8') as f:
        f.write('\nRetrying the complete production object set with the x64 linker and /DEBUG:NONE.\n');f.flush()
        run=subprocess.run([str(vc/'bin/Hostx64/x64/link.exe'),'@'+str(response)],cwd=server/'src/map',env=env,stdout=f,stderr=subprocess.STDOUT)
    return run.returncode

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
    ap.add_argument('--dependencies-root',type=Path,help='Reuse an existing server toolchain/library tree for an isolated source snapshot')
    ap.add_argument('--project',choices=['map-server','map-server-generator'])
    ap.add_argument('--relink-only',action='store_true',help='Reuse already compiled production objects; omit only PDB generation')
    ap.add_argument('--output',type=Path,default=ROOT/'Outputs/CelestialDial/server-build')
    args=ap.parse_args();server=args.server.resolve();out=args.output.resolve()
    dependencies_root=args.dependencies_root.resolve() if args.dependencies_root else server
    (out/'bin').mkdir(parents=True,exist_ok=True)
    names=['src/common/world_environment_wire.hpp','src/map/world_environment.cpp','src/map/world_environment.hpp','src/map/atcommand.cpp','src/map/pc.hpp','src/map/clif.cpp',
           'src/map/map-server.vcxproj','src/map/map-server-generator.vcxproj']
    names += ['src/map/battle.cpp','src/map/battle.hpp','conf/battle/misc.conf','conf/import/battle_conf.txt']
    names += ['src/map/pincode_ui.cpp','src/map/pincode_ui.hpp']
    names += [name for name in ['src/map/world_environment_profiles.cpp','src/map/world_environment_profiles.hpp',
              'conf/world_environment.yml','conf/import/world_environment.yml'] if (server/name).exists()]
    hashes={name:hashlib.sha256((server/name).read_bytes()).hexdigest() for name in names}
    msbuild='C:/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe'
    results=[]
    env=os.environ.copy()
    if dependencies_root != server:
        # Resolve project headers from this snapshot before the reused dependency
        # tree. Mixing physical copies breaks pragma-once in skill headers.
        env['CL'] = '/I"' + str(server / 'src') + '" ' + env.get('CL', '')
    # Embed compiler debug records in objects; no shared PDB service is needed.
    env['_CL_']=(env.get('_CL_','')+' /Z7').strip()
    for project in [args.project] if args.project else ['map-server','map-server-generator']:
        print('BUILD '+project,flush=True)
        log=out/(project+'.log')
        cmd=[msbuild,str(server/f'src/map/{project}.vcxproj'),'/t:Build','/m:2','/nologo','/verbosity:minimal',
             '/p:PreferredToolArchitecture=x64',
             '/p:Configuration=Release','/p:Platform=x64','/p:BuildProjectReferences=false','/p:SolutionDir='+str(dependencies_root)+'\\',
             '/p:OutDir='+str(out/'bin')+'\\','/p:IntDir='+str(out/'obj'/project)+'\\']
        if args.relink_only:
            result=relink_without_pdb(server,out,project,log,dependencies_root)
        else:
            with log.open('w',encoding='utf8') as f:
                run=subprocess.run(cmd,cwd=server/'src/map',stdout=f,stderr=subprocess.STDOUT,env=env)
            result=run.returncode
            if result and any(error in log.read_text(encoding='utf8',errors='replace') for error in ['MSPDB140.DLL','LNK1318']):
                result=relink_without_pdb(server,out,project,log,dependencies_root)
        target=out/'bin'/(project+'.exe')
        if result or not target.exists():
            raise RuntimeError(log.read_text(encoding='utf8',errors='replace')[-5000:])
        results.append({'project':project,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        print('PASS '+project,flush=True)
    assert all(hashlib.sha256((server/n).read_bytes()).hexdigest()==h for n,h in hashes.items()),'Sources changed during build'
    report={'passed':True,'deployed':False,'sources':hashes,'targets':results}
    (out/('build-result'+('-'+args.project if args.project else '')+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
