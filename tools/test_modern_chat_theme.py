"""Offline Classic/New chat transitions using the stock resize/layout bodies.

Only OS/file APIs, drawing, image loading and allocation are boundaries. This
does not replace in-game visual acceptance or test the full user patch profile.
"""
import argparse
import struct
from unicorn.x86_const import *
from test_chat_item_icons import IconMachine
from test_modern_chat_tabs import contract as tabs_contract
from test_modern_chat_ui import pack


def contract(m):
    tag = m.pe.__data__.find(b'ModernChatUI.Theme.v1\0'); assert tag >= 0
    va = m.base + m.pe.get_rva_from_offset(tag)
    data = m.pe.get_memory_mapped_image(); pos = data.find(pack(va))
    assert pos >= 0 and data.find(pack(va), pos+1) < 0
    names = 'state load toggle aux mainRefresh floatRefresh mainSkin floatSkin controls floating input notify'.split()
    return dict(zip(names, [m.r(m.base+pos+4+i*4) for i in range(len(names))]))


class ThemeMachine(IconMachine):
    def __init__(self, exe):
        super().__init__(exe)
        self.c = contract(self)
        self.w(self.c['state']+4, 1)
        self.stub(0xA32E00, lambda: self.ret(0, 0))
        self.stub(self.c['mainSkin'], lambda: self.ret(0))
        self.stub(self.c['floatSkin'], lambda: self.ret(0))
        self.parent, self.tab = self.setup(594, 194)
        self.w(0x131F6B0, self.parent)
        for off, value in [(0x11C, 16), (0x120, 71), (0x124, 24), (0x30, 8),
                           (0x1C, 63), (0x20, 200), (0x108, 578)]:
            self.w(self.parent+off, value)
        for off, width in [(0xBC, 456), (0xC0, 90)]:
            child = self.r(self.parent+off); self.setsize(child, width, 16)
            self.string('Keep draft' if off == 0xBC else 'Keep recipient', child+0xD8)
        self.u.mem_write(0x131F50C, b'\x01')
        self.u.mem_write(0x15FAAEC, b'\x01')
        # Child-control positioning executes stock +0x10 methods.
        for off in [0x100, 0x104, 0x128, 0x12C]:
            self.setsize(self.r(self.parent+off), 10, 10)

    def theme(self, modern):
        self.w(self.c['state'], modern)
        self.invoke(self.c['notify'], 0)


def test_transitions(exe):
    m = ThemeMachine(exe); p, tab = m.parent, m.tab
    identities = bytes(m.u.mem_read(m.r(p+0xF4), 20))
    m.w(p+0x114, 3); m.w(tab+0x7C, 3)
    for modern in [0, 1, 0, 1, 1, 0]:
        m.theme(modern)
        assert m.r(p+0x124) == (42 if modern else 24)
        assert m.r(p+0x11C) == (2 if modern else 16)
        assert m.r(p+0x114) == m.r(tab+0x7C) == 3
        assert identities == bytes(m.u.mem_read(m.r(p+0xF4), 20))
        assert m.str_value(m.r(p+0xBC)+0xD8) == 'Keep draft'
        assert m.str_value(m.r(p+0xC0)+0xD8) == 'Keep recipient'
        if modern:
            assert (m.r(p+0x18), m.r(p+0x20)) == (198, 196)
            assert (m.r(tab+0x14), m.r(tab+0x18), m.r(tab+0x20)) == (530, 20, 178)
            assert m.r(m.r(p+0xE0)+0x20) == 0xFFFFFF9C
            assert m.r(m.r(p+0xBC)+0x14) == 399
        else:
            assert (m.r(p+0x18), m.r(p+0x20)) == (194, 200)
            assert (m.r(tab+0x14), m.r(tab+0x18), m.r(tab+0x20)) == (355, 16, 0)
            assert m.r(m.r(p+0xBC)+0x14) == 456
            assert m.r(m.r(p+0xC0)+0x14) == 90
    # The retained private table is inert in Classic; right-click is native.
    m.invoke(m.r(m.r(tab)+0x80), tab, [20, 8])
    m.invoke(m.r(m.r(tab)+0x84), tab, [20, 8])
    assert m.r(tabs_contract(m)['state']) == 0


def test_routing(exe):
    m = ThemeMachine(exe)
    # Main draw/overlay, edits, pane paint, clicks and events select stock in
    # Classic. Test route boundaries independently of native texture files.
    routes = [(0x1037F80+0x50, 0x8F3340, 0), (0x1037F80+0xAC, 0x8DE120, 0),
              (0x1037F80+0x64, 0x8F6C20, 2), (0x1037F80+0x94, 0x8FC220, 6),
              (0x1037F80+0x6C, 0x8F87C0, 2), (0x1037F80+0x7C, 0x8F72E0, 2),
              (0x1037EA8+0x50, 0x8F6270, 0), (0x1037EA8+0xAC, 0x8DE230, 0),
              (0x102D2D0, 0x851960, 0), (0x1028DFC, 0x824870, 0),
              (0x1028EE8, 0x824FC0, 0), (0x101B03C+0x94, 0x78A5F0, 6)]
    m.stub(m.c['mainRefresh'], lambda: m.ret(0))
    m.stub(m.c['floatRefresh'], lambda: m.ret(0))
    m.w(m.c['state'], 0)
    for slot, original, argc in routes:
        calls = []
        def original_call():
            calls.append((m.u.reg_read(UC_X86_REG_ECX), m.args(argc)))
            m.ret(argc*4, 0x1234)
        m.stub(original, original_call)
        m.invoke(m.r(slot), m.parent, list(range(argc)))
        assert calls == [(m.parent, list(range(argc)))]


def test_float_transition(exe):
    m = ThemeMachine(exe); floating = m.window(340, 210, 0x1037EA8)
    for off in [0xB4, 0xBC, 0xDC, 0xE0, 0xE4]:
        m.w(floating+off, m.window(10, 10, 0x102DD44, floating))
    for modern in [1, 0, 1, 0]:
        m.w(m.c['state'], modern)
        m.invoke(m.c['floatRefresh'], floating)
        assert m.r(m.r(floating+0xE4)+0x1C) == (0xFFFFFF9C if modern else 328)
        assert m.r(m.r(floating+0xDC)+0x1C) == (328 if modern else 316)
        assert m.r(m.r(floating+0xE0)+0x1C) == (312 if modern else 304)
    assert m.r(floating+0x14) == 340 and m.r(floating+0x18) == 210


def test_style_restore(exe):
    m = ThemeMachine(exe); p = m.parent
    for slot in [0x1028DFC, 0x1028EE8]:
        edit = m.r(p+(0xBC if slot == 0x1028DFC else 0xC0))
        original = [2, 3, 4, 5, 1, 0x800080, 1]
        fields = [0x8C, 0x90, 0x94, 0x98, 0xF4, 0xA8, 0xD4]
        for off, value in zip(fields, original): m.w(edit+off, value)
        m.w(m.c['state'], 1); m.invoke(m.r(slot), edit)
        assert [m.r(edit+off) for off in fields] == original
        pix, _, _ = m.pixels(edit)
        assert m.r(pix) == 0x80404040 and m.r(pix+4) == 0xFFFFFFFF


def test_skin_restore(exe):
    m = ThemeMachine(exe); p = m.parent; gear = m.r(p+0x12C)
    m.string('', gear+0x94)
    m.u.hook_del(m._stub_handles.pop(m.c['mainSkin']))
    def copy():
        dest, src, count = m.args(3)
        m.u.mem_write(dest, bytes(m.u.mem_read(src, count))); m.ret(0, dest)
    m.iat(0xFC1760, copy)
    images = []
    def image_init():
        path, variant, force = m.args(3)
        obj = m.u.reg_read(UC_X86_REG_ECX); text = m.cstr(path)
        images.append((obj, text, variant, force))
        size = 10 if text.endswith('.png') else 14
        m.w(obj+0xB4, size); m.w(obj+0xB8, size); m.ret(12, 1)
    m.stub(0x82DAC0, image_init)
    native = ['skin\\battle_option2_a.bmp', 'skin\\battle_option2_b.bmp', 'skin\\battle_option2_b.bmp']
    for modern in [0, 1]:
        m.w(m.c['state'], modern)
        for variant, call in enumerate([0x8E9407, 0x8E944C, 0x8E9491]):
            target = call+5+struct.unpack('<i', bytes(m.u.mem_read(call+1, 4)))[0]
            source = m.text_buffer(native[variant]); m.invoke(target, gear, [source, variant, 0])
            if modern: assert images[-1][1].endswith('icon_settings.png')
            else: assert images[-1][1] == native[variant]
            m.u.mem_write(source, b'gone\0')  # Native temporary string freed/reused.
    for modern in [0, 1, 0]:
        images.clear(); m.w(m.c['state'], modern); m.invoke(m.c['mainSkin'], p)
        assert len(images) == 3
        assert [v[2] for v in images] == [0, 1, 2]
        if not modern: assert [v[1] for v in images] == native
        else: assert all(v[1].endswith('icon_settings.png') for v in images)
        assert (m.r(gear+0x14), m.r(gear+0x18)) == ((10, 10) if modern else (14, 14))


def test_saved_theme_and_toggle(exe):
    m = ThemeMachine(exe); c = m.c; persisted = [0]; paths = []
    def open_file():
        paths.append(m.cstr(m.args(7)[0])); m.ret(28, 42)
    def read_file():
        handle, dest, size, count, overlap = m.args(5)
        assert (handle, size, overlap) == (42, 1, 0)
        m.u.mem_write(dest, bytes(persisted)); m.w(count, 1); m.ret(20, 1)
    writes = []
    def write_file():
        handle, data, size, count, overlap = m.args(5)
        writes.append(bytes(m.u.mem_read(data, size))); m.w(count, size); m.ret(20, 1)
    m.iat(0xFC1224, open_file); m.iat(0xFC122C, read_file)
    m.iat(0xFC1234, write_file); m.iat(0xFC1238, lambda: m.ret(4, 1))
    for value in [0, 1, 7]:
        persisted[0] = value; m.w(c['state'], 1); m.w(c['state']+4, 0)
        m.invoke(c['load'], 0); assert m.r(c['state']) == (value if value <= 1 else 1)
    assert paths == [r'savedata\roglobal_ui_theme.dat']*3
    # Optional unrelated windows are absent; keep the real theme toggle and
    # chat subscriber, file writer and stock chat resizing under execution.
    m.stub(0xA47B90, lambda: m.ret(4, 0))
    m.stub(0xA39340, lambda: m.ret(4, 0))
    m.w(c['state'], 0)
    # The real main-chat dispatch registers the live subscriber. Registration
    # must not depend on patch-time writes into another patch's cached block.
    m.w(c['state']+40, 0)
    m.invoke(m.r(0x1037F80+0x94), m.parent, [0, 0, 0, 0, 0, 0])
    assert m.r(c['state']+40) == c['notify'], 'chat refresh subscriber missing from output'
    for value in [1, 0, 1, 0]:
        m.invoke(c['toggle'], 0)
        assert m.r(c['state']) == value and writes[-1] == bytes([value])
        assert m.r(m.parent+0x124) == (42 if value else 24), (value, m.r(m.parent+0x124), hex(m.r(c['state']+40)), hex(c['notify']), hex(m.r(0x131F6B0)))


def test_clear_keys(exe):
    m = ThemeMachine(exe)
    for modern in [0, 1]:
        m.w(m.c['state'], modern)
        for site in [0x8F6CE7, 0x8FC555, 0x8FC9C2, 0x8FCAD8, 0x8FCB33,
                     0x8FE02A, 0x8FE229, 0x9022A2, 0x90235D]:
            for flags in [0x202, 0x247, 0xA82]:
                m.u.reg_write(UC_X86_REG_ESP, 0x3000F000)
                m.u.reg_write(UC_X86_REG_EFLAGS, flags)
                m.u.reg_write(UC_X86_REG_EAX, 0x12345678)
                m.u.emu_start(site, site+5, count=1000)
                assert m.u.reg_read(UC_X86_REG_EIP) == site+5
                assert m.u.reg_read(UC_X86_REG_ESP) == 0x3000EFFC
                assert m.u.reg_read(UC_X86_REG_EFLAGS) == flags
                assert m.u.reg_read(UC_X86_REG_EAX) == 0x12345678
                assert m.r(0x3000EFFC) == (0 if modern else 0xFFFF00FF)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('exe'); args = ap.parse_args()
    for test in [test_transitions, test_routing, test_float_transition, test_style_restore,
                 test_skin_restore, test_saved_theme_and_toggle, test_clear_keys]:
        test(args.exe); print('PASS', test.__name__, flush=True)
    print('Offline theme checks passed; in-game theme/skin acceptance still required.')
