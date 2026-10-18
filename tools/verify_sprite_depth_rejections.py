"""Prove renderer patches reject mismatched clients before changing their hooks."""
from pathlib import Path
import argparse, json
import pefile
from build_native_act_job_ui import ROOT, ORIGINAL
from verify_native_act_job_ui_warp import fixture_at, export

def verify(out,allocation_only=False):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    fixture=fixture_at(out)
    source=ORIGINAL.read_bytes();pe=pefile.PE(data=source)
    rows=[]
    cases=[
        ('bad-emitter',0xC4A5B1,'UniformSpriteRHW','sprite quad emitter differs'),
        ('bad-body',0xC40F7B,'FloorSafeSpriteDepth','actor rect builder differs'),
        ('bad-shadow',0xC49FB3,'FloorSafeSpriteDepth','shadow builder differs'),
        ('bad-player-vtable',0x109481C,'FloorSafeSpriteDepth','unexpected CPlayer vtable'),
    ]
    for name,site,patch,error in ([] if allocation_only else cases):
        raw=bytearray(source);offset=pe.get_offset_from_rva(site-0x400000);raw[offset]^=1
        bad=out/(name+'.exe');bad.write_bytes(raw)
        target=export(fixture,out/name,bad,[patch],expect_error=error)
        if target.exists():
            result=pefile.PE(str(target))
            for va,n in [(0xC4A5B1,5),(0xC40F9F,5),(0xC49FEE,22)]:
                before=pe.get_offset_from_rva(va-0x400000)
                assert result.get_data(va-0x400000,n)==bytes(raw[before:before+n])
        rows.append(dict(case=name,rejected=True,renderer_hook_writes=0))
        print('PASS '+name,flush=True)
    patch=fixture/'Scripts/Patches/FloorSafeSpriteDepth.qjs';saved=patch.read_bytes()
    marker=b'\tconst self = FloorSafeSpriteDepth;';assert saved.count(marker)==1
    try:
        patch.write_bytes(saved.replace(marker,b'\tCACHE.put("CelestialDial.Contract.v3", {runtimeBase: 0x171d000, runtimeSize: 0x1000});\r\n'+marker,1))
        target=export(fixture,out/'owned-runtime-overlap',ORIGINAL,['FloorSafeSpriteDepth'],expect_error='allocation overlaps existing weather runtime')
        if target.exists():
            result=pefile.PE(str(target))
            for va,n in [(0xC4A5B1,5),(0xC40F9F,5),(0xC49FEE,22)]:
                assert result.get_data(va-0x400000,n)==pe.get_data(va-0x400000,n)
        rows.append(dict(case='owned-runtime-overlap',rejected=True,renderer_hook_writes=0));print('PASS owned-runtime-overlap',flush=True)
    finally:patch.write_bytes(saved)
    (out/'verification.json').write_text(json.dumps(dict(cases=rows,status='pass'),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=ROOT/'Outputs/sprite-depth-main-20261018/rejection-gates')
    p.add_argument('--allocation-only',action='store_true')
    a=p.parse_args();verify(a.out,a.allocation_only)
