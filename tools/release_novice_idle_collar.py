"""Guarded male-only GRF deployment of the idle-collar correction."""
from pathlib import Path
import sys,json,configparser,re,struct
import pefile
import novice_hd_common as b
from clan_grf_transaction import replace_records,digest
from dual_weapon_formats.grf_reader import GrfFile
from package_hd_job_ui_grf import write_grf
ROOT=b.ROOT;WORK=ROOT/'Assets/HDNovice/idle-collar-v5';GAME=Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes')
CLIENT=GAME/'2025-07-16_Ragexe_175220998_clientinfo_patched.exe'
RECORD=ROOT/'Inputs/HDNovice/records/novice-idle-collar-v5.json';RECEIPT=ROOT/'Inputs/HDNovice/records/novice-idle-collar-v5-installation.json'

def client_check():
 p=CLIENT
 assert p.parent.resolve()==GAME.resolve()
 q=(ROOT/'Scripts/Patches/NativeActJobPreviews.qjs').read_text(encoding='utf8');blob=json.loads(re.search(r'NativeActJobPreviews.blob = (\{.*?\});',q,re.S).group(1));pe=pefile.PE(str(p));ib=pe.OPTIONAL_HEADER.ImageBase
 read=lambda va,n:pe.get_data(va-ib,n)
 patch=read(0x974e9e,6);assert patch[0]==0xe9 and patch[5]==0x90
 payload=0x974e9e+5+struct.unpack_from('<i',patch,1)[0]-blob['exports']['NativeActSkillBridge'];expected=bytearray.fromhex(blob['hex'])
 for off in blob['relocations']:struct.pack_into('<I',expected,off,(struct.unpack_from('<I',expected,off)[0]+payload-blob['imageBase'])&0xffffffff)
 assert read(payload,len(expected))==expected
 assert read(0x8b3557,7).hex()=='6a01e8c292efff'
 eq=read(0x7acef9,5);assert eq[0]==0xe8 and 0x7acefe+struct.unpack_from('<i',eq,1)[0]==payload+blob['exports']['@NativeActEquipmentDraw@52']
 return dict(path=str(p),sha256=b.sha(p.read_bytes()),native_preview_payload_verified=True)


def retain_matching_acceptance(record):
 # Approval belongs to exact exported resources, never merely to a version label.
 record['user_visual_acceptance']=False
 record.pop('acceptance_record',None)
 path=ROOT/'Inputs/HDNovice/records/novice-idle-collar-v5-acceptance.json'
 if path.exists():
  approved=b.load(path)
  expected={r['entry']:r['sha256'] for r in approved['resources']}
  actual={r['entry']:r['sha256'] for r in record['resources']}
  if approved.get('user_visual_acceptance') and actual==expected:
   record['user_visual_acceptance']=True
   record['acceptance_record']=path.relative_to(ROOT).as_posix()
 record['documentation']='docs/novice-hd-sprites.md'
 return record


def payloads():
 v=b.load(WORK/'verification.json');qa=b.load(WORK/'visual-review.json');corrections=b.load(WORK/'collar-corrections.json')
 assert qa['status']=='offline_review_passed' and qa['reviewed_files']==v['files']
 assert v['walking_combat_and_female_unchanged'] and v['native_head_anchors_preserved']==912
 assert [(r['sex'],r['changed_frames'],r['unchanged_frames']) for r in v['coverage']]==[('male',15,441),('female',0,456)]
 for row in corrections:
  assert b.sha((WORK/f"idle/male/{row['direction']}.png").read_bytes())==row['result_sha256']
  if 'source' in row:assert row['horizontal_coordinates_identical'] and row['outside_support_pixels_identical'] and row['below_y80_pixels_identical'] and row['minimum_vertical_jacobian']>.45
 assert all(r['actions']==104 and r['frame_uses']==456 and r['independent_sprite_decode'] for r in v['coverage'])
 allrows={}
 for row in v['files']:
  raw=(WORK/row['path']).read_bytes();assert b.sha(raw)==row['sha256'];sex='남' if row['sex']=='male' else '여';key=f'data/sprite/인간족/몸통/{sex}/초보자_{sex}{Path(row["path"]).suffix}';allrows[key]=raw
  if row['sex']=='female':assert raw==(WORK/f'baseline/female/body{Path(row["path"]).suffix}').read_bytes()
 desired={k:v for k,v in allrows.items() if '/남/' in k};assert len(desired)==2
 return desired,allrows,v

def package():
 desired,allrows,v=payloads();path=WORK/'release/novice-hd-idle-collar-v5.grf';write_grf(allrows,path)
 record=dict(status='verified_idle_collar_correction_ready',version='v5',work=WORK.relative_to(ROOT).as_posix(),reason='Male idle collar was covered by the chin compared with walking; locally lower its registration while retaining the native head and accepted body width.',authorization='User-reported defect correction under ongoing authorized sprite implementation/deployment.',resources=[dict(entry=k,sha256=b.sha(raw),bytes=len(raw)) for k,raw in sorted(allrows.items())],files=v['files'],changed_resources=2,changed_male_frame_uses=15,unchanged_frame_uses=897,affected_idle_directions=[0,1,2,6,7],native_head_anchors_identical=912,full_native_timing_preserved=True,walking_and_combat_pixel_identical=True,female_files_byte_identical_to_v4=True,review='Assets/HDNovice/idle-collar-v5/idle-walk-review.html',all_action_review='Assets/HDNovice/idle-collar-v5/full-action-review.html',pixel_review='Assets/HDNovice/idle-collar-v5/pixel-review.html',distribution=path.relative_to(ROOT).as_posix(),distribution_sha256=digest(path),baseline_acceptance_record='Inputs/HDNovice/records/novice-proportions-v4-acceptance.json',user_visual_acceptance=False,live_client_acceptance=False)
 retain_matching_acceptance(record)
 b.save(RECORD,record);print(json.dumps(dict(package=str(path),resources=4,bytes=path.stat().st_size)))

def deploy():
 desired,allrows,_=payloads();record=b.load(RECORD);exe=client_check();ini=GAME/'DATA.INI';ih=b.sha(ini.read_bytes());config=configparser.ConfigParser();config.read(ini,encoding='utf8');order=[name for _,name in sorted(config.items('Data'),key=lambda r:int(r[0]))];assert order.count('maindata.grf')==1
 for name in order[:order.index('maindata.grf')]:
  path=(GAME/name).resolve();assert path.parent==GAME.resolve();g=GrfFile(path)
  try:assert not(set(g.entries)&set(allrows)),('Higher-priority Novice override',name)
  finally:g.close()
 for name in allrows:assert not (GAME/name).exists(),('Loose override',name)
 target=(GAME/'maindata.grf').resolve();assert target.parent==GAME.resolve();pins={r['entry']:r['sha256'] for r in b.load(WORK/'baseline.json')['baseline']};g=GrfFile(target)
 try:
  for name,raw in allrows.items():assert b.sha(g.read(name)) in (pins[name],b.sha(raw)),('Baseline changed',name)
 finally:g.close()
 receipt=replace_records(target,desired,RECEIPT)
 if receipt['status']=='already_current' and RECEIPT.exists():receipt=b.load(RECEIPT)
 g=GrfFile(target)
 try:
  for name,raw in allrows.items():assert g.read(name)==raw
 finally:g.close()
 assert b.sha(Path(exe['path']).read_bytes())==exe['sha256'] and b.sha(ini.read_bytes())==ih
 record.update(status='deployed_idle_collar_correction_pending_user_visual_confirmation',installed_archive=str(target),installed_sha256=digest(target),installation_receipt=RECEIPT.relative_to(ROOT).as_posix(),unrelated_records_preserved=receipt['unrelated_records_preserved'],client=exe,executable_unchanged=True,data_ini_unchanged=True)
 retain_matching_acceptance(record)
 if record['user_visual_acceptance']:record['status']='deployed_idle_collar_correction_accepted'
 for path in [RECORD,WORK/'deployment.json',ROOT/'Inputs/HDNovice/records/novice-current.json']:b.save(path,record)
 print(json.dumps(dict(status=record['status'],changed_resources=2,unrelated_records_preserved=record['unrelated_records_preserved'],walking_combat_female_unchanged=True)))

if __name__=='__main__':{'package':package,'deploy':deploy}[sys.argv[1]]()
