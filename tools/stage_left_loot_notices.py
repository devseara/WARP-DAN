"""Append LeftLootNotices to an existing client while auditing every old byte.

Runs the production QJS via the bounded Node adapter. Only five native loot
vtable entries and PE allocation metadata may change in the original image.
The installed executable is never replaced, and existing outputs are refused.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import pefile


ROOT = Path(__file__).resolve().parents[1]
VTABLE = 0x103274C
SLOTS = (0, 4, 19, 20, 37)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def imports(pe):
    return [(entry.dll, [(item.name, item.ordinal, item.address) for item in entry.imports])
            for entry in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', [])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, default='node')
    args = parser.parse_args()
    report_path = args.output.with_suffix('.preservation.json')
    emission_path = args.output.with_suffix('.emission.json')
    require(args.source.resolve() != args.output.resolve(), 'Stage before deployment')
    for path in (args.output, report_path, emission_path):
        require(not path.exists(), 'Refusing to overwrite '+str(path))
    original = args.source.read_bytes()
    pe = pefile.PE(data=original)
    base = pe.OPTIONAL_HEADER.ImageBase
    require(base == 0x400000 and pe.FILE_HEADER.Machine == 0x14C and
            pe.OPTIONAL_HEADER.Magic == 0x10B, 'Expected the x86 Ragexe image')
    require(b'LeftLootNotices.v1\0' not in original, 'Loot stack is already installed')
    overlay_start = pe.get_overlay_data_start_offset() or len(original)
    overlay = original[overlay_start:]
    tail = max(pe.sections, key=lambda section: section.VirtualAddress)
    require(tail.Name.rstrip(b'\0') == b'.xdiff', 'Expected the existing WARP .xdiff section')
    require(tail.PointerToRawData + tail.SizeOfRawData == overlay_start,
            'The last virtual section must also be the last file section')
    offset = tail.PointerToRawData + align(max(tail.Misc_VirtualSize, tail.SizeOfRawData), 16)
    rva = tail.VirtualAddress + offset - tail.PointerToRawData
    request = dict(source=str(args.source.resolve()), source_sha256=digest(original),
                   image_base=base, source_mapped_end=overlay_start,
                   allocation_offset=offset, allocation_rva=rva,
                   sections=[dict(rva=s.VirtualAddress, offset=s.PointerToRawData,
                                  raw_size=s.SizeOfRawData) for s in pe.sections])
    emission = json.loads(subprocess.check_output([
        str(args.node), str(ROOT / 'tools/emit_left_loot_notices.cjs')],
        input=json.dumps(request), text=True))
    require(emission['production_qjs_executed'] is True and
            emission['source_sha256'] == digest(original), 'QJS emission source mismatch')
    allocations = emission['allocations']
    require(allocations and allocations[0]['phy'] == offset, 'Unexpected first allocation')
    append_end = emission['append_end']
    require(append_end > offset and append_end - offset <= 32 * 1024 * 1024,
            'Invalid payload append size')
    last_end = offset
    for allocation in allocations:
        require(allocation['phy'] >= last_end and allocation['size'] > 0,
                'Overlapping or empty allocation')
        require(allocation['vir'] == base + rva + allocation['phy'] - offset,
                'Incorrect allocation virtual address')
        last_end = allocation['phy'] + allocation['size']
    require(last_end == append_end, 'Unexpected allocation end')
    raw_size = align(append_end - tail.PointerToRawData, pe.OPTIONAL_HEADER.FileAlignment)
    end = tail.PointerToRawData + raw_size
    data = bytearray(original[:overlay_start])
    data.extend(bytes(end - len(data)))
    data.extend(overlay)
    slot_offsets = {pe.get_offset_from_rva(VTABLE + slot * 4 - base): slot for slot in SLOTS}
    written_slots = set()
    allowed = []
    for write in emission['writes']:
        pos, replacement = write['offset'], bytes.fromhex(write['after'])
        require(bytes(data[pos:pos+len(replacement)]).hex() == write['before'],
                'Write-before audit mismatch at '+hex(pos))
        if pos < overlay_start:
            require(pos in slot_offsets and len(replacement) == 4 and pos not in written_slots,
                    'Unexpected write to an existing client byte at '+hex(pos))
            target = struct.unpack('<I', replacement)[0]
            require(any(a['vir'] <= target < a['vir'] + a['size'] for a in allocations),
                    'Vtable target is outside the appended payload')
            written_slots.add(pos)
            allowed.append((pos, 4, 'Loot vtable slot '+str(slot_offsets[pos])))
        else:
            require(any(a['phy'] <= pos and pos+len(replacement) <= a['phy']+a['size']
                        for a in allocations), 'Write outside an allocated payload range')
        data[pos:pos+len(replacement)] = replacement
    require(written_slots == set(slot_offsets), 'All five loot vtable slots must be changed')

    def put(pos, value, label='PE allocation metadata'):
        data[pos:pos+4] = struct.pack('<I', value)
        allowed.append((pos, 4, label))

    delta = raw_size - tail.SizeOfRawData
    for pos, value in [
        (tail.get_file_offset()+8, append_end-tail.PointerToRawData),
        (tail.get_file_offset()+16, raw_size),
        (tail.get_file_offset()+36, tail.Characteristics | 0xE0000060),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),
         align(tail.VirtualAddress+append_end-tail.PointerToRawData, pe.OPTIONAL_HEADER.SectionAlignment)),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'), pe.OPTIONAL_HEADER.SizeOfCode+delta),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfInitializedData'), pe.OPTIONAL_HEADER.SizeOfInitializedData+delta),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum'), 0),
    ]:
        put(pos, value)
    certificate = pe.OPTIONAL_HEADER.DATA_DIRECTORY[4]
    if certificate.Size:
        require(certificate.VirtualAddress >= overlay_start, 'Certificate is not in the overlay')
        put(certificate.get_file_offset(), certificate.VirtualAddress+end-overlay_start,
            'Overlay certificate offset')
    restored = bytearray(data[:overlay_start])
    for pos, size, _ in allowed:
        restored[pos:pos+size] = original[pos:pos+size]
    require(restored == original[:overlay_start], 'Unrelated existing client bytes changed')
    require(data[end:] == overlay, 'Overlay changed')
    final = pefile.PE(data=bytes(data))
    require(imports(final) == imports(pe), 'Import table changed')
    require(b'LeftLootNotices.v1\0' in data[offset:append_end], 'Missing loot contract marker')
    for allocation in allocations:
        require(final.get_data(allocation['vir']-base, allocation['size']) ==
                data[allocation['phy']:allocation['phy']+allocation['size']],
                'Final PE payload mapping differs')
    report = dict(source=str(args.source.resolve()), source_sha256=digest(original),
                  candidate=str(args.output.resolve()), candidate_sha256=digest(data),
                  patch_sha256=emission['patch_sha256'], payload_sha256=emission['payload_sha256'],
                  allocation_base=base+rva, allocation_bytes=append_end-offset,
                  native_vtable=VTABLE, native_slots=list(SLOTS), allowed_changes=allowed,
                  production_qjs_executed=True, unrelated_bytes_preserved=True,
                  overlay_preserved=True, imports_preserved=True,
                  deployed=False, live_visual_accepted=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as handle:
        handle.write(data)
    with emission_path.open('x', encoding='utf-8') as handle:
        json.dump(emission, handle, indent=2)
        handle.write('\n')
    with report_path.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
