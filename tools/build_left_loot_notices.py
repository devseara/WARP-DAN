"""Build the import-free 2025-07-16 left-side loot payload; never install an EXE."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

import pefile


ROOT = Path(__file__).resolve().parents[1]
MAGIC = 0x544F4F4C
VERSION = 1
CLIENT = 20250716


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def api_size_argument(value):
    size = int(value, 0)
    if size <= 0 or size % 4:
        raise argparse.ArgumentTypeError('API size must be a positive multiple of four bytes')
    return size


def msvc_tools():
    program_files = os.environ.get('ProgramFiles(x86)')
    require(program_files, 'ProgramFiles(x86) is unavailable; run this builder on Windows')
    vswhere = Path(program_files) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    require(vswhere.is_file(), 'Visual Studio vswhere.exe was not found')
    installation = subprocess.check_output([
        str(vswhere), '-latest', '-products', '*', '-requires',
        'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property',
        'installationPath',
    ], text=True).strip()
    require(installation, 'Visual Studio with the x86 C++ toolchain was not found')
    vs = Path(installation)
    version = (vs / 'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
    tool_dir = vs / 'VC/Tools/MSVC' / version / 'bin/Hostx64/x86'
    require((tool_dir / 'cl.exe').is_file() and (tool_dir / 'link.exe').is_file(),
            'The selected MSVC x86 compiler/linker is incomplete')
    return tool_dir


def extract_payload(dll, api_size):
    with pefile.PE(str(dll)) as pe:
        require(pe.FILE_HEADER.Machine == 0x14C and pe.OPTIONAL_HEADER.Magic == 0x10B,
                'Loot payload must be an x86 PE32 image')
        for directory in ('IMAGE_DIRECTORY_ENTRY_IMPORT', 'IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT'):
            entry = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY[directory]]
            require(not entry.VirtualAddress and not entry.Size,
                    'Loot payload must not import DLLs, including delay-loaded imports')

        sections = [section for section in pe.sections
                    if section.Name.rstrip(b'\0') != b'.reloc' and section.Misc_VirtualSize]
        require(sections, 'Relocation container has no payload sections')
        first = min(section.VirtualAddress for section in sections)
        # Optimized loops can reference a one-past-the-last-array sentinel.
        end = max(section.VirtualAddress + section.Misc_VirtualSize for section in sections) + 16
        code = bytearray(end - first)
        for section in sections:
            data = section.get_data()[:section.Misc_VirtualSize]
            offset = section.VirtualAddress - first
            code[offset:offset + len(data)] = data

        relocs = []
        relocated_offsets = set()
        for block in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
            for relocation in block.entries:
                if relocation.type == 0:  # IMAGE_REL_BASED_ABSOLUTE padding.
                    continue
                require(relocation.type == 3, 'Only x86 HIGHLOW relocations are supported')
                offset = relocation.rva - first
                require(0 <= offset <= len(code) - 4, 'Relocation site is outside the payload')
                require(offset not in relocated_offsets, 'Duplicate relocation site')
                target = struct.unpack_from('<I', code, offset)[0] - pe.OPTIONAL_HEADER.ImageBase - first
                require(0 <= target < len(code), 'Relocation target is outside the payload')
                struct.pack_into('<I', code, offset, target)
                relocated_offsets.add(offset)
                relocs.append(offset)
        relocs.sort()

        export_directory = getattr(pe, 'DIRECTORY_ENTRY_EXPORT', None)
        require(export_directory is not None, 'Loot payload has no exports')
        exports = {}
        for symbol in export_directory.symbols:
            require(symbol.name is not None and not symbol.forwarder,
                    'Loot payload exports must be named and must not be forwarded')
            name = symbol.name.decode('ascii')
            offset = symbol.address - first
            require(name not in exports, 'Duplicate export name: ' + name)
            require(any(section.VirtualAddress <= symbol.address <
                        section.VirtualAddress + section.Misc_VirtualSize for section in sections),
                    'Export is outside payload sections: ' + name)
            exports[name] = offset
        exports = dict(sorted(exports.items()))
        require('LootApi' in exports, 'Required export LootApi is missing')
        api_rva = exports['LootApi'] + first
        require(any(section.Characteristics & 0x80000000 and
                    section.VirtualAddress <= api_rva and
                    api_rva + api_size <= section.VirtualAddress + section.Misc_VirtualSize
                    for section in sections), 'LootApi does not fit inside a writable payload section')

    body = struct.pack('<' + 'I' * len(relocs), *relocs) + code
    header = struct.pack('<8I', MAGIC, VERSION, len(code), len(relocs),
                         exports['LootApi'], api_size, CLIENT, zlib.crc32(body))
    return header + body, exports, len(code), len(relocs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path,
                        default=ROOT / 'Outputs/left-loot-notices-20261018/runtime')
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'Scripts/Runtime/LeftLootNotices')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'Inputs/LeftLootNotices')
    parser.add_argument('--api-size', type=api_size_argument, default=16,
                        help='LootApi structure size in bytes (default: 16)')
    args = parser.parse_args()

    source = args.source_dir.resolve() / 'runtime.cpp'
    require(source.is_file(), 'Loot runtime source is missing: ' + str(source))
    tools = msvc_tools()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    obj = work / 'runtime.obj'
    dll = work / 'relocation-container.dll'
    subprocess.run([
        str(tools / 'cl.exe'), '/nologo', '/c', '/TP', '/GR-', '/O2', '/Oi', '/GS-',
        '/Zl', '/W4', '/WX', '/Brepro', '/Fo' + str(obj), str(source),
    ], cwd=work, check=True)
    subprocess.run([
        str(tools / 'link.exe'), '/nologo', '/DLL', '/NOENTRY', '/NODEFAULTLIB',
        '/MACHINE:X86', '/DYNAMICBASE:NO', '/NXCOMPAT', '/OPT:REF', '/OPT:ICF',
        '/INCREMENTAL:NO', '/BREPRO', '/OUT:' + str(dll), str(obj),
    ], cwd=work, check=True)

    payload, exports, size, relocation_count = extract_payload(dll, args.api_size)
    metadata = {
        'version': VERSION, 'client': CLIENT, 'size': size, 'api_size': args.api_size,
        'relocation_count': relocation_count, 'exports': exports,
        'source_sha256': hashlib.sha256(source.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        'payload_sha256': hashlib.sha256(payload).hexdigest(), 'runtime_imports': [],
    }
    output = args.output_dir.resolve() / 'runtime.bin'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
