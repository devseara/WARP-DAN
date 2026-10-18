"""Compare description job eligibility with the real pc.cpp predicates in both modes."""
from pathlib import Path
import argparse, os, re, subprocess, json


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--server',type=Path,required=True)
    ap.add_argument('--compiler',type=Path,required=True);args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=root/'Outputs/ItemDescription/requirements-tests';out.mkdir(parents=True,exist_ok=True)
    read=lambda p:(args.server/p).read_text(encoding='utf8')
    pc=read('src/map/pc.cpp');module=read('src/map/item_description.cpp')
    enums='\n'.join(re.search(r'enum '+name+r'\b[^}]+};',read(path),re.S)[0] for path,name in
        [('src/map/pc.hpp','weapon_type'),('src/map/itemdb.hpp','e_item_job')])
    defines='\n'.join(line for line in read('src/map/map.hpp').splitlines() if re.match(r'#define (JOBL_|MAPID_FIRSTMASK)',line))
    predicates=pc[pc.index('static bool pc_job_can_use_item('):pc.index('uint8 pc_isequip(')]
    production=module[module.index('bool description_job_allowed('):module.index('void append_requirements(')]
    source='''#include <cassert>
#include <iostream>
#include <common/mmo.hpp>
#define nullpo_retr(value,ptr) if(!(ptr))return value
constexpr int SC_SPIRIT=1, SL_SUPERNOVICE=2, PC_PERM_USE_ALL_EQUIPMENT=3;
#define EQP_HELM (EQP_HEAD_LOW|EQP_HEAD_MID|EQP_HEAD_TOP)
#define EQP_ARMS (EQP_HAND_R|EQP_HAND_L)
struct Spirit { int val2=SL_SUPERNOVICE; } spirit;
struct map_session_data { int class_=0; bool permission=false;
    struct { unsigned base_level=85; } status;
    struct { bool enabled=false; const Spirit* getSCE(int) const {return enabled?&spirit:nullptr;} } sc;
};
struct item_data { uint64 class_base[3]{}; int class_upper=0,equip=0,type=IT_ARMOR,weapon_level=0,subtype=0; };
bool pc_has_permission(const map_session_data* s,int) {return s->permission;}
'''+enums+'\n'+defines+'\n'+predicates+'\n'+production+'''
int main(){
    map_session_data s; item_data d; unsigned tested=0;
    for(int job=0;job<32;++job) for(int branch:{0,JOBL_2_1,JOBL_2_2})
    for(int mode:{0,JOBL_UPPER,JOBL_BABY,JOBL_THIRD,JOBL_THIRD|JOBL_UPPER,JOBL_THIRD|JOBL_BABY,JOBL_FOURTH|JOBL_THIRD,JOBL_FOURTH|JOBL_THIRD|JOBL_UPPER})
    for(int upper=0;upper<128;++upper) for(int matched:{0,1}){
        s.class_=job|branch|mode;d.class_upper=upper;
        for(auto& mask:d.class_base)mask=0;
        const int index=branch==JOBL_2_1?1:branch==JOBL_2_2?2:0;
        d.class_base[index]=1ULL<<(matched?job:(job+1)%32);
        assert(description_job_allowed(&s,d)==(pc_job_can_use_item(&s,&d)&&pc_isItemClass(&s,&d)));++tested;
    }
    d={};s={};assert(!description_job_allowed(&s,d));
    s.permission=true;assert(description_job_allowed(&s,d));s.permission=false;
    s.sc.enabled=true;d.equip=EQP_HEAD_TOP;s.status.base_level=89;assert(!description_job_allowed(&s,d));
    s.status.base_level=90;assert(description_job_allowed(&s,d));
    d.equip=EQP_HAND_R;d.type=IT_WEAPON;d.weapon_level=4;s.status.base_level=96;
    for(int type:{W_DAGGER,W_1HSWORD,W_1HAXE,W_2HAXE,W_MACE,W_STAFF,W_2HSTAFF}){d.subtype=type;assert(description_job_allowed(&s,d));}
    d.subtype=W_BOW;assert(!description_job_allowed(&s,d));
    std::cout<<"PASS: "<<tested<<" job/class parity cases, permission and Super Novice exceptions.\\n";
}
'''
    (out/'requirements.cpp').write_text(source,encoding='utf8')
    vc=args.compiler.resolve().parents[3];sdk=Path('C:/Program Files (x86)/Windows Kits/10');ver='10.0.26100.0'
    env=os.environ.copy();env['INCLUDE']=';'.join(str(p) for p in [vc/'include',sdk/'Include'/ver/'ucrt',sdk/'Include'/ver/'shared',sdk/'Include'/ver/'um'])
    env['LIB']=';'.join(str(p) for p in [vc/'lib/x64',sdk/'Lib'/ver/'ucrt/x64',sdk/'Lib'/ver/'um/x64'])
    results={}
    for mode in ['prerenewal','renewal']:
        exe=out/(mode+'.exe');cmd=[str(args.compiler),'/nologo','/std:c++17','/EHsc','/MT','/O2','/DWIN32',f'/I{args.server}/src',str(out/'requirements.cpp'),f'/Fe:{exe}',f'/Fo:{out}/{mode}.obj']
        if mode=='renewal':cmd.append('/DRENEWAL')
        result=subprocess.run(cmd,env=env,capture_output=True,text=True)
        (out/(mode+'-build.log')).write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        result=subprocess.run([str(exe)],capture_output=True,text=True,check=True);results[mode]=result.stdout.strip()
    (out/'verification.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))


if __name__=='__main__':main()
