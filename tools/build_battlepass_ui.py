"""Build the private Battle Pass UI plus the exact VIP/Bestiary sprite renderers.

Only build outputs/payloads are written. No installation or profile changes.
"""
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
    source = ROOT / 'Scripts/Runtime/BattlepassUI/runtime.cpp'
    vip_path = ROOT / 'Scripts/Runtime/VipUI/runtime.cpp'
    monster = ROOT / 'tools/native/bestiary_preview.cpp'
    work = ROOT / 'Outputs/battlepass-redesign-20260922/runtime'
    work.mkdir(parents=True, exist_ok=True)
    vip = vip_path.read_text(encoding='utf8')
    # Compile the same reviewed native Alt+Q compositor as VIP, with private
    # storage and no VIP packet/window code. This cannot enable the VIP feature.
    rect = vip[vip.index('static void rect('):vip.index('// Private VIP chrome.')]
    portrait = vip[vip.index('static const u8* worn('):vip.index('static const Control questControls')]
    portrait = portrait.replace('VipPortrait', 'BpPortrait')
    unit = ('typedef unsigned int u32;typedef unsigned char u8;typedef unsigned short u16;\n'
            '#define EXPORT extern "C" __declspec(dllexport)\n'
            'template<class T>T& at(void* p,int o){return *reinterpret_cast<T*>(static_cast<u8*>(p)+o);}\n'
            'static constexpr int X(int v){return v*460/1412;}\n'
            'static constexpr int Y(int v){return v*362/1114;}\n'
            'EXPORT void* BpPortraitCanvas=0;\n' + rect + portrait)
    avatar = work / 'vip-character.cpp'
    avatar.write_text(unit, encoding='utf8')
    vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    vs = Path(subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
                                     'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip())
    version = (vs / 'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
    tools = vs / 'VC/Tools/MSVC' / version / 'bin/Hostx64/x86'
    objects = []
    for src in (source, avatar, monster):
        obj = work / (src.stem + '.obj')
        subprocess.run([str(tools/'cl.exe'), '/nologo', '/c', '/TP', '/GR-', '/O2', '/Oi', '/GS-', '/Zl', '/W4', '/WX',
                        '/Fo'+str(obj), str(src)], cwd=work, check=True)
        objects.append(str(obj))
    dll = work / 'relocation-container.dll'
    subprocess.run([str(tools/'link.exe'), '/nologo', '/DLL', '/NOENTRY', '/NODEFAULTLIB', '/MACHINE:X86',
                    '/DYNAMICBASE:NO', '/NXCOMPAT', '/OPT:REF', '/OPT:ICF', '/BREPRO', '/EXPORT:_BestiaryPreview@32',
                    '/OUT:'+str(dll), *objects], cwd=work, check=True)
    pe = pefile.PE(str(dll))
    assert not getattr(pe, 'DIRECTORY_ENTRY_IMPORT', None)
    sections = [s for s in pe.sections if s.Name.rstrip(b'\0') != b'.reloc']
    first = min(s.VirtualAddress for s in sections)
    end = max(s.VirtualAddress+s.Misc_VirtualSize for s in sections)
    code = bytearray(end-first)
    for s in sections:
        data = s.get_data()[:s.Misc_VirtualSize]
        code[s.VirtualAddress-first:s.VirtualAddress-first+len(data)] = data
    relocs = []
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for r in block.entries:
            if not r.type:
                continue
            assert r.type == 3
            offset = r.rva-first
            target = struct.unpack_from('<I', code, offset)[0]-pe.OPTIONAL_HEADER.ImageBase-first
            assert 0 <= target < len(code)
            struct.pack_into('<I', code, offset, target)
            relocs.append(offset)
    exports = {s.name.decode():s.address-first for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    body = struct.pack('<'+'I'*len(relocs), *relocs)+code
    header = struct.pack('<8I', 0x35555042, 4, len(code), len(relocs), exports['BpApi'], 80, 7728, zlib.crc32(body))
    target = ROOT/'Inputs/BattlepassUI/runtime.bin'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(header+body)
    meta = {'version':4, 'client':20250716, 'size':len(code), 'api_size':80, 'board_size':7728, 'exports':exports,
            'source_sha256':hashlib.sha256(source.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
            'vip_portrait_sha256':hashlib.sha256(unit.encode()).hexdigest(),
            'bestiary_sha256':hashlib.sha256(monster.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
            'payload_sha256':hashlib.sha256(target.read_bytes()).hexdigest(), 'runtime_imports':[]}
    target.with_suffix('.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf8')
    print(json.dumps(meta, indent=2))

if __name__ == '__main__':
    main()
