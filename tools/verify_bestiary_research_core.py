"""Compile/run actual C++ research definitions and journal, with isolated test files."""
from pathlib import Path
import subprocess,os,json,tempfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    server=ROOT.parent/'BanquetOfHeroes';out=ROOT/'Outputs/Bestiary/verification/research/core-test';out.mkdir(parents=True,exist_ok=True)
    source=(server/'src/map/bestiary_research.cpp').read_text()
    def function(start,end):return source.split(start,1)[1].split(end,1)[0]
    capture='int collect_party'+function('int collect_party','TIMER_FUNC(tick)')
    capture+='std::vector<Record> capture'+function('std::vector<Record> capture','void record(')
    (out/'capture-under-test.inc').write_text(capture,encoding='utf-8')
    death=(server/'src/map/mob.cpp').read_text()
    assert 'tmpsd[r] && md->dmglog[r].dmg>0' in death
    assert 'src && type==0 && !md->state.npc_killmonster' in death
    assert 'if( !rebirth ) { // Only trigger event on final kill\n\t\tbestiary_research::record(research_credit);' in death
    vc=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231');sdk=Path('C:/Program Files (x86)/Windows Kits/10');version='10.0.26100.0'
    env=os.environ.copy();env['INCLUDE']=';'.join(str(p) for p in [vc/'include',sdk/'Include'/version/'ucrt',sdk/'Include'/version/'shared',sdk/'Include'/version/'um'])
    env['LIB']=';'.join(str(p) for p in [vc/'lib/x64',sdk/'Lib'/version/'ucrt/x64',sdk/'Lib'/version/'um/x64'])
    includes=[out,server/'src',server/'3rdparty/rapidyaml/src',server/'3rdparty/rapidyaml/ext/c4core/src',server/'3rdparty/libconfig']
    cmd=[str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++17','/EHsc','/MT','/O2','/DWIN32','/D_CRT_SECURE_NO_WARNINGS',*[f'/I{p}' for p in includes],str(ROOT/'tools/native/bestiary_research_core_test.cpp'),str(server/'src/common/database.cpp'),str(server/'src/map/bestiary_journal.cpp'),str(server/'.vs/build/ryml.lib'),f'/Fe:{out}/research-core-test.exe',f'/Fo:{out}/']
    run=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'build.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError((run.stdout+run.stderr)[-6500:])
    directory=tempfile.mkdtemp(prefix='run-',dir=out)
    run=subprocess.run([str(out/'research-core-test.exe'),str(server),directory],capture_output=True,text=True,timeout=120)
    if run.returncode:raise RuntimeError(f'Core test failed {run.returncode}: '+run.stdout+run.stderr)
    report={'passed':True,'checks':run.stdout.strip(),'artifacts':directory,'boundaries':'Actual definitions, capture functions and WAL. Capture uses minimal player/map fixtures; allocator/log boundaries are stubbed.'}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
