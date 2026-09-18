"""Run existing native behavior suites against the staged VIP renderer/skin."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('exe',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--game',type=Path,help='Optional local game folder for actual item BMPs')
    ap.add_argument('--only',nargs='+',help='Rerun only failed suites after fixing a fixture dependency')
    args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    names=('ui','visibility','quest_ui','tickets','first_quest','quest_items','buffs',
           'purchase','membership_cards','button_pngs','membership_buttons',
           'open_order','portrait','upgrade_effect','benefit_boxes','submit_confirmation','compact',
           'upgrade_race','benefit_hover','timer_visibility')
    if args.only:
        assert set(args.only)<=set(names)
        names=tuple(args.only)
    def run(name):
        command=[sys.executable,'-u',str(ROOT/'tools'/f'test_vip_{name}.py'),str(args.exe.resolve())]
        if name not in ('button_pngs','membership_buttons','open_order','portrait','upgrade_effect'):
            command+=['--output',str(out/name)]
        if args.game and name in ('quest_ui','tickets','quest_items'):
            command+=['--game',str(args.game.resolve())]
        try:
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=480)
            (out/(name+'.log')).write_bytes(result.stdout+result.stderr)
            code=result.returncode
        except subprocess.TimeoutExpired as error:
            (out/(name+'.log')).write_bytes((error.stdout or b'')+(error.stderr or b'')+b'\nTIMEOUT\n')
            code=124
        print(('PASS' if not code else 'FAIL')+' '+name,flush=True)
        return name,code
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=dict(pool.map(run,names))
    previous=json.loads((out/'results.json').read_text()) if (out/'results.json').is_file() else {}
    previous.update(results)
    (out/'results.json').write_text(json.dumps(previous,indent=2)+'\n')
    return int(any(results.values()))

if __name__=='__main__':sys.exit(main())
