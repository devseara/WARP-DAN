#!/usr/bin/env python3
"""Run the maintained Main20250716 canonical-name native regression suite.

Each suite executes the final PE, stubbing documented external services. This
gate does not claim live game rendering or authorize deployment/database changes.
"""
import argparse,json,subprocess,sys,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--pe',type=Path,required=True);ap.add_argument('--deps',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
root=Path(__file__).resolve().parent;args.output.mkdir(parents=True,exist_ok=True)
suites=['verify_extname_cache_pe.py','verify_extname_party_pe.py',
 'verify_character_create_actions_pe.py','verify_character_create_callback_pe.py',
 'verify_extname_companion_pe.py','verify_extname_companion_rename_pe.py',
 'verify_extname_npc_pe.py','verify_extname_social_reuse_pe.py',
 'verify_extname_mail_pe.py','verify_extname_quest_pe.py',
 'verify_extname_star_pe.py','verify_extname_battleground_pe.py',
 'verify_extname_guild_log_pe.py','verify_extname_boss_tracker_pe.py',
 'verify_auxiliary_identity_pe.py','verify_name_eh_frames_pe.py','verify_legacy_creation_enter_pe.py']
result={'pe':str(args.pe.resolve()),'sha256':hashlib.sha256(args.pe.read_bytes()).hexdigest(),'suites':[]}
for suite in suites:
 command=[sys.executable,str(root/suite)]
 command+=([str(args.pe)] if suite=='verify_extname_cache_pe.py' else ['--pe',str(args.pe)])
 command+=['--deps',str(args.deps)]
 p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
 log=args.output/(Path(suite).stem+'.log');log.write_text(p.stdout+p.stderr,encoding='utf-8')
 row={'suite':suite,'passed':p.returncode==0,'returncode':p.returncode,'log':str(log.resolve())};result['suites'].append(row)
 print(('PASS ' if row['passed'] else 'FAIL ')+suite,flush=True)
 if p.returncode:print((p.stdout+p.stderr)[-5000:],flush=True)
result['passed']=all(row['passed'] for row in result['suites'])
(args.output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(f'PASS all{len(suites)} canonical-name suites' if result['passed'] else 'FAIL canonical-name aggregate',flush=True)
raise SystemExit(0 if result['passed'] else 1)
