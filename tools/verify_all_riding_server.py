"""Compile the production All_Riding policy and state-recalculation code offline.

The real state algorithm and attack condition switch are extracted verbatim.
Database storage and unrelated actor types are minimal test doubles. The full
map-server build remains a separate required gate.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(source, prefix):
    match = re.search('^' + re.escape(prefix) + r'[^\n]*\{.*?^\}', source, re.M | re.S)
    assert match, prefix
    return match.group()


def verify(server, out):
    status = (server / 'src/map/status.cpp').read_text(encoding='utf-8')
    skill = (server / 'src/map/skill.cpp').read_text(encoding='utf-8')
    policy = function(status, 'bool status_all_riding_combat_allowed(')
    algorithm = function(status, 'void status_calc_state_sub(')
    begin = status.index('\t// Can\'t attack\n', status.index('void status_calc_state('))
    end = status.index('\t// Can\'t warp\n', begin)
    attack = status[begin:end]
    assert 'case SC_ALL_RIDING:' in attack and '!status_all_riding_combat_allowed(&bl)' in attack
    assert 'sc->getSCE(SC_ALL_RIDING) && !status_all_riding_combat_allowed(src)' in status
    assert 'sd.sc.getSCE(SC_ALL_RIDING) && !status_all_riding_combat_allowed(&sd)' in skill
    for mode in ['re', 'pre-re']:
        db = (server / f'db/{mode}/status.yml').read_text(encoding='utf-8')
        entry = db.split('  - Status: All_Riding\n', 1)[1].split('  - Status:', 1)[0]
        assert 'NoAttackCond: true' in entry and 'NoAttack: true' not in entry
    battle = (server / 'src/map/battle.cpp').read_text(encoding='utf-8')
    assert re.search(
        r'"all_riding_combat"\s*,\s*&battle_config\.all_riding_combat,\s*0,\s*0,\s*1', battle
    )
    fixture = r'''
#include <array>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <map>
#include <memory>
enum { BL_PC=1, BL_MOB=2 };
enum sc_type { SC_ALL_RIDING, SC_DANCING, SC_LONGING, SC_STUN };
enum e_scs_flag { SCS_NOATTACK, SCS_NOATTACKCOND };
struct block_list { int type; };
struct status_change_entry { int val4=0; };
struct status_change : std::map<sc_type,status_change_entry> {
 struct { bool attack=false; } cant;
 bool hasSCE(sc_type t) const { return count(t)!=0; }
};
struct s_status_change_db { std::array<bool,2> state{}; };
struct { int all_riding_combat=0; } battle_config;
struct Database : std::map<sc_type,std::shared_ptr<s_status_change_db>> {
 std::shared_ptr<s_status_change_db> find(sc_type t) { auto i=std::map<sc_type,std::shared_ptr<s_status_change_db>>::find(t);return i==end()?nullptr:i->second; }
} status_db;
const char* script_get_constant_str(const char*,int) { return "test"; }
void ShowError(const char*,...) { std::fprintf(stderr,"Unexpected production state error\n");std::exit(1); }
void require(bool b,const char* reason) { if(!b) {std::fprintf(stderr,"FAIL %s\n",reason);std::exit(1);} }
// @policy
// @algorithm
void recalc(block_list& bl,status_change& sc,std::shared_ptr<s_status_change_db> scdb,bool start) {
// @attack
}
int main() {
 for(auto t:{SC_ALL_RIDING,SC_DANCING,SC_LONGING,SC_STUN})status_db[t]=std::make_shared<s_status_change_db>();
 status_db[SC_ALL_RIDING]->state[SCS_NOATTACKCOND]=true;
 status_db[SC_DANCING]->state[SCS_NOATTACKCOND]=true;
 status_db[SC_LONGING]->state[SCS_NOATTACKCOND]=true;
 status_db[SC_STUN]->state[SCS_NOATTACK]=true;
 int cases=0;
 for(int enabled:{0,1})for(int kind:{BL_PC,BL_MOB})for(bool stun:{false,true})for(bool dancing:{false,true})for(bool longing:{false,true}) {
  battle_config.all_riding_combat=enabled; block_list actor{kind};status_change sc;
  require(!status_all_riding_combat_allowed(nullptr),"null is never allowed");
  sc[SC_ALL_RIDING]={};
  if(stun)sc[SC_STUN]={};
  if(dancing)sc[SC_DANCING]={1}; // Ensemble, controlled by Longing.
  if(longing)sc[SC_LONGING]={};
  recalc(actor,sc,status_db[SC_ALL_RIDING],true);
  bool other=stun||(dancing&&!longing);
  require(sc.cant.attack==(!(enabled&&kind==BL_PC)||other),"mount policy and other active restrictions compose");
  sc.erase(SC_ALL_RIDING);recalc(actor,sc,status_db[SC_ALL_RIDING],false);
  require(sc.cant.attack==other,"dismount preserves other restrictions");
  sc[SC_ALL_RIDING]={};recalc(actor,sc,status_db[SC_ALL_RIDING],true);
  require(sc.cant.attack==(!(enabled&&kind==BL_PC)||other),"remount restores configured policy");
  if(stun) {sc.erase(SC_STUN);recalc(actor,sc,status_db[SC_STUN],false);
   require(sc.cant.attack==(!(enabled&&kind==BL_PC)||(dancing&&!longing)),"ending another restriction recalculates mounted state");}
  ++cases;
 }
 std::printf("PASS %d production state cases: off/on, PC/non-PC, stun, dancing, Longing, remount\n",cases);
}
'''
    fixture = (
        fixture.replace('// @policy', policy)
        .replace('// @algorithm', algorithm)
        .replace('// @attack', attack)
    )
    out.mkdir(parents=True, exist_ok=True)
    source = out / 'state-test.cpp'
    source.write_text(fixture, encoding='utf-8')
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
    exe = out / 'state-test.exe'
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
    run = subprocess.run(
        ['cmd.exe', '/d', '/c', str(script)], cwd=out, capture_output=True, text=True, timeout=120
    )
    assert run.returncode == 0, run.stdout + run.stderr
    run = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stdout + run.stderr
    names = [
        'src/map/status.cpp',
        'src/map/status.hpp',
        'src/map/skill.cpp',
        'src/map/battle.cpp',
        'src/map/battle.hpp',
        'db/re/status.yml',
        'db/pre-re/status.yml',
        'conf/battle/player.conf',
        'conf/import/battle_conf.txt',
    ]
    report = dict(
        passed=True,
        cases=32,
        stdout=run.stdout.strip(),
        sources={n: hashlib.sha256((server / n).read_bytes()).hexdigest() for n in names},
        native_server_runtime_accepted=False,
    )
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(run.stdout.strip())


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server', type=Path, default=ROOT.parent / 'BanquetOfHeroes')
    ap.add_argument(
        '--output', type=Path, default=ROOT / 'Outputs/all-riding-combat-20261018/server-state-test'
    )
    args = ap.parse_args()
    verify(args.server.resolve(), args.output.resolve())
