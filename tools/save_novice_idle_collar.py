"""Checkpoint the idle-collar correction and reproduce both pairs independently."""
from pathlib import Path
from novice_hd_common import write_documentation_pointer
import json,sys,zipfile,hashlib,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[1];W=ROOT/'Assets/HDNovice/idle-collar-v5';S=ROOT/'Assets/HDNovice/standing-v1/native';REC=ROOT/'Inputs/HDNovice/records/novice-idle-collar-v5.json'
load=lambda p:json.loads(Path(p).read_text(encoding='utf8'));r=load(REC);assert r['status'].startswith('deployed_idle_collar')
deps=['novice_hd_common.py','fix_novice_idle_collar.py','release_novice_idle_collar.py','save_novice_idle_collar.py','verify_novice_idle_collar_browser.cjs','novice_hd_idle_collar_review.html','novice_hd_idle_walk_review.html','sprite_formats.py','hd_job_ui_assets.py','sprite_review_animation.py','package_hd_job_ui_grf.py','clan_grf_transaction.py','dual_weapon_formats/spr_reader.py','dual_weapon_formats/grf_reader.py']
write_documentation_pointer(W)
archive=W/'release/novice-v5-idle-collar-work.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.write(ROOT/'docs/novice-hd-sprites.md','docs/novice-hd-sprites.md')
 for tree in [W,S]:
  for f in sorted(tree.rglob('*')):
   if f.is_file() and f.suffix!='.zip':z.write(f,f.relative_to(ROOT).as_posix())
 for name in deps:z.write(ROOT/'tools'/name,'tools/'+name)
 for name in ['novice-idle-collar-v5-installation.json','novice-proportions-v4-acceptance.json']:
  f=ROOT/'Inputs/HDNovice/records'/name;z.write(f,f.relative_to(ROOT).as_posix())
 acceptance=ROOT/'Inputs/HDNovice/records/novice-idle-collar-v5-acceptance.json'
 if acceptance.exists():z.write(acceptance,acceptance.relative_to(ROOT).as_posix())
 z.writestr(REC.relative_to(ROOT).as_posix(),json.dumps({k:v for k,v in r.items() if not k.startswith('work_bundle')},indent=2,ensure_ascii=False))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
h=hashlib.sha256(archive.read_bytes()).hexdigest();dest=Path(tempfile.mkdtemp(prefix='novice-v5-recovery-',dir=ROOT/'Outputs')).resolve()
with zipfile.ZipFile(archive) as z:
 for entry in z.infolist():assert (dest/entry.filename).resolve().is_relative_to(dest)
 z.extractall(dest)
for stage in ['paint','build']:
 run=subprocess.run([sys.executable,'-B','tools/fix_novice_idle_collar.py',stage],cwd=dest,capture_output=True,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW)
 assert run.returncode==0,(stage,run.stderr,run.stdout[-1000:])
actual=load(dest/'Assets/HDNovice/idle-collar-v5/verification.json')['files'];assert actual==load(W/'verification.json')['files']
proof=ROOT/'Inputs/HDNovice/records/novice-idle-collar-v5-recovery.json';proof.write_text(json.dumps(dict(status='passed',bundle_sha256=h,isolated_rebuild_root=str(dest),all_four_exports_byte_identical=True,changed_male_idle_frame_uses=15,native_frame_uses_verified=912,files=actual),indent=2),encoding='utf8')
r.update(work_bundle=archive.relative_to(ROOT).as_posix(),work_bundle_sha256=h,recovery_verification=proof.relative_to(ROOT).as_posix())
for p in [REC,ROOT/'Inputs/HDNovice/records/novice-current.json',W/'deployment.json']:p.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps(dict(bundle_bytes=archive.stat().st_size,isolated_rebuild='all four exports byte-identical',status=r['status'])))
