"""Refresh source pins/action coverage for the planned native second jobs/mounts."""
from pathlib import Path
import json,sys,hashlib,copy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import first_job_hd_sprites as hd
from dual_weapon_formats.grf_reader import GrfFile
OUT=ROOT/'Inputs/HDFirstJobs/second-jobs-mount-plan-20261012.json'

def run():
    old=hd.base.load(ROOT/'Assets/HDFirstJobs/accepted-v1/second-jobs-native-inventory.json');archive=GrfFile(old['source_archive']);rows=[]
    try:
        for before in old['pairs']:
            row=copy.deepcopy(before);spr=archive.read(row['stem']+'.spr');act_raw=archive.read(row['stem']+'.act');act=hd.base.read_act(act_raw)
            assert hashlib.sha256(spr).hexdigest()==row['spr_sha256'] and hashlib.sha256(act_raw).hexdigest()==row['act_sha256'],(row['job'],row['sex'],'native source drift')
            assert len(act.actions)==row['actions'] and sum(map(len,act.actions))==row['frame_uses']
            row['source_hashes_rechecked']=True
            row['action_groups']=[dict(group=i,label=hd.GROUPS[i],actions=list(range(i*8,i*8+8)),frame_counts=[len(fs) for fs in act.actions[i*8:i*8+8]],ms=[v*25 for v in act.speeds[i*8:i*8+8]]) for i in range(13)]
            rows.append(row)
        aliases=sorted(k for k in archive.entries if '/몸통/' in k and k.endswith('.act') and any(x in k for x in ['페코','마운트','라이딩','riding','mount']))
    finally:archive.close()
    result=dict(status='planning_only',audit_date='2026-10-12',source_archive=old['source_archive'],pairs=rows,mounted_alias_actions=aliases,
        totals={group:dict(sets=sum(r['group']==group for r in rows),frame_uses=sum(r['frame_uses'] for r in rows if r['group']==group),stored_sprites=sum(r['sprites'] for r in rows if r['group']==group),referenced_poses=sum(r['used_sprite_indices'] for r in rows if r['group']==group)) for group in ['2-1','2-2','mount']},
        mount_modes=dict(combat_peco='OPTION_RIDING; pilot with actual mounted body and weapon groups',cosmetic_all_riding='Current server All_Riding has NoAttack and skill checks; combat requires separate explicit client/server implementation'),
        new_artwork_created=False,new_server_or_client_changes=False)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8');print(json.dumps(dict(status='rechecked',sets=len(rows),totals=result['totals'],mount_aliases=aliases),ensure_ascii=True))

if __name__=='__main__':run()
