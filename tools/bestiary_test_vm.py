"""Verify the exported Bestiary x86, including behavioral ABI/lifecycle tests.

Native engine boundaries are deliberately mocked. This establishes emitted
code behavior and ownership, not native SPR rendering or live UI acceptance.
Requires pefile and unicorn in the analysis Python environment.
"""
from __future__ import annotations
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EFLAGS)

S = dict(window=0, tab=4, detail=156, tracked=160, selected=32, count=52, pressed=68, hover=72, focused=84,
         length=88, due=92, pending=96, edit=116, race=120, popup=124, rows=132)


class VM:
    def __init__(self, pe, manifest):
        self.m = manifest
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        mapped = pe.get_memory_mapped_image()
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.u.mem_map(self.base, (len(mapped) + 4095) & ~4095)
        self.u.mem_write(self.base, mapped)
        self.u.mem_map(0x60000000, 0x200000)
        self.stop, self.stack, self.heap = 0x60000000, 0x60008000, 0x60010000
        self.stubs, self.calls, self.focus, self.capture, self.now = {}, [], 0, 0, 1000
        self.native_text = self.alloc(128)
        self.state = manifest['state']['vir']
        self.window = self.alloc(0xB4)
        self.u.mem_write(self.window, struct.pack('<I', manifest['vtable']['vir']))
        self.u.mem_write(self.window + 0x28, b'\1')
        self.set('window', self.window)
        self.stub(0xA33100, 0, lambda ecx, args: self.focus)
        self.stub(0xA4B760, 4, self.set_focus)
        self.stub(0xA32E00, 0, lambda ecx, args: self.capture)
        self.stub(0xA482E0, 0, self.release_capture)
        self.stub(0x8210A0, 0, lambda ecx, args: self.native_text)
        self.stub(0xA90350, 0, lambda ecx, args: 0x60000100)
        self.stub(0xA8D4A0, 4, lambda ecx, args: 0x60000200)
        self.stub(0xA1DC80, 36)
        self.stub(0x86E240, 4)
        self.stub(0x880AD0, 8, self.mouse_down)
        self.stub(0x880BB0, 8, self.mouse_up)
        self.stub(0x880CB0, 8)
        self.stub(0x5A8AF0, 4)
        self.stub(0x60000010, 0, lambda ecx, args: self.now)
        self.write32(manifest['timeGetTimeIat'], 0x60000010)
        self.u.hook_add(UC_HOOK_CODE, self.step)

    def alloc(self, size):
        address = self.heap
        self.heap += (size + 15) & ~15
        return address

    def write32(self, address, value):
        self.u.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def read32(self, address):
        return struct.unpack('<I', self.u.mem_read(address, 4))[0]

    def set(self, field, value):
        self.write32(self.state + S[field], value)

    def get(self, field):
        return self.read32(self.state + S[field])

    def string(self, value):
        data = value.encode('ascii') if isinstance(value, str) else value
        address = self.alloc(len(data) + 1)
        self.u.mem_write(address, data + b'\0')
        return address

    def cstring(self, address):
        out = bytearray()
        for i in range(256):
            b = self.u.mem_read(address + i, 1)[0]
            if not b:
                return bytes(out)
            out.append(b)
        raise AssertionError('Unterminated native string')

    def stub(self, address, pop, handler=None):
        self.stubs[address] = (pop, handler)
        self.u.mem_write(address, b'\xc2' + struct.pack('<H', pop) if pop else b'\xc3')

    def step(self, uc, address, size, context):
        if address == self.stop:
            uc.emu_stop()
        if address not in self.stubs:
            return
        pop, handler = self.stubs[address]
        esp, ecx = uc.reg_read(UC_X86_REG_ESP), uc.reg_read(UC_X86_REG_ECX)
        args = [self.read32(esp + 4 + i) for i in range(0, pop, 4)]
        self.calls.append((address, ecx, args))
        result = handler(ecx, args) if handler else 1
        uc.reg_write(UC_X86_REG_EAX, (result or 0) & 0xffffffff)
        # Native calls may destroy all volatile registers. Tests must not rely
        # on a helpful mock preserving ECX/EDX across thiscall or stdcall.
        uc.reg_write(UC_X86_REG_ECX, 0xCAFE0001)
        uc.reg_write(UC_X86_REG_EDX, 0xCAFE0002)

    def set_focus(self, ecx, args):
        self.focus = args[0]

    def release_capture(self, ecx, args):
        self.capture = 0

    def mouse_down(self, ecx, args):
        self.capture = ecx

    def mouse_up(self, ecx, args):
        self.capture = 0

    def run(self, key, args=(), ecx=None, pop=None):
        entry = self.m[key]['vir'] if isinstance(key, str) else key
        esp = self.stack
        self.u.mem_write(esp, struct.pack('<I', self.stop) + b''.join(struct.pack('<I', x & 0xffffffff) for x in args))
        saved = {UC_X86_REG_EBX: 0xBEEFBEEF, UC_X86_REG_ESI: 0xABABABAB,
                 UC_X86_REG_EDI: 0xCDCDCDCD, UC_X86_REG_EBP: 0xEFEFEFEF}
        for reg, value in saved.items():
            self.u.reg_write(reg, value)
        self.u.reg_write(UC_X86_REG_ESP, esp)
        self.u.reg_write(UC_X86_REG_ECX, self.window if ecx is None else ecx)
        self.u.reg_write(UC_X86_REG_EFLAGS, 0x202)
        self.u.emu_start(entry, self.stop, count=1000000)
        assert self.u.reg_read(UC_X86_REG_ESP) == esp + 4 + (len(args) * 4 if pop is None else pop), key
        assert all(self.u.reg_read(reg) == value for reg, value in saved.items()), f'{key}: nonvolatile register clobber'
        return self.u.reg_read(UC_X86_REG_EAX)

    def filter(self, query='', race=0):
        self.u.mem_write(self.m['query']['vir'], query.encode() + b'\0')
        self.set('race', race)
        self.run('filter', [0] * 4)
        return [self.read32(self.state + S['rows'] + i * 4) for i in range(self.get('count'))]


def verify_dispatch(pe, manifest):
    # Exact 2025 GetNoParamTalkType fallback patched by CustomSlashCommand.
    base = pe.OPTIONAL_HEADER.ImageBase
    entry = 0x00D5CDF4
    assert pe.get_data(entry - base, 1) == b'\xe9'
    target = manifest['bestiary']['toggle']['vir'] if manifest.get('bestiary') else manifest['previousToggle']
    active = bool(manifest.get('bestiary'))
    for command in (b'/bestiary', b'/bestiary_extra', b'/not_registered'):
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        mapped = pe.get_memory_mapped_image()
        u.mem_map(base, (len(mapped) + 4095) & ~4095)
        u.mem_write(base, mapped)
        u.mem_map(0x60000000, 0x10000)
        stop, ebp, esp, caller, text = 0x60000000, 0x60008000, 0x60007FEC, 0x60008100, 0x60008200
        def w(address, value):
            u.mem_write(address, struct.pack('<I', value))
        w(esp, 0x11111111); w(esp + 4, 0x22222222)
        w(ebp, caller); w(ebp + 4, stop); w(ebp + 8, text); w(caller + 4, 0x12345678)
        u.mem_write(text, command + b'\0')
        u.reg_write(UC_X86_REG_ESP, esp); u.reg_write(UC_X86_REG_EBP, ebp)
        hits = []
        if active:
            u.mem_write(target, b'\xc3')
        def step(uc, address, size, user):
            if address == target:
                assert active, 'dispatcher reached a removed Bestiary cave'
                hits.append(address)
            if address == stop:
                uc.emu_stop()
        u.hook_add(UC_HOOK_CODE, step)
        u.emu_start(entry, stop, count=10000)
        expected = active and command == b'/bestiary'
        assert len(hits) == int(expected)
        assert u.reg_read(UC_X86_REG_EAX) == (0 if expected else 3)
        assert u.reg_read(UC_X86_REG_ESP) == ebp + 12
        assert u.reg_read(UC_X86_REG_EDI) == 0x11111111
        assert u.reg_read(UC_X86_REG_ESI) == 0x22222222
        assert u.reg_read(UC_X86_REG_EBP) == caller

