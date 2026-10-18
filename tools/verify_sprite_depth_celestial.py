"""Export both orders with CelestialDial's registered player-draw owner intact."""
import argparse, json, shutil
from pathlib import Path
from build_native_act_job_ui import ROOT, ORIGINAL
from verify_native_act_job_ui_warp import fixture_at, export
from verify_floor_safe_sprite_depth import emulate, Image

def verify(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    fixture=fixture_at(out)
    shutil.copytree(ROOT/'Assets/AutoCombatUI',fixture/'Assets/AutoCombatUI')
    rows=[]
    for name,patches in [
        ('weather-first',['AutoCombatUI','CelestialDial','UniformSpriteRHW','FloorSafeSpriteDepth']),
        ('depth-first',['UniformSpriteRHW','FloorSafeSpriteDepth','AutoCombatUI','CelestialDial']),
    ]:
        target=export(fixture,out/name,ORIGINAL,patches)
        image=Image(target);result=emulate(target)
        assert image.read(0xC4A5B1,5)==bytes.fromhex('0f1f440000')
        assert image.u32(0x109481C)!=0xD3A220,'Weather draw owner was replaced'
        rows.append(dict(case=name,path=str(target),floor=result,
                         weather_player_draw=hex(image.u32(0x109481C)),uniform_rhw=True))
        print('PASS '+name,flush=True)
    (out/'verification.json').write_text(json.dumps(rows,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    verify(p.parse_args().out)
