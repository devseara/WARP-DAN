"""V48 death routing and standard native Rod/Staff family support."""

import argparse
from pathlib import Path
import struct
import build_mounted_mage_attachments as base


def scope(c, reg):
    mod = {'eax': 'b8', 'esi': 'be', 'edi': 'bf'}[reg]
    for raw, op in [
        ('80' + mod + 'cc02000000', '74'),
        ('83' + mod + '5c02000002', '75'),
        ('83' + mod + 'c804000002', '75'),
        ('83' + mod + '6002000000', '75'),
    ]:
        c.hex(raw).farbranch(op, 'stock')


def supported(c, reg, incoming=False):
    # Preserve all non-family item-specific sprite identities through native
    # fallback. Rod/Staff1601..1609 share the native 롯드 resource family.
    if incoming:
        c.hex('8b5514')
    else:
        c.hex(
            {
                'eax': '8b9040040000',
                'esi': '8b9640040000',
                'edi': '8b9740040000',
                'ebx': '8b9340040000',
            }[reg]
        )
    c.hex('81fab1040000').branch('74', 'weapon_allowed')
    c.hex('81ea4106000083fa08').farbranch('77', 'stock')
    c.label('weapon_allowed')
    if incoming:
        c.hex('837d1800')
    else:
        c.hex('83' + {'eax': 'b8', 'esi': 'be', 'edi': 'bf', 'ebx': 'bb'}[reg] + '4404000000')
    c.farbranch('75', 'stock')


def string_return(c, label, ext, stem):
    raw = ('sprite\\인간족\\여우마법사\\여우마법사_여_' + stem + '.' + ext).encode('cp949')
    c.hex('5a8b4c240451c70100000000c7411000000000c741140f000000')
    c.hex('68' + struct.pack('<I', len(raw)).hex()).pointer('68', label)
    c.link('e8', 0x4F1940).hex('58c21800')
    return raw


def specifications():
    specs = base.specifications()
    out = []
    for old in specs:
        name = old['name']
        c = base.Code()
        if name == 'appearance weapon loading':
            c.hex('52')
            scope(c, 'edi')
            supported(c, 'edi', True)
            c.hex('5a').link('e9', 0xD3EA23)
            c.label('stock').hex('5a3887cc020000').branch('75', 'blocked').link('e9', 0xD3EA23)
            c.label('blocked').link('e9', 0xD3EA75)
        elif name == 'equipment weapon loading':
            c.hex('52')
            scope(c, 'esi')
            supported(c, 'esi')
            c.hex('5a').link('e9', 0xD40472)
            c.label('stock').hex('5a80becc02000000').branch('75', 'blocked').link('e9', 0xD40472)
            c.label('blocked').link('e9', 0xD4112E)
        elif name == 'main mounted weapon drawing':
            c.hex('528b473c')
            scope(c, 'eax')
            supported(c, 'eax')
            c.hex('83fe05').farbranch('75', 'stock')
            c.hex('5a').link('e9', 0x604338)
            c.label('stock').hex('5a8b473c80b8cc02000001').branch('75', 'draw').link('e9', 0x604540)
            c.label('draw').link('e9', 0x604338)
        elif name.startswith('mounted dagger '):
            ext = 'act' if ' act ' in name else 'spr'
            target = 0xD8A010 if ext == 'act' else 0xD8A160
            c.hex('52')
            scope(c, 'esi')
            supported(c, 'esi')
            c.hex('81be40040000b1040000').farbranch('75', 'rod')
            knife = string_return(c, 'knife_file', ext, '단검')
            c.label('rod')
            rod = string_return(c, 'rod_file', ext, '롯드')
            c.label('stock').hex('5a').link('e9', target)
            c.label('knife_file')
            c.raw.extend(knife + b'\0')
            c.label('rod_file')
            c.raw.extend(rod + b'\0')
        elif name == 'mount transition weapon refresh':
            c.hex(
                '558bec53568bd90fb6b1cc0200008a4508ffb1540400008881cc0200008b01ff50708bc63a4508'
            ).farbranch('74', 'stock')
            for raw in ['83bb5c02000002', '83bbc804000002', '83bb6002000000']:
                c.hex(raw).farbranch('75', 'stock')
            supported(c, 'ebx')
            c.hex('ffb344040000ffb3400400008bcb8b03ff5060')
            c.label('stock').hex('5e5b8be55dc20400')
        else:
            out.append(old)
            continue
        out.append(
            dict(name=name, site=old['site'], kind=old['kind'], stock=old['stock'], **c.finish())
        )
    return out


def build(source, out):
    original = base.specifications
    patch = base.ROOT / 'Scripts/Patches/MountedMageAttachments.qjs'
    active = patch.read_bytes()
    try:
        rows = specifications()
        base.specifications = lambda: rows
        base.sync_qjs()
        candidate_qjs = patch.read_bytes()
        report = base.build(source, out)
        (out / 'MountedMageAttachments-candidate.qjs').write_bytes(candidate_qjs)
        return report
    finally:
        base.specifications = original
        patch.write_bytes(active)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    build(args.source.resolve(), args.out.resolve())
