"""Offline emitted-x86 tab-menu tests, including native popup selection.

Execute native tab hit testing, popup/list events and main command dispatch.
Window allocation/rendering and native create/delete bodies are explicit
boundaries; this does not claim live visual or persistence acceptance.
"""
import argparse
from pathlib import Path
from unicorn import UcError
from unicorn.x86_const import *
from test_chat_item_icons import IconMachine
from test_modern_chat_ui import pack


def contract(m):
    tag = m.pe.__data__.find(b'ModernChatUI.Tabs.v1\0')
    assert tag >= 0
    va = m.base + m.pe.get_rva_from_offset(tag)
    data = m.pe.get_memory_mapped_image()
    record = data.find(pack(va))
    assert record >= 0 and data.find(pack(va), record + 1) < 0
    names = 'state down up open event destroy vtable defaults layout'.split()
    return dict(zip(names, [m.r(m.base + record + 4 + i*4) for i in range(len(names))]))


class TabsMachine(IconMachine):
    def __init__(self, exe):
        super().__init__(exe)
        self.c = contract(self)
        self.created = []; self.closed = []; self.commands = []; self.labels = []
        self.popup = 0; self.fail_create = False
        # Execute the actual chat event switch; stop only at the native
        # create/delete bodies, which own the existing maps and persistence.
        self.u.hook_del(self._stub_handles.pop(0x8FC220))
        self.w(0x15BEECC, 0)
        self.stub(0x8DC600, lambda: self.ret(4))
        for address, command in [(0x8FDE11, 0x176), (0x8FE0A4, 0xCA)]:
            self.stub(address, lambda command=command: self.command(command))
        self.stub(0xA39340, self.make_popup)
        self.stub(0xA2E770, self.close_popup)
        self.stub(0xA47B90, lambda: self.ret(4, self.popup if self.args(1)[0] == 0x1A else 0))
        self.stub(0x8BC640, self.popup_resize)
        self.stub(0x83DD90, self.add_row)
        self.stub(0x8925E0, lambda: self.ret(4))
        self.parent, self.tab = self.setup(names=('Main', 'Battle', 'Guild', 'Party', 'Market'))
        self.w(self.tab + 0x28, 1); self.w(self.tab + 0x30, 0)
        self.w(0x131F6B0, self.parent)
        self.w(0x15FAAE0, 5); self.w(0x15FAAE8, 0)
        self.w(self.parent + 0x110, 12)
        self.u.mem_write(0x15FAAEC, b'\x01')  # Native CanDragWnd: unlocked.
        self.invoke(self.c['layout'], self.parent)

    def command(self, command):
        assert self.u.reg_read(UC_X86_REG_EDI) == self.parent
        self.commands.append((command, self.r(self.parent + 0x114)))
        self.u.reg_write(UC_X86_REG_EAX, 0)
        self.u.reg_write(UC_X86_REG_EIP, 0x8FE497)

    def make_popup(self):
        assert self.u.reg_read(UC_X86_REG_ECX) == 0x131F4E8 and self.args(1) == [0x1A]
        if self.fail_create:
            self.ret(4, 0); return
        self.labels = []
        self.popup = self.window(156, 32, 0x1034B94)
        child = self.window(156, 32, 0x102CAC8, self.popup)
        self.w(self.popup + 0x28, 1); self.w(child + 0x28, 1)
        self.w(self.popup + 0xB4, child)
        strings = self.alloc(48)
        self.w(child + 0x88, strings); self.w(child + 0x8C, strings)
        self.w(child + 0xB8, 16); self.w(child + 0xC4, 1)
        self.w(0x131F6FC, self.popup)
        self.created.append(self.popup)
        self.ret(4, self.popup)

    def close_popup(self):
        assert self.args(1) == [0x1A]
        if self.popup:
            # Manager destruction is a boundary; the emitted destructor is
            # exercised separately below, avoiding a nested emulation call.
            self.closed.append(self.popup)
            self.w(self.c['state'] + 12, 0); self.w(self.c['state'] + 16, 0)
            self.popup = 0; self.w(0x131F6FC, 0)
        self.ret(4)

    def popup_resize(self):
        obj = self.u.reg_read(UC_X86_REG_ECX)
        assert obj == self.popup and self.args(2) == [156, 32]
        self.setsize(obj, *self.args(2)); self.setsize(self.r(obj + 0xB4), *self.args(2))
        self.ret(8)

    def add_row(self):
        child = self.u.reg_read(UC_X86_REG_ECX)
        self.labels.append(self.cstr(self.args(1)[0]))
        self.w(child + 0x8C, self.r(child + 0x8C) + 24)
        self.ret(4)

    def right(self, index=0):
        x = index * 106 + 20
        capture = self.r(0x131F4E8 + 0x19C)
        self.w(0x11E40E8, 1)
        self.invoke(self.c['down'], self.tab, [x, 8])
        assert self.r(0x131F4E8 + 0x19C) == capture, 'right-click changed mouse capture'
        self.w(0x11E40E8, 3)  # Native mouse-up transition, not idle (0).
        self.invoke(self.c['up'], self.tab, [x, 8])

    def select(self, row):
        child = self.r(self.popup + 0xB4)
        assert self.r(child + 0xD4) == 0x1A, 'selection routed to legacy dropdown'
        # Run actual native ListBox mouse-up: hit test -> popup event ->
        # chat dispatcher -> popup manager close. Sender is natively null.
        self.invoke(0x858D10, child, [10, row*16 + 8])


def test_menu(m):
    for index in range(5):
        m.right(index)
        assert m.labels == ['Delete Tab', 'Create New Tab']
        assert m.r(m.parent + 0x114) == index == m.r(m.tab + 0x7C)
        assert m.r(m.popup) == m.c['vtable']
        assert m.r(m.popup + 0x20) == 186
        m.select(0)
        assert m.commands[-1] == (0xCA, index) and m.popup == 0
    m.right(2); m.select(1)
    assert m.commands[-1] == (0x176, 2)
    assert len(m.commands) == 6 and len(m.closed) == 6
    # The later Inventory skin replaces shared +0x70 with inventory hover.
    # Chat must retain the profiled native hover, not copy that later hook.
    vt = m.r(m.tab)
    assert m.r(vt - 4) == m.r(0x102DD40)
    for offset in range(0, 0xD4, 4):
        if offset not in (0x50, 0x80, 0x84):
            expected = 0x85A170 if offset == 0x70 else m.r(0x102DD44 + offset)
            assert m.r(vt + offset) == expected, (hex(offset), hex(m.r(vt+offset)), hex(expected))
    assert m.r(0x102DD44 + 0x80) == 0x5A8A50
    assert m.r(m.c['vtable'] - 4) == m.r(0x1034B90)


def test_guards(m):
    for xy in [(-1, 8), (530, 8), (20, -1), (20, 20), (900, 8)]:
        m.invoke(m.c['down'], m.tab, xy); m.invoke(m.c['up'], m.tab, xy)
    assert not m.created
    m.invoke(m.c['up'], m.tab, [20, 8]); assert not m.created
    m.invoke(m.c['down'], m.tab, [20, 8])
    m.invoke(m.c['up'], m.tab, [126, 8]); assert not m.created
    m.invoke(m.c['down'], m.tab, [20, 8])
    m.w(0x11E40E8, 0); m.invoke(m.c['layout'], m.parent)
    m.invoke(m.c['up'], m.tab, [20, 8]); assert not m.created
    m.w(0x131F4E8 + 0x19C, m.tab); m.right(); assert not m.created


def test_lock(m):
    lock = lambda value: m.u.mem_write(0x15FAAEC, bytes([value]))
    lock(0)
    for index in range(5):
        m.right(index)
    m.invoke(m.c['open'], m.tab, [1, 126])
    assert not m.created and not m.commands
    assert m.r(m.tab + 0x7C) == m.r(m.parent + 0x114) == 0
    # Ordinary left selection remains usable while locked.
    m.invoke(m.r(m.r(m.tab) + 0x64), m.tab, [126, 8])
    assert m.r(m.tab + 0x7C) == m.r(m.parent + 0x114) == 1
    m.invoke(m.r(m.r(m.tab) + 0x7C), m.tab, [126, 8])
    for before, after in [(1, 0), (0, 1)]:
        lock(before); m.invoke(m.c['down'], m.tab, [20, 8])
        lock(after); m.invoke(m.c['up'], m.tab, [20, 8])
        assert not m.created
    # Layout cancels an in-flight press even if unlocking precedes release.
    lock(1); m.invoke(m.c['down'], m.tab, [20, 8])
    lock(0); m.w(0x11E40E8, 2); m.invoke(m.c['layout'], m.parent)
    lock(1); m.invoke(m.c['up'], m.tab, [20, 8])
    assert not m.created
    for row in [0, 1]:
        lock(1); m.right(2)
        popup = m.popup
        lock(0)
        m.invoke(m.c['event'], popup, [0, 0x27, row, 0, 0, 0])
        assert not m.commands
        lock(1)
        m.invoke(m.c['event'], popup, [0, 0x27, row, 0, 0, 0])
        assert not m.commands, 'unlock replayed a retired locked action'
        lock(0); m.select(row)
        assert not m.commands and not m.popup
        lock(1)
    for row, command in [(0, 0xCA), (1, 0x176)]:
        m.right(2); m.select(row)
        assert m.commands[-1] == (command, 2)
    assert len(m.commands) == 2


def test_native_tab_state(m):
    # Execute the actual UITabCtrl/base constructors. Only the unrelated
    # base object and CRT allocation are boundaries; do not invent +0x30=1.
    m.stub(0x7DB200, lambda: m.ret(0, m.u.reg_read(UC_X86_REG_ECX)))
    m.stub(0xDBBC4F, lambda: m.ret(0, m.alloc(m.args(1)[0])))
    native = m.alloc(0x100)
    m.invoke(0x837010, native)
    assert m.r(native + 0x28) == 1 and m.r(native + 0x30) == 0
    m.w(m.tab + 0x28, m.r(native + 0x28))
    m.w(m.tab + 0x30, m.r(native + 0x30))
    m.right(1)
    assert m.popup, 'visible native tab (+0x28=1,+0x30=0) rejected the right-click'
    m.select(1)
    assert m.commands == [(0x176, 1)]
    m.w(m.tab + 0x28, 0)
    m.right(1)
    assert m.popup == 0, 'hidden/disabled tab accepted right-click'


def test_native_mouse_poll(m):
    manager = 0x131F4E8
    m.w(manager + 0x1B4, 0)
    m.w(0x11E40E4, 0); m.w(0x11E40EC, 0)
    m.stub(0xA23470, lambda: m.ret(8))  # OS cursor boundary
    m.stub(0x85A170, lambda: m.ret(8))  # native hover paint only
    # Execute actual UIWindow child hit testing before each complete native
    # no-capture mouse dispatch. Only the manager's root-list search is doubled.
    empty = m.alloc(12)
    m.w(empty, empty); m.w(empty + 4, empty)
    m.w(m.tab + 0x50, empty)
    def hit():
        m.u.reg_write(UC_X86_REG_ECX, m.tab)
        m.u.reg_write(UC_X86_REG_EIP, 0xA23220)
    m.stub(0xA336D0, hit)
    code = m.alloc(256)
    x, y = 20 + m.r(m.tab + 0x1C), 8 + m.r(m.tab + 0x20)
    prefix = (b'\x55\x8b\xec\x81\xec' + pack(0x90) + b'\x53\x56\x57\xbb' + pack(manager) +
              b'\xc7\x45\x8c' + pack(y) + b'\xc7\x45\x90' + pack(x) + b'\xe9')
    m.u.mem_write(code, prefix + pack(0xA46940 - (code + len(prefix) + 4)))
    done = code + 192
    m.u.mem_write(done, b'\x5f\x5e\x5b\x8b\xe5\x5d\xc3')
    m.stub(0xA470CC, lambda: m.u.reg_write(UC_X86_REG_EIP, done))
    # Native transitions are 1=down, 2=held, 3=up, 0=idle.
    for state in [1, 2, 2, 3]:
        m.w(0x11E40E8, state)
        m.invoke(code, manager)
        assert m.r(manager + 0x19C) == 0
        m.invoke(m.c['layout'], m.parent)
    assert m.labels == ['Delete Tab', 'Create New Tab'] and m.popup
    m.w(0x11E40E8, 0); m.invoke(m.c['layout'], m.parent)
    assert m.popup, 'idle layout dismissed the menu'
    m.select(0)
    assert m.commands == [(0xCA, 0)]


def popup_manager_fixture(m):
    """Real native manager traversal: popup root -> child-list -> UIListBox."""
    m.right()
    popup = m.popup
    child = m.r(popup + 0xB4)
    def linked_list(owner, offset, objects):
        sentinel = m.alloc(12)
        nodes = [m.alloc(12) for _ in objects]
        m.w(sentinel, nodes[0] if nodes else sentinel)
        m.w(sentinel + 4, nodes[-1] if nodes else sentinel)
        for i, (node, obj) in enumerate(zip(nodes, objects)):
            m.w(node, nodes[i+1] if i+1 < len(nodes) else sentinel)
            m.w(node+4, nodes[i-1] if i else sentinel)
            m.w(node+8, obj)
        m.w(owner+offset, sentinel)
        return sentinel
    linked_list(child, 0x50, [])
    linked_list(popup, 0x50, [child])
    linked_list(0x131F4E8, 0x17C, [popup])
    linked_list(0x131F4E8, 0x4F0B8, [])
    m.w(child+0x74, 301); m.w(popup+0x74, 302)
    m.w(0x131F4E8+0x4F0C4, 0)
    m.w(child+0x1C, 0); m.w(child+0x20, 0)
    return popup, child


def test_popup_manager_hit(m, expect_crash=False):
    popup, child = popup_manager_fixture(m)
    x, y = m.r(popup+0x1C)+10, m.r(popup+0x20)+8
    if expect_crash:
        # Hit testing does not use SEH. Make page zero inaccessible like the
        # live process, rather than executing fixture zeros at the bad slot.
        m.u.mem_unmap(0, 0x1000)
        try:
            m.invoke(0xA336D0, 0x131F4E8, [x, y])
        except UcError:
            assert m.u.reg_read(UC_X86_REG_EIP) == 0x162
            assert m.u.reg_read(UC_X86_REG_EAX) == m.c['vtable']
            assert m.r(m.u.reg_read(UC_X86_REG_ESP)) == 0xA336FA
            print('REPRODUCED: native manager call at 00A336F4 -> popup vtable+0xC8 -> 00000162', flush=True)
            return
        raise AssertionError('Reported popup hit-test crash was not reproduced')
    # Check every preserved virtual, including ID/focus/hit-test methods past
    # +0xB0. Only the destructor and selection callback belong to this patch.
    for offset in range(-4, 0xD4, 4):
        if offset not in (0, 0x94):
            assert m.r(m.c['vtable']+offset) == m.r(0x1034B94+offset), hex(offset)
    for dx, dy in [(10,8), (10,24), (100,16)]:
        m.invoke(0xA336D0, 0x131F4E8, [m.r(popup+0x1C)+dx, m.r(popup+0x20)+dy])
        assert m.u.reg_read(UC_X86_REG_EAX) == child
    # Exercise focus leave/enter on the popup itself as well as its child.
    m.w(child+0x28, 0)
    m.invoke(0xA336D0, 0x131F4E8, [x,y])
    assert m.u.reg_read(UC_X86_REG_EAX) == popup
    m.w(child+0x28, 1)
    for xy in [(0,0), (x+300,y), (x,y+40)]:
        m.invoke(0xA336D0, 0x131F4E8, xy)
        assert m.u.reg_read(UC_X86_REG_EAX) == 0
    m.invoke(0xA336D0, 0x131F4E8, [x,y])
    assert m.u.reg_read(UC_X86_REG_EAX) == child
    m.select(1)
    assert m.commands == [(0x176, 0)] and m.popup == 0


def test_limits_and_stale(m):
    m.right()
    m.w(m.parent + 0x114, 1); m.select(0)
    assert not m.commands, 'selection changed while menu open'
    m.right()
    panes = m.r(m.parent + 0xF4); pane = m.r(panes)
    m.w(panes, pane + 16); m.select(0); m.w(panes, pane)
    assert not m.commands, 'stale/replaced pane accepted'
    m.right(); m.w(0x131F6B0, 0); m.select(0); m.w(0x131F6B0, m.parent)
    assert not m.commands, 'closed owner accepted'
    m.w(0x15FAAE8, 7); m.right(); m.select(1)
    assert not m.commands, 'detached tabs ignored in max count'
    m.w(0x15FAAE8, 0)
    m.w(m.parent + 0xF8, panes + 4); m.w(0x15FAAE0, 1)
    m.right(); m.select(0)
    assert not m.commands, 'last tab deleted'
    m.right(); m.select(1)
    assert m.commands == [(0x176, 0)], 'last tab cannot create a new one'
    m.right()
    popup = m.popup
    m.invoke(m.c['event'], popup, [0, 0x27, 1, 0, 0, 0])
    m.invoke(m.c['event'], popup, [0, 0x27, 1, 0, 0, 0])
    assert len(m.commands) == 2, 'duplicate callback repeated action'


def test_lifetime(m):
    m.fail_create = True; m.right(); assert not m.created and not m.commands
    m.fail_create = False; m.right()
    popup = m.popup
    m.invoke(m.c['destroy'], popup, [1])
    assert m.r(m.c['state'] + 12) == m.r(m.c['state'] + 16) == 0
    m.right()
    popup = m.popup
    # A different native list reusing window 0x1A must retire the callback.
    m.invoke(m.c['event'], popup, [0, 0x53, 1, 0, 0, 0])
    assert m.r(popup) == 0x1034B94 and m.r(m.c['state'] + 16) == 0
    assert m.r(m.r(popup + 0xB4) + 0xD4) == 1


def test_defaults(m):
    from lupa.lua51 import LuaRuntime
    lua = LuaRuntime()
    lua.execute('ChatSubWnd_6 = {TabName="stale"}')
    lua.execute((Path(__file__).resolve().parents[1] / 'Assets/ModernChatUI/ModernChatDefaults.lub').read_text())
    g = lua.globals()
    assert [g[f'ChatSubWnd_{i}']['TabName'] for i in range(1, 6)] == ['Main','Battle','Guild','Party','Market']
    assert g.ChatSubWnd_6 is None and g.CanDragWnd == 0
    for i in range(1, 6):
        tab = g[f'ChatSubWnd_{i}']
        assert tab.TabState == 'On'
        assert all(tab[f'option{n}'] in (0, 1) for n in range(1, 26))
    assert [i for i in range(1, 26) if g.ChatSubWnd_3[f'option{i}']] == [5]
    assert [i for i in range(1, 26) if g.ChatSubWnd_4[f'option{i}']] == [4]
    assert [i for i in range(1, 26) if g.ChatSubWnd_5[f'option{i}']] == [1]
    assert m.r(0xD649F2) == m.c['defaults']
    assert m.cstr(m.c['defaults']) == r'Lua Files\ChatWndInfo\ModernChatDefaults'
    # Only the failure/fresh-layout fallback is redirected, not savedata.
    assert bytes(m.u.mem_read(0xD649ED, 4)) == bytes.fromhex('6a 00 6a 01')
    assert m.r(m.parent + 0x114) == m.r(m.tab + 0x7C) == 0
    assert bytes(m.u.mem_read(0x8D7709, 10)) == bytes.fromhex('c7 86 14 01 00 00 00 00 00 00'), 'native first selection changed'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('exe')
    ap.add_argument('--expect-popup-crash', action='store_true'); args = ap.parse_args()
    if args.expect_popup_crash:
        test_popup_manager_hit(TabsMachine(args.exe), True)
        raise SystemExit(0)
    for test in [test_popup_manager_hit, test_native_tab_state, test_native_mouse_poll, test_menu, test_lock, test_guards, test_limits_and_stale, test_lifetime, test_defaults]:
        test(TabsMachine(args.exe)); print('PASS', test.__name__, flush=True)
    print('Offline native routing verified; in-game appearance and save/reload still require acceptance.')
