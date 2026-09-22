"""Run emitted BPUI plain-name x86, with explicit native/GDI boundary doubles.

Validates the two call sites, canonical names, bounded reads/fitting, configured
font, DC restoration and x86 ABI. This is offline evidence, not a live screenshot.
Works with BattlepassUI alone; does not require Gacha or shared EXTN hooks.
"""
import argparse
from pathlib import Path
import struct

from PIL import ImageFont
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.x86_const import UC_X86_REG_ECX
from test_modern_chat_ui import Machine, pack


def contract(m):
    data = m.pe.get_memory_mapped_image()
    marker = data.find(b'BattlepassUI.PlainName.v1\0')
    assert marker >= 0, 'Battle Pass plain-name fix missing'
    key = pack(m.base + marker)
    positions = []
    start = 0
    while (start := data.find(key, start)) >= 0:
        positions.append(start)
        start += 1
    assert len(positions) == 1, positions
    return dict(zip(('state', 'draw', 'plain', 'height', 'offset', 'capacity'),
                    struct.unpack_from('<6I', data, positions[0] + 4)))


class NameMachine(Machine):
    def stub(self, address, fn):
        if address in self.boundaries:
            self.u.hook_del(self.boundaries[address])
        self.boundaries[address] = self.u.hook_add(
            UC_HOOK_CODE, lambda u, a, s, d: fn(), begin=address, end=address)

    def __init__(self, exe):
        self.boundaries = {}
        super().__init__(exe, Path('.'))
        self.c = contract(self)
        self.font = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', self.c['height'])
        self.drawn = []
        self.surface_ok = True
        self.convert_ok = True
        self.measure_ok = True
        self.color = 0x123456
        self.selected_font = 88
        self.released = 0
        self.font_calls = 0
        self.source_spans = []
        self.shared_calls = []

        def shared_text():
            self.shared_calls.append(self.args(9))
            raise AssertionError('Plain player name entered shared decorated TextDraw')

        self.stub(0xA25A70, shared_text)
        self.stub(0x5443C0, self.context)
        self.stub(0x546F60, self.setup_font)
        self.stub(0x546270, lambda: self.ret(20, 99))
        self.stub(0x5446F0, self.release)
        for iat, fn in [(0xFC1200, self.convert), (0xFC1120, self.select_font),
                        (0xFC112C, self.extent), (0xFC10E0, self.set_color),
                        (0xFC10DC, self.draw_text)]:
            boundary = self.alloc(16)
            self.stub(boundary, fn)
            self.w(iat, boundary)

    def context(self):
        ptr = self.u.reg_read(UC_X86_REG_ECX)
        self.w(ptr, self.args(1)[0] if self.surface_ok else 0)
        self.saved_font = self.selected_font
        self.ret(4, ptr)

    def setup_font(self):
        assert self.args(4) == [0, self.c['height'], 0, 0], self.args(4)
        self.font_calls += 1
        self.ret(16)

    def select_font(self):
        dc, font = self.args(2)
        old = self.selected_font
        self.selected_font = font
        self.ret(8, old)

    def release(self):
        self.released += 1
        self.selected_font = self.saved_font  # native wrapper restores original font
        self.ret(0)

    def convert(self):
        cp, flags, source, length, dest, capacity = self.args(6)
        assert cp == 65001 and flags == 0 and 0 < length < self.c['capacity']
        self.source_spans.append((source, length))
        data = bytes(self.u.mem_read(source, length)).decode('utf-8', errors='replace').encode('utf-16le')
        assert len(data) // 2 <= capacity
        self.u.mem_write(dest, data)
        self.ret(24, len(data) // 2 if self.convert_ok else 0)

    def wide(self, ptr, count):
        return bytes(self.u.mem_read(ptr, count * 2)).decode('utf-16le')

    def extent(self):
        dc, ptr, count, out = self.args(4)
        name = self.wide(ptr, count)  # strict: dangling surrogates fail here
        self.w(out, int(self.font.getlength(name)))
        self.w(out + 4, self.c['height'])
        self.ret(16, int(self.measure_ok))

    def set_color(self):
        dc, color = self.args(2)
        old = self.color
        self.color = color
        self.ret(8, old)

    def draw_text(self):
        dc, x, y, ptr, count = self.args(5)
        self.drawn.append((self.wide(ptr, count), x, y, self.color))
        self.ret(20, 1)

    def name(self, obj, raw, x=92, y=57, width=526):
        src = self.c['state'] + self.c['offset']
        self.u.mem_write(src, raw.ljust(24, b'\0') + b'NEIGHBOR_MUST_NOT_BE_READ\0')
        self.drawn = []
        self.invoke(self.c['plain'], 0, (obj, src, x, y, width, 0x965B35))
        assert self.color == 0x123456 and self.selected_font == 88
        assert not self.shared_calls
        return self.drawn


def verify(exe):
    m = NameMachine(exe)
    c = m.c
    assert c['capacity'] == 24 and c['offset'] == 52
    # Decode actual draw call sites: [color, width, y, x, BPUI.player], push esi,
    # call the private helper. Names must not go through the decorated renderer.
    start = c['draw'] - m.base
    code = m.pe.get_memory_mapped_image()[start:start + 65536]
    instructions = []
    for ins in m.cs.disasm(code, c['draw']):
        instructions.append(ins)
        if ins.mnemonic.startswith('ret'):
            break
    assert instructions[-1].mnemonic.startswith('ret'), 'Incomplete BPUI draw routine'
    sites = []
    for i, ins in enumerate(instructions):
        if ins.mnemonic == 'call' and ins.op_str == hex(c['plain']):
            pushed = instructions[i-6:i]
            assert all(p.mnemonic == 'push' for p in pushed)
            assert pushed[-1].op_str == 'esi'
            values = [int(p.op_str, 0) for p in pushed[:-1]]
            assert values[0] == 0x965B35 and values[4] == c['state'] + c['offset']
            sites.append(tuple(values[1:4]))
    assert sorted(sites) == [(141, 52, 643), (526, 57, 92)], sites
    assert code.count(pack(c['state'] + c['offset'])) >= 2

    obj = m.window(796, 510)
    for width, y, x in sites:
        assert m.name(obj, b'DevSeara', x, y, width) == [('DevSeara', x, y, 0x965B35)]
    for value in ('Alice', 'Admin', 'test', 'GuildMaster', 'Admin test', 'Jos\u00e9', '\u30bd\u30e9', 'Dev\U0001f600Seara'):
        assert m.name(obj, value.encode())[0][0] == value, value
    for width in (0, 1, 10, 20, 35, 70, 141, 526):
        for name in ('W' * 23, 'Dev\U0001f600Seara'):
            drawn = m.name(obj, name.encode(), width=width)
            if drawn:
                shown = drawn[0][0]
                assert name.startswith(shown) and int(m.font.getlength(shown)) <= width
    # Guard the 24-byte snapshot field even for a malformed, unterminated name.
    src = c['state'] + c['offset']
    def guard(u, access, address, size, value, user):
        assert address + size <= src + 23, (address, size)
    hook = m.u.hook_add(UC_HOOK_MEM_READ, guard, begin=src, end=src + 47)
    assert m.name(obj, b'A' * 24)[0][0] == 'A' * 23
    m.u.hook_del(hook)
    assert m.name(obj, b'') == []
    for flag in ('surface_ok', 'convert_ok', 'measure_ok'):
        setattr(m, flag, False)
        assert m.name(obj, b'DevSeara') == []
        setattr(m, flag, True)
    assert m.font_calls > 0 and m.released > 0
    print(f'PASS: {Path(exe).name}: both BPUI fields use exact names; Unicode/fit/read bounds, '
          f'{c["height"]}px font, failure paths, GDI restoration and x86 ABI')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe')
    verify(parser.parse_args().exe)
