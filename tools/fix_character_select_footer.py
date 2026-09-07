"""Apply the guarded CharacterNamesStatic footer correction to an existing PE.

Preserves all other patches, including injected sections and the EOF overlay.
Does not modify or launch the supplied source executable.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]


def footer_edits():
    source = (ROOT / 'Scripts/Patches/CharacterNamesStatic.qjs').read_text()
    block = source.split('// Character-select footer consumers', 1)[1].split('CharacterNamesStatic.SelectedRefs', 1)[0]
    return [(int(a, 16), bytes.fromhex(b), bytes.fromhex(c)) for a, b, c in
            re.findall(r'\[(0x[0-9A-F]+),"([0-9A-F ]+)","([0-9A-F ]+)"\]', block)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--expected-sha256', required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    original = args.source.read_bytes()
    assert hashlib.sha256(original).hexdigest() == args.expected_sha256
    assert args.source.resolve() != args.output.resolve()
    pe = pefile.PE(data=original, fast_load=True)
    assert pe.FILE_HEADER.Machine == 0x14c and pe.OPTIONAL_HEADER.ImageBase == 0x400000
    assert pe.get_data(0xd2060d - 0x400000, 5) == bytes.fromhex('be 17 01 00 00'), 'Requires canonical 279-byte parser'
    result = bytearray(original)
    allowed = set()
    evidence = []
    edits = footer_edits()
    assert len(edits) == 37
    for va, before, after in edits:
        offset = pe.get_offset_from_rva(va - 0x400000)
        assert len(before) == len(after) and original[offset:offset + len(before)] == before, hex(va)
        result[offset:offset + len(before)] = after
        allowed.update(range(offset, offset + len(before)))
        evidence.append({'va': hex(va), 'file_offset': offset, 'before': before.hex(' '), 'after': after.hex(' ')})
    checksum_at = pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum')
    result[checksum_at:checksum_at + 4] = pefile.PE(data=bytes(result), fast_load=True).generate_checksum().to_bytes(4, 'little')
    allowed.update(range(checksum_at, checksum_at + 4))
    assert len(result) == len(original)
    changed = [i for i, (a, b) in enumerate(zip(original, result)) if a != b]
    assert set(changed) <= allowed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    report = {'schema': 'character_select_footer_fix/v1', 'source': str(args.source.resolve()),
              'source_sha256': args.expected_sha256, 'output': str(args.output.resolve()),
              'output_sha256': hashlib.sha256(result).hexdigest(), 'instruction_count': len(edits),
              'changed_byte_count_including_checksum': len(changed),
              'all_other_bytes_identical': True, 'edits': evidence}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'edits'}, indent=2))


if __name__ == '__main__':
    main()
