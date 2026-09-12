"""Profile native monster-preview RTTI and inspect x86 functions in a supplied PE.

Read-only: writes reports/disassembly to --output, never changes the input PE.
Requires pefile and capstone (the repository's analysis environment).
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32


class Image:
    def __init__(self, path):
        self.path = path
        self.raw = path.read_bytes()
        self.pe = pefile.PE(data=self.raw, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.cs = Cs(CS_ARCH_X86, CS_MODE_32)

    def offset(self, va):
        return self.pe.get_offset_from_rva(va - self.base)

    def va(self, offset):
        return self.base + self.pe.get_rva_from_offset(offset)

    def read(self, va, size):
        offset = self.offset(va)
        return self.raw[offset:offset + size]

    def executable(self, va):
        section = self.pe.get_section_by_rva(va - self.base)
        return bool(section and section.Characteristics & 0x20000000)

    def xrefs(self, value, code_only=False):
        hits = []
        needle = struct.pack('<I', value)
        for m in re.finditer(re.escape(needle), self.raw):
            try:
                va = self.va(m.start())
                if not code_only or self.executable(va):
                    hits.append(va)
            except pefile.PEFormatError:
                pass
        return hits

    def disasm(self, va, size):
        return '\n'.join(f'{i.address:08X}  {i.bytes.hex(" "):30} {i.mnemonic:8} {i.op_str}'
                         for i in self.cs.disasm(self.read(va, size), va))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('exe', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--disasm', type=lambda s: int(s, 0), action='append', default=[])
    ap.add_argument('--size', type=lambda s: int(s, 0), default=0x180)
    ap.add_argument('--xref', type=lambda s: int(s, 0), action='append', default=[])
    args = ap.parse_args()
    image = Image(args.exe)
    if image.pe.FILE_HEADER.Machine != 0x14c:
        raise ValueError('Only x86 PE images are supported')
    args.output.mkdir(parents=True, exist_ok=True)
    for va in args.disasm:
        text = image.disasm(va, args.size)
        (args.output / f'{va:08x}.asm').write_text(text, encoding='utf-8')
        print(text)
    for va in args.xref:
        print(f'XREF {va:#x}: ' + ', '.join(hex(v) for v in image.xrefs(va, True)))
    if args.disasm or args.xref:
        return
    classes = []
    for name in ['UIMonsterDisplayWnd', 'UIMonsterInfoWnd', 'CUIMonsterInfo@AdventureGuide',
                 'CUIMonster@AdventureGuide', 'UINavigationV4Wnd', 'UINaviLinkButton']:
        token = ('.?AV' + name + '@@').encode()
        offset = image.raw.find(token + b'\0')
        if offset < 0:
            continue
        descriptor = image.va(offset - 8)
        row = {'name': name, 'type_descriptor': hex(descriptor), 'vtables': []}
        for ref in image.xrefs(descriptor):
            col = ref - 12
            try:
                signature, suboffset, cd = struct.unpack('<III', image.read(col, 12))
                if signature != 0 or suboffset != 0 or cd != 0:
                    continue
                for slot in image.xrefs(col):
                    table = slot + 4
                    entries = struct.unpack('<53I', image.read(table, 53 * 4))
                    if not all(image.executable(v) for v in entries[:20]):
                        continue
                    entry = {'va': hex(table), 'col': hex(col),
                             'entries': {str(i): hex(v) for i, v in enumerate(entries)},
                             'code_references': [hex(v) for v in image.xrefs(table, True)]}
                    row['vtables'].append(entry)
                    for index in (0, 4, 20, 25, 28, 31, 35):
                        target = entries[index]
                        (args.output / f'{name.replace("@", "_")}-slot{index}-{target:08x}.asm').write_text(
                            image.disasm(target, 0x300), encoding='utf-8')
            except (pefile.PEFormatError, struct.error):
                pass
        classes.append(row)
    result = {'input': str(args.exe.resolve()), 'sha256': hashlib.sha256(image.raw).hexdigest(),
              'image_base': hex(image.base), 'classes': classes}
    (args.output / 'rtti.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
