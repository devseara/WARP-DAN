"""Execute real character-select footer instructions on canonical login records.

First runs the existing complete native page/create/delete consumer regression.
Then executes preview normalization, slot selection, resource-gender loads, and
the selected-character stat/map loads from the PE (no rewritten instruction model).
The old PE must reproduce the live slot/gender/stat mismatch.
"""
import argparse
import hashlib
import json
import runpy
import struct
import sys
from pathlib import Path

# Load optional isolated dependencies before importing the emulator.
bootstrap = argparse.ArgumentParser(add_help=False)
bootstrap.add_argument('--deps', type=Path)
dependency_args, _ = bootstrap.parse_known_args()
if dependency_args.deps:
    sys.path.insert(0, str(dependency_args.deps.resolve()))

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS

ROOT = Path(__file__).resolve().parents[1]
RECORD = 0x40000000
GENDER_READS = [0x79c88e, 0x79c8f3, 0x79c964, 0x79c9cb, 0x79ca38, 0x79caa3,
                0x79cb0b, 0x79cb80, 0x79cc01, 0x79cc6c, 0x79cd0f, 0x79cd9b, 0x79ce12]
STAT_READS = [0x79f304, 0x79f34c, 0x79f394, 0x79f3dc, 0x79f424, 0x79f46c]


def emulator(path):
    pe = pefile.PE(str(path), fast_load=True)
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    u.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
    u.mem_write(0x400000, pe.get_memory_mapped_image())
    u.mem_map(RECORD, 0x3000)
    u.reg_write(UC_X86_REG_ESP, RECORD + 0x2800)
    return u


def one(u, pc, reg, pointer_reg=UC_X86_REG_EDI):
    u.reg_write(pointer_reg, RECORD)
    u.emu_start(pc, 0, count=1)
    return u.reg_read(reg)


def fixture(name, slot, sex):
    raw = bytearray(279)
    struct.pack_into('<I', raw, 0, 5 + slot)
    struct.pack_into('<H', raw, 84, 4013)
    raw[108:236] = name.ljust(128, b'\0')
    raw[236:242] = bytes([99, 83, 67, 51, 35, 19])
    raw[242] = slot
    raw[246:262] = b'prontera.rsw'.ljust(16, b'\0')
    struct.pack_into('<II', raw, 262, 123456, 11)
    raw[278] = sex
    return bytes(raw)


def game_start(u, raw, account_sex):
    u.mem_write(RECORD, raw)
    u.mem_write(0x15fb23c, bytes([account_sex]))
    u.reg_write(UC_X86_REG_ESI, RECORD)
    stack = u.reg_read(UC_X86_REG_ESP)
    u.emu_start(0x79d71c, 0x79d73c, count=40)
    assert u.reg_read(UC_X86_REG_EIP) == 0x79d73c
    assert u.reg_read(UC_X86_REG_ESP) == stack
    a = struct.unpack('<I', u.mem_read(0x15fb238, 4))[0]
    b = struct.unpack('<I', u.mem_read(0x15ff8f8, 4))[0]
    assert a == b
    return a


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--deps', type=Path)
    ap.add_argument('--before', type=Path, required=True)
    ap.add_argument('--pe', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    saved = sys.argv
    sys.argv = ['verify_character_info_pe.py', '--pe', str(args.pe), '--deps', str(args.deps.resolve()) if args.deps else '']
    native = runpy.run_path(str(ROOT / 'tools/verify_character_info_pe.py'))
    sys.argv = saved
    old, fixed = emulator(args.before), emulator(args.pe)
    regression = []
    for name, slot, sex in [(b'LOUIS T STEINHIL', 0, 1), (b'weqweqweqw', 1, 0)]:
        old.mem_write(RECORD, fixture(name, slot, sex))
        regression.append({'name': name.decode(), 'expected_slot': slot, 'expected_gender': sex,
                           'old_slot': one(old, 0x79c761, UC_X86_REG_ECX),
                           'old_gender': one(old, 0x79c88e, UC_X86_REG_EAX),
                           'old_str': one(old, 0x79f304, UC_X86_REG_EAX, UC_X86_REG_EBX),
                           'old_game_start_gender': game_start(old, fixture(name, slot, sex), 1)})
    assert [r['old_slot'] for r in regression] == [0, 0]
    assert [r['old_gender'] for r in regression] == [0, 0]
    assert [r['old_str'] for r in regression] == [0, 0]
    assert [r['old_game_start_gender'] for r in regression] == [0, 0]
    cases = 0
    n = native['Native']()
    for name in [b'LOUIS T STEINHIL', b'weqweqweqw', b'A' * 127, b'B' * 66 + b'c' + b'B' * 60]:
        for slot in [0, 1, 8, 14, 67]:
            for sex in [0, 1, 99]:
                for account_sex in [0, 1]:
                    raw = fixture(name, slot, sex)
                    # Reach the UI through the actual native paginated record copy.
                    n.u.mem_write(native['OBJECT'] + 0x1cc, b'\0' * 16)
                    n.u.mem_write(0x15fb23c, bytes([account_sex]))
                    n.run(0xd205f0, struct.pack('<HH', 0xb72, 283) + raw)
                    canonical = bytes(n.u.mem_read(native['OBJECT'] + native['ARRAY'], 279))
                    expected_sex = account_sex if sex == 99 else sex
                    assert canonical[:278] == raw[:278] and canonical[278] == expected_sex
                    fixed.mem_write(RECORD, canonical)
                    # Exercise the UI's own compatibility normalization as well.
                    fixed.mem_write(RECORD + 278, bytes([sex]))
                    fixed.mem_write(0x15fb23c, bytes([account_sex]))
                    fixed.reg_write(UC_X86_REG_EDI, RECORD)
                    fixed.emu_start(0x79c646, 0x79c65b, count=20)
                    assert fixed.reg_read(UC_X86_REG_EIP) == 0x79c65b
                    assert fixed.mem_read(RECORD + 278, 1)[0] == expected_sex
                    assert bytes(fixed.mem_read(RECORD + 108, 128)) == raw[108:236], 'Preview must never write into name'
                    assert one(fixed, 0x79c761, UC_X86_REG_ECX) == slot
                    for pc in GENDER_READS:
                        assert one(fixed, pc, UC_X86_REG_EAX) == expected_sex, hex(pc)
                    assert one(fixed, 0x79f1c9, UC_X86_REG_ECX, UC_X86_REG_EBX) == expected_sex
                    for pc, expected in zip(STAT_READS, raw[236:242]):
                        assert one(fixed, pc, UC_X86_REG_EAX, UC_X86_REG_EBX) == expected
                    assert one(fixed, 0x79f4b9, UC_X86_REG_EAX, UC_X86_REG_EBX) == RECORD + 246
                    assert one(fixed, 0x79c81b, UC_X86_REG_EAX) == 11
                    fixed.reg_write(UC_X86_REG_EDI, RECORD)
                    fixed.emu_start(0x79c828, 0, count=1)
                    assert not fixed.reg_read(UC_X86_REG_EFLAGS) & 0x40
                    assert one(fixed, 0x8eeed0, UC_X86_REG_ECX, UC_X86_REG_ESI) == slot
                    assert one(fixed, 0x8eeefa, UC_X86_REG_EAX, UC_X86_REG_ESI) == 11
                    for pc, reg in [(0x79abf1, UC_X86_REG_EDX), (0x79d30e, UC_X86_REG_EDI)]:
                        stack = fixed.reg_read(UC_X86_REG_ESP)
                        one(fixed, pc, UC_X86_REG_EAX, reg)
                        assert struct.unpack('<I', fixed.mem_read(stack - 4, 4))[0] == 11
                        fixed.reg_write(UC_X86_REG_ESP, stack)
                    one(fixed, 0x79d701, UC_X86_REG_EAX, UC_X86_REG_ESI)
                    assert not fixed.reg_read(UC_X86_REG_EFLAGS) & 0x40
                    # Actual initial card and repaint gender branches, including fallback.
                    fixed.mem_write(RECORD, raw)
                    fixed.reg_write(UC_X86_REG_EDX, RECORD)
                    fixed.emu_start(0x79abb6, 0x79abc9, count=10)
                    assert fixed.reg_read(UC_X86_REG_ESI) == expected_sex
                    fixed.reg_write(UC_X86_REG_EDI, RECORD)
                    fixed.reg_write(UC_X86_REG_EBX, RECORD + 0x1000)
                    fixed.reg_write(UC_X86_REG_ESI, slot)
                    fixed.emu_start(0x79d2c0, 0x79d2e0, count=15)
                    assert fixed.reg_read(UC_X86_REG_EAX) == expected_sex
                    assert game_start(fixed, raw, account_sex) == expected_sex
                    cases += 1
    # Execute the omitted complete native CHARACTER_INFO refresh (not only a load).
    refresh = native['Native']()
    u = refresh.u
    stub = native['STOP'] + 0x500
    owner = native['OBJECT']
    vtable = native['HEAP'] + 0x1000
    u.mem_write(0x121333c, struct.pack('<I', owner))
    u.mem_write(owner, struct.pack('<I', vtable))
    u.mem_write(vtable + 0x18, struct.pack('<I', stub))
    slots = []

    def getter(u, pc, size, data):
        if pc != stub:
            return
        sp = u.reg_read(UC_X86_REG_ESP)
        message, slot = struct.unpack('<II', u.mem_read(sp + 4, 8))
        assert message == 8 and slot in (0, 1)
        slots.append(slot)
        refresh.ret(5, owner + native['ARRAY'] + slot * 279)

    u.hook_add(UC_HOOK_CODE, getter)
    for slot in (0, 1):
        raw = fixture(b'Long refresh name ' + b'R' * 100, slot, 1 - slot)
        dest = owner + native['ARRAY'] + slot * 279
        u.mem_write(dest, raw[:4] + b'\xa5' * 275)
        u.mem_write(0x15ffcb4, raw[:4])
        refresh.run(0xd224c0, raw)
        assert bytes(u.mem_read(dest, 279)) == raw
    assert slots == [0, 1]
    report = {'schema': 'character_select_footer_execution/v1', 'before_sha256': hashlib.sha256(args.before.read_bytes()).hexdigest(),
              'pe_sha256': hashlib.sha256(args.pe.read_bytes()).hexdigest(), 'native_page_create_delete_passed': True,
              'footer_vectors': cases, 'original_bug_reproduced': regression,
              'native_game_start_gender_setter_passed': True, 'full_native_record_refresh_slots': slots,
              'full_name_preserved': True, 'live_visual_acceptance': False}
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS', cases, 'native parser + preview/footer vectors; old PE reproduces live corruption')


if __name__ == '__main__':
    main()
