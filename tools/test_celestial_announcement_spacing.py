"""Execute the announcement-position bridge with the real Celestial runtime.

Native UI/network boundaries use the existing explicit Unicorn doubles. This
checks positioning and preservation, not live visual acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile
from unicorn.x86_const import *
from test_celestial_dial import Machine


class BridgeMachine(Machine):
    def __init__(self, path):
        self.hooks = {}
        super().__init__(path)
        self.u.hook_del(self.hooks[0xA79710])
        self.expected = None
        self.tails = 0
        self.stub(0xA79710, self.native_tail)
        self.top_balloon = self.alloc(0xB4)
        self.middle_balloon = self.alloc(0xB4)
        self.u.mem_write(self.top_balloon, bytes(range(0xB4)))
        self.u.mem_write(self.middle_balloon, bytes(reversed(range(0xB4))))
        self.w(self.mode + 0x61C, self.top_balloon)
        self.w(self.mode + 0x620, self.middle_balloon)
        self.middle_before = bytes(self.u.mem_read(self.middle_balloon, 0xB4))
        site = bytes(self.u.mem_read(0xC74FB0, 5))
        assert site[0] == 0xE8
        assert 0xC74FB5 + struct.unpack('<i', site[1:])[0] == self.c['bridge']

    def stub(self, pc, fn):
        result = super().stub(pc, fn)
        self.hooks[pc] = result
        return result

    def native_tail(self):
        for reg, value in self.expected.items():
            assert self.u.reg_read(reg) == value, ('native tail register/flags', reg)
        self.tails += 1
        self.ret(0, 0x13579BDF)

    def bridge(self, y, null_mode=False, null_balloon=False):
        before = bytearray(self.u.mem_read(self.top_balloon, 0xB4))
        self.w(self.mode + 0x61C, 0 if null_balloon else self.top_balloon)
        sp = 0x4000F000
        self.u.mem_write(sp, struct.pack('<I', 0x41000000))
        self.expected = {
            UC_X86_REG_EAX: 0x12345678, UC_X86_REG_ECX: 0x12135F0,
            UC_X86_REG_EDX: 0x23456789, UC_X86_REG_EBX: 0 if null_mode else self.mode,
            UC_X86_REG_ESI: 0x456789AB, UC_X86_REG_EDI: 0x56789ABC,
            UC_X86_REG_EBP: 0x6789ABCD, UC_X86_REG_ESP: sp,
            UC_X86_REG_EFLAGS: 0x247,
        }
        for reg, value in self.expected.items():
            self.u.reg_write(reg, value)
        tails = self.tails
        self.u.emu_start(self.c['bridge'], 0x41000000, count=15000000)
        assert self.u.reg_read(UC_X86_REG_EIP) == 0x41000000
        assert self.u.reg_read(UC_X86_REG_ESP) == sp + 4
        assert self.u.reg_read(UC_X86_REG_EAX) == 0x13579BDF
        assert self.tails == tails + 1
        if not null_mode and not null_balloon:
            struct.pack_into('<I', before, 0x20, y)
        assert bytes(self.u.mem_read(self.top_balloon, 0xB4)) == bytes(before), 'top balloon changed beyond Y'
        assert bytes(self.u.mem_read(self.middle_balloon, 0xB4)) == self.middle_before, 'middle balloon changed'


def checks(path):
    m = BridgeMachine(path)
    m.bridge(51)  # Waiting for first server snapshot retains native placement.
    assert len(m.sent) == 1 and m.r(m.c['top']) == 24
    m.receive(m.snapshot(protocol=6))
    m.bridge(114)
    obj = m.r(m.c['state'])
    assert m.r(obj + 0x20) + 98 + 8 == m.r(m.top_balloon + 0x20)
    for width, height in [(800, 600), (1024, 768), (1920, 1080), (3440, 1440)]:
        m.w(m.renderer + 0x28, width)
        m.w(m.renderer + 0x2C, height)
        m.bridge(114)
        assert m.r(obj + 0x1C) == (width - 280) // 2
    m.w(m.renderer + 0x28, 200)
    m.bridge(51)
    assert not m.r(obj + 0x28)
    m.w(m.renderer + 0x28, 1280)
    m.bridge(114)
    m.bridge(114, null_balloon=True)
    m.bridge(114)
    for packet_id in (0x91, 0x92):
        old_cookie = m.r(m.c['state'] + 12)
        old_snapshot = m.snapshot(protocol=6, push=True)
        m.invoke(m.r(0xCAA2E0 + (packet_id - 0x73) * 4))
        m.bridge(51)
        assert m.r(m.c['state'] + 12) != old_cookie
        m.receive(old_snapshot)
        m.bridge(51)
        m.receive(m.snapshot(protocol=6))
        m.bridge(114)
    m.now += 90001
    m.bridge(51)
    assert not m.r(obj + 0x28)
    m.receive(m.snapshot(protocol=6))
    m.bridge(114)
    m.bridge(0, null_mode=True)
    assert m.r(m.c['top']) == 24
    m.bridge(51)
    m.receive(m.snapshot(protocol=6))
    m.bridge(114)
    m.w(m.mode, 0)
    m.bridge(51)
    return {'exe': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'native_frames': m.tails, 'passed': True}


def preservation(receipt_path):
    r = json.loads(receipt_path.read_text())
    before = Path(r['source']).read_bytes()
    after = Path(r['candidate']).read_bytes()
    assert hashlib.sha256(before).hexdigest() == r['source_sha256']
    assert hashlib.sha256(after).hexdigest() == r['candidate_sha256']
    a, b = pefile.PE(data=before), pefile.PE(data=after)
    end = a.get_overlay_data_start_offset() or len(before)
    restored = bytearray(after[:end])
    for offset, size, _ in r['allowed_changes']:
        restored[offset:offset + size] = before[offset:offset + size]
    assert bytes(restored) == before[:end], 'unrelated existing bytes changed'
    assert a.get_overlay() == b.get_overlay(), 'overlay changed'
    def imports(pe):
        return [(entry.dll.decode(), [(symbol.name, symbol.ordinal, symbol.address)
                                    for symbol in entry.imports]) for entry in pe.DIRECTORY_ENTRY_IMPORT]
    assert imports(a) == imports(b), 'imports changed'
    return {'receipt': str(receipt_path.resolve()), 'hashes_verified': True,
            'unrelated_bytes_preserved': True, 'overlay_preserved': True, 'imports_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', nargs='+', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = {'scope': 'announcement spacing and native frame preservation only',
              'cases': [checks(path) for path in args.exe], 'live_visual_accepted': False}
    if args.receipt:
        report['preservation'] = preservation(args.receipt)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
