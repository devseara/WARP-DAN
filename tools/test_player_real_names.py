"""Execute the emitted EXTN cache and text code; no game or database is opened.

Pass a real-WARP client and the TextPackageProbe JSON from verify_text_packages.
Only platform text conversion/drawing APIs are mocked by TextMachine.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile
from verify_text_packages import TextMachine, require


def packet(version, name, kind=0, colored=True, full_name=None, social=True):
    if version == 4:
        size, offsets, type_offset = 657 if colored else 653, (140, 268, 396, 524), 652
    else:
        size, offsets, type_offset = 777 if colored else 773, (164, 292, 420, 548), 772
    data = bytearray(size)
    struct.pack_into('<HHII', data, 0, 0x0BB7, size, 0x4558544E, 2000001)

    def field(offset, value, capacity=128):
        raw = value.encode('utf-8')
        require(len(raw) < capacity, 'fixture field too long')
        data[offset:offset + len(raw)] = raw

    field(12, name, 128 if version == 4 else 24)
    if version == 3 and full_name is not None:
        field(36, full_name)
    values = ('new1', '1', 'GuildMaster', 'Admin') if social else ('', '', '', '')
    for offset, value in zip(offsets, values):
        field(offset, value)
    if version == 3:
        for offset, value in zip((676, 700, 724, 748), values):
            field(offset, value, 24)
    data[type_offset] = kind
    if colored:
        struct.pack_into('<I', data, type_offset + 1, 0x112233)
    return bytes(data)


def verify(client, snapshot):
    text = snapshot['text']
    machine = TextMachine(pefile.PE(str(client)))
    machine.measured = []

    def extent(args):
        value = bytes(machine.uc.mem_read(args[1], args[2] * 2)).decode('utf-16le')
        machine.measured.append(value)
        machine.uc.mem_write(args[3], struct.pack('<ii', len(value) * 7, 14))
        return 1

    machine.iat(0xFC112C, 16, extent)
    sequence = 0

    def receive(raw):
        nonlocal sequence
        slot = text['extnVir'] + 16 + (sequence & 1023) * 1024
        machine.uc.mem_write(slot, struct.pack('<I', len(raw)) + raw)
        sequence += 1
        machine.uc.mem_write(text['extnVir'] + 4, struct.pack('<I', sequence))
        machine.call(text['frameVir'], [])

    def lookup(key, expected, kind=0, entity=0, color=None):
        machine.uc.mem_write(0x29002000, key.encode('utf-8') + b'\0')
        row = machine.call(text['lookupVir'], [0x29002000])
        require(row != 0, f'missing cache entry: {key}')
        require(machine.ansi(row + 144) == expected,
                f'expected real name {expected!r}, got {machine.ansi(row + 144)!r}')
        require(machine.u32(row + 4) == kind and machine.u32(row + 8) == entity,
                'name metadata kind changed')
        if color is not None:
            require(machine.u32(row + 12) == color, 'name color changed')

    def draw(key, expected, color=0xFFFFFF, expected_color=0x332211):
        raw = key.encode('utf-16le')
        machine.uc.mem_write(0x29004000, raw + b'\0\0')
        machine.draws = []
        machine.color = color
        machine.call(text['textOutVir'], [1, 20, 30, 0x29004000, len(raw) // 2])
        require(machine.draws == [(expected, expected_color)], 'draw text/color mismatch')
        require(machine.color == color, 'HDC color was not restored')
        machine.measured = []
        machine.call(text['extentVir'], [1, 0x29004000, len(raw) // 2, 0x29005000])
        require(machine.measured == [expected], 'measurement used a different name')

    cases = []
    for colored in (True, False):
        receive(packet(4, 'DevSeara', colored=colored))
        lookup('DevSeara', 'DevSeara', color=0x332211 if colored else 0)
        draw('DevSeara', 'DevSeara', expected_color=0x332211 if colored else 0xFFFFFF)
        cases.append(f'V4 all tags present, color={colored}: real name drawn and measured')

    receive(packet(4, 'DevSeara'))
    for label in ('NPC name segment', 'character selection after map exit', 'overhead name', 'social name label'):
        # All these consumers share the same name text bridge. No refresh packet
        # is sent between draws, covering cached-name reuse at character select.
        draw('DevSeara', 'DevSeara')
        cases.append(label + ': cached value stays plain')
    draw('DevSeara', 'DevSeara', color=0, expected_color=0)
    cases.append('dark outline and foreground color restoration preserved')

    for value in ('Admin [Real]{Name}(One)', 'N' * 127, '勇者' * 20 + 'Alpha'):
        receive(packet(4, value))
        lookup(value, value, color=0x332211)
        draw(value, value)
    cases.append('literal punctuation, 127-byte names and Unicode preserved')

    for version in (3, 4):
        receive(packet(version, 'NoTags', social=False))
        lookup('NoTags', 'NoTags', color=0x332211)
        draw('NoTags', 'NoTags')
    cases.append('names without social fields preserved')

    for colored in (True, False):
        for full in (None, 'FullCanonical_' + 'N' * 90):
            expected = full or 'DevSeara'
            receive(packet(3, 'DevSeara', full_name=full, colored=colored))
            lookup('DevSeara', expected, color=0x332211 if colored else 0)
            draw('DevSeara', expected, expected_color=0x332211 if colored else 0xFFFFFF)
            if full:
                lookup(full, full)
                draw(full, full, expected_color=0x332211 if colored else 0xFFFFFF)
    cases.append('V3 canonical full-name alias and short-name fallback preserved')

    for version in (3, 4):
        receive(packet(version, 'MetadataOwner'))
        for kind, value in enumerate(('new1', '1', 'GuildMaster', 'Admin'), 1):
            lookup(value, value, kind=kind)
    cases.append('separate party, guild, position and title fields preserved')

    for kind in range(1, 8):
        for version in (3, 4):
            name = f'Entity{version}_{kind}'
            receive(packet(version, name, kind=kind))
            lookup(name, name, entity=kind, color=0x332211)
            draw(name, name, expected_color=0xFFFFFF)
    cases.append('monster, NPC, portal and companion names unaffected')

    draw('Ordinary dialogue text', 'Ordinary dialogue text', expected_color=0xFFFFFF)
    cases.append('unmatched dialogue unchanged; x86 stack/register checks pass')
    return {'passed': True, 'cases': cases, 'live_tested': False,
            'platform_text_apis_mocked': True,
            'client_sha256': hashlib.sha256(client.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', type=Path)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.client, json.loads(args.state.read_text(encoding='utf-8')))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    for case in result['cases']:
        print('PASS: ' + case)
