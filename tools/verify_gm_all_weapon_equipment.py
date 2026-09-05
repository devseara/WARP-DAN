"""Compile the actual baseline/candidate equip-point and slot-selection source.
This verifies a staged server change; it never modifies or launches the server.
"""
from pathlib import Path
import subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Outputs/gm_all_weapons_20260905'
def block(s,start):
    opening=s.index('{',start);depth=1;i=opening+1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[start:i]
def function(s):
    return block(s,s.index('int32 pc_equippoint_sub('))
def selector(s):
    start=s.index('if(pos == EQP_ARMS &&')
    return block(s,start)
old=(OUT/'before_src_map_pc.cpp').read_text(encoding='utf-8')
new=(OUT/'pc.cpp').read_text(encoding='utf-8')
header=r"""
#include <cstdio>
#include <cstdlib>
using int32=int;
const int IT_WEAPON=1,IT_ARMOR=2,IT_AMMO=3,IT_SHADOW=4;
const int EQP_HAND_R=2,EQP_HAND_L=32,EQP_WEAPON=2,EQP_ARMS=34,EQP_HEAD_TOP=256;
const int EQP_SHADOW_WEAPON=131072,EQP_SHADOW_ARMS=393216;
const int EQI_HAND_R=0,EQI_HAND_L=1;
const int W_DAGGER=1,W_1HSWORD=2,W_1HAXE=6;
const int AS_LEFT=1,MAPID_SECONDMASK=255,MAPID_ASSASSIN=12,MAPID_KAGEROUOBORO=29;
const int PC_PERM_USE_ALL_EQUIPMENT=3;
struct map_session_data { bool permission;int class_;int skill; };
struct item_data {int type,subtype,equip;};
bool itemdb_isequip2(const item_data* id){return id->type==IT_WEAPON||id->type==IT_ARMOR||id->type==IT_SHADOW;}
bool pc_has_permission(const map_session_data* sd,int){return sd->permission;}
int pc_checkskill(const map_session_data* sd,int){return sd->skill;}
#define nullpo_ret(p) if(!(p)) return 0
"""
cpp=header+function(old).replace('pc_equippoint_sub','baseline_equippoint')+'\n'+function(new)+'\n'
for name,source in [('baseline_select',old),('candidate_select',new)]:
    cpp+='int '+name+'(const map_session_data* sd,const item_data* id,int pos,int req_pos,int* equip_index){\n(void)sd;\n'+selector(source)+'\nreturn pos;\n}\n'
cpp+=r"""
int checks=0;
void require(bool good){++checks;if(!good){std::fprintf(stderr,"check %d failed\n",checks);std::exit(1);}}
int main(){
 const int masks[]={EQP_HAND_R,EQP_HAND_L,EQP_ARMS,EQP_SHADOW_WEAPON,EQP_HEAD_TOP,0};
 const int requests[]={EQP_HAND_R,EQP_HAND_L,EQP_ARMS};
 const int jobs[]={0,MAPID_ASSASSIN,MAPID_KAGEROUOBORO};
 for(int kind=IT_WEAPON;kind<=IT_SHADOW;++kind)
 for(int weapon=1;weapon<=23;++weapon)
 for(int mask:masks)
 for(int job:jobs)
 for(int skill=0;skill<=1;++skill){
  map_session_data sd={false,job,skill};item_data id={kind,weapon,mask};
  int base=baseline_equippoint(&sd,&id),actual=pc_equippoint_sub(&sd,&id);
  require(actual==base);
  for(int permission=0;permission<=1;++permission){
   sd.permission=permission!=0;
   base=baseline_equippoint(&sd,&id);actual=pc_equippoint_sub(&sd,&id);
   bool gm_weapon=permission&&kind==IT_WEAPON&&(mask&EQP_ARMS);
   require(actual==(gm_weapon?EQP_ARMS:base));
   for(int req:requests)
   for(int right=0;right<=1;++right)
   for(int left=0;left<=1;++left){
    int occupied[]={right?7:-1,left?8:-1};
    int chosen=candidate_select(&sd,&id,actual,req,occupied);
    if(gm_weapon){
     int expected=req;
     if(req==EQP_ARMS){
#ifdef RENEWAL
      expected=right&&!left?EQP_HAND_L:EQP_HAND_R;
#else
      expected=right?EQP_HAND_L:EQP_HAND_R;
#endif
     }
     require(chosen==expected);
     require(chosen==EQP_HAND_R||chosen==EQP_HAND_L);
    }else{
     require(chosen==baseline_select(&sd,&id,base,req,occupied));
    }
   }
  }
 }
 require(pc_equippoint_sub(nullptr,nullptr)==0);
 std::printf("%d compiled source checks passed\n",checks);
}
"""
(OUT/'equipment_matrix.cpp').write_text(cpp,encoding='utf-8')
vs=Path(r'C:/Program Files/Microsoft Visual Studio/18/Community/Common7/Tools/VsDevCmd.bat')
cmd=['@echo off','call "'+str(vs)+'" -arch=x64 -host_arch=x64 >nul','if errorlevel 1 exit /b %errorlevel%']
for mode in ['renewal','classic']:
    exe=OUT/('equipment_matrix_'+mode+'.exe')
    cmd+=['cl.exe /nologo /std:c++17 /W4 /WX /O2 /EHsc '+('/DRENEWAL ' if mode=='renewal' else '')+'/Fo"'+str(OUT/('equipment_matrix_'+mode+'.obj'))+'" /Fe"'+str(exe)+'" "'+str(OUT/'equipment_matrix.cpp')+'"','if errorlevel 1 exit /b %errorlevel%','"'+str(exe)+'"','if errorlevel 1 exit /b %errorlevel%']
(OUT/'verify-equipment.cmd').write_bytes(('\r\n'.join(cmd)+'\r\n').encode())
run=subprocess.run(['cmd.exe','/d','/c',str(OUT/'verify-equipment.cmd')],capture_output=True,text=True)
(OUT/'equipment_matrix.log').write_text(run.stdout+run.stderr)
print(run.stdout+run.stderr,end='');run.check_returncode()
report={'passed':True,'modes':['renewal','classic'],'weapon_classes':23,'input_masks':['right','left','both','shadow','head','none'],'source':'actual functions/branches extracted from baseline and staged pc.cpp','candidate_sha256':hashlib.sha256((OUT/'pc.cpp').read_bytes()).hexdigest(),'checks':run.stdout.splitlines()}
(OUT/'equipment_matrix.json').write_text(json.dumps(report,indent=2)+'\n')
