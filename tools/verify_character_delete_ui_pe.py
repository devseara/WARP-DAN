"""Execute Main 2025 deletion-reservation ACK and character-select UI code.

Uses the real PE instructions. Native time, UI methods and string services are
stubbed; no client/server is launched and no character/database is changed.
--expect-stale is a negative control for the pre-fix date consumers.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

bootstrap = argparse.ArgumentParser(add_help=False)
bootstrap.add_argument('--deps', type=Path)
dependency_args, _ = bootstrap.parse_known_args()
if dependency_args.deps:
    sys.path.insert(0, str(dependency_args.deps.resolve()))

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_ESI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP,
)

OWNER, UI, TABLE = 0x40000000, 0x40010000, 0x40018000
STACK, STOP, NOW = 0x60000000, 0x61000000, 1700000000
READS = {
    0x79AB17: ('8b 80 9e 00 00 00', '8b 80 06 01 00 00'),
    0x79AD50: ('8b 80 9e 00 00 00', '8b 80 06 01 00 00'),
    0x79D40F: ('8b 87 9e 00 00 00', '8b 87 06 01 00 00'),
    0x79D502: ('8b 80 9e 00 00 00', '8b 80 06 01 00 00'),
    0x79EFC0: ('83 bf 9e 00 00 00 00', '83 bf 06 01 00 00 00'),
    0x79F002: ('ff b7 9e 00 00 00', 'ff b7 06 01 00 00'),
    0x8571CB: ('8b 80 9e 00 00 00', '8b 80 06 01 00 00'),
}


class Native:
    def __init__(self, pe):
        self.u = u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0, 0x1000)  # native SEH registration at fs:[0]
        u.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        u.mem_write(0x400000, pe.get_memory_mapped_image())
        for address, size in ((OWNER, 0x20000), (STACK, 0x10000), (STOP, 0x1000)):
            u.mem_map(address, size)
        u.mem_write(0xFC1B68, struct.pack('<I', STOP + 0x100))
        self.dates, self.toggles = [], {}
        self.end = ()
        u.hook_add(UC_HOOK_CODE, self.hook)

    def words(self, address, count=1):
        return struct.unpack('<' + 'I' * count, self.u.mem_read(address, 4 * count))

    def ret(self, argc=0, value=0):
        u = self.u
        sp = u.reg_read(UC_X86_REG_ESP)
        pc = self.words(sp)[0]
        u.reg_write(UC_X86_REG_EAX, value)
        u.reg_write(UC_X86_REG_ESP, sp + 4 + argc * 4)
        u.reg_write(UC_X86_REG_EIP, pc)

    def hook(self, u, pc, size, unused):
        if pc in self.end:
            u.emu_stop()
        elif pc == STOP + 0x100:
            pointer = self.words(u.reg_read(UC_X86_REG_ESP) + 4)[0]
            u.mem_write(pointer, struct.pack('<q', NOW))
            self.ret(value=NOW)
        elif pc == 0xA87040:
            self.dates.append(self.words(u.reg_read(UC_X86_REG_ESP) + 4)[0])
            self.ret(1)
        elif pc == 0xA87170:
            self.ret(value=1)
        elif pc == 0xA87060:
            self.ret()
        elif pc == STOP + 0x200:
            self.ret()
        elif pc == STOP + 0x210:
            self.toggles[u.reg_read(UC_X86_REG_ECX)] = self.words(u.reg_read(UC_X86_REG_ESP) + 4)[0]
            self.ret(1)

    def run(self, start, end):
        self.end = end if isinstance(end, tuple) else (end,)
        self.u.emu_start(start, 0, count=10000)
        assert self.u.reg_read(UC_X86_REG_EIP) in self.end, 'native block did not finish'

    def reserve_ack(self, delay):
        u = self.u
        for index in (0, 1):
            raw = bytearray(279)
            struct.pack_into('<I', raw, 0, 1000 + index)
            raw[108:236] = b'Admin qweqw213'.ljust(128, b'\0')
            raw[242] = index
            u.mem_write(OWNER + 0x4068 + index * 279, bytes(raw))
        u.mem_write(OWNER + 0x1CC, struct.pack('<I', 2))
        packet = OWNER + 0x1A000
        u.mem_write(packet, struct.pack('<HIII', 0x828, 1001, 1, delay))
        u.reg_write(UC_X86_REG_EDI, OWNER)
        u.reg_write(UC_X86_REG_EBX, packet)
        u.reg_write(UC_X86_REG_EBP, STACK + 0x8000)
        u.reg_write(UC_X86_REG_ESP, STACK + 0x4000)
        before = bytes(u.mem_read(OWNER + 0x4068, 2 * 279))
        self.run(0xD2129F, 0xD213C3)
        assert u.reg_read(UC_X86_REG_ESP) == STACK + 0x4000
        record = OWNER + 0x4068 + 279
        after = bytearray(before)
        struct.pack_into('<I', after, 279 + 262, NOW + delay)
        assert bytes(u.mem_read(OWNER + 0x4068, 2 * 279)) == bytes(after)
        return record

    def select_ui(self, record):
        u = self.u
        request, confirm, cancel = UI + 0x1000, UI + 0x2000, UI + 0x3000
        u.mem_write(TABLE + 0x98, struct.pack('<I', STOP + 0x200))
        u.mem_write(TABLE + 0xD4, struct.pack('<I', STOP + 0x210))
        for field, button in ((0xC0, request), (0x100, confirm), (0xC4, cancel)):
            u.mem_write(UI + field, struct.pack('<I', button))
            u.mem_write(button, struct.pack('<I', TABLE))
        u.reg_write(UC_X86_REG_ESI, UI)
        u.reg_write(UC_X86_REG_EDI, record)
        u.reg_write(UC_X86_REG_EBP, STACK + 0x8000)
        u.reg_write(UC_X86_REG_ESP, STACK + 0x4000)
        self.run(0x79EFC0, (0x79F046, 0x79F084))
        assert u.reg_read(UC_X86_REG_ESP) == STACK + 0x4000
        return {'request_hidden': u.mem_read(request + 0xAC, 1)[0],
                'confirm_toggle': self.toggles[confirm],
                'cancel_toggle': self.toggles[cancel],
                'time_constructor_arguments': self.dates}

    def refresh_date_reads(self, record):
        values = []
        for pc, pointer_register in ((0x79AB17, UC_X86_REG_EAX), (0x79AD50, UC_X86_REG_EAX),
                                     (0x79D40F, UC_X86_REG_EDI), (0x79D502, UC_X86_REG_EAX),
                                     (0x8571CB, UC_X86_REG_EAX)):
            self.u.reg_write(pointer_register, record)
            self.u.emu_start(pc, 0, count=1)
            values.append(self.u.reg_read(UC_X86_REG_EAX))
        return values

    def preview_reservation(self, record):
        """Run the alternate native preview refresh through its date branch."""
        self.dates = []
        preview = OWNER + 0x1B000
        self.u.mem_write(preview, b'\0' * 0x15C)
        self.u.mem_write(UI + 0x108, struct.pack('<I', preview))
        self.u.mem_write(UI + 0x120, struct.pack('<I', 1))
        self.u.mem_write(STACK + 0x8008, struct.pack('<I', record))
        self.u.reg_write(UC_X86_REG_ESI, UI)
        self.u.reg_write(UC_X86_REG_EDI, 0)
        self.u.reg_write(UC_X86_REG_EBP, STACK + 0x8000)
        self.u.reg_write(UC_X86_REG_ESP, STACK + 0x4000)
        self.run(0x79AD45, (0x79ADD4, 0x79AE11))
        assert self.u.reg_read(UC_X86_REG_ESP) == STACK + 0x4000
        result = {'date_arguments': self.dates[:], 'preview_flags': self.words(preview + 0x148, 2)}
        self.dates = []
        return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--deps', type=Path)
    ap.add_argument('--pe', required=True, type=Path)
    ap.add_argument('--report', required=True, type=Path)
    ap.add_argument('--expect-stale', action='store_true')
    args = ap.parse_args()
    pe = pefile.PE(str(args.pe))
    assert pe.FILE_HEADER.Machine == 0x14C
    for address, variants in READS.items():
        expected = bytes.fromhex(variants[0 if args.expect_stale else 1])
        assert pe.get_data(address - 0x400000, len(expected)) == expected, hex(address)
    vectors = []
    for delay in (0, 86400):
        native = Native(pe)
        record = native.reserve_ack(delay)
        reads = native.refresh_date_reads(record)
        assert reads == [0 if args.expect_stale else NOW + delay] * 5
        preview = native.preview_reservation(record)
        assert preview['preview_flags'] == ((0, 0) if args.expect_stale else (16, 16))
        assert preview['date_arguments'] == ([] if args.expect_stale else [NOW + delay])
        state = native.select_ui(record)
        expected = {'request_hidden': 0, 'confirm_toggle': 0, 'cancel_toggle': 0,
                    'time_constructor_arguments': []} if args.expect_stale else {
                        'request_hidden': 1, 'confirm_toggle': 1, 'cancel_toggle': 1,
                        'time_constructor_arguments': [NOW + delay]}
        assert state == expected, state
        vectors.append({'delay': delay, 'ack_date': NOW + delay, 'refresh_reads': reads,
                        'preview': preview, 'ui': state})
    # Long names can instead make the old date look like arbitrary ASCII bytes.
    native = Native(pe)
    record = native.reserve_ack(0)
    native.u.mem_write(record + 108, b'N' * 127 + b'\0')
    reads = native.refresh_date_reads(record)
    assert reads == [0x4E4E4E4E if args.expect_stale else NOW] * 5
    state = native.select_ui(record)
    assert state['time_constructor_arguments'] == [0x4E4E4E4E if args.expect_stale else NOW]
    vectors.append({'name_bytes': 127, 'refresh_reads': reads, 'ui': state})
    native = Native(pe)
    record = native.reserve_ack(0)
    native.u.mem_write(record + 262, b'\0' * 4)
    assert native.refresh_date_reads(record) == [0, 0, 0, 0, 0]
    state = native.select_ui(record)
    assert state == {'request_hidden': 0, 'confirm_toggle': 0, 'cancel_toggle': 0,
                     'time_constructor_arguments': []}
    vectors.append({'reserved': False, 'ui': state})
    # Result zero is the server's already-queued response. Both before/after
    # clients correctly select generic error 0x718; the translation was wrong.
    native = Native(pe)
    packet = OWNER + 0x1A000
    native.u.mem_write(packet, struct.pack('<HIII', 0x828, 1001, 0, 0))
    native.u.mem_write(STACK + 0x8008, struct.pack('<I', packet))
    native.u.reg_write(UC_X86_REG_EBP, STACK + 0x8000)
    native.u.reg_write(UC_X86_REG_ESP, STACK + 0x4000)
    native.run(0xD2126B, 0xD21286)
    assert native.words(native.u.reg_read(UC_X86_REG_ESP))[0] == 0x718
    vectors.append({'reservation_result': 0, 'native_message_id': '0x718'})
    result = {'pe': str(args.pe.resolve()),
              'sha256': hashlib.sha256(args.pe.read_bytes()).hexdigest(),
              'negative_control': args.expect_stale, 'passed': True, 'vectors': vectors,
              'live_acceptance': False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(('REPRODUCED stale UI' if args.expect_stale else 'PASS corrected UI') +
          ': native 0x0828 ACK followed by real character-selection controls; '
          'zero/day delay and 127-byte name; stack and record bounds preserved')


if __name__ == '__main__':
    main()
