"""Stage only the announcement placement bridge in an existing Celestial v3 client.

Does not rebuild payloads, run the client, or replace the installed executable.
All existing bytes except the frame call, bridge record and PE allocation
metadata must be identical. The original executable overlay is retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import pefile

ROOT = Path(__file__).resolve().parents[1]
FIELDS = 'api state frame reset receive draw hit destroy bridge receiver top vtable'.split()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def emit(node, frame, top, base):
    return bytes.fromhex(subprocess.check_output([
        str(node), str(ROOT/'tools/emit_celestial_frame.cjs'),
        str(frame), str(top), str(base)], text=True))


def contract(pe):
    image = pe.get_memory_mapped_image()
    marker = image.index(b'CelestialDial.v3\0')
    key = struct.pack('<I', pe.OPTIONAL_HEADER.ImageBase + marker)
    record = image.index(key)
    assert image.find(key, record+1) < 0, 'Ambiguous Celestial contract'
    return dict(zip(FIELDS, struct.unpack_from('<12I', image, record+4))), record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--node', type=Path, default='node')
    args = ap.parse_args()
    assert args.source.resolve() != args.output.resolve(), 'Stage before deployment'
    assert not args.output.exists(), 'Refusing to overwrite a staged client'
    original = args.source.read_bytes()
    pe = pefile.PE(data=original)
    base = pe.OPTIONAL_HEADER.ImageBase
    assert base == 0x400000 and pe.FILE_HEADER.Machine == 0x14c
    c, record = contract(pe)
    hook = 0xC74FB0
    assert pe.get_data(hook-base, 5) == b'\xe8'+struct.pack('<i', c['bridge']-hook-5)
    # Accept only the exact earlier bridge; this prevents stacking the upgrade.
    prior = b'\x9c\x60\x53\xe8'+struct.pack('<i', c['frame']-c['bridge']-8)+b'\x61\x9d\xe9'+struct.pack('<i', 0xA79710-c['bridge']-15)
    assert pe.get_data(c['bridge']-base, len(prior)) == prior, 'Unexpected or already upgraded frame bridge'
    assert pe.get_data(0xC856C4-base, 15) == bytes.fromhex('8b8e1c0600006a336a008b01ff5010'), 'Top announcement owner/position differs'
    overlay_start = pe.get_overlay_data_start_offset() or len(original)
    overlay = original[overlay_start:]
    tail = max(pe.sections, key=lambda s:s.VirtualAddress)
    assert tail.Name.rstrip(b'\0') in (b'.xdiff', b'.celdial')
    assert tail.PointerToRawData+tail.SizeOfRawData == overlay_start
    align = lambda n,a:(n+a-1)//a*a
    rva = tail.VirtualAddress+align(max(tail.Misc_VirtualSize, tail.SizeOfRawData), 16)
    bridge = base+rva
    code = emit(args.node, c['frame'], c['top'], bridge)
    offset = tail.PointerToRawData+rva-tail.VirtualAddress
    raw_size = align(offset-tail.PointerToRawData+len(code), pe.OPTIONAL_HEADER.FileAlignment)
    end = tail.PointerToRawData+raw_size
    data = bytearray(original[:overlay_start])
    data.extend(bytes(end-len(data)))
    data.extend(overlay)
    data[offset:offset+len(code)] = code
    allowed = []

    def change(pos, replacement, label):
        data[pos:pos+len(replacement)] = replacement
        allowed.append((pos, len(replacement), label))

    def put(pos, value, label):
        change(pos, struct.pack('<I', value), label)

    virtual_size = rva-tail.VirtualAddress+len(code)
    delta = raw_size-tail.SizeOfRawData
    for pos, value in [
        (tail.get_file_offset()+8, virtual_size),
        (tail.get_file_offset()+16, raw_size),
        (tail.get_file_offset()+36, tail.Characteristics | 0xE0000060),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'), align(rva+len(code), pe.OPTIONAL_HEADER.SectionAlignment)),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'), pe.OPTIONAL_HEADER.SizeOfCode+delta),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfInitializedData'), pe.OPTIONAL_HEADER.SizeOfInitializedData+delta),
        (pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum'), 0),
    ]:
        put(pos, value, 'PE allocation metadata')
    cert = pe.OPTIONAL_HEADER.DATA_DIRECTORY[4]
    if cert.Size:
        assert cert.VirtualAddress >= overlay_start
        put(cert.get_file_offset(), cert.VirtualAddress+end-overlay_start, 'Overlay certificate offset')
    change(pe.get_offset_from_rva(hook-base), b'\xe8'+struct.pack('<i', bridge-hook-5), 'Celestial frame call')
    put(pe.get_offset_from_rva(record+4+FIELDS.index('bridge')*4), bridge, 'Celestial bridge record')
    restored = bytearray(data[:overlay_start])
    for pos, size, _ in allowed:
        restored[pos:pos+size] = original[pos:pos+size]
    assert restored == original[:overlay_start], 'Unrelated existing bytes changed'
    assert data[end:] == overlay
    final = pefile.PE(data=bytes(data))
    assert final.get_data(bridge-base, len(code)) == code
    imports = lambda p:[(d.dll, [(i.name, i.ordinal, i.address) for i in d.imports]) for d in p.DIRECTORY_ENTRY_IMPORT]
    assert imports(final) == imports(pe)
    assert contract(final)[0] == {**c, 'bridge':bridge}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    report = dict(source=str(args.source.resolve()), source_sha256=digest(original),
                  candidate=str(args.output.resolve()), candidate_sha256=digest(data),
                  bridge=bridge, bridge_size=len(code), allowed_changes=allowed,
                  unrelated_bytes_preserved=True, overlay_preserved=True,
                  imports_preserved=True, deployed=False, live_visual_accepted=False)
    args.output.with_suffix('.preservation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
