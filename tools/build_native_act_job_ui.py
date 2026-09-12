"""Compile and embed the static native ACT UI bridge; no generated sprite pack."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import pefile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/native/native_act_job_ui.cpp'
TEMPLATE = ROOT / 'tools/native/native_act_job_ui.qjs.in'
TARGET = ROOT / 'Scripts/Patches/NativeActJobPreviews.qjs'
ORIGINAL = ROOT / '2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe'
TOOL_DIR = Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x86')
REFERENCE = 'ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff'
OUT = ROOT / 'Outputs/native-act-job-ui/native'


def build(compiler=TOOL_DIR / 'cl.exe', original=ORIGINAL, check=False):
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE:
        raise ValueError('Expected the recorded original 2025-07-16 reference')
    client = pefile.PE(data=raw)
    OUT.mkdir(parents=True, exist_ok=True)
    obj, exe = OUT / 'native-act.obj', OUT / 'native-act.exe'
    for args in [
        [str(compiler), '/nologo', '/c', '/O2', '/Oi', '/GS-', '/GR-', '/Zl', '/W4', '/WX',
         '/EHs-c-', '/arch:SSE2', '/Fo' + str(obj), str(SOURCE)],
        [str(compiler.parent / 'link.exe'), '/nologo', '/nodefaultlib', '/machine:x86', '/safeseh:no',
         '/entry:NativeActSkillBridge', '/subsystem:windows', '/base:0x10000000', '/fixed:no',
         '/dynamicbase', '/opt:ref', '/incremental:no', '/brepro', '/out:' + str(exe), str(obj)],
    ]:
        subprocess.run(args, check=True, cwd=OUT)
    pe = pefile.PE(str(exe))
    assert not getattr(pe, 'DIRECTORY_ENTRY_IMPORT', None)
    sections = [s for s in pe.sections if not s.Name.startswith(b'.reloc')]
    start, end = min(s.VirtualAddress for s in sections), max(s.VirtualAddress+s.Misc_VirtualSize for s in sections)
    blob = bytearray(end-start)
    for s in sections:
        data = s.get_data()[:s.Misc_VirtualSize]
        blob[s.VirtualAddress-start:s.VirtualAddress-start+len(data)] = data
    # Export/debug directory names and linker timestamps are not runtime data.
    for directory in [pe.OPTIONAL_HEADER.DATA_DIRECTORY[0], pe.OPTIONAL_HEADER.DATA_DIRECTORY[6]]:
        if directory.Size:
            lo, hi = directory.VirtualAddress-start, directory.VirtualAddress-start+directory.Size
            assert 0 <= lo <= hi <= len(blob)
            blob[lo:hi] = bytes(hi-lo)
    relocs = []
    for block in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
        for r in block.entries:
            if not r.type:
                continue
            assert r.type == 3 and start <= r.rva < end
            off = r.rva-start
            value = struct.unpack_from('<I', blob, off)[0]
            assert pe.OPTIONAL_HEADER.ImageBase+start <= value < pe.OPTIONAL_HEADER.ImageBase+end
            relocs.append(off)
    info = dict(imageBase=pe.OPTIONAL_HEADER.ImageBase+start, hex=blob.hex(), relocations=relocs,
                exports={s.name.decode():s.address-start for s in pe.DIRECTORY_ENTRY_EXPORT.symbols},
                source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    checks = [dict(va=va, hex=client.get_data(va-0x400000, n).hex()) for va,n in [
        (0x8b3557,7), (0x7acdd5,12), (0x7ace60,0x9e), (0x7adbc0,0x185),
        (0xa1b7c0,0x4f9), (0x974700,0x40), (0x974e0f,0x158),
        (0xfd5ce4,0x44), (0x53c6a0,0xad), (0x53cfc0,0x40), (0x566b70,16), (0x5663d0,16),
    ]]
    calls = []
    for sites, old in [([0x7acd71,0x7acdb1,0x7aec6b,0x7aed3f],0x1967c30),
                       ([0x974b20,0x974b56,0x974b76,0x974d35,0x974e04],0x1967bf0)]:
        for va in sites:
            calls.append(dict(va=va,stock=client.get_data(va-0x400000,5).hex(),clan=(b'\xe8'+struct.pack('<i',old-va-5)).hex()))
    legacy = [dict(va=0x1967bf0,hex='81ec800100008d04245750ffb4248c0100008bf9'),
              dict(va=0x1967c30,hex='81ec800100008d84248401000083bc249801000010')]
    text = TEMPLATE.read_text(encoding='utf-8')
    for key,value in [('blob',info),('checks',checks),('calls',calls),('legacyChecks',legacy)]:
        text += '\nNativeActJobPreviews.'+key+' = '+json.dumps(value,separators=(',',':'))+';\n'
    data = text.replace('\r\n','\n').replace('\n','\r\n').encode('utf-8')
    if check:
        assert TARGET.read_bytes() == data, 'Generated QJS is stale'
    else:
        TARGET.write_bytes(data)
    (OUT/'blob.json').write_text(json.dumps(info,indent=2))
    print(json.dumps(dict(bytes=len(blob),relocations=len(relocs),exports=info['exports'],check=check)))
    return info


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compiler', type=Path, default=TOOL_DIR/'cl.exe')
    ap.add_argument('--profile-client', type=Path, default=ORIGINAL)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    build(args.compiler,args.profile_client,args.check)
