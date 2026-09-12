"""Build and execute real server YAML reload tests without starting a server."""
from pathlib import Path
import argparse,subprocess,os,json,hashlib
from build_bestiary_lore import roster
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');args=ap.parse_args()
    server=args.server.resolve();out=ROOT/'Outputs/Bestiary/verification/native/yaml-test';out.mkdir(parents=True,exist_ok=True)
    mobs,_=roster(server)
    (out/'active-mob-ids.txt').write_text('\n'.join(map(str,sorted(mobs))),encoding='ascii')
    source=(server/'src/map/bestiary_catalog.inc').read_text(encoding='utf-8')
    actual=source[source.index('struct LoreEntry'):source.index('std::unique_ptr<LoreDatabase>')]
    (out/'bestiary_lore_under_test.inc').write_text(actual,encoding='utf-8')
    vc=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231')
    sdk=Path('C:/Program Files (x86)/Windows Kits/10');ver='10.0.26100.0'
    env=os.environ.copy();env['INCLUDE']=';'.join(str(p) for p in [vc/'include',sdk/'Include'/ver/'ucrt',sdk/'Include'/ver/'shared',sdk/'Include'/ver/'um'])
    env['LIB']=';'.join(str(p) for p in [vc/'lib/x64',sdk/'Lib'/ver/'ucrt/x64',sdk/'Lib'/ver/'um/x64'])
    includes=[out,server/'src',server/'3rdparty/rapidyaml/src',server/'3rdparty/rapidyaml/ext/c4core/src',server/'3rdparty/libconfig']
    cmd=[str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++17','/EHsc','/MT','/O2','/DWIN32','/D_CRT_SECURE_NO_WARNINGS',*[f'/I{p}' for p in includes],str(ROOT/'tools/native/bestiary_yaml_test.cpp'),str(server/'src/common/database.cpp'),str(server/'.vs/build/ryml.lib'),f'/Fe:{out}/yaml-test.exe',f'/Fo:{out}/']
    run=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'build.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError((run.stdout+run.stderr)[-6500:])
    run=subprocess.run([str(out/'yaml-test.exe'),str(out),str(server)],capture_output=True,text=True)
    if run.returncode:raise RuntimeError(f'YAML test failed {run.returncode}: '+run.stdout+run.stderr)
    report={'passed':True,'source':'Real server database.cpp and rapidyaml; allocator/log boundaries substituted','checks':run.stdout.strip(),'lore_sha256':hashlib.sha256((server/'db/bestiary_lore.yml').read_bytes()).hexdigest()}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
