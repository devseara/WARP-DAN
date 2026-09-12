"""Compile/embed the profiled HD preview bridges; no DLL is deployed."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess
import pefile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--compiler',type=Path,help='MSVC Hostx64/x86/cl.exe (link.exe in the same directory)')
parser.add_argument('--profile-client',type=Path,default=ROOT/'2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe',help='Verified baseline Ragexe used for original-byte checks')
args=parser.parse_args()
OUT=ROOT/'Outputs/hd-job-ui/native';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'tools/native/hd_job_ui.cpp'
COMPILER=args.compiler or Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x86/cl.exe')
subprocess.run([str(COMPILER),'/nologo','/c','/O2','/Oi','/GS-','/GR-','/Zl','/EHs-c-',f'/Fo{OUT / "preview.obj"}',str(SOURCE)],check=True)
subprocess.run([str(COMPILER.parent/'link.exe'),'/nologo','/nodefaultlib','/machine:x86','/safeseh:no','/entry:HDJobResolve','/subsystem:windows','/base:0x10000000','/fixed:no','/dynamicbase','/opt:ref','/incremental:no',f'/out:{OUT / "preview.exe"}',str(OUT/'preview.obj')],check=True)
pe=pefile.PE(str(OUT/'preview.exe'));assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',None)
start=0x1000;end=max(s.VirtualAddress+s.Misc_VirtualSize for s in pe.sections if not s.Name.startswith(b'.reloc'))
blob=bytearray(end-start)
for s in pe.sections:
 if s.Name.startswith(b'.reloc'):continue
 data=s.get_data()[:s.Misc_VirtualSize];at=s.VirtualAddress-start;blob[at:at+len(data)]=data
relocs=[]
for block in pe.DIRECTORY_ENTRY_BASERELOC:
 for e in block.entries:
  if not e.type:continue
  assert e.type==3 and start<=e.rva<end;relocs.append(e.rva-start)
exports={s.name.decode():s.address-start for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
info={'imageBase':pe.OPTIONAL_HEADER.ImageBase+start,'hex':blob.hex(),'relocations':relocs,'exports':exports,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
(OUT/'blob.json').write_text(json.dumps(info,indent=2))
print(json.dumps({'bytes':len(blob),'exports':exports,'relocations':len(relocs)}))
manifest=json.loads((ROOT/'Assets/HDJobUI/manifest.json').read_text())
pairs=[{key:row[key] for key in ('resource_hex','preview','fallback')} for row in manifest['pairs']]
pristine=args.profile_client
raw=pristine.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='73349f3606de8e9535d91b73e0177813c38369f06795f5a91200715a177f1a9f'
client=pefile.PE(data=raw)
site_rows=[]
for is_string,addresses,old in [(True,[0x7ACD71,0x7ACDB1,0x7AEC6B,0x7AED3F],0x1967C30),(False,[0x974B20,0x974B56,0x974B76,0x974D35,0x974E04],0x1967BF0)]:
 for va in addresses:
  stock=client.get_data(va-0x400000,5);assert stock[0]==0xe8
  site_rows.append(dict(va=va,stock=stock.hex(),clan=(b'\xe8'+struct.pack('<i',old-va-5)).hex(),string=is_string))
checks=[[va,client.get_data(va-0x400000,10).hex()] for va in (0xA8D4A0,0xA8D9F0,0x4F1940,0x4F08F0,0x573750,0x573060)]
text=(ROOT/'tools/native/hd_job_ui.qjs.in').read_text()
for key,value in [('blob',info),('nativeChecks',checks),('sites',site_rows),('pairs',pairs),('files',sorted({f for p in manifest['pairs'] for f in p['files']}))]:
 text+='\nHDJobSpritePreviews.'+key+' = '+json.dumps(value,separators=(',',':'))+';\n'
(ROOT/'Scripts/Patches/HDJobSpritePreviews.qjs').write_bytes(text.replace('\r\n','\n').replace('\n','\r\n').encode('utf-8'))