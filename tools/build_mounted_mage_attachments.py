"""Build a review-only female Mage/Fox attachment client in an owned PE section."""

import argparse
import hashlib
import json
import struct
from pathlib import Path
import pefile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class Code:
    def __init__(self):
        self.raw = bytearray()
        self.labels = {}
        self.branches = []
        self.links = []

    def hex(self, s):
        self.raw.extend(bytes.fromhex(s))
        return self

    def label(self, s):
        self.labels[s] = len(self.raw)
        return self

    def branch(self, op, target):
        self.hex(op)
        self.branches.append((len(self.raw), target))
        self.raw.append(0)
        return self

    def farbranch(self, op, target):
        self.hex('0f' + format(int(op, 16) + 0x10, '02x'))
        self.branches.append((len(self.raw), target, 4))
        self.raw.extend(bytes(4))
        return self

    def link(self, op, target):
        self.hex(op)
        self.links.append(dict(offset=len(self.raw), target=target))
        self.raw.extend(bytes(4))
        return self

    def pointer(self, op, label):
        self.hex(op)
        self.links.append(dict(offset=len(self.raw), label=label, kind='local'))
        self.raw.extend(bytes(4))
        return self

    def finish(self):
        for branch in self.branches:
            off, target = branch[:2]
            if len(branch) == 3:
                struct.pack_into('<i', self.raw, off, self.labels[target] - off - 4)
            else:
                rel = self.labels[target] - off - 1
                assert -128 <= rel <= 127
                self.raw[off] = rel & 255
        for link in self.links:
            if 'label' in link:
                link['target'] = self.labels[link.pop('label')]
        return dict(hex=self.raw.hex(), links=self.links)


def eligible(c, reg):
    # Live V45 snapshot: +0x2C0 is 0 while the visible Mage class +0x25C
    # and body job +0x4C8 are both 2. Do not equate those class fields.
    mod = {'eax': 'b8', 'ebx': 'bb', 'esi': 'be', 'edi': 'bf'}[reg]
    c.hex('80' + mod + 'cc02000000').branch('74', 'stock')
    c.hex('83' + mod + '5c02000002').branch('75', 'stock')
    c.hex('83' + mod + 'c804000002').branch('75', 'stock')
    c.hex('83' + mod + '6002000000').branch('75', 'stock')


def legacy_specifications():
    def old(c, reg):
        mod = {'ebx': 'bb', 'esi': 'be', 'edi': 'bf'}[reg]
        c.hex('80' + mod + 'cc02000000').branch('74', 'stock')
        c.hex('83' + mod + 'c002000002').branch('75', 'stock')
        c.hex('83' + mod + '6002000000').branch('75', 'stock')

    c = Code()
    old(c, 'ebx')
    c.hex('8b4424048d50e083fa0f').branch('76', 'use')
    c.hex('8d50b883fa1f').branch('77', 'stock')
    c.label('use').hex('83e00789442404c744240800000000')
    c.label('stock').link('e9', 0x70F4B0)
    head = c.finish()
    c = Code()
    old(c, 'edi')
    c.link('e9', 0xD3EA23)
    c.label('stock').hex('3887cc020000').branch('75', 'blocked').link('e9', 0xD3EA23)
    c.label('blocked').link('e9', 0xD3EA75)
    appearance = c.finish()
    c = Code()
    old(c, 'esi')
    c.link('e9', 0xD40472)
    c.label('stock').hex('80becc02000000').branch('75', 'blocked').link('e9', 0xD40472)
    c.label('blocked').link('e9', 0xD4112E)
    weapon = c.finish()
    return [
        dict(name='mounted Mage head pose', site=0xD36676, kind='call', stock='e8358e9dff', **head),
        dict(
            name='appearance weapon loading',
            site=0xD3EA1B,
            kind='jump',
            stock='3887cc0200007552',
            **appearance,
        ),
        dict(
            name='equipment weapon loading',
            site=0xD40465,
            kind='jump',
            stock='80becc020000000f85bc0c0000',
            **weapon,
        ),
    ]


def combat(c, action_hex):
    c.hex(action_hex + '8d50e083fa0f').branch('76', 'combat')
    c.hex('8d50b883fa1f').branch('77', 'stock')
    c.label('combat')


def knife(c, reg):
    mod = {'eax': 'b8', 'esi': 'be', 'edi': 'bf'}[reg]
    c.hex('81' + mod + '40040000b1040000').branch('75', 'stock')
    c.hex('83' + mod + '4404000000').branch('75', 'stock')


def v46_specifications():
    # Main compositor's ACT-frame availability gate, with neutral head-frame
    # availability checked independently from the moving body frame.
    c = Code().hex('518b473c')
    eligible(c, 'eax')
    c.hex('8d56ff83fa03').branch('77', 'stock')
    combat(c, '8b0424')
    c.hex('83e0078904248b4db4').link('e8', 0x70F6B0)
    c.hex('8b4f3c85c0').branch('7e', 'skip').link('e9', 0x6043CD)
    c.label('stock').hex('8b4db4').link('e8', 0x70F6B0)
    c.hex('8b4f3c39413c').branch('7d', 'skip').link('e9', 0x6043CD)
    c.label('skip').link('e9', 0x604532)
    guard = c.finish()
    # Full selector contract: selected ACT frame plus action/frame override
    # outputs consumed by native headgear attachment calculation 0x605170.
    c = Code().hex('558bec538bd9')
    eligible(c, 'ebx')
    c.hex('8b45084883f803').branch('77', 'stock')
    combat(c, '8b4338')
    c.hex('83e0078b551089028b5514c702000000008b5518c60201')
    c.hex('8b4d0c6a0050').link('e8', 0x70F4B0)
    c.hex('5b8be55dc21400')
    c.label('stock').hex('8bcb5b8be55d').link('e9', 0xD36ED0)
    head = c.finish()
    # The native headgear phase-ratio pass may otherwise replace our selected
    # neutral frame after the primary selector has returned.
    c = Code().hex('8b473c')
    eligible(c, 'eax')
    c.hex('8d56ff83fa03').branch('77', 'stock')
    combat(c, '8b442404')
    c.hex('83e00789442404c744240800000000')
    c.label('stock').link('e9', 0x70F4B0)
    ratio = c.finish()
    # Separate draw gate: enable only the authored main weapon (part5).
    # Part6 is the native slash effect, not a shield; it has no mounted art.
    c = Code().hex('8b473c')
    eligible(c, 'eax')
    knife(c, 'eax')
    c.hex('83fe05').branch('75', 'stock').link('e9', 0x604338)
    c.label('stock').hex('8b473c80b8cc02000001').branch('75', 'draw').link('e9', 0x604540)
    c.label('draw').link('e9', 0x604338)
    draw = c.finish()
    c = Code()
    eligible(c, 'edi')
    # Full appearance refresh receives the new equipment in caller arguments;
    # CPlayer+0x440 may still be zero on initial spawn/relog.
    c.hex('817d14b1040000').branch('75', 'stock')
    c.hex('837d1800').branch('75', 'stock')
    c.link('e9', 0xD3EA23)
    c.label('stock').hex('3887cc020000').branch('75', 'blocked').link('e9', 0xD3EA23)
    c.label('blocked').link('e9', 0xD3EA75)
    appearance = c.finish()
    c = Code()
    eligible(c, 'esi')
    knife(c, 'esi')
    c.link('e9', 0xD40472)
    c.label('stock').hex('80becc02000000').branch('75', 'blocked').link('e9', 0xD40472)
    c.label('blocked').link('e9', 0xD4112E)
    weapon = c.finish()
    specs = [
        dict(
            name='head availability',
            site=0x6043B7,
            kind='jump',
            stock='518b4db4e8f0b210008b4f3c39413c7c05e965010000',
            **guard,
        ),
        dict(name='main head selection', site=0x6043E8, kind='call', stock='e8e32a7300', **head),
        dict(
            name='headgear phase selection', site=0x6044D9, kind='call', stock='e8d2af1000', **ratio
        ),
        dict(
            name='main mounted weapon drawing',
            site=0x604328,
            kind='jump',
            stock='8b473c80b8cc020000010f8408020000',
            **draw,
        ),
        dict(
            name='appearance weapon loading',
            site=0xD3EA1B,
            kind='jump',
            stock='3887cc0200007552',
            **appearance,
        ),
        dict(
            name='equipment weapon loading',
            site=0xD40465,
            kind='jump',
            stock='80becc020000000f85bc0c0000',
            **weapon,
        ),
    ]
    for ext, site, target in [
        ('act', 0xD40A6A, 0xD8A010),
        ('spr', 0xD40A92, 0xD8A160),
        ('act', 0xD40C3B, 0xD8A010),
        ('spr', 0xD40C95, 0xD8A160),
        ('act', 0xD40D8E, 0xD8A010),
        ('spr', 0xD40DE6, 0xD8A160),
    ]:
        c = Code()
        eligible(c, 'esi')
        knife(c, 'esi')
        c.hex('837c241001').branch('75', 'stock')  # native weapon class 1, dagger
        raw = ('sprite\\인간족\\여우마법사\\여우마법사_여_단검.' + ext).encode('cp949')
        c.hex('8b4c240451c70100000000c7411000000000c741140f000000')
        c.hex('68' + struct.pack('<I', len(raw)).hex()).pointer('68', 'filename')
        c.link('e8', 0x4F1940).hex('58c21800')
        c.label('stock').link('e9', target)
        c.label('filename')
        c.raw.extend(raw + b'\0')
        stock = (b'\xe8' + struct.pack('<i', target - site - 5)).hex()
        specs.append(
            dict(
                name=f'mounted dagger {ext} filename {site:X}',
                site=site,
                kind='call',
                stock=stock,
                **c.finish(),
            )
        )
    return specs


def v47_specifications():
    specs = v46_specifications()
    # Native SetAllRiding refreshes only the shield. Retain that exact work,
    # then refresh the current Knife through the real virtual equipment setter
    # when the mount byte changes, including the return to unmounted resources.
    c = Code().hex('558bec53568bd90fb6b1cc0200008a4508ffb1540400008881cc0200008b01ff5070')
    c.hex('8bc63a4508').branch('74', 'done')
    for raw in [
        '83bb5c02000002',
        '83bbc804000002',
        '83bb6002000000',
        '81bb40040000b1040000',
        '83bb4404000000',
    ]:
        c.hex(raw).branch('75', 'done')
    c.hex('ffb344040000ffb3400400008bcb8b03ff5060')
    c.label('done').hex('5e5b8be55dc20400')
    specs.append(
        dict(
            name='mount transition weapon refresh',
            site=0xD3E340,
            kind='jump',
            stock='558bec8a4508',
            **c.finish(),
        )
    )
    return specs


def v48_specifications():
    specs = v47_specifications()
    # CPlayer::SetAction(3) explicitly normalizes mounted classes to their
    # unmounted body before loading death resources, even while All_Riding
    # remains active. Route only these two female Fox-Mage body producers.
    for site, target, ext in [(0xD41E90, 0xD5B8E0, 'act'), (0xD41EE2, 0xD5BC30, 'spr')]:
        c = Code()
        eligible(c, 'edi')
        c.hex('837d0803').branch('75', 'stock')
        c.hex('c744240822100000')
        c.label('stock').link('e9', target)
        stock = (b'\xe8' + struct.pack('<i', target - site - 5)).hex()
        specs.append(
            dict(
                name='mounted death body ' + ext, site=site, kind='call', stock=stock, **c.finish()
            )
        )
    return specs


def specifications():
    return v48_specifications()


def sync_qjs():
    specs = specifications()
    original = (
        ROOT / '2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe'
    )
    assert (
        hashlib.sha256(original.read_bytes()).hexdigest()
        == 'ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff'
    )
    native_diff = original.read_bytes()[0xF55000:0xF55400].hex()
    template = ROOT / 'Scripts/Runtime/MountedMageAttachments/patch.qjs.in'
    text = template.read_text(encoding='utf-8')
    text = text.replace('__SPECS__', json.dumps(specs, indent='\t'))
    text = text.replace('__NATIVE_DIFF__', native_diff)
    target = ROOT / 'Scripts/Patches/MountedMageAttachments.qjs'
    target.write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))


def align(v, a):
    return (v + a - 1) // a * a


def build(source, out):
    assert not out.exists(), 'Use a fresh candidate directory.'
    raw = source.read_bytes()
    pe = pefile.PE(data=raw, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    normalized = bytearray(raw)
    restored = []
    v48 = next((s for s in pe.sections if s.Name.rstrip(b'\0') == b'.mgfix4'), None)
    v47 = next((s for s in pe.sections if s.Name.rstrip(b'\0') == b'.mgfix3'), None)
    v46 = next((s for s in pe.sections if s.Name.rstrip(b'\0') == b'.mgfix2'), None)
    legacy = (
        v48
        or v47
        or v46
        or next((s for s in pe.sections if s.Name.rstrip(b'\0') == b'.mgfix'), None)
    )
    if legacy is not None:
        # Restore only the three byte-exact owned V45 sites. Preserve all later
        # UI/name/deletion/weather sections added by other work.
        cursor = 0
        for s in (
            v48_specifications()
            if v48
            else (
                v47_specifications()
                if v47
                else v46_specifications() if v46 else legacy_specifications()
            )
        ):
            cursor = align(cursor, 16)
            va = base + legacy.VirtualAddress + cursor
            code = bytearray.fromhex(s['hex'])
            for f in s['links']:
                if f.get('kind') == 'local':
                    struct.pack_into('<I', code, f['offset'], va + f['target'])
                else:
                    struct.pack_into('<i', code, f['offset'], f['target'] - (va + f['offset'] + 4))
            assert pe.get_data(va - base, len(code)) == bytes(code), 'Unrecognized legacy payload'
            n = len(bytes.fromhex(s['stock']))
            opcode = b'\xe8' if s['kind'] == 'call' else b'\xe9'
            expected = opcode + struct.pack('<i', va - s['site'] - 5) + b'\x90' * (n - 5)
            assert pe.get_data(s['site'] - base, n) == expected, 'Unrecognized legacy hook'
            off = pe.get_offset_from_rva(s['site'] - base)
            normalized[off : off + n] = bytes.fromhex(s['stock'])
            restored.append(dict(site=s['site'], bytes=n))
            cursor += len(code)
    specs = specifications()
    payload = bytearray()
    hooks = []
    sa, fa = pe.OPTIONAL_HEADER.SectionAlignment, pe.OPTIONAL_HEADER.FileAlignment
    rva = align(
        max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData) for s in pe.sections), sa
    )
    assert base + rva >= base + pe.OPTIONAL_HEADER.SizeOfImage
    for s in specs:
        off = pe.get_offset_from_rva(s['site'] - base)
        assert normalized[off : off + len(bytes.fromhex(s['stock']))].hex() == s['stock'], s['name']
        payload.extend(bytes(align(len(payload), 16) - len(payload)))
        offset = len(payload)
        code = bytearray.fromhex(s['hex'])
        for f in s['links']:
            if f.get('kind') == 'local':
                struct.pack_into('<I', code, f['offset'], base + rva + offset + f['target'])
            else:
                struct.pack_into(
                    '<i', code, f['offset'], f['target'] - (base + rva + offset + f['offset'] + 4)
                )
        payload.extend(code)
        hooks.append(dict(**s, cave=base + rva + offset))
    clean = normalized
    header = pe.sections[-1].get_file_offset() + 40
    first = min(s.PointerToRawData for s in pe.sections if s.SizeOfRawData)
    shift = max(0, align(header + 40, fa) - first)
    assert (
        not pe.FILE_HEADER.PointerToSymbolTable
        and not pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].VirtualAddress
    )
    # Check raw-file pointer owners before growing headers.
    pe.parse_data_directories(directories=[6])
    assert not getattr(pe, 'DIRECTORY_ENTRY_DEBUG', [])
    if shift:
        clean[first:first] = bytes(shift)
        for s in pe.sections:
            assert not s.PointerToRelocations and not s.PointerToLinenumbers
            if s.SizeOfRawData:
                struct.pack_into(
                    '<I',
                    clean,
                    s.get_field_absolute_offset('PointerToRawData'),
                    s.PointerToRawData + shift,
                )
        struct.pack_into(
            '<I',
            clean,
            pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfHeaders'),
            align(header + 40, fa),
        )
    raw_start = align(len(clean), fa)
    raw_size = align(len(payload), fa)
    clean.extend(bytes(raw_start - len(clean)) + payload + bytes(raw_size - len(payload)))
    overlay = pe.get_overlay_data_start_offset()
    if overlay is not None:
        clean.extend(raw[overlay:])
    section_name = (
        b'.mgfix5'
        if v48
        else b'.mgfix4' if v47 else b'.mgfix3' if v46 else b'.mgfix2' if legacy else b'.mgfix'
    )
    clean[header : header + 40] = struct.pack(
        '<8sIIIIIIHHI', section_name, len(payload), rva, raw_size, raw_start, 0, 0, 0, 0, 0x60000020
    )
    struct.pack_into(
        '<H',
        clean,
        pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),
        pe.FILE_HEADER.NumberOfSections + 1,
    )
    struct.pack_into(
        '<I',
        clean,
        pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),
        align(rva + len(payload), sa),
    )
    struct.pack_into(
        '<I',
        clean,
        pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),
        pe.OPTIONAL_HEADER.SizeOfCode + raw_size,
    )
    allowed = {va for row in restored for va in range(row['site'], row['site'] + row['bytes'])}
    for h in hooks:
        va = h['site']
        n = len(h['stock']) // 2
        off = pe.get_offset_from_rva(va - base)
        off += shift if off >= first else 0
        clean[off : off + n] = (
            (b'\xe8' if h['kind'] == 'call' else b'\xe9')
            + struct.pack('<i', h['cave'] - va - 5)
            + b'\x90' * (n - 5)
        )
        allowed.update(range(va, va + n))
    out.mkdir(parents=True)
    candidate = out / 'client.exe'
    candidate.write_bytes(clean)
    new = pefile.PE(str(candidate), fast_load=True)
    changes = []
    for s in pe.sections:
        a = s.get_data()
        b = new.get_data(s.VirtualAddress, len(a))
        assert len(a) == len(b)
        for i in np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8)):
            va = base + s.VirtualAddress + int(i)
            assert va in allowed, hex(va)
            changes.append(hex(va))
    report = dict(
        status='review_candidate',
        installed=False,
        source=str(source),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        candidate=str(candidate),
        candidate_sha256=hashlib.sha256(clean).hexdigest(),
        section=section_name.decode(),
        isolated_payload=[hex(base + rva), hex(base + rva + len(payload))],
        all_other_existing_section_bytes_preserved=True,
        restored_legacy_hooks=restored,
        hooks=hooks,
        changed_existing_bytes=changes,
    )
    (out / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    pe.close()
    new.close()
    print('Built isolated review client:', candidate)
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--sync-qjs', action='store_true')
    a = ap.parse_args()
    if a.sync_qjs:
        sync_qjs()
    if a.source:
        build(a.source.resolve(), a.out.resolve())
