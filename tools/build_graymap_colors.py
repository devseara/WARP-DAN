"""Compile the import-free static palette payload; QJS embeds it, no DLL ships."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib
import pefile

ROOT = Path(__file__).resolve().parents[1]


def msvc_bin(override):
    """Find a matched x86 cl/link pair without pinning a local VS version."""
    if override:
        candidates = [override]
    else:
        candidates = []
        if os.environ.get('VCToolsInstallDir'):
            candidates.append(Path(os.environ['VCToolsInstallDir']) / 'bin/Hostx64/x86')
        vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
        if vswhere.is_file():
            result = subprocess.run([str(vswhere), '-latest', '-products', '*',
                '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                '-property', 'installationPath'], check=True, capture_output=True, text=True)
            if result.stdout.strip():
                base = Path(result.stdout.strip()) / 'VC/Tools/MSVC'
                candidates.extend(p / 'bin/Hostx64/x86' for p in sorted(base.iterdir(), reverse=True))
    for candidate in candidates:
        if all((candidate / name).is_file() for name in ['cl.exe', 'link.exe']):
            return candidate.resolve()
    raise RuntimeError('x86 MSVC tools not found; supply --msvc-bin with a matched cl.exe/link.exe directory')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--msvc-bin', type=Path, help='Override the x86 MSVC compiler/linker directory')
    tools = msvc_bin(parser.parse_args().msvc_bin)
    source=ROOT/'Scripts/Runtime/GrayMap/colors.cpp'
    work_root=ROOT/'Outputs/GrayMap/colors-runtime';work_root.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='build-',dir=work_root))
    obj,dll=work/'colors.obj',work/'relocation-container.dll'
    subprocess.run([str(tools/'cl.exe'),'/nologo','/c','/TP','/GR-','/O2','/Oi','/GS-','/Zl','/W4','/WX','/Fo'+str(obj),str(source)],check=True)
    subprocess.run([str(tools/'link.exe'),'/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/MACHINE:X86','/DYNAMICBASE:NO','/NXCOMPAT','/OPT:REF','/OPT:ICF','/BREPRO','/OUT:'+str(dll),str(obj)],check=True)
    pe=pefile.PE(str(dll));assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',None)
    sections=[s for s in pe.sections if s.Name.rstrip(b'\0')!=b'.reloc']
    first=min(s.VirtualAddress for s in sections);end=max(s.VirtualAddress+s.Misc_VirtualSize for s in sections)
    code=bytearray(end-first)
    for s in sections:
        data=s.get_data()[:s.Misc_VirtualSize];code[s.VirtualAddress-first:s.VirtualAddress-first+len(data)]=data
    relocs=[]
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for r in block.entries:
            if not r.type:continue
            assert r.type==3
            offset=r.rva-first;target=struct.unpack_from('<I',code,offset)[0]-pe.OPTIONAL_HEADER.ImageBase-first
            assert 0<=target<len(code)
            struct.pack_into('<I',code,offset,target);relocs.append(offset)
    exports={s.name.decode():s.address-first for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    body=struct.pack('<'+'I'*len(relocs),*relocs)+code
    payload=struct.pack('<8I',0x434D5247,6,len(code),len(relocs),exports['GrayMapState'],20250716,0,zlib.crc32(body))+body
    out=ROOT/'Assets/GrayMap/colors.bin';out.write_bytes(payload)
    meta=dict(version=6,client=20250716,size=len(code),exports=exports,source_sha256=hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),payload_sha256=hashlib.sha256(payload).hexdigest(),runtime_imports=[])
    out.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
