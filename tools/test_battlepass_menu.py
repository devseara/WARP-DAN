"""Execute the real WARP-exported Battle Pass menu control at native boundaries.

Checks both themes, compact placement, hit testing, installed texture paths,
child lifecycle and server-approved BPUI opening/refresh. Offline only.
"""
import argparse
import itertools
import json
import struct
from pathlib import Path

import pefile
from bestiary_test_vm import VM
from test_battlepass_board import BoardMachine
from test_battlepass_text import configured

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (0xC0, 0xC3, 0xC2, 0xC4, 0xC7, 0x175, 0x169, 0xDB, 0x1AE,
            0xC1, 0x1CD, 0x18F, 0x1DC, 0x1D9, 0x1FF, 0x200, 0x172,
            0x21C, 0x17B, 0x237, 0x178, 0x245, 0x220, 0x24B, 0x206)


def verify(exe, state_file):
    state = json.loads(state_file.read_text(encoding='utf-8'))
    menu = next(e['value'] for e in reversed(state['events'])
                if e['topic'] == 'ROGlobalZeroMenu.QjsOnly')
    button = menu['battlepass']
    pe = pefile.PE(str(exe), fast_load=True)
    v = VM(pe, {'state': {'vir': 0x60001080},
                'vtable': {'vir': button['buttonVtableVir']}, 'timeGetTimeIat': 0xFC17B0})
    v.stub(menu['themeLoadBridgeVir'], 0)
    v.stub(0xDBBC4F, 0, lambda c, a: v.alloc(0x120))
    v.stub(0x8172B0, 0, lambda c, a: c)
    loaded, parents = [], []

    def load(c, a):
        name = v.cstring(a[0]).decode('latin1')
        loaded.append(name)
        if a[1] == 0:
            width, height = (32, 34) if '_old_' in name else (45, 41)
            v.write32(c + 0xBC, a[0]); v.write32(c + 0xD0, len(name))
            v.write32(c + 0xB4, width); v.write32(c + 0xB8, height)

    def size(c, a):
        v.write32(c + 0x14, a[0]); v.write32(c + 0x18, a[1])
        surface = v.alloc(32)
        v.write32(surface + 4, a[0]); v.write32(surface + 8, a[1])
        v.write32(c + 0x24, surface)

    def add(c, a):
        parents.append((c, a[0])); v.write32(a[0] + 0x10, c)

    def position(c, a):
        v.write32(c + 0x1C, a[0]); v.write32(c + 0x20, a[1])

    v.stub(0x82DAC0, 12, load); v.stub(0xA1CB70, 8, size); v.stub(0xA1B780, 4, add)
    v.stub(v.read32(button['buttonVtableVir'] + 0xD4), 4, lambda c, a: v.write32(c + 0x28, a[0]))
    v.stub(v.read32(button['buttonVtableVir'] + 0x10), 8, position)
    parent = v.alloc(0x200)
    v.write32(parent + 0x28, 1); v.u.mem_write(0x160227C, b'\1')
    callback = v.read32(button['requestCellVir'])
    assert callback == state['battlepass']['menuRequestVir']
    v.write32(button['requestCellVir'], 0)
    v.run(button['ensureVir'], ecx=parent); assert not parents
    v.write32(button['requestCellVir'], callback)
    earlier = [state[k] for k in ('hunt', 'item', 'support', 'bestiary', 'vip')]
    count = 0
    for theme in (1, 0, 1):
        v.write32(menu['themeStateVir'], theme); v.run(button['ensureVir'], ecx=parent)
        child = v.read32(button['buttonStateVir'])
        assert v.read32(child + 0x2C) == 0x3FF
        assert (v.read32(child + 0x14), v.read32(child + 0x18)) == ((45, 41) if theme else (32, 34))
        before = len(loaded); v.run(button['ensureVir'], ecx=parent); assert len(loaded) == before
        for bits in itertools.product((0, 1), repeat=5):
            for route, bit in zip(earlier, bits): v.write32(route['visibleVir'], bit)
            for native in (0, 4, 5, 25):
                v.write32(menu['visibleMaskVir'], (1 << native) - 1)
                v.write32(menu['gridStrideYVir'], 61)
                v.run(button['syncVir'], ecx=parent)
                row, col = divmod(native + sum(bits), 5)
                expected = (13 + 68 * col, 12 + 61 * row) if theme else (9 + 42 * col, 23 + 43 * row)
                assert (v.read32(child + 0x1C), v.read32(child + 0x20)) == expected
                assert v.read32(child + 0x28) == 1
                assert v.run(menu['hitTestWrapperVir'], [expected[0] + 1, expected[1] + 1], ecx=parent) == child
                count += 1
        for address, old in ((button['visibleVir'], 1), (button['requestCellVir'], callback), (parent + 0x28, 1)):
            v.write32(address, 0); v.run(button['syncVir'], ecx=parent)
            assert v.read32(child + 0x28) == 0; v.write32(address, old)
        v.u.mem_write(0x160227C, b'\0'); v.run(button['syncVir'], ecx=parent)
        assert not v.read32(child + 0x28); v.u.mem_write(0x160227C, b'\1')
    assert len(parents) == 1 and len(set(loaded)) == 6
    expected = {f'bt_battlepass_{theme}{s}.bmp' for theme in ('', 'old_') for s in ('normal', 'mouseon', 'pressed')}
    assert {name.rsplit('\\', 1)[-1] for name in loaded} == expected
    for name in set(loaded):
        assert '\\uirenewal\\menuicon\\' in name
        deployed = exe.parent / 'data/texture' / Path(name.replace('\\', '/'))
        assert deployed.read_bytes() == (ROOT / 'Assets/BattlepassUI/menuicon' / deployed.name).read_bytes(), name
    # 25 stock commands + six optional controls + MENU need seven rows.
    head = v.alloc(32); nodes = [v.alloc(32) for _ in COMMANDS]
    v.write32(head, nodes[0]); v.u.mem_write(head + 13, b'\1')
    for i, (node, command) in enumerate(zip(nodes, COMMANDS)):
        v.write32(node, head); v.write32(node + 4, nodes[i-1] if i else head)
        v.write32(node + 8, nodes[i+1] if i+1 < len(nodes) else head)
        v.write32(node + 16, command); v.write32(node + 20, child)
    v.write32(parent + 0xB4, head)
    for route in earlier + [button]: v.write32(route['visibleVir'], 1)
    v.run(menu['measureRowsVir'], ecx=parent)
    assert v.read32(menu['rowCountVir']) == 7 and v.read32(menu['panelHeightVir']) == 444
    v.write32(button['visibleVir'], 0); v.write32(menu['vip']['visibleVir'], 0)
    v.run(menu['measureRowsVir'], ecx=parent); assert v.read32(menu['rowCountVir']) == 6
    v.stub(0x81A5A0, 4); v.run(button['buttonDestructorVir'], [0], ecx=child)
    assert not v.read32(button['buttonStateVir'])
    other = v.alloc(0x200); v.run(button['ensureVir'], ecx=other)
    assert len(parents) == 2 and parents[-1][0] == other

    # Closing stays local; opening now waits for the authoritative BPUI reply.
    m = BoardMachine(str(exe)); s = m.c['state']; timers = []
    # Real servers advertise the earlier protocol capabilities with v5.
    m.w(s + 32 + 1188, 512 | 32 | 16)
    timer_set, timer_kill = m.alloc(16), m.alloc(16)
    def start():
        assert m.args(4)[:3] == [0, 0, 1000]
        timers.append('start'); m.ret(16, 567)
    def stop():
        assert m.args(2) == [0, 567]
        timers.append('stop'); m.ret(8, 1)
    m.stub(timer_set, start); m.stub(timer_kill, stop)
    m.w(s + 16, timer_set); m.w(s + 20, timer_kill)
    def click(): m.invoke(button['buttonMouseUpVir'], m.obj, (0, 0))
    before = len(m.sent); click()
    assert not m.r(m.obj + 0x28) and m.r(s + 3020) == 1 and len(m.sent) == before
    click(); assert not m.r(m.obj + 0x28) and m.r(s + 3020) == 0
    assert m.sent[before:] == [(0xBF9, 16, 0x49555042, 5, 21, 0)] and not timers
    approved=configured();struct.pack_into('<H',approved,10,struct.unpack_from('<H',approved,10)[0]|32)
    m.receive(approved);assert m.r(m.obj + 0x28) and timers == ['start']
    click(); assert not m.r(m.obj + 0x28) and timers == ['start', 'stop']
    before = len(m.sent); m.w(button['requestCellVir'], 0); click()
    assert len(m.sent) == before and not m.r(m.obj + 0x28)
    # A first menu open has no server snapshot yet. Exercise the unchanged
    # v1 -> v2 -> v7 negotiation and real window creation via the menu route.
    m.w(button['requestCellVir'], callback); m.w(s, 0); m.w(s + 24, 0)
    m.u.mem_write(s + 32, bytes(2872))
    m.stub(0xDBBC4F, lambda: m.ret(0, m.alloc(m.args(1)[0])))
    m.stub(0x86B950, lambda: m.ret(4))
    head = m.alloc(12); m.w(head, head); m.w(head + 4, head)
    m.w(0x131F4E8 + 0x17C, head); m.w(0x131F4E8 + 0x180, 0)
    packets = []
    def send():
        size, ptr = m.args(2); assert size in (12, 16)
        packets.append(bytes(m.u.mem_read(ptr, size))); m.ret(8)
    m.stub(m.r(m.c['api'] + 16), send)
    click();assert not m.r(s),'menu request must not construct a frame'
    assert packets[-1] == struct.pack('<HHIHH', 0xBF9, 12, 0x49555042, 1, 21)
    native = next(e['value'] for e in state['events'] if e['topic'] == 'BattlepassUI.Native')
    def tick(): m.invoke(native['timerVir'], 0, (0, 0, 0, 0))
    legacy = bytearray(788)
    struct.pack_into('<HHIHH', legacy, 0, 0xBF6, 788, 0x49555042, 1, 32 | 16 | 0x8000)
    m.receive(legacy);m.obj = m.r(s);m.owner = m.obj
    assert m.obj and m.r(m.obj + 0x28) and m.r(0x131F4E8 + 0x180) == 1
    tick()
    assert packets[-1] == struct.pack('<HHIHHI', 0xBF9, 16, 0x49555042, 2, 0, 0)
    details = legacy + bytearray(2240 - len(legacy))
    struct.pack_into('<H', details, 2, 2240); struct.pack_into('<H', details, 8, 2)
    struct.pack_into('<I', details, 1188, 16 | 32 | 512 | 1024 | 2048)
    m.receive(details); tick()
    assert packets[-1] == struct.pack('<HHIHHI', 0xBF9, 16, 0x49555042, 7, 0, 0)
    m.receive(configured())
    assert m.r(s + 24) == 1 and m.r(m.obj + 0x28) and m.r(0x131F4E8 + 0x180) == 1
    print(f'PASS: {count} Battle Pass placements/hit tests, six installed texture paths, seven rows, gates, child recreation, native close/reopen, exact BPUI refresh and timer lifecycle; ABI preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('exe', type=Path); parser.add_argument('state', type=Path)
    args = parser.parse_args(); verify(args.exe, args.state)
