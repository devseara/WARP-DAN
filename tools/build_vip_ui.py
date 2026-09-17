"""Compile the independent, import-free VIP frame. Never installs game EXEs."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib
import pefile

ROOT = Path(__file__).resolve().parents[1]

def main():
    vswhere = Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
    vs = Path(subprocess.check_output([str(vswhere),'-latest','-products','*','-requires',
              'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip())
    version = (vs/'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
    tools = vs/'VC/Tools/MSVC'/version/'bin/Hostx64/x86'
    source = ROOT/'Scripts/Runtime/VipUI/runtime.cpp'
    work = ROOT/'Outputs/vip-ui-20260917/runtime'
    work.mkdir(parents=True,exist_ok=True)
    obj,dll=work/'runtime.obj',work/'relocation-container.dll'
    subprocess.run([str(tools/'cl.exe'),'/nologo','/c','/TP','/GR-','/O2','/Oi','/GS-','/Zl','/W4','/WX',
                    '/Fo'+str(obj),str(source)],cwd=work,check=True)
    subprocess.run([str(tools/'link.exe'),'/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/MACHINE:X86',
                    '/DYNAMICBASE:NO','/NXCOMPAT','/OPT:REF','/OPT:ICF','/BREPRO','/OUT:'+str(dll),str(obj)],cwd=work,check=True)
    pe=pefile.PE(str(dll))
    assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',None)
    sections=[s for s in pe.sections if s.Name.rstrip(b'\0')!=b'.reloc']
    first=min(s.VirtualAddress for s in sections)
    end=max(s.VirtualAddress+s.Misc_VirtualSize for s in sections)
    code=bytearray(end-first)
    for s in sections:
        data=s.get_data()[:s.Misc_VirtualSize]
        code[s.VirtualAddress-first:s.VirtualAddress-first+len(data)]=data
    relocs=[]
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for r in block.entries:
            if not r.type: continue
            assert r.type==3
            offset=r.rva-first
            target=struct.unpack_from('<I',code,offset)[0]-pe.OPTIONAL_HEADER.ImageBase-first
            assert 0<=target<len(code)
            struct.pack_into('<I',code,offset,target)
            relocs.append(offset)
    exports={s.name.decode():s.address-first for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    body=struct.pack('<'+'I'*len(relocs),*relocs)+code
    header=struct.pack('<8I',0x32504956,2,len(code),len(relocs),exports['VipApi'],0,0,zlib.crc32(body))
    out=ROOT/'Inputs/VipUI/runtime.bin'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(header+body)
    meta={'version':2,'client':20250716,'size':len(code),'api_size':88,'exports':exports,
          'source_sha256':hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
          'payload_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'runtime_imports':[]}
    out.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    print(json.dumps(meta,indent=2))

if __name__=='__main__': main()
