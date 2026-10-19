"""Review-only reversed corpse-depth correction for mounted female Mage.

The native reversed 0x9C path sinks above-anchor rows. Clamp that path only
for this mounted body during A64..71. Keep the existing floor/shadow hooks.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
import pefile
from build_mounted_mage_attachments import Code, align

ROOT = Path(__file__).resolve().parents[1]
SITE, RESUME = 0xC40FA6, 0xC40FAE
STOCK = 'f30f59257cd41d01'
SOURCE = 'a01c93ff5e2ef491fadb29a7bf4e0bae05eae4c6130301c643f8c34eb9b9d9e5'


def specification():
    c = Code().hex('9c508b07')  # preserve native depth-bias EAX and EFLAGS
    for raw in ['3d10480901', '83bf5c02000002', '83bfc804000002', '83bf6002000000']:
        c.hex(raw).branch('75', 'stock')
    c.hex('80bfcc02000000').branch('74', 'stock')
    c.hex('837f3840').branch('72', 'stock')
    c.hex('837f3847').branch('77', 'stock')
    c.pointer('f30f5f25', 'zero').pointer('f30f5f2d', 'zero')
    c.label('stock').hex('589d' + STOCK).link('e9', RESUME)
    c.label('zero').hex('00000000')
    return dict(site=SITE, stock=STOCK, **c.finish())


def relocate(spec, address):
    code = bytearray.fromhex(spec['hex'])
    for link in spec['links']:
        value = (
            address + link['target']
            if link.get('kind') == 'local'
            else link['target'] - address - link['offset'] - 4
        )
        struct.pack_into('<I' if link.get('kind') == 'local' else '<i', code, link['offset'], value)
    return code


def build(source, out):
    assert not out.exists()
    before = source.read_bytes()
    assert hashlib.sha256(before).hexdigest() == SOURCE, 'Profile the actual current client first.'
    pe = pefile.PE(data=before)
    assert pe.get_data(SITE - 0x400000, 8).hex() == STOCK
    assert pe.get_data(0xC40F9F - 0x400000, 5)[0] == 0xE9
    assert not any(s.Name.rstrip(b'\0') == b'.mgdead' for s in pe.sections)
    data = bytearray(before)
    fa, sa = pe.OPTIONAL_HEADER.FileAlignment, pe.OPTIONAL_HEADER.SectionAlignment
    rva = align(pe.OPTIONAL_HEADER.SizeOfImage, sa)
    spec = specification()
    payload = relocate(spec, 0x400000 + rva)
    header = pe.sections[-1].get_file_offset() + 40
    first = min(s.PointerToRawData for s in pe.sections if s.SizeOfRawData)
    shift = max(0, align(header + 40, fa) - first)
    pe.parse_data_directories(directories=[6])
    assert not getattr(pe, 'DIRECTORY_ENTRY_DEBUG', [])
    assert (
        not pe.FILE_HEADER.PointerToSymbolTable
        and not pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].VirtualAddress
    )
    if shift:
        data[first:first] = bytes(shift)
        for s in pe.sections:
            assert not s.PointerToRelocations and not s.PointerToLinenumbers
            if s.SizeOfRawData:
                struct.pack_into(
                    '<I',
                    data,
                    s.get_field_absolute_offset('PointerToRawData'),
                    s.PointerToRawData + shift,
                )
        struct.pack_into(
            '<I',
            data,
            pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfHeaders'),
            align(header + 40, fa),
        )
    raw = align(len(data), fa)
    size = align(len(payload), fa)
    data.extend(bytes(raw - len(data)) + payload + bytes(size - len(payload)))
    overlay = pe.get_overlay() or b''
    data.extend(overlay)
    data[header : header + 40] = struct.pack(
        '<8sIIIIIIHHI', b'.mgdead', len(payload), rva, size, raw, 0, 0, 0, 0, 0x60000020
    )
    struct.pack_into(
        '<H',
        data,
        pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),
        pe.FILE_HEADER.NumberOfSections + 1,
    )
    struct.pack_into(
        '<I',
        data,
        pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),
        align(rva + len(payload), sa),
    )
    struct.pack_into(
        '<I',
        data,
        pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),
        pe.OPTIONAL_HEADER.SizeOfCode + size,
    )
    off = pe.get_offset_from_rva(SITE - 0x400000)
    if off >= first:
        off += shift
    data[off : off + 8] = b'\xe9' + struct.pack('<i', 0x400000 + rva - SITE - 5) + b'\x90' * 3
    final = pefile.PE(data=bytes(data))
    allowed = set(range(SITE, SITE + 8))
    for s in pe.sections:
        a, b = s.get_data(), final.get_data(s.VirtualAddress, s.SizeOfRawData)
        assert len(a) == len(b)
        delta = np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8))
        assert all(0x400000 + s.VirtualAddress + int(i) in allowed for i in delta)
    assert (final.get_overlay() or b'') == overlay
    out.mkdir(parents=True)
    target = out / 'client.exe'
    target.write_bytes(data)
    report = dict(
        installed=False,
        status='review_candidate',
        source_sha256=SOURCE,
        candidate_sha256=hashlib.sha256(data).hexdigest(),
        candidate=str(target),
        all_other_mapped_bytes_preserved=True,
        hook=hex(SITE),
        cave=hex(0x400000 + rva),
        live_acceptance=False,
        spec=spec,
    )
    (out / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Built isolated corpse-depth candidate:', target)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    build(a.source.resolve(), a.out.resolve())
