"""Execute the emitted left-loot payload with explicit native/OS boundary doubles.

These focused offline checks do not establish live-client acceptance.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)


ROOT = Path(__file__).resolve().parents[1]


class Machine:
    BASE = 0x20000000
    STOP = 0x41000000
    STACK = 0x4000F000

    def __init__(self, payload_path):
        payload = payload_path.read_bytes()
        metadata = json.loads(payload_path.with_suffix('.json').read_text(encoding='utf8'))
        assert hashlib.sha256(payload).hexdigest() == metadata['payload_sha256']
        magic, version, size, count, api, api_size, client, crc = struct.unpack_from('<8I', payload)
        assert (magic, version, api_size, client) == (0x544F4F4C, 1, 16, 20250716)
        assert len(payload) == 32 + count * 4 + size
        assert zlib.crc32(payload[32:]) == crc
        assert metadata['runtime_imports'] == []
        code = bytearray(payload[32 + count * 4:])
        for offset in struct.unpack_from('<' + 'I' * count, payload, 32):
            value = struct.unpack_from('<I', code, offset)[0]
            assert offset + 4 <= size and value < size
            struct.pack_into('<I', code, offset, value + self.BASE)
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(0x00400000, 0x01C00000)
        self.u.mem_map(self.BASE, (size + 4095) & ~4095)
        self.u.mem_write(self.BASE, bytes(code))
        self.u.mem_map(0x30000000, 0x02000000)
        self.u.mem_map(0x40000000, 0x10000)
        self.u.mem_map(self.STOP, 0x1000)
        self.next = 0x30000000
        self.now = 1000
        self.exports = {name: self.BASE + offset for name, offset in metadata['exports'].items()}
        for name, address in tuple(self.exports.items()):
            if name.startswith('@'):
                self.exports[name.split('@')[1]] = address
        assert self.exports['LootApi'] == self.BASE + api
        self.messages = []
        self.draws = []
        self.ticks = []
        self.resizes = []
        self.destroyed = []
        self.closed = []
        self.callbacks = []
        self.paint_id = 0
        self.request_width = 270
        self.invalid_surface = False
        self.surfaces = []
        self.object = self.alloc(0x200)
        self.renderer = self.alloc(64)
        self.w(0x12515F8, self.renderer)
        self.w(self.renderer + 0x28, 1280)
        self.w(self.renderer + 0x2C, 720)
        for index, address in enumerate((0x8C5860, 0x8B5520, 0x8BAF00, 0x893200)):
            self.w(self.exports['LootApi'] + index * 4, address)
        self.stub(0x8C5860, self.stock_message)
        self.stub(0x8B5520, self.stock_draw)
        self.stub(0x8BAF00, lambda: (self.ticks.append(self.ecx()), self.ret()))
        self.stub(0x893200, self.stock_destroy)
        self.stub(0xA245C0, self.resize)
        self.stub(0xA2E770, self.close)
        clock = self.alloc(16)
        self.w(0xFC17B0, clock)
        self.stub(clock, lambda: self.ret(value=self.now))
        self.set_size(self.object, 270, 32)

    def alloc(self, size):
        address = self.next
        self.next += (size + 15) & ~15
        assert self.next < 0x32000000
        return address

    def r(self, address):
        return struct.unpack('<I', bytes(self.u.mem_read(address, 4)))[0]

    def w(self, address, value):
        self.u.mem_write(address, struct.pack('<I', value & 0xFFFFFFFF))

    def ecx(self):
        return self.u.reg_read(UC_X86_REG_ECX)

    def args(self, count):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        return tuple(self.r(sp + 4 + index * 4) for index in range(count))

    def ret(self, pop=0, value=0):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        target = self.r(sp)
        self.u.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        self.u.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        # Deliberately clobber volatile registers like a native callee may do.
        self.u.reg_write(UC_X86_REG_ECX, 0xCCCCCCCC)
        self.u.reg_write(UC_X86_REG_EDX, 0xDDDDDDDD)
        self.u.reg_write(UC_X86_REG_EIP, target)

    def stub(self, address, function):
        self.callbacks.append(self.u.hook_add(
            UC_HOOK_CODE, lambda *_: function(), begin=address, end=address))

    def invoke(self, name, this=0, args=(), edx=0):
        pc = self.exports[name] if isinstance(name, str) else name
        sp = self.STACK
        values = (self.STOP,) + tuple(value & 0xFFFFFFFF for value in args)
        self.u.mem_write(sp, struct.pack('<' + 'I' * len(values), *values))
        saved = {UC_X86_REG_EBX: 0xBBBBBBBB, UC_X86_REG_ESI: 0xEEEEEEEE,
                 UC_X86_REG_EDI: 0xFFFFFFFF, UC_X86_REG_EBP: 0xABABABAB}
        for register, value in saved.items():
            self.u.reg_write(register, value)
        self.u.reg_write(UC_X86_REG_ECX, this)
        self.u.reg_write(UC_X86_REG_EDX, edx)
        self.u.reg_write(UC_X86_REG_ESP, sp)
        self.u.emu_start(pc, self.STOP, count=20000000)
        assert self.u.reg_read(UC_X86_REG_EIP) == self.STOP, 'Payload did not return'
        assert self.u.reg_read(UC_X86_REG_ESP) == sp + 4 + len(args) * 4, 'Stack imbalance'
        for register, value in saved.items():
            assert self.u.reg_read(register) == value, 'Callee-save register changed'
        return self.u.reg_read(UC_X86_REG_EAX)

    def set_size(self, obj, width, height):
        assert 1 <= width <= 4096 and 1 <= height <= 256
        surface = self.alloc(64)
        buffer_size = width * height * 4
        pixels = self.alloc(buffer_size + 32)
        self.u.mem_write(pixels, b'\xA5' * 16 + bytes(buffer_size) + b'\x5A' * 16)
        self.w(obj + 0x14, width)
        self.w(obj + 0x18, height)
        self.w(obj + 0x24, surface)
        self.w(surface + 4, 0 if self.invalid_surface else width)
        self.w(surface + 8, height)
        self.w(surface + 0x18, pixels + 16)
        self.surfaces.append((pixels, buffer_size))

    def resize(self):
        width, height = self.args(2)
        self.resizes.append((self.ecx(), width, height))
        self.set_size(self.ecx(), width, height)
        self.ret(8)

    def stock_message(self):
        args = self.args(6)
        self.messages.append((self.ecx(), args))
        if args[1] == 0x24:
            self.set_size(self.ecx(), self.request_width, 32)
        self.ret(24, 0xABC00000 | args[1])

    def stock_draw(self):
        obj = self.ecx()
        self.draws.append((obj, self.paint_id))
        surface = self.r(obj + 0x24)
        width, height = self.r(surface + 4), self.r(surface + 8)
        pixels = self.r(surface + 0x18)
        assert width >= 4 and height == 32
        # Native GDI uses zero-alpha text/background; preserve a partial-alpha
        # icon pixel too. Leave the first corner at the runtime's magenta clear.
        row = [0x00FF00FF, 0, 0x80112233, self.paint_id] + [0x00EEEEEE] * (width - 4)
        self.u.mem_write(pixels, struct.pack('<' + 'I' * width, *row) * height)
        self.ret()

    def stock_destroy(self):
        obj = self.ecx()
        self.destroyed.append((obj, self.args(1)[0]))
        self.ret(4, obj)

    def close(self):
        self.closed.append((self.ecx(), self.args(1)[0]))
        self.ret(4)

    def count(self):
        return self.r(self.exports['LootState'] + 4)

    def pickup(self, marker, width=270):
        self.paint_id = marker
        self.request_width = width
        first = (11, 0x24, 22, 33, 44, 55)
        second = (66, 0x22, 77, 88, 99, 111)
        before = len(self.messages)
        result = self.invoke('LootMessage', self.object, first)
        assert result == 0xABC00024
        result = self.invoke('LootMessage', self.object, second)
        assert result == 0xABC00022
        assert self.messages[before:] == [(self.object, first), (self.object, second)], \
            'Stock messages were duplicated or altered'

    def pixels(self):
        surface = self.r(self.object + 0x24)
        return (self.r(surface + 0x18), self.r(surface + 4), self.r(surface + 8), surface)

    def draw(self):
        self.invoke('LootDraw', self.object)
        pixels, width, height, surface = self.pixels()
        assert bytes(self.u.mem_read(surface + 0x1C, 1)) == b'\x01'
        assert bytes(self.u.mem_read(surface + 0x28, 1)) == b'\x01'
        self.check_guards()
        return pixels, width, height

    def row_pixels(self, row):
        pixels, width, _, _ = self.pixels()
        return struct.unpack('<4I', bytes(self.u.mem_read(pixels + row * 36 * width * 4, 16)))

    def check_guards(self):
        for pixels, size in self.surfaces:
            assert bytes(self.u.mem_read(pixels, 16)) == b'\xA5' * 16, 'Pixel buffer underrun'
            assert bytes(self.u.mem_read(pixels + 16 + size, 16)) == b'\x5A' * 16, 'Pixel buffer overrun'


def queue_and_alpha_checks(path):
    m = Machine(path)
    for marker in range(1, 7):
        m.now = 1000 + marker * 100
        m.pickup(marker, 270 + marker * 10)
        assert m.count() == min(marker, 5)
    assert len(m.draws) == 6, 'A pickup was rendered more than once'
    _, width, height = m.draw()
    assert (width, height) == (330, 176)
    assert [m.row_pixels(i)[3] for i in range(5)] == [0xFF000000 | i for i in (6, 5, 4, 3, 2)], \
        'Newest-first queue did not remove exactly the oldest entry'
    assert all(m.row_pixels(i)[:3] == (0, 0xFF000000, 0x80112233) for i in range(5)), \
        'Magenta transparency, opaque black text or partial icon alpha changed'
    pixels, width, _, _ = m.pixels()
    for row in range(4):
        gap = pixels + (row * 36 + 32) * width * 4
        assert bytes(m.u.mem_read(gap, width * 4 * 4)) == bytes(width * 4 * 4), 'Row gap was not transparent'
    assert (m.r(m.object + 0x1C), m.r(m.object + 0x20)) == (10, 240)
    assert m.r(m.object + 0x38) == m.r(m.object + 0x40) == 255
    m.now = 8200  # Second pickup expires exactly; the remaining four stay ordered.
    m.invoke('LootTick', m.object)
    assert m.count() == 4 and not m.closed
    m.draw()
    assert [m.row_pixels(i)[3] & 0xFFFFFF for i in range(4)] == [6, 5, 4, 3]
    assert m.r(m.object + 0x18) == 140
    m.now = 8600
    m.invoke('LootTick', m.object)
    assert m.count() == 0 and m.closed == [(0x131F4E8, 0x3A)]
    m.invoke('LootTick', m.object)
    assert len(m.closed) == 1, 'An expired singleton was closed repeatedly'
    assert not m.ticks, 'Stock single-toast expiry was invoked'
    m.check_guards()


def fade_and_wrap_checks(path):
    for start in (1000, 0xFFFFFF00):
        m = Machine(path)
        m.now = start
        m.pickup(0x123456)
        for age, alpha in ((0, 255), (4000, 255), (5500, 127), (6500, 42), (6999, 0)):
            m.now = (start + age) & 0xFFFFFFFF
            m.invoke('LootTick', m.object)
            assert m.count() == 1 and not m.closed
            m.draw()
            corner, black, partial, marker = m.row_pixels(0)
            assert corner == 0
            assert black == alpha << 24, (age, hex(black), alpha)
            assert partial == ((128 * alpha // 255) << 24) | 0x112233
            assert marker == (alpha << 24) | 0x123456
        m.now = (start + 7000) & 0xFFFFFFFF
        m.invoke('LootTick', m.object)
        assert m.count() == 0 and len(m.closed) == 1
        m.check_guards()


def native_lifecycle_checks(path):
    m = Machine(path)
    args = (9, 0x10, 8, 7, 6, 5)
    assert m.invoke('LootMessage', m.object, args) == 0xABC00010
    assert m.messages == [(m.object, args)] and m.count() == 0 and not m.draws
    # A standalone item update must not manufacture a pickup notification.
    m.invoke('LootMessage', m.object, (0, 0x22, 0, 0, 0, 0))
    assert m.count() == 0 and not m.draws
    m.invoke('LootMessage', m.object, (0, 0x24, 0, 0, 0, 0))
    m.invoke('LootTick', m.object)
    assert not m.closed, 'Pending native item pair was closed prematurely'
    m.invoke('LootDraw', m.object)
    assert len(m.draws) == 1 and m.count() == 0, 'Pending draw queued a duplicate item'
    m.paint_id = 27
    m.invoke('LootMessage', m.object, (0, 0x22, 0, 0, 0, 0))
    assert m.count() == 1 and len(m.draws) == 2
    m.invoke('LootMessage', m.object, (0, 0x22, 0, 0, 0, 0))
    assert m.count() == 1 and len(m.draws) == 2
    other = m.alloc(0x200)
    assert m.invoke('LootDestroy', other, (2,)) == other
    assert m.count() == 1, 'Unrelated destruction cleared the active queue'
    assert m.invoke('LootDestroy', m.object, (1,)) == m.object
    assert m.r(m.exports['LootState']) == 0 and m.count() == 0
    assert m.destroyed == [(other, 2), (m.object, 1)]
    m.object = other
    m.set_size(other, 270, 32)
    m.pickup(47)
    m.draw()
    assert m.count() == 1 and m.row_pixels(0)[3] == 0xFF00002F
    # Owner replacement also discards stale pixels if no destructor hook runs.
    m.object = m.alloc(0x200)
    m.set_size(m.object, 270, 32)
    m.pickup(48)
    m.draw()
    assert m.count() == 1 and m.row_pixels(0)[3] == 0xFF000030
    m.check_guards()


def layout_and_failure_checks(path):
    m = Machine(path)
    for width, height in ((800, 600), (1024, 768), (1920, 1080), (3440, 1440)):
        m.w(m.renderer + 0x28, width)
        m.w(m.renderer + 0x2C, height)
        m.pickup(123, 1200)
        m.draw()
        assert m.r(m.object + 0x14) == min(width - 20, 1024)
        m.invoke('LootPosition', m.object, (9999, 9999))
        assert m.r(m.object + 0x1C) == 10
        assert m.r(m.object + 0x20) == height // 3
        assert m.r(m.object + 0x20) + m.r(m.object + 0x18) <= height - 32
    # Resize an existing full queue without waiting for another pickup. Snapshot
    # widths remain independent of the smaller live canvas, so widening restores.
    m.pickup(125, 1200)
    for width, height, expected_width, expected_y in (
            (800, 600, 780, 200), (1920, 1080, 1024, 360), (200, 200, 180, 14)):
        m.w(m.renderer + 0x28, width)
        m.w(m.renderer + 0x2C, height)
        before = len(m.messages)
        m.invoke('LootTick', m.object)
        m.draw()
        assert m.count() == 5 and len(m.messages) == before
        assert (m.r(m.object + 0x14), m.r(m.object + 0x18)) == (expected_width, 176)
        assert (m.r(m.object + 0x1C), m.r(m.object + 0x20)) == (10, expected_y)
        assert m.r(m.object + 0x20) + 176 <= height - 10
        assert m.row_pixels(0)[3] == 0xFF00007D
    m.w(m.renderer + 0x28, 0)
    m.w(m.renderer + 0x2C, 0)
    m.pickup(124, 1200)
    m.draw()
    assert m.r(m.object + 0x14) == 780
    assert m.r(m.object + 0x20) == 200
    m.check_guards()
    # Malformed/absent native surface must not be read or queued.
    bad = Machine(path)
    bad.invalid_surface = True
    bad.pickup(77)
    assert bad.count() == 0 and not bad.draws
    bad.invoke('LootTick', bad.object)
    assert len(bad.closed) == 1
    bad.check_guards()
    missing = Machine(path)
    missing.pickup(78)
    missing.w(missing.object + 0x24, 0)
    missing.invoke('LootDraw', missing.object)
    assert missing.count() == 1
    missing.check_guards()


def native_root_render_checks(path, client):
    """Run the native root branch and surface uploader up to the GPU boundary."""
    m = Machine(path)
    m.pickup(0x123456)
    m.now += 5500
    m.draw()
    pixels, width, height, surface = m.pixels()
    before = bytes(m.u.mem_read(pixels, width * height * 4))
    assert m.row_pixels(0)[1] == 0x7F000000
    assert bytes(m.u.mem_read(m.object + 0x78, 1)) == b'\0', 'Root canvas mode changed'
    with pefile.PE(str(client)) as pe:
        base = pe.OPTIONAL_HEADER.ImageBase
        assert base == 0x400000 and pe.FILE_HEADER.Machine == 0x14C
        read = lambda address, size: pe.get_data(address - base, size)
        assert read(0xA49158, 6) == bytes.fromhex('80 7f 78 01 75 3a')
        assert read(0xFD5CE4 + 0x30, 4) == struct.pack('<I', 0x53EA90)
        assert read(0x53EA90, 16) == bytes.fromhex('55 8b ec 83 ec 10 57 8b f9 83 7f 18 00 0f 84 ee')
        assert read(0x53F2D5, 6) == bytes.fromhex('6a 00 6a 00 6a 04'), \
            'Native preserve-alpha path no longer selects format 4'
        spans = ((0xA49158, 0xA491CC), (0x53EA90, 0x53EB98), (0x53F290, 0x53F54B))
        span_hashes = {}
        for start, end in spans:
            raw = read(start, end - start)
            m.u.mem_write(start, raw)
            span_hashes[hex(start)] = hashlib.sha256(raw).hexdigest()

    # A pre-existing full-size texture avoids testing allocator/list ownership.
    # Actual native alpha upload and root rendering execute; only texture/GPU
    # upload/draw and the window's modulation getter are explicit doubles.
    m.u.mem_map(0, 4096)  # Native uploader's SEH record uses fs:[0].
    window_vtable, surface_vtable, texture_vtable = (m.alloc(256) for _ in range(3))
    texture, head, node = (m.alloc(64) for _ in range(3))
    getter, upload, gpu_draw = (m.alloc(16) for _ in range(3))
    m.w(m.object, window_vtable)
    m.w(window_vtable + 0xA0, getter)
    m.w(surface, surface_vtable)
    m.w(surface_vtable + 0x30, 0x53EA90)
    m.w(texture, texture_vtable)
    m.w(texture_vtable + 0x20, upload)
    m.w(texture_vtable + 0x28, gpu_draw)
    m.w(head, node)
    m.w(node, head)
    m.w(node + 8, texture)
    m.w(surface + 0x20, head)
    m.w(surface + 0x24, 1)
    uploads, draws = [], []
    m.stub(getter, lambda: m.ret(value=255))

    def upload_pixels():
        values = m.args(7)
        assert m.ecx() == texture
        assert values == (0, 0, width, height, pixels, 0, width)
        uploads.append(bytes(m.u.mem_read(values[4], width * height * 4)))
        m.ret(28)

    def draw_texture():
        assert m.ecx() == texture
        draws.append(m.args(5))
        m.ret(20)

    m.stub(upload, upload_pixels)
    m.stub(gpu_draw, draw_texture)
    frame = 0x4000F000
    m.w(frame - 0x28, 0x131F4E8)
    m.u.reg_write(UC_X86_REG_EBP, frame)
    m.u.reg_write(UC_X86_REG_ESP, 0x4000E000)
    m.u.reg_write(UC_X86_REG_EDI, m.object)
    m.u.reg_write(UC_X86_REG_ESI, 0xEEEEEEEE)
    m.u.reg_write(UC_X86_REG_EBX, 0x131F4E8)
    m.u.emu_start(0xA49158, 0xA491CC, count=100000)
    assert m.u.reg_read(UC_X86_REG_EIP) == 0xA491CC, 'Native root branch failed to return'
    assert m.u.reg_read(UC_X86_REG_ESP) == 0x4000E000, 'Native root branch stack imbalance'
    assert m.u.reg_read(UC_X86_REG_EDI) == m.object
    assert m.u.reg_read(UC_X86_REG_ESI) == 0xEEEEEEEE
    assert m.u.reg_read(UC_X86_REG_EBX) == 0x131F4E8
    assert uploads == [before], 'Native uploader replaced faded per-pixel alpha'
    assert draws == [(10, 240, width, height, 255)]
    assert bytes(m.u.mem_read(pixels, width * height * 4)) == before
    assert bytes(m.u.mem_read(surface + 0x1C, 1)) == b'\0', 'Native upload did not consume dirty state'
    m.check_guards()
    return {'client': str(client), 'executed_native_spans_sha256': span_hashes,
            'result': 'Root surface draw uploads the exact faded BGRA pixels without alpha override'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, default=ROOT / 'Inputs/LeftLootNotices/runtime.bin')
    parser.add_argument('--client', type=Path,
                        default=Path('D:/AAARAGNAROK/Banquet of Heroes/Eitr Origin/Eitr.exe'))
    parser.add_argument('--output', type=Path, help='Optional JSON evidence path')
    args = parser.parse_args()
    checks = (queue_and_alpha_checks, fade_and_wrap_checks,
              native_lifecycle_checks, layout_and_failure_checks)
    passed = []
    for check in checks:
        check(args.payload)
        passed.append(check.__name__)
        print('PASS', check.__name__)
    native_render = native_root_render_checks(args.payload, args.client)
    passed.append('native_root_render_checks')
    print('PASS native_root_render_checks')
    evidence = {
        'result': 'passed', 'checks': passed,
        'payload_sha256': hashlib.sha256(args.payload.read_bytes()).hexdigest(),
        'native_render': native_render,
        'scope': 'Exact compiled x86 payload with native message/draw/resize/clock/manager/destructor doubles',
        'limitations': 'Does not establish live rendering, native stock draw fidelity, or installed hook placement',
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf8')
    print('PASS LeftLootNotices focused native behavior and ABI; live-client acceptance pending.')


if __name__ == '__main__':
    main()
