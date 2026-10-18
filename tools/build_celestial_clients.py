"""Build isolated Celestial dial WARP fixtures without changing installed clients."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes')
ORIGINAL = ROOT/'2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe'

def fixture(path, runtime_inputs=None):
    path.mkdir(parents=True, exist_ok=True)
    for name in ('win32', 'Scripts', 'Tables', 'Patches', 'Languages', 'Styles'):
        shutil.copytree(ROOT/name, path/name, dirs_exist_ok=True)
    shutil.copy2(ROOT/'Patches.yml', path/'Patches.yml')
    shutil.copytree(ROOT/'Inputs/CelestialDial', path/'Inputs/CelestialDial', dirs_exist_ok=True)
    if runtime_inputs:
        for name in ('runtime.bin', 'runtime.json'):
            shutil.copy2(runtime_inputs/name, path/'Inputs/CelestialDial'/name)
    # Both monster HUD skins are packaged from their actual resource roots.
    for name in ('Assets/GachaUI','Assets/BattlepassUI','Assets/ROGlobalZeroMenu','Inputs/AutoUI','Inputs/BattlepassUI'):
        if (ROOT/name).is_dir():
            shutil.copytree(ROOT/name, path/name, dirs_exist_ok=True)
    for filename in ('assets.json', 'assets-wings-and-stars.json'):
        manifest = json.loads((ROOT/'Assets/TargetMonsterHUD'/filename).read_text(encoding='utf8'))
        relative = manifest['resource_root']
        source = ROOT/relative if (ROOT/relative).is_dir() else GAME/relative
        shutil.copytree(source, path/relative, dirs_exist_ok=True)
    return path

def build(fx, output, patches, source=ORIGINAL, inputs=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = output.with_suffix('.yml')
    profile.write_text('from: '+json.dumps(source.as_posix())+'\nto: '+json.dumps(output.as_posix())+
        '\ninputs: '+(json.dumps(inputs) if inputs else '{}')+'\npatches:\n'+''.join('    - '+p+'\n' for p in patches), encoding='utf8')
    result = subprocess.run([str(fx/'win32/WARP_console.exe'), '-using', str(profile)], cwd=fx,
                            capture_output=True, timeout=180)
    output.with_suffix('.log').write_bytes(result.stdout+result.stderr)
    if result.returncode or b'-E-' in result.stdout+result.stderr or not output.is_file():
        raise RuntimeError((result.stdout+result.stderr).decode(errors='replace')[-4500:])
    print(output)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT/'Outputs/CelestialDial/clients')
    ap.add_argument('--runtime-inputs', type=Path, help='Use a staged payload for isolated fixtures')
    args=ap.parse_args()
    out=args.output.resolve();fx=fixture(out/'fixture',args.runtime_inputs)
    cases={'standalone':['CelestialDial'], 'monster-first':['TargetMonsterHealthBar','CelestialDial'],
           'dial-first':['CelestialDial','TargetMonsterHealthBar'],
           'framed-peers':['BattlepassUI','GachaUI','CelestialDial'],
           'framed-reverse':['CelestialDial','GachaUI','BattlepassUI']}
    for name,patches in cases.items():
        build(fx,out/(name+'.exe'),patches)

if __name__=='__main__':
    main()
