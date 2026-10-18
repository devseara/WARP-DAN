"""Run real Banquet descriptor/identity code with its actual YAML loader, without services."""
from pathlib import Path
import argparse,subprocess,os,json,hashlib,shutil
from generate_item_description_data import load_db
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
    ap.add_argument('--compiler',type=Path,default=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x64/cl.exe'))
    ap.add_argument('--sdk-version',default='10.0.26100.0')
    ap.add_argument('--debug-runtime',action='store_true',help='Match a /MTd, iterator-level-0 server ryml.lib');args=ap.parse_args()
    server=args.server.resolve();out=ROOT/'Outputs/ItemDescription/server-tests';out.mkdir(parents=True,exist_ok=True)
    source=(server/'src/map/item_description.cpp').read_text(encoding='utf8')
    parts=[]
    for start,end in [('struct Effect {','template<size_t N> void copy'),('template<size_t N> void copy','const char* type_name'),('w::u64 fingerprint(','void initialize('),('struct Builder {','void append_refine(')]:
        parts.append(source[source.index(start):source.index(end)])
    (out/'item_description_watch_under_test.inc').write_text(source[source.index('void reload()'):source.index('void process_request(')],encoding='utf8')
    (out/'item_description_request_under_test.inc').write_text(source[source.index('void process_request('):source.rindex('} // namespace item_description')],encoding='utf8')
    (out/'item_description_under_test.inc').write_text('\n'.join(parts),encoding='utf8')
    compiler=args.compiler.resolve();vc=compiler.parents[3];sdk=Path('C:/Program Files (x86)/Windows Kits/10');ver=args.sdk_version
    env=os.environ.copy();env['INCLUDE']=';'.join(str(p)for p in[vc/'include',sdk/'Include'/ver/'ucrt',sdk/'Include'/ver/'shared',sdk/'Include'/ver/'um'])
    env['LIB']=';'.join(str(p)for p in[vc/'lib/x64',sdk/'Lib'/ver/'ucrt/x64',sdk/'Lib'/ver/'um/x64'])
    includes=[out,server/'src',server/'3rdparty/rapidyaml/src',server/'3rdparty/rapidyaml/ext/c4core/src',server/'3rdparty/libconfig']
    runtime=['/MTd','/D_ITERATOR_DEBUG_LEVEL=0'] if args.debug_runtime else ['/MT']
    cmd=[str(compiler),'/nologo','/std:c++17','/EHsc',*runtime,'/O2','/DWIN32','/D_CRT_SECURE_NO_WARNINGS',*[f'/I{p}'for p in includes],str(ROOT/'tools/native/item_description_server_test.cpp'),str(server/'src/common/database.cpp'),str(server/'.vs/build/ryml.lib'),f'/Fe:{out}/server-test.exe',f'/Fo:{out}/']
    result=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError((result.stdout+result.stderr)[-5000:])
    metadata=out/'metadata';metadata.mkdir(exist_ok=True)
    for relative in ['db/item_description_db.yml','db/item_description_generated.yml','db/import/item_description_db.yml']:
        target=metadata/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(server/relative,target)
    shutil.copy2(server/'db/item_description_db.yml',metadata/'item_description_db.yml')
    sources={};items=load_db(server,'db/item_db.yml','Prerenewal',sources);options=load_db(server,'db/item_randomopt_db.yml','Prerenewal',sources)
    (metadata/'ids.txt').write_text(' '.join(str(i) for i in items)+'\n'+' '.join(str(i) for i in options)+'\n')
    result=subprocess.run([str(out/'server-test.exe'),str(out),str(metadata)],capture_output=True,text=True,timeout=90)
    if result.returncode:raise RuntimeError(f'Server tests failed ({result.returncode}): '+result.stdout+result.stderr)
    report={'passed':True,'checks':result.stdout.strip(),'engine_boundaries_mocked':True,'source_sha256':hashlib.sha256((server/'src/map/item_description.cpp').read_bytes()).hexdigest()}
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
