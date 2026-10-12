"""Build a relocatable static x86 clan-skin payload with no runtime imports."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,zlib
import pefile
ROOT=Path(__file__).resolve().parents[1]
TOOL_DIR=Path(r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86')
SOURCE=ROOT/'Scripts/Runtime/ClanBodySkins/runtime.cpp'

def build(tool_dir=TOOL_DIR):
    work=ROOT/'Outputs/clan-body-skins/runtime';work.mkdir(parents=True,exist_ok=True)
    obj=work/'runtime.obj';dll=work/'relocation-container.dll'
    commands=[
        [str(tool_dir/'cl.exe'),'/nologo','/c','/TP','/GR-','/O2','/Oi','/GS-','/Zl','/W4','/WX','/Fo'+str(obj),str(SOURCE)],
        [str(tool_dir/'link.exe'),'/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/MACHINE:X86','/DYNAMICBASE:NO','/NXCOMPAT','/OPT:REF','/OPT:ICF','/BREPRO','/OUT:'+str(dll),str(obj)]
    ]
    for args in commands:subprocess.run(args,cwd=work,check=True)
    pe=pefile.PE(str(dll));assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',None)
    sections=[s for s in pe.sections if s.Name.rstrip(b'\0')!=b'.reloc']
    first=min(s.VirtualAddress for s in sections);end=max(s.VirtualAddress+s.Misc_VirtualSize for s in sections)
    code=bytearray(end-first)
    for s in sections:
        d=s.get_data()[:s.Misc_VirtualSize];code[s.VirtualAddress-first:s.VirtualAddress-first+len(d)]=d
    relocs=[]
    for block in getattr(pe,'DIRECTORY_ENTRY_BASERELOC',[]):
        for r in block.entries:
            if not r.type:continue
            assert r.type==3;off=r.rva-first;value=struct.unpack_from('<I',code,off)[0]
            target=value-pe.OPTIONAL_HEADER.ImageBase-first;assert 0<=target<len(code)
            struct.pack_into('<I',code,off,target);relocs.append(off)
    exports={s.name.decode():s.address-first for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    required=['ClanSkinApi','@ClanBodyHook@32','@ClanAlternateBodyHook@32','@ClanBodyMapHook@20','@ClanPaletteHook@20']
    for name in required:assert name in exports,(name,exports)
    body=struct.pack('<'+'I'*len(relocs),*relocs)+code
    header=struct.pack('<8I',0x4e4b5343,1,len(code),len(relocs),exports['ClanSkinApi'],0,0,zlib.crc32(body))
    out=ROOT/'Inputs/ClanBodySkins/runtime.cskb';out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(header+body)
    report={'schema':'clan-body-skins-v2','api_version':2,'api_size':40,'source':str(SOURCE.relative_to(ROOT)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'payload_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'code_size':len(code),'relocations':relocs,'exports':exports,'runtime_imports':[],'native_client':20250716,'compiler':str(tool_dir)}
    out.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    from clan_perspective_bridge import bridge
    perspective,_=bridge(0)
    perspective_path=out.with_name('perspective.bin')
    perspective_path.write_bytes(perspective)
    perspective_meta={'version':1,'client':20250716,'bytes':len(perspective),
                      'crc32':zlib.crc32(perspective),'sha256':hashlib.sha256(perspective).hexdigest(),
                      'source':'tools/clan_perspective_bridge.py',
                      'source_sha256':hashlib.sha256((ROOT/'tools/clan_perspective_bridge.py').read_bytes()).hexdigest()}
    perspective_path.with_suffix('.json').write_text(json.dumps(perspective_meta,indent=2),encoding='utf8')
    print(json.dumps({'payload':str(out),'code_size':len(code),'exports':exports}))
    return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--tool-dir',type=Path,default=TOOL_DIR);args=ap.parse_args();build(args.tool_dir)
