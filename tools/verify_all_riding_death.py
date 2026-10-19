"""Compile the production death-clear loop and check scoped mount persistence."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def function(text, prefix):
    match = re.search('^' + re.escape(prefix) + r'[^\{]*\{.*?^\}', text, re.M | re.S)
    assert match, prefix
    return match.group()


def verify(server, out):
    text = (server / 'src/map/status.cpp').read_text(encoding='utf-8')
    policy = function(text, 'bool status_all_riding_combat_allowed(')
    clear = function(text, 'int32 status_change_clear(')
    fixture = r'''
#include <array>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>
using int32 = int;
enum { BL_PC=1, BL_MOB=2, ELE_HOLY=6, ELE_DARK=7 };
enum sc_type { SC_ALL_RIDING, SC_STUN, SC_OTHER, SC_PERSIST, SC_ELEMENTALCHANGE,
 SC_GUILD_STATS_TIER_1,SC_GUILD_STATS_TIER_2,SC_GUILD_STATS_TIER_3,SC_GUILD_STATS_TIER_4,SC_GUILD_STATS_TIER_5 };
enum { SCF_NOREMOVEONDEAD,SCF_NOCLEARBUFF };
struct status_change_entry { int val2=0; };
struct status_change : std::map<sc_type,status_change_entry> {
 int comet_x=9,comet_y=8,sg_counter=7,opt1=6,opt2=5,opt3=4;
 status_change_entry* getSCE(sc_type type) { auto i=find(type);return i==end()?nullptr:&i->second; }
 void deleteSCE(sc_type type) { erase(type); }
};
struct block_list { int type;status_change* sc; };
struct entry { std::array<bool,2> flag{}; };
std::map<sc_type,std::shared_ptr<entry>> status_db;
struct { int all_riding_combat=0; } battle_config;
status_change* status_get_sc(block_list* bl) { return bl?bl->sc:nullptr; }
int ends=0,notifications=0;
void status_change_end(block_list* bl,sc_type type) { ++ends;bl->sc->erase(type); }
void clif_changeoption(block_list*) { ++notifications; }
void require(bool value,const char* reason) { if(!value){std::fprintf(stderr,"FAIL %s\n",reason);std::exit(1);} }
// @policy
// @clear
int main() {
 for(int s=SC_ALL_RIDING;s<=SC_GUILD_STATS_TIER_5;++s)status_db[(sc_type)s]=std::make_shared<entry>();
 status_db[SC_PERSIST]->flag[SCF_NOREMOVEONDEAD]=true;
 status_db[SC_ALL_RIDING]->flag[SCF_NOCLEARBUFF]=true;
 int cases=0;
 for(int enabled:{0,1})for(int kind:{BL_PC,BL_MOB})for(int type:{0,1,2,3})for(bool mounted:{false,true}) {
  battle_config.all_riding_combat=enabled;status_change sc;block_list actor{kind,&sc};
  if(mounted)sc[SC_ALL_RIDING]={};
  sc[SC_STUN]={};sc[SC_OTHER]={};sc[SC_PERSIST]={};ends=notifications=0;
  require(status_change_clear(&actor,type)==1,"clear completed");
  bool keepMount=mounted&&((type==0&&enabled&&kind==BL_PC)||type==3);
  require((sc.getSCE(SC_ALL_RIDING)!=nullptr)==keepMount,"mount persistence is death-only, player-only and opt-in");
  require(!sc.getSCE(SC_STUN)&&!sc.getSCE(SC_OTHER),"unrelated death/clear cleanup preserved");
  require((sc.getSCE(SC_PERSIST)!=nullptr)==(type==0),"existing NoRemoveOnDead behavior preserved");
  require(sc.opt1==0&&sc.opt2==0&&sc.opt3==0,"native option reset preserved");
  require(notifications==((type==0||type==2)?1:0),"native option notifications preserved");
  if(type==0&&keepMount) {
   // Reviving does not manufacture another mount or replace its status entry.
   auto* same=sc.getSCE(SC_ALL_RIDING);require(same!=nullptr,"mount remains available for native death pose/revival");
   status_change_end(&actor,SC_ALL_RIDING);require(!sc.getSCE(SC_ALL_RIDING),"normal expiry/dismount can still end retained mount");
  }
  ++cases;
 }
 block_list missing{BL_PC,nullptr};require(status_change_clear(&missing,0)==0,"missing status is safe");
 std::printf("PASS %d death-clear cases: opt-in PC mount persistence; stock cleanup, logout and expiry retained\n",cases);
}
'''.replace(
        '// @policy', policy
    ).replace(
        '// @clear', clear
    )
    out.mkdir(parents=True, exist_ok=True)
    source = out / 'death-test.cpp'
    source.write_text(fixture, encoding='utf-8')
    exe = out / ('death-test.exe' if os.name == 'nt' else 'death-test')
    if os.name == 'nt':
        vswhere = (
            Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))
            / 'Microsoft Visual Studio/Installer/vswhere.exe'
        )
        vs = subprocess.check_output(
            [
                str(vswhere),
                '-latest',
                '-products',
                '*',
                '-requires',
                'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                '-property',
                'installationPath',
            ],
            text=True,
        ).strip()
        script = out / 'compile.cmd'
        script.write_text(
            '@echo off\ncall "'
            + str(Path(vs) / 'Common7/Tools/VsDevCmd.bat')
            + '" -arch=x64 -host_arch=x64 >nul\n'
            'if errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /EHsc /W3 /O2 "'
            + str(source)
            + '" /Fe:"'
            + str(exe)
            + '"\n'
            'exit /b %errorlevel%\n'
        )
        command = ['cmd.exe', '/d', '/c', str(script)]
    else:
        compiler = os.environ.get('CXX') or shutil.which('c++') or shutil.which('g++')
        assert compiler, 'C++17 compiler required.'
        command = [compiler, '-std=c++17', '-O2', str(source), '-o', str(exe)]
    run = subprocess.run(command, cwd=out, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    run = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stdout + run.stderr
    result = dict(
        passed=True,
        cases=32,
        stdout=run.stdout.strip(),
        native_status_clear_loop_extracted_verbatim=True,
        live_death_visual_accepted=False,
    )
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(run.stdout.strip())


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        '--server',
        type=Path,
        default=root if (root / 'src/map/status.cpp').exists() else root.parent / 'BanquetOfHeroes',
    )
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.output:
        verify(args.server.resolve(), args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='mounted-death-') as folder:
            verify(args.server.resolve(), Path(folder))
