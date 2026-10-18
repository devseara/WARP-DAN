"""V16 full female Mage live-test release using existing GRF transaction/signing."""
from pathlib import Path
import sys,subprocess,json,hashlib
import hd_sprite_release as r
r.WORK=r.ROOT/'Assets/HDFirstJobs/animation-audit-v1/female-mage-grounded-preparation-v16'
r.RELEASE=r.ROOT/'Assets/HDFirstJobs/releases/female-mage-grounded-v16-20261012'
r.RESOURCE_RECORD=r.ROOT/'Inputs/HDFirstJobs/female-mage-grounded-v16.json'
r.INSTALLATION_RECORD=r.ROOT/'Inputs/HDFirstJobs/female-mage-grounded-v16-installation.json'
r.PATCH_FILENAME='female-mage-grounded-v16.grf'
def closed():
 p=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name '*Ragexe*','*roid*','*GRF*' -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,creationflags=0x08000000)
 assert p.returncode==0 and p.stdout.strip()=='0','Close client/GRF Editor before installation'
def prepare():
 closed();v=r.hd.base.load(r.WORK/'verification.json');assert v['both_soles_exact_native_rows'] and v['all_456_export_reopened_rasters_exact'];files=[dict(path='candidate/mage-female'+e,sha256=r.sha((r.WORK/('candidate/mage-female'+e)).read_bytes())) for e in ['.spr','.act']];r.save(r.RESOURCE_RECORD,dict(status='live_test_authorized',files=files,installed=False,deployment_authorized=True,known_issue='Melee3 first-frame detached residue A88/A89/A94/A95 remains'))
 r.inspect();r.prepare();p=r.RELEASE/'release.json';j=r.hd.base.load(p);j.update(acceptance_basis='User: install on grf for live testing. V14 design/preparation accepted, V16 boot correction authorized for live test.',deployment_authorized=True,live_acceptance_pending=True,known_issue='Melee3 first-frame detached residue in four frames');r.save(p,j)
def install():closed();r.install()
def verify():
 report=r.hd.base.load(r.RELEASE/'release.json');assert report['installed'];expected=r.desired();a=r.GrfFile(r.GAME/'maindata.grf');discovery=r.hd.base.load(r.RELEASE/'archive-discovery.json');preserved=0
 try:
  for name,raw in expected.items():assert a.read(name)==raw
  for row in discovery['body_resources']:
   if row['archive']=='maindata.grf' and row['entry'] not in expected:assert r.sha(a.read(row['entry']))==row['sha256'];preserved+=1
 finally:a.close()
 sig=r.verify_signature();rescan=r.RELEASE/'asset-manifest-independent.txt';p=subprocess.run([sys.executable,str(r.SERVER/'tools/riftlock_assets.py'),'--game-root',str(r.GAME),'--client-exe',str(r.GAME/r.CLIENT),'--output',str(rescan)],capture_output=True,text=True,creationflags=0x08000000);(r.RELEASE/'asset-rescan.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf-8');assert p.returncode==0;assert rescan.read_bytes()==(r.GAME/'riftlock-assets-v1.txt').read_bytes()
 act=r.hd.base.read_act(expected[r.STEM+'.act']);assert len(act.actions)==104 and sum(map(len,act.actions))==456
 result=dict(status='installed_verified_live_test_pending',resources=2,other_hd_resources_preserved=preserved,actions=104,frames=456,signature_verified=True,independent_manifest_match=True,installed=True,live_client_tested=False,files={k:r.sha(v) for k,v in expected.items()},backup=str(r.RELEASE/'maindata.grf.before'),known_issue='Melee3 detached residue A88/A89/A94/A95 F0 remains');r.save(r.RELEASE/'installed-verification.json',result);print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':
 for stage in sys.argv[1:]:globals()[stage]()
