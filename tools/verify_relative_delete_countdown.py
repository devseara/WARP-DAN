"""Execute the real 2025 card Draw, including clear/date/string/draw ordering.

OS time, texture services, message lookup, string formatting and final text
rasterization are boundary doubles. Card control flow, date loads, relative
conversion, native coordinates, SEH cleanup and stack are real x86.
This verifies native integration, not live visual acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

CARD, OWNER, RECORD, DATA, STACK, STOP = (0x40000000, 0x40001000, 0x40002000,
                                        0x40003000, 0x50000000, 0x60000000)
NOW = 1792305000
SEEDS = {UC_X86_REG_EBX: 0x11111111, UC_X86_REG_ESI: 0x22222222,
         UC_X86_REG_EDI: 0x33333333, UC_X86_REG_EBP: 0x44444444}


class Machine:
    def __init__(self, path):
        self.pe = pefile.PE(str(path))
        self.u = u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0, 0x1000)
        u.mem_map(0x400000, (self.pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        u.mem_write(0x400000, self.pe.get_memory_mapped_image())
        for address, size in ((CARD, 0x40000), (STACK, 0x10000), (STOP, 0x1000)):
            u.mem_map(address, size)
        self.w(0x121333C, OWNER)
        self.w(OWNER, 0x10932F0)
        self.w(0x10932F0 + 0x18, STOP + 0x100)
        self.w(0xFC1B68, STOP + 0x110)
        self.w(0x15FFD5C, 1)
        self.w(CARD, 0x102ED38)
        self.w(CARD + 0x14, 161)
        self.w(CARD + 0x18, 197)
        self.w(CARD + 0x24, DATA + 0x1000)
        self.w(CARD + 0x120, 3)
        self.w(CARD + 0x128, 2)
        self.w(CARD + 0x12C, 3)
        u.mem_write(DATA, b'Deletable on: %02d/%02d\0')
        u.mem_write(DATA + 0x80, b'%02d:%02d:%02d\0')
        self.now, self.slot = NOW, 3
        self.drawn, self.events, self.constructed, self.destroyed = [], [], [], []
        self.has_record = True
        self.heap = DATA + 0x2000
        u.hook_add(UC_HOOK_CODE, self.hook)

    def w(self, at, value):
        self.u.mem_write(at, struct.pack('<I', value & 0xFFFFFFFF))

    def d(self, at):
        return struct.unpack('<I', self.u.mem_read(at, 4))[0]

    def args(self, count):
        return list(struct.unpack('<' + 'I' * count,
                    self.u.mem_read(self.u.reg_read(UC_X86_REG_ESP) + 4, count * 4)))

    def ret(self, count=0, value=0):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        self.u.reg_write(UC_X86_REG_EIP, self.d(sp))
        self.u.reg_write(UC_X86_REG_ESP, sp + 4 + count * 4)
        self.u.reg_write(UC_X86_REG_EAX, value)

    def z(self, pointer):
        return bytes(self.u.mem_read(pointer, 128)).split(b'\0')[0].decode('ascii')

    def hook(self, u, pc, size, unused):
        receiver = u.reg_read(UC_X86_REG_ECX)
        if pc == STOP:
            u.emu_stop()
        elif pc == 0xA1CB30:
            assert receiver == CARD and self.args(1) == [0xFFFF00FF]
            self.events.append('native_card_clear')
            self.drawn.clear()
            self.ret(1)
        elif pc == 0x823E10:
            assert receiver == CARD
            self.events.append('native_card_background')
            self.ret()
        elif pc == STOP + 0x100:
            assert receiver == OWNER
            message, index, a, b, c = self.args(5)
            assert (message, index, a, b, c) == (8, self.slot, 0, 0, 0)
            self.ret(5, RECORD if self.has_record else 0)
        elif pc == STOP + 0x110:
            assert self.args(1) == [0]
            self.events.append('scoped_relative_time')
            u.reg_write(UC_X86_REG_ECX, 0xBAD10001)
            u.reg_write(UC_X86_REG_EDX, 0xBAD10002)
            self.ret(value=self.now)
        elif pc == 0xA87170:
            self.ret(value=int(self.d(receiver) < self.now))
        elif pc == 0xA9ED30:
            message, = self.args(1)
            assert message in (0xC20, 0xD15)
            self.ret(value=DATA if message == 0xC20 else DATA + 0x80)
        elif pc == 0xA94930:
            out, fmt = self.args(2)
            pattern = self.z(fmt)
            values = self.args(2 + pattern.count('%'))[2:]
            raw = (pattern % tuple(values)).encode()
            u.mem_write(out, b'\0' * 24)
            if len(raw) < 16:
                u.mem_write(out, raw + b'\0')
                self.w(out + 20, 15)
            else:
                self.heap += 0x100
                self.w(out, self.heap)
                self.w(out + 20, len(raw))
                u.mem_write(self.heap, raw + b'\0')
            self.w(out + 16, len(raw))
            self.constructed.append(out)
            self.ret(value=out)
        elif pc == 0x4F08F0:
            assert receiver in self.constructed
            self.destroyed.append(receiver)
            self.ret()
        elif pc == 0xA21C90:
            text, length, font, height, bold, extra = self.args(6)
            assert receiver == CARD and (length, font, height, bold, extra) == (0, 0, 11, 0, 0)
            self.ret(6, len(self.z(text)) * 6)
        elif pc == 0xA25A70:
            x, y, text, length, font, height, color, bold, extra = self.args(9)
            shown = self.z(text)
            assert receiver == CARD and (length, font, height, bold, extra) == (0, 0, 11, 0, 0)
            assert x == 79 - len(shown) * 6 // 2
            assert y == 40 and color in (0xFF, 0xFF0000)
            self.events.append('native_card_time_draw')
            self.drawn.append({'slot': self.slot, 'text': shown, 'x': x, 'y': y, 'color': color})
            self.ret(9, 1)
        elif pc == 0xDBBBD4:
            self.ret()

    def record(self, date, name=b'wqeqwe'):
        raw = bytearray(279)
        raw[108:236] = name.ljust(128, b'\0')
        raw[242] = self.slot
        struct.pack_into('<I', raw, 262, date)
        self.u.mem_write(RECORD, bytes(raw))

    def run(self):
        self.events, self.constructed, self.destroyed = [], [], []
        self.drawn = [{'text': 'old_parent_overlay'}]
        sp = STACK + 0x8000
        self.w(sp, STOP)
        for reg, value in SEEDS.items():
            self.u.reg_write(reg, value)
        self.u.reg_write(UC_X86_REG_ESP, sp)
        self.u.reg_write(UC_X86_REG_ECX, CARD)
        self.u.emu_start(0x856E10, 0, count=100000)
        assert self.u.reg_read(UC_X86_REG_EIP) == STOP
        assert self.u.reg_read(UC_X86_REG_ESP) == sp + 4
        assert all(self.u.reg_read(reg) == value for reg, value in SEEDS.items())
        assert self.events.count('native_card_clear') == 1
        assert sorted(self.constructed) == sorted(self.destroyed)
        return self.drawn[:]


def verify(path, before=None):
    m = Machine(path)
    assert m.d(0x101D474) == 0x79D170, 'Parent overlay must be retired'
    assert m.d(0x8571CD) == m.d(0x79D411) == 0x106
    cases = []
    for slot in (0, 1, 3, 16):
        m.slot = slot
        m.w(CARD + 0x12C, slot)
        for name in (b'wqeqwe', b'N' * 127):
            m.record(NOW + 5, name)
            for elapsed, expected in [(0, '00:00:05'), (1, '00:00:04'), (4, '00:00:01'),
                                      (5, '00:00:00'), (6, '00:00:00')]:
                m.now = NOW + elapsed
                drawn = m.run()
                assert len(drawn) == 1 and drawn[0]['text'] == expected, drawn
                assert drawn[0]['color'] == (0xFF0000 if elapsed > 5 else 0xFF)
                assert m.events.index('native_card_clear') < m.events.index('native_card_time_draw')
                cases.append({'slot': slot, 'name_bytes': len(name), 'elapsed': elapsed,
                              'drawn': drawn, 'events': m.events[:]})
    m.now = NOW
    m.record(NOW + 90061)
    assert m.run()[0]['text'] == '25:01:01'
    m.record(0)
    assert m.run() == []
    m.has_record = False
    assert m.run() == []
    formatter = 0x85720F + struct.unpack('<i', m.u.mem_read(0x85720B, 4))[0]
    for date, expected in [(NOW + 5, (0, 0, 5)), (NOW, (0, 0, 0)),
                           (NOW - 1, (0, 0, 0)), (NOW + 90061, (25, 1, 1))]:
        sp, out = STACK + 0x8000, DATA + 0x800
        m.w(RECORD, date)
        m.u.mem_write(out - 4, b'G' * 24)
        m.w(sp, STOP)
        m.w(sp + 4, out)
        for reg, value in SEEDS.items():
            m.u.reg_write(reg, value)
        m.u.reg_write(UC_X86_REG_ESP, sp)
        m.u.reg_write(UC_X86_REG_ECX, RECORD)
        m.u.emu_start(formatter, 0, count=1000)
        raw = bytes(m.u.mem_read(out - 4, 24))
        assert raw[:4] == raw[-4:] == b'GGGG'
        assert struct.unpack_from('<3H', raw, 10) == expected
        assert m.d(RECORD) == date and m.u.reg_read(UC_X86_REG_EAX) == out
        assert m.u.reg_read(UC_X86_REG_ESP) == sp + 8
        assert all(m.u.reg_read(reg) == value for reg, value in SEEDS.items())
    negative = None
    if before:
        old = Machine(before)
        old.record(NOW + 5)
        assert old.run() == [], 'Old card should erase the overlay and miss the queued date'
        negative = {'reproduced_missing_native_date': True, 'parent_overlay_erased_by_card_clear': True,
                    'sha256': hashlib.sha256(before.read_bytes()).hexdigest()}
    return {'passed': True, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'vectors': cases, 'negative_control': negative, 'expired_clamps_to_zero': True,
            'real_card_clear_and_draw_order': True, 'native_string_cleanup_and_x86_abi': True,
            'both_name_lengths_and_pagination': True, 'converter_bounds': True,
            'live_acceptance': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pe', required=True, type=Path)
    ap.add_argument('--before', type=Path)
    ap.add_argument('--report', required=True, type=Path)
    args = ap.parse_args()
    result = verify(args.pe, args.before)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS real card Draw: clear/background/date/relative-time/text ordering, '
          '5/4/1/0 countdown, expiry colors, 127-byte names, slot mapping, cleanup and ABI')
