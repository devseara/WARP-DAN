"""Compile a freestanding x86 build container and embed it in ItemDescriptionUI.qjs.

The DLL-format file is a link container only. Runtime deployment is QJS/EXE-only.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess
import pefile
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compiler',type=Path,default=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x86/cl.exe'))
    args=ap.parse_args();source=ROOT/'tools/native/item_description.cpp'
    out=ROOT/'Outputs/ItemDescription/native';out.mkdir(parents=True,exist_ok=True)
    obj=out/'item_description.obj';container=out/'item_description.build.dll'
    subprocess.run([str(args.compiler),'/nologo','/c','/O2','/Oi-','/Oy-','/GS-','/GR-','/Zl','/arch:SSE2','/EHs-c-','/std:c++17',f'/Fo{obj}',str(source)],check=True)
    subprocess.run([str(args.compiler.parent/'link.exe'),'/nologo','/dll','/noentry','/nodefaultlib','/machine:x86','/safeseh:no','/base:0x10000000','/fixed:no','/dynamicbase','/opt:ref','/incremental:no',f'/out:{container}',str(obj)],check=True)
    pe=pefile.PE(str(container));assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',None),'Runtime imports are forbidden'
    begin=min(s.VirtualAddress for s in pe.sections)
    end=max(s.VirtualAddress+s.Misc_VirtualSize for s in pe.sections if not s.Name.startswith(b'.reloc'))
    image=bytearray(end-begin)
    for sec in pe.sections:
        if sec.Name.startswith(b'.reloc'):continue
        data=sec.get_data()[:sec.Misc_VirtualSize];position=sec.VirtualAddress-begin;image[position:position+len(data)]=data
    relocations=[]
    for block in getattr(pe,'DIRECTORY_ENTRY_BASERELOC',[]):
        for entry in block.entries:
            if not entry.type:continue
            assert entry.type==3 and begin<=entry.rva<end
            value=int.from_bytes(image[entry.rva-begin:entry.rva-begin+4],'little')
            assert pe.OPTIONAL_HEADER.ImageBase+begin<=value<pe.OPTIONAL_HEADER.ImageBase+end
            relocations.append(entry.rva-begin)
    exports={s.name.decode().lstrip('_@').split('@')[0]:s.address-begin for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,source.with_name('item_description_wire.hpp')]}
    blob={'imageBase':pe.OPTIONAL_HEADER.ImageBase+begin,'source_sha256':sources,'exports':exports,'relocations':relocations,'hex':image.hex()}
    (out/'blob.json').write_text(json.dumps(blob,indent=2)+'\n')
    patch=ROOT/'Scripts/Patches/ItemDescriptionUI.qjs'
    if patch.exists():
        text=patch.read_text(encoding='utf8');start='// BEGIN GENERATED ITEM DESCRIPTION\n';stop='// END GENERATED ITEM DESCRIPTION\n'
        generated=start+'ItemDescriptionNative.Blob = '+json.dumps(blob,separators=(',',':'))+';\n'+stop
        if start in text:
            a=text.index(start);b=text.index(stop,a)+len(stop);text=text[:a]+generated+text[b:]
        else:text+='\n'+generated
        patch.write_bytes(text.replace('\r\n','\n').replace('\n','\r\n').encode('utf8'))
    print(json.dumps({'bytes':len(image),'relocations':len(relocations),'exports':exports,'imports':0}))
if __name__=='__main__':main()
