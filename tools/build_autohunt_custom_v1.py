"""Build the import-free Custom AutoHunt UI v1 image consumed only at patch time."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import zlib
import pefile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/native/autohunt_custom_v1.cpp'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x86/cl.exe'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'Outputs/AutoHuntCustomV1/native-v2'
    output.mkdir(parents=True, exist_ok=True)
    obj, container = output / 'custom.obj', output / 'custom.build.dll'
    subprocess.run([str(args.compiler), '/nologo', '/c', '/O2', '/Oi-', '/Oy-', '/GS-', '/GR-', '/Zl', '/arch:SSE2', '/EHs-c-', '/std:c++17', f'/Fo{obj}', str(SOURCE)], check=True)
    subprocess.run([str(args.compiler.parent / 'link.exe'), '/nologo', '/dll', '/noentry', '/nodefaultlib', '/machine:x86', '/safeseh:no', '/base:0x10000000', '/fixed:no', '/dynamicbase', '/opt:ref', '/incremental:no', '/Brepro', f'/out:{container}', str(obj)], check=True)
    pe = pefile.PE(str(container))
    assert not getattr(pe, 'DIRECTORY_ENTRY_IMPORT', None), 'Runtime imports are forbidden'
    begin = min(s.VirtualAddress for s in pe.sections)
    end = max(s.VirtualAddress + s.Misc_VirtualSize for s in pe.sections if not s.Name.startswith(b'.reloc'))
    image = bytearray(end - begin)
    for section in pe.sections:
        if section.Name.startswith(b'.reloc'):
            continue
        data = section.get_data()[:section.Misc_VirtualSize]
        image[section.VirtualAddress - begin:section.VirtualAddress - begin + len(data)] = data
    relocs = []
    for block in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
        for entry in block.entries:
            if not entry.type:
                continue
            assert entry.type == 3 and begin <= entry.rva <= end - 4
            value = struct.unpack_from('<I', image, entry.rva - begin)[0]
            assert pe.OPTIONAL_HEADER.ImageBase + begin <= value < pe.OPTIONAL_HEADER.ImageBase + end
            relocs.append(entry.rva - begin)
    exports = {s.name.decode().lstrip('_@').split('@')[0]: s.address - begin for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
    assert set(exports) == {'AutoHuntCustomConfig', 'AutoHuntCustomDraw', 'AutoHuntCustomDown', 'AutoHuntCustomMove', 'AutoHuntCustomUp', 'AutoHuntCustomWheel'}
    payload = struct.pack('<' + 'I' * len(relocs), *relocs) + image
    blob = struct.pack('<8I', 0x31564341, 2, len(image), len(relocs), pe.OPTIONAL_HEADER.ImageBase + begin, 620, 20250716, zlib.crc32(payload)) + payload
    metadata = {'version': 2, 'client': 20250716, 'config_size': 620, 'size': len(image), 'exports': exports, 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'payload_sha256': hashlib.sha256(blob).hexdigest(), 'imports': 0}
    target = ROOT / 'Inputs/AutoUI'
    json_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode('ascii')
    if args.check:
        assert (target / 'custom-v1.bin').read_bytes() == blob, 'Custom AutoHunt UI v1 payload is stale'
        assert (target / 'custom-v1.json').read_bytes() == json_bytes, 'Custom AutoHunt UI v1 metadata is stale'
    else:
        (target / 'custom-v1.bin').write_bytes(blob)
        (target / 'custom-v1.json').write_bytes(json_bytes)
    print(json.dumps(metadata))

if __name__ == '__main__':
    main()
