"""Exercise real WARP exports and rejection gates in an isolated fixture."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import tempfile
import pefile
from build_native_act_job_ui import ROOT, ORIGINAL, OUT


def fixture_at(out):
    fixture=out/'fixture';fixture.mkdir()
    for name in ('win32','Scripts','Tables','Patches','Inputs','Languages','Styles','Images'):
        if (ROOT/name).exists():
            shutil.copytree(ROOT/name,fixture/name,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'Patches.yml',fixture/'Patches.yml')
    (fixture/'Assets').mkdir()
    # Premium metadata is optional in this checkout; no preview assets are needed.
    premium=fixture/'Patches/Premium.yml'
    if not premium.exists():
        premium.write_text('{}\n')
    return fixture


def export(fixture,folder,source,patches,expect_error=None):
    folder.mkdir();target=folder/'client.exe';profile=folder/'profile.yml'
    profile.write_text('from: '+json.dumps(str(source.resolve()))+'\nto: '+json.dumps(str(target.resolve()))+
                       '\ninputs: {"$skillTreeRepaintFloor": {"data": "363030206d7300", "display": "600 ms", "type": 10}}\npatches:\n'+''.join('    - '+p+'\n' for p in patches))
    run=subprocess.run([str(fixture/'win32/WARP_console.exe'),'-using',str(profile)],cwd=fixture,
                       capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    log=run.stdout+run.stderr;(folder/'warp.log').write_bytes(log)
    if expect_error:
        assert expect_error.encode() in log,log.decode(errors='replace')[-5000:]
        if target.exists():
            a,b=pefile.PE(str(source)),pefile.PE(str(target))
            for va,n in [(0x8b3557,7),(0x974e9e,6),(0x7acef9,5)]:
                assert a.get_data(va-0x400000,n)==b.get_data(va-0x400000,n)
    else:
        assert run.returncode==0 and b'-E-' not in log and target.exists(),log.decode(errors='replace')[-5000:]
    return target


def verify(source,target,only_native=True,extra_writes=(),extra_allocations=()):
    a,b=pefile.PE(str(source)),pefile.PE(str(target));blob=json.loads((OUT/'blob.json').read_text())
    assert b.get_data(0x8b3557-0x400000,7).hex()=='6a01e8c292efff'
    patch=b.get_data(0x974e9e-0x400000,6);assert patch[0]==0xe9 and patch[5]==0x90
    entry=0x974e9e+5+struct.unpack_from('<i',patch,1)[0];payload=entry-blob['exports']['NativeActSkillBridge']
    expected=bytearray.fromhex(blob['hex'])
    for off in blob['relocations']:
        struct.pack_into('<I',expected,off,(struct.unpack_from('<I',expected,off)[0]+payload-blob['imageBase'])&0xffffffff)
    assert bytes(expected)==b.get_data(payload-0x400000,len(expected))
    eq=b.get_data(0x7acef9-0x400000,5);assert eq[0]==0xe8
    assert 0x7acefe+struct.unpack_from('<i',eq,1)[0]==payload+blob['exports']['@NativeActEquipmentDraw@52']
    text=(ROOT/'Scripts/Patches/NativeActJobPreviews.qjs').read_text()
    calls=json.loads(re.search(r'NativeActJobPreviews.calls = (\[.*?\]);',text).group(1))
    for row in calls:assert b.get_data(row['va']-0x400000,5).hex()==row['stock'],'UI preview route remains active'
    allowed={0x8b3558,*range(0x974e9e,0x974ea4),*range(0x7acef9,0x7acefe)}
    allowed.update(row['va']+i for row in calls for i in range(5))
    for va,n in extra_writes:allowed.update(range(va,va+n))
    changed=[]
    if only_native:
        for s in a.sections:
            if not s.Characteristics&0x20000000:continue
            raw=s.get_data();after=b.get_data(s.VirtualAddress,len(raw))
            for i,(v,w) in enumerate(zip(raw,after)):
                if v==w:continue
                va=0x400000+s.VirtualAddress+i
                assert va in allowed or payload<=va<payload+len(expected) or any(p<=va<p+n for p,n in extra_allocations),hex(va)
                changed.append(hex(va))
        old=a.get_data(payload-0x400000,len(expected)) if a.get_section_by_rva(payload-0x400000) else b''
        assert not any(old),'Payload overlaps existing bytes'
    return dict(target=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                payload=hex(payload),existing_code_changes=changed)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--clan-client',type=Path,help='Also verify the recorded prepatched v11 client')
    ap.add_argument('--clan-patch',action='store_true',help='Also verify both orders with the optional local ClanBodySkins patch')
    args=ap.parse_args();out=Path(tempfile.mkdtemp(prefix='native-act-warp-',dir=ROOT/'Outputs'))
    fixture=fixture_at(out);rows=[]
    cases=[('stock',ORIGINAL,['NativeActJobPreviews']),
           ('repaint-first',ORIGINAL,['ReduceExpensiveUIRender','NativeActJobPreviews']),
           ('preview-first',ORIGINAL,['NativeActJobPreviews','ReduceExpensiveUIRender'])]
    if args.clan_client:
        cases.append(('v11',args.clan_client,['NativeActJobPreviews']))
    if args.clan_patch:
        if not (ROOT/'Scripts/Patches/ClanBodySkins.qjs').exists():
            ap.error('--clan-patch requires the optional ClanBodySkins implementation')
        cases.extend([('clan-first',ORIGINAL,['ClanBodySkins','NativeActJobPreviews']),
                      ('native-first',ORIGINAL,['NativeActJobPreviews','ClanBodySkins'])])
    for label,source,patches in cases:
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        target=export(fixture,out/label,source,patches)
        row=verify(source,target,label in ('stock','v11'));row['case']=label;rows.append(row)
        if label in ('repaint-first','preview-first'):
            assert pefile.PE(str(target)).get_dword_at_rva(0x103f6b0-0x400000)!=0x977e80,'Repaint gate was not installed'
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        print('PASS '+label,flush=True)
    for label,address in [('bad-renderer',0xa1b851),('bad-resource-loader',0x974b56)]:
        bad=out/(label+'.exe');raw=bytearray(ORIGINAL.read_bytes());pe=pefile.PE(data=bytes(raw))
        raw[pe.get_offset_from_rva(address-0x400000)]^=1;bad.write_bytes(raw)
        export(fixture,out/label,bad,['NativeActJobPreviews'],
               'UI resource calls are neither stock' if label=='bad-resource-loader' else 'native bytes differ')
        rows.append(dict(case=label,rejected_before_hook_writes=True));print('PASS '+label,flush=True)
    patch=fixture/'Scripts/Patches/NativeActJobPreviews.qjs';saved=patch.read_bytes()
    try:
        patch.write_bytes(saved+b'\r\nNativeActJobPreviews.blob.relocations = [0x7fffffff];\r\n')
        export(fixture,out/'bad-relocation',ORIGINAL,['NativeActJobPreviews'],'invalid payload relocation')
    finally:
        patch.write_bytes(saved)
    rows.append(dict(case='bad-relocation',rejected_before_hook_writes=True));print('PASS bad-relocation',flush=True)
    # WARP restores original bytes when reopening its own output.
    again=export(fixture,out/'reapply',out/'stock/client.exe',['NativeActJobPreviews'])
    rows.append(dict(case='safe-reapply',**verify(ORIGINAL,again)));print('PASS safe-reapply',flush=True)
    (out/'results.json').write_text(json.dumps(rows,indent=2));print('PASS '+str(out),flush=True)


if __name__=='__main__':main()
