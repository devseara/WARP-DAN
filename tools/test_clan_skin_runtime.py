"""Run the real x86 resolver tests, optionally checking the server wire policy."""
from pathlib import Path
import argparse,subprocess
from build_clan_skin_runtime import ROOT,TOOL_DIR

def run(tool_dir=TOOL_DIR,server=None,test_source=None,artifact_name="runtime-test"):
    vc=tool_dir.parents[2];sdk=Path(r'C:\Program Files (x86)\Windows Kits\10')
    sdk_versions=sorted((sdk/'Include').glob('10.*'),key=lambda p:tuple(map(int,p.name.split('.'))))
    sdk_version=sdk_versions[-1].name
    out=ROOT/'Outputs/clan-body-skins/runtime';out.mkdir(parents=True,exist_ok=True)
    source=test_source or ROOT/'tools/tests/clan_skin_runtime_test.cpp'
    if server:
        policy=(server/'src/map/clan_skin_policy.hpp').resolve();assert policy.is_file()
        wrapper=out/'runtime-policy-test.cpp'
        wrapper.write_text('#include "'+policy.as_posix()+'"\n#define CLAN_POLICY_PRESENT 1\n#include "'+source.as_posix()+'"\n',encoding='utf8')
        source=wrapper
    exe=out/(artifact_name+'.exe')
    args=[str(tool_dir/'cl.exe'),'/nologo','/std:c++17','/O2','/W4','/WX','/EHsc','/MD','/I'+str(vc/'include'),'/I'+str(sdk/f'Include/{sdk_version}/ucrt'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe),str(source),'/link','/LIBPATH:'+str(vc/'lib/x86'),'/LIBPATH:'+str(sdk/f'Lib/{sdk_version}/ucrt/x86'),'/LIBPATH:'+str(sdk/f'Lib/{sdk_version}/um/x86')]
    subprocess.run(args,cwd=out,check=True)
    result=subprocess.run([str(exe)],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
    (out/(artifact_name+'.log')).write_bytes(result.stdout);print(result.stdout.decode('utf8',errors='replace'))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--tool-dir',type=Path,default=TOOL_DIR);ap.add_argument('--server',type=Path);args=ap.parse_args();run(args.tool_dir,args.server)
