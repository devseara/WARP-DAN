"""Compile the freestanding x86 fit helper and embed its relocatable image.

No DLL is deployed. PE is only a build container; WARP injects its code/data.
"""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess
import pefile

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compiler',type=Path,default=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x86/cl.exe'))
    args=ap.parse_args()
    source=ROOT/'tools/native/bestiary_preview.cpp'
    out=ROOT/'Outputs/Bestiary/verification/native/fit-helper';out.mkdir(parents=True,exist_ok=True)
    obj=out/'preview.obj';exe=out/'preview.exe'
    subprocess.run([str(args.compiler),'/nologo','/c','/O2','/GS-','/GR-','/Zl','/arch:SSE2','/fp:precise','/EHs-c-',f'/Fo{obj}',str(source)],check=True)
    subprocess.run([str(args.compiler.parent/'link.exe'),'/nologo','/nodefaultlib','/machine:x86','/safeseh:no','/entry:BestiaryPreview@32','/subsystem:windows','/base:0x10000000','/fixed:no','/dynamicbase','/opt:ref','/incremental:no',f'/out:{exe}',str(obj)],check=True)
    pe=pefile.PE(str(exe))
    assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',None),'Helper must be freestanding'
    begin=0x1000;end=max(s.VirtualAddress+s.Misc_VirtualSize for s in pe.sections if not s.Name.startswith(b'.reloc'))
    image=bytearray(end-begin)
    for sec in pe.sections:
        if sec.Name.startswith(b'.reloc'):continue
        data=sec.get_data()[:sec.Misc_VirtualSize];pos=sec.VirtualAddress-begin;image[pos:pos+len(data)]=data
    relocs=[]
    for block in getattr(pe,'DIRECTORY_ENTRY_BASERELOC',[]):
        for entry in block.entries:
            if not entry.type:continue
            assert entry.type==3 and begin<=entry.rva<end
            relocs.append(entry.rva-begin)
    blob={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'imageBase':pe.OPTIONAL_HEADER.ImageBase+begin,'entryOffset':pe.OPTIONAL_HEADER.AddressOfEntryPoint-begin,'relocations':relocs,'hex':image.hex()}
    pe.close()
    (out/'blob.json').write_text(json.dumps(blob,indent=2))
    patch=ROOT/'Scripts/Patches/BestiaryUI.qjs';text=patch.read_text()
    start='// BEGIN GENERATED BESTIARY PREVIEW\n';endmark='// END GENERATED BESTIARY PREVIEW\n'
    generated=start+'BestiaryNative.PreviewBlob = '+json.dumps(blob,separators=(',',':'))+';\n'+endmark
    if start in text:
        first=text.index(start);last=text.index(endmark,first)+len(endmark);text=text[:first]+generated+text[last:]
    else:text+='\n'+generated
    patch.write_bytes(text.replace('\r\n','\n').replace('\n','\r\n').encode())
    print(json.dumps({'bytes':len(image),'relocations':len(relocs),'entry_offset':blob['entryOffset'],'source_sha256':blob['source_sha256']}))


if __name__=='__main__':main()
