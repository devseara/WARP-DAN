"""Verify UniformSpriteRHW statically and through real WARP exports.

Static gate: the emitter tail, the v0/v1-only alpha sort key and the census of
emitter call sites still match the profile the patch was proven against.
Export gate: the patch alone changes exactly 0x00C4A5B1..0x00C4A5B5, and it
composes with ClanBodySkins (both orders, former bridge site stock) and with
AllowDualCustomWeaponSprites (Z-only helper at 0x00C4A647 kept).
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import tempfile
import pefile
from build_native_act_job_ui import ROOT, ORIGINAL
from verify_native_act_job_ui_warp import fixture_at, export
from verify_clan_body_skins import verify as verify_clan, HOOKS as CLAN_HOOKS

QJS = ROOT / 'Scripts/Patches/UniformSpriteRHW.qjs'
SITE, NOP = 0xC4A5B1, bytes.fromhex('0f1f440000')
EMITTER, SHADOW_WRAPPER = 0xC4A0D0, 0xC4A670
FORMER_CLAN_SITE, FORMER_CLAN_BYTES = 0xC4A63E, bytes.fromhex('8b45d80b8824010000')
DUAL_DEPTH_SITE = 0xC4A647
# 0x00550B10 alpha queues key on (v0.rhw + v1.rhw) / 2, or v0.rhw at 0x00550D0F.
SORT_KEY = bytes.fromhex('f30f10400cf30f5c402c')
SORT_KEY_SITES = 6
EMITTER_CALLS, SHADOW_CALLS = 34, 5


def image(pe, data):
    def read(va, n):
        off = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
        return data[off:off + n]
    return read


def code_sections(pe):
    return [s for s in pe.sections if s.Characteristics & 0x20000000]


def call_census(pe):
    counts = {EMITTER: 0, SHADOW_WRAPPER: 0}
    for s in code_sections(pe):
        raw = s.get_data()[:s.Misc_VirtualSize]
        start = pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress
        for i in range(len(raw) - 4):
            if raw[i] == 0xE8:
                dst = (start + i + 5 + struct.unpack_from('<i', raw, i + 1)[0]) & 0xFFFFFFFF
                if dst in counts:
                    counts[dst] += 1
    return counts


def static_gate():
    integration = integration_gate()
    text = QJS.read_bytes()
    assert text.startswith(b'/*') and b'\n' not in text.replace(b'\r\n', b''), 'QJS must be CRLF without BOM'
    tail = int(re.search(rb'UniformSpriteRHW\.tail = 0x([0-9A-F]+);', text).group(1), 16)
    tail_hex = bytes.fromhex(re.search(rb"UniformSpriteRHW\.tailHex = '([0-9a-f]+)';", text).group(1).decode())
    assert int(re.search(rb'UniformSpriteRHW\.site = 0x([0-9A-F]+);', text).group(1), 16) == SITE
    pe = pefile.PE(str(ORIGINAL)); data = ORIGINAL.read_bytes(); read = image(pe, data)
    assert read(tail, len(tail_hex)) == tail_hex, 'Emitter tail differs from the patch signature'
    assert read(SITE, 5) == bytes.fromhex('f30f1055e0')
    sort_sites = data[pe.get_offset_from_rva(0x550B10 - 0x400000):][:0x2D0].count(SORT_KEY)
    assert sort_sites == SORT_KEY_SITES, f'Alpha sort key sites changed: {sort_sites}'
    census = call_census(pe)
    assert census == {EMITTER: EMITTER_CALLS, SHADOW_WRAPPER: SHADOW_CALLS}, census
    return dict(tail=hex(tail), tail_bytes=len(tail_hex), sort_key_sites=sort_sites,
                emitter_calls=census[EMITTER], shadow_wrapper_calls=census[SHADOW_WRAPPER],
                integration=integration)


def integration_gate():
    """Catch the missing-source/profile and reused-ID regression before export."""
    entries = re.findall(r'^([0-9]+)\s*:\s*(\w+)\s*$',
                         (ROOT / 'Tables/Patch.yml').read_text(encoding='utf-8'), re.M)
    assert len(entries) == len({n for n, _ in entries}), 'Duplicate patch ID'
    catalog = {name: int(number) for number, name in entries}
    required = {'GrayMap': 388, 'CelestialDial': 389,
                'UniformSpriteRHW': 390, 'FloorSafeSpriteDepth': 391}
    # Older unrelated symbols have compatibility aliases; these four must not.
    assert all(sum(symbol == name for _, symbol in entries) == 1 for name in required)
    assert all(catalog.get(name) == number for name, number in required.items()), required
    profile = (ROOT / 'profiles/2025-07-16 PROFILE MAIN.yml').read_text(encoding='utf-8')
    selected = re.findall(r'^\s*-\s+(\w+)\s*$', profile, re.M)
    tree = (ROOT / 'Patches/Special.yml').read_text(encoding='utf-8')
    for name in ['UniformSpriteRHW', 'FloorSafeSpriteDepth']:
        assert selected.count(name) == 1, f'MAIN must select {name} exactly once'
        assert re.search(r'^\s*- ' + name + r':\s*$', tree, re.M), f'Missing tree entry: {name}'
        assert (ROOT / 'Scripts/Patches' / (name + '.qjs')).is_file(), name
    for name in ['Scripts/Patches/ClanBodySkins.qjs', 'tools/build_clan_skin_runtime.py',
                 'tools/verify_clan_body_skins.py', 'tools/verify_clan_release_warp.py']:
        text = (ROOT / name).read_text(encoding='utf-8')
        assert not re.search(r'preparePerspective|installPerspective|clan_perspective|perspective\.bin', text), name
    assert not (ROOT / 'Inputs/ClanBodySkins/perspective.bin').exists()
    assert not (ROOT / 'Inputs/ClanBodySkins/perspective.json').exists()
    assert not (ROOT / 'profiles/2025-07-16 PROFILE RIFTLOCK CLASSIC NPC.yml').exists()
    return dict(patch_ids=required,main_selects_both=True,legacy_clan_owner_removed=True)


def changed_code(source, target):
    a, b = pefile.PE(str(source)), pefile.PE(str(target))
    out = []
    for s in code_sections(a):
        before = s.get_data()[:s.Misc_VirtualSize]
        after = b.get_data(s.VirtualAddress, len(before))
        out += [0x400000 + s.VirtualAddress + i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    return out, b


def check_target(target, extra_allowed=(), any_other=False):
    changed, pe = changed_code(ORIGINAL, target)
    read = image(pe, target.read_bytes())
    assert read(SITE, 5) == NOP, 'UniformSpriteRHW NOP missing'
    if any_other:
        return read, changed
    allowed = set(range(SITE, SITE + 5))
    for va, n in extra_allowed:
        allowed.update(range(va, va + n))
    stray = [hex(va) for va in changed if va not in allowed]
    assert not stray, f'Unexpected native code changes: {stray[:16]}'
    return read, changed


def run(out=None):
    report = dict(static=static_gate(), cases=[], live_tested=False)
    out = out or Path(tempfile.mkdtemp(prefix='uniform-sprite-rhw-', dir=ROOT / 'Outputs'))
    fixture = fixture_at(out)
    clan_writes = [(va, size) for va, size, _ in CLAN_HOOKS]
    cases = [('rhw-only', ['UniformSpriteRHW']),
             ('clan-only', ['ClanBodySkins']),
             ('clan-first', ['ClanBodySkins', 'UniformSpriteRHW']),
             ('rhw-first', ['UniformSpriteRHW', 'ClanBodySkins']),
             ('dual-weapon', ['AllowDualCustomWeaponSprites', 'UniformSpriteRHW'])]
    for name, patches in cases:
        target = export(fixture, out / name, ORIGINAL, patches)
        row = dict(case=name, patches=patches, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        if name == 'rhw-only':
            _, changed = check_target(target)
            assert changed == list(range(SITE, SITE + 5)), changed
            row['native_changed'] = [hex(va) for va in changed]
        elif name == 'clan-only':
            clan = verify_clan(target, source=ORIGINAL, verbose=False)
            read = image(pefile.PE(str(target)), target.read_bytes())
            assert read(SITE, 5) == bytes.fromhex('f30f1055e0'), 'ClanBodySkins must not own RHW'
            assert read(FORMER_CLAN_SITE, 9) == FORMER_CLAN_BYTES
            row.update(unrelated_native_code_unchanged=clan['unrelated_native_code_unchanged'])
        elif name.startswith(('clan-', 'rhw-')):
            clan = verify_clan(target, verbose=False)
            allocations = [(int(clan['payload_va'], 16), clan['payload_bytes'])]
            allocations += [(clan['native_api'][i + 1], size + 5) for i, (_, size, _) in enumerate(CLAN_HOOKS)]
            read, _ = check_target(target, clan_writes + allocations)
            assert read(FORMER_CLAN_SITE, 9) == FORMER_CLAN_BYTES, 'Former clan RHW bridge site is not stock'
        else:
            read, _ = check_target(target, any_other=True)
            assert read(DUAL_DEPTH_SITE, 1) == b'\xe9', 'Dual-weapon Z helper hook missing'
            row['dual_weapon_depth_hook'] = hex(DUAL_DEPTH_SITE)
        report['cases'].append(row)
        print('PASS ' + name, flush=True)
    report['status'] = 'source_and_export_verified'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-only', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = dict(static=static_gate(), live_tested=False) if args.static_only else run()
    print(json.dumps(result, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2), encoding='utf8')
