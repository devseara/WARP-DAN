"""Compile and execute the real staged or installed WENV server module in isolation."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
    ap.add_argument('--test-source',type=Path)
    ap.add_argument('--include-server-headers',action='store_true')
    args=ap.parse_args()
    vswhere=Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
    vs=Path(subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip())
    version=(vs/'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
    vc=vs/'VC/Tools/MSVC'/version
    sdk=Path(os.environ['ProgramFiles(x86)'])/'Windows Kits/10'
    sdk_version=sorted(p.name for p in (sdk/'Lib').iterdir() if p.is_dir())[-1]
    env=os.environ.copy()
    env['INCLUDE']=';'.join(str(p) for p in [vc/'include',sdk/'Include'/sdk_version/'ucrt',sdk/'Include'/sdk_version/'um',sdk/'Include'/sdk_version/'shared'])
    if args.include_server_headers:env['INCLUDE']=str(args.server.resolve()/'src')+';'+env['INCLUDE']
    env['LIB']=';'.join(str(p) for p in [vc/'lib/x64',sdk/'Lib'/sdk_version/'ucrt/x64',sdk/'Lib'/sdk_version/'um/x64'])
    out=ROOT/'Outputs/CelestialDial/server-test';out.mkdir(parents=True,exist_ok=True)
    test_source=args.test_source.resolve() if args.test_source else args.server.resolve()/'tools/test_world_environment.cpp'
    exe=out/(test_source.stem+'.exe')
    cmd=[str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++17','/EHsc','/MT','/W4','/WX','/D_CRT_SECURE_NO_WARNINGS','/utf-8',
         '/Fe'+str(exe),'/Fo'+str(out/(test_source.stem+'.obj')),str(test_source)]
    subprocess.run(cmd,cwd=out,env=env,check=True)
    subprocess.run([str(exe)],cwd=out,check=True)

if __name__=='__main__':
    main()
