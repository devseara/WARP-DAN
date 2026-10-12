"""Execute emitted control hover and native gear tooltip routing offline.

Cursor notification, image initialization and tooltip painting are boundaries.
Native string assignment, coordinate conversion and gear hover remain real.
No client is started; this does not claim in-game visual acceptance.
"""
import argparse
from unicorn.x86_const import *
from test_chat_item_icons import IconMachine
from test_modern_chat_ui import pack


def contract(m):
    tag = m.pe.__data__.find(b'ModernChatUI.Tooltips.v1\0')
    assert tag >= 0
    va = m.base + m.pe.get_rva_from_offset(tag)
    data = m.pe.get_memory_mapped_image()
    pos = data.find(pack(va))
    assert pos >= 0 and data.find(pack(va), pos + 1) < 0
    names = 'cursor gear emoticons send settings locked unlocked history channel'.split()
    return dict(zip(names, [m.r(m.base + pos + 4 + 4*i) for i in range(len(names))]))


def publisher(m):
    cursor = m.alloc(0x200); m.w(0x121333C, cursor)
    calls = []
    def show():
        assert m.u.reg_read(UC_X86_REG_ECX) == cursor
        text, x, y, color, flag, substitute = m.args(6)
        calls.append((m.cstr(text), x, y, color, flag, substitute))
        m.ret(24)
    m.stub(0xA753D0, show)
    m.stub(0xA4AD20, lambda: m.ret(20))
    return calls


def test_control_tooltips(m, c):
    calls = publisher(m)
    labels = dict(emoticons='Emoticons', send='Send Message', settings='Chat Settings',
                  locked='Chat Locked', unlocked='Chat Unlocked', history='PM History',
                  channel='Send to All / Party / Guild / Allies / Clan')
    assert {k: m.cstr(c[k]) for k in labels} == labels
    for width, height in [(180, 100), (594, 240), (800, 320)]:
        parent, tab = m.setup(width, height)
        m.w(parent + 0x1C, 73); m.w(parent + 0x20, 91)
        edit = m.r(parent + 0xBC); recipient = m.r(parent + 0xC0)
        m.string('Unsent draft', edit + 0xD8); m.string('PM target', recipient + 0xD8)
        for unlocked in [0, 1, 0]:
            m.u.mem_write(0x15FAAEC, bytes([unlocked]))
            for x in [2,3,22,23,width-76,width-75,width-52, width-51, width-28, width-27, width-19,
                      width-18, width-11, width-10, width-4, width-3]:
                for y in [height-43, height-42, height-23, height-22, height-21,
                          height-20, height-1, height]:
                    expected = None
                    if 3 <= x < 23 and height-42 <= y < height-22:
                        expected = labels['history']
                    if width-75 <= x < width-51 and height-42 <= y < height-22:
                        expected = labels['channel']
                    if width-51 <= x < width-3 and height-42 <= y < height-22:
                        expected = 'Emoticons' if x < width-27 else 'Send Message'
                    if width-18 <= x < width-10 and height-20 <= y < height:
                        expected = 'Chat Unlocked' if unlocked else 'Chat Locked'
                    before = len(calls)
                    m.invoke(c['cursor'], parent, [x, y])
                    assert len(calls) == before + (expected is not None), (x, y, expected)
                    if expected:
                        assert calls[-1] == (expected, x+83, y+67, 0xFFFFFFFF, 0, 0)
        for field, value in [(0x30, 0), (0xBC, 0)]:
            saved = m.r(parent + field); m.w(parent + field, value)
            before = len(calls)
            m.invoke(c['cursor'], parent, [width-40, height-32])
            assert len(calls) == before
            m.w(parent + field, saved)
        for capture in [parent, tab]:
            m.w(0x131F4E8 + 0x19C, capture); before = len(calls)
            m.invoke(c['cursor'], parent, [width-15, height-10])
            assert len(calls) == before
        m.w(0x131F4E8 + 0x19C, 0)
        assert m.str_value(edit + 0xD8) == 'Unsent draft'
        assert m.str_value(recipient + 0xD8) == 'PM target'
    before = len(calls); m.w(0x121333C, 0)
    m.invoke(c['cursor'], parent, [width-40, height-32])
    assert len(calls) == before, 'missing cursor manager was not guarded'


def test_gear_tooltip(m, c):
    calls = publisher(m)
    def memmove():
        dest, src, count = m.args(3)
        m.u.mem_write(dest, bytes(m.u.mem_read(src, count))); m.ret(0, dest)
    m.iat(0xFC1760, memmove)  # CRT boundary; execute native std::string assign.
    parent, tab = m.setup()
    m.w(parent + 0x1C, 73); m.w(parent + 0x20, 91)
    gear = m.window(24, 20, 0x1029820, parent)
    m.w(gear + 0x1C, 545); m.w(gear + 0x20, 220)
    m.w(gear + 0x2C, 0xC1)
    images = []
    def image_init():
        assert m.u.reg_read(UC_X86_REG_ECX) == gear
        path, variant, extra = m.args(3)
        images.append((m.cstr(path), variant, extra)); m.ret(12)
    m.stub(0x82DAC0, image_init)
    # Exercise initial assignment and repeated assignment, including a prior
    # heap-backed hint. The native string routine must release/retain safely.
    for initial in ['', 'Previous tooltip longer than inline storage']:
        m.string(initial, gear + 0x94)
        for variant in range(3):
            m.invoke(c['gear'], gear, [m.text_buffer('old.bmp'), variant, 0])
            assert m.str_value(gear + 0x94) == 'Chat Settings'
            assert images[-1][0].endswith(r'uirenewal\chat\icon_settings.png'), images[-1]
            assert images[-1][1:] == (variant, 0)
            assert m.r(gear) == 0x1029820 and m.r(gear + 0x2C) == 0xC1
    # Execute the stock button's hover implementation, not a custom substitute.
    m.invoke(0x8274A0, gear, [7, 8])
    assert calls[-1][0] == 'Chat Settings'
    assert calls[-1][1:3] == (618, 291)
    assert calls[-1][3:] == (0xFFFFFFFF, 0, 1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('exe'); args = ap.parse_args()
    for test in [test_control_tooltips, test_gear_tooltip]:
        m = IconMachine(args.exe); test(m, contract(m))
        print('PASS', test.__name__, flush=True)
    print('Offline hover routing verified; in-game tooltip appearance still needs acceptance.')
