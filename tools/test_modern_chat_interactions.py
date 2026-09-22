"""Native PM dropdown and emotion action routing; no game/network activity.

Executes stock PM-history construction, list selection, recipient assignment,
emotion providers and native icon activation. Allocation/render/network/close
manager boundaries are explicit fixtures, not claims of live UI acceptance.
"""
import argparse
from collections import deque
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_chat_item_icons import IconMachine
from test_modern_chat_tabs import TabsMachine
from test_modern_chat_ui import pack


def contract(m):
    tag = m.pe.__data__.find(b'ModernChatUI.Interactions.v1\0')
    assert tag >= 0
    va = m.base + m.pe.get_rva_from_offset(tag)
    data = m.pe.get_memory_mapped_image(); pos = data.find(pack(va))
    assert pos >= 0 and data.find(pack(va), pos+1) < 0
    names = 'history emoji click historyTip normal recent favorites channel channelTip'.split()
    return dict(zip(names, [m.r(m.base+pos+4+i*4) for i in range(len(names))]))


class HistoryMachine(TabsMachine):
    def __init__(self, exe):
        super().__init__(exe)
        self.actions = contract(self)
        self.recipient = self.r(self.parent+0xC0)
        self.w(self.recipient, 0x1028E98)  # Native whisper edit, including SetText.
        self.string('DraftRecipient', self.recipient+0xD8)
        self.w(self.recipient+0x88, 80)  # Native maximum recipient length.
        self.string('Unsent message', self.r(self.parent+0xBC)+0xD8)
        self.w(self.parent+0x1C, 63); self.w(self.parent+0x20, 200)
        self.stub(0xA47B90, lambda: self.ret(4, self.parent if self.args(1)[0] == 1
                                          else self.popup if self.args(1)[0] == 0x1A else 0))
        self.stub(0x8BC640, self.history_resize)
        self.stub(0xDBBC4F, lambda: self.ret(0, self.alloc(self.args(1)[0])))
        self.stub(0xA70950, lambda: self.ret(0))  # OS IME caret update.
        def copy():
            dest, src, count = self.args(3)
            self.u.mem_write(dest, bytes(self.u.mem_read(src, count))); self.ret(0, dest)
        self.iat(0xFC1760, copy); self.iat(0xFC1740, copy)
        self.history([])

    def history_resize(self):
        obj = self.u.reg_read(UC_X86_REG_ECX); w, h = self.args(2)
        assert obj == self.popup and w in (112, 156) and 16 <= h <= 80
        self.setsize(obj, w, h); child = self.r(obj+0xB4); self.setsize(child, w, h)
        count = (self.r(child+0x8C)-self.r(child+0x88))//24
        self.w(child+0x98, min(self.r(child+0x98), max(0, count-h//16)))
        self.ret(8)

    def make_popup(self):
        super().make_popup()
        if not self.popup: return
        child = self.r(self.popup+0xB4)
        strings = self.alloc(24*32)
        self.w(child+0x88, strings); self.w(child+0x8C, strings)
        scrollbar = self.window(12, 80, 0x102CAC8, child)
        # Scrollbar rendering is a boundary; native list range and offset run.
        table = self.alloc(0xD4); self.w(scrollbar, table)
        invalidate = self.alloc(16); self.w(table+0x98, invalidate)
        self.stub(invalidate, lambda: self.ret(0))
        position = self.alloc(16); self.w(table+0x10, position)
        self.stub(position, lambda: self.ret(8))
        self.w(child+0xAC, scrollbar)

    def history(self, names):
        self.names = names; strings = self.alloc(max(24, 24*len(names)))
        for i, name in enumerate(names): self.string(name, strings+i*24)
        self.w(self.recipient+0x11C, strings)
        self.w(self.recipient+0x120, strings+len(names)*24)
        self.w(self.recipient+0x124, strings+len(names)*24)
        self.w(self.recipient+0x128, 0)

    def invoke(self, address, obj=0, args=None):
        trace = deque(maxlen=24)
        def step(u, address, size, data):
            if address < 0x400000:
                raise AssertionError(('invalid native history dispatch', hex(address),
                                      [hex(pc) for pc in trace]))
            trace.append(address)
        hook = self.u.hook_add(UC_HOOK_CODE, step)
        try:
            return super().invoke(address, obj, args or [])
        except Exception:
            print('History dispatch IP', hex(self.u.reg_read(UC_X86_REG_EIP)),
                  'SP', hex(self.u.reg_read(UC_X86_REG_ESP)),
                  'trace', [hex(address) for address in trace], flush=True)
            raise
        finally:
            self.u.hook_del(hook)

    def open_history(self):
        self.click_control(8)

    def click_control(self, x):
        xy = [x, self.r(self.parent+0x18)-32]
        self.invoke(self.r(self.r(self.parent)+0x64), self.parent, xy)
        self.invoke(self.r(self.r(self.parent)+0x7C), self.parent, xy)

    def pick_history(self, row):
        child = self.r(self.popup+0xB4)
        assert self.r(child+0xD4) == 1, 'PM list routed to tab popup instead of main chat'
        # Native ListBox scroll offset, then a click in the first visible row.
        self.w(child+0x98, row)
        self.invoke(0x858D10, child, [10, 8])

    def mouse_poll(self, state, x, y):
        """Run the native dispatcher, including its outside-popup close pass.

        Root-list search and hover rendering are boundaries. Coordinate
        conversion, down/held/up dispatch, capture and dismissal stay native.
        """
        manager = 0x131F4E8
        if not hasattr(self, 'poll_code'):
            self.poll_code = self.alloc(256)
            self.stub(0xA336D0, lambda: self.ret(8, self.parent))
            self.stub(0xA23470, lambda: self.ret(8))
            self.stub(0x880CB0, lambda: self.ret(8))
            empty = self.alloc(12)
            self.w(empty, empty); self.w(empty+4, empty)
            self.w(manager+0x17C, empty)
            done = self.poll_code+192
            self.u.mem_write(done, b'\x5f\x5e\x5b\x8b\xe5\x5d\xc3')
            self.stub(0xA470CC, lambda: self.u.reg_write(UC_X86_REG_EIP, done))
        self.w(0x11E40E4, state); self.w(0x11E40E8, 0); self.w(0x11E40EC, 0)
        x += self.r(self.parent+0x1C); y += self.r(self.parent+0x20)
        prefix = (b'\x55\x8b\xec\x81\xec' + pack(0x90) + b'\x53\x56\x57\xbb' + pack(manager) +
                  b'\xc7\x45\x8c' + pack(y) + b'\xc7\x45\x90' + pack(x) + b'\xe9')
        self.u.mem_write(self.poll_code, prefix+pack(0xA46940-(self.poll_code+len(prefix)+4)))
        self.invoke(self.poll_code, manager)


def test_native_dropdown_clicks(exe):
    m = HistoryMachine(exe); m.history(['Friend', 'Previous PM'])
    labels = dict(zip([0x55, 0x56, 0x1B5, 0x939, 0xFC0],
                      map(m.text_buffer, ['All', 'Party', 'Guild', 'Allies', 'Clan'])))
    m.stub(0xA9ED30, lambda: m.ret(0, labels[m.args(1)[0]]))
    for x, expected in [(530, ['All', 'Party', 'Guild', 'Allies', 'Clan']),
                        (8, ['Friend', 'Previous PM', ''])]:
        position = (m.r(m.parent+0x1C), m.r(m.parent+0x20))
        for state in [1, 2, 2, 3]:
            m.mouse_poll(state, x, 208)
            if state != 3:
                assert not m.popup, 'popup opened before button release'
                assert m.r(0x131F4E8+0x19C) == m.parent
            assert (m.r(m.parent+0x1C), m.r(m.parent+0x20)) == position
        assert m.popup, ('dropdown was closed during native click dispatch',
                         x, m.created, m.closed)
        assert m.labels == expected
        assert m.r(0x131F4E8+0x19C) == 0
        m.mouse_poll(0, x, 208); assert m.popup
        m.invoke(0x858D10, m.r(m.popup+0xB4), [10, 8])
        assert not m.popup


def test_dropdown_press_guards(exe):
    m = HistoryMachine(exe); m.history(['Friend'])
    before = len(m.created)
    # Different control, just outside each edge, and outside the whole chat.
    for start, end in [(8, (530,208)), (530, (8,208)), (8, (2,208)),
                       (8, (23,208)), (530, (518,208)), (530, (543,208)),
                       (8, (8,197)), (8, (8,218)), (530, (-30,-40))]:
        m.mouse_poll(1, start, 208)
        m.mouse_poll(2, *end)
        m.mouse_poll(3, *end)
        assert len(m.created) == before and m.r(0x131F4E8+0x19C) == 0
        assert (m.r(m.parent+0x1C), m.r(m.parent+0x20)) == (63,200)
    # A release without a matching press does not open either dropdown.
    for x in [8, 530]: m.mouse_poll(3, x, 208)
    assert len(m.created) == before
    # Lock affects tab editing/dragging, not changing one's chat destination.
    for locked in [0, 1]:
        m.u.mem_write(0x15FAAEC, bytes([locked]))
        m.mouse_poll(1, 8, 208); m.mouse_poll(2, 200, 50)
        m.mouse_poll(3, 8, 208)
        assert m.popup and m.labels == ['Friend', '']
        m.pick_history(0)
    # Lost capture must cancel, without releasing the new owner's capture.
    m.mouse_poll(1, 8, 208); m.w(0x131F4E8+0x19C, m.tab)
    before = len(m.created)
    m.invoke(m.r(m.r(m.parent)+0x7C), m.parent, [8,208])
    assert len(m.created) == before and m.r(0x131F4E8+0x19C) == m.tab
    m.w(0x131F4E8+0x19C, 0)
    # Switching to Classic during a press still cleans up capture, but cannot
    # launch a New-only control. A subsequent New click must work normally.
    if b'ModernChatUI.Theme.v1\0' in m.pe.__data__:
        from test_modern_chat_theme import contract as theme_contract
        theme = theme_contract(m)['state']
        m.mouse_poll(1, 8, 208); m.w(theme, 0)
        m.mouse_poll(3, 8, 208)
        assert not m.popup and m.r(0x131F4E8+0x19C) == 0
        m.w(theme, 1); m.click_control(8); assert m.popup


def test_history(exe):
    m = HistoryMachine(exe)
    m.open_history(); assert not m.popup and not m.commands
    assert m.r(m.parent+0xB4) == m.r(0x131F4E8+0x1A0) == m.recipient
    assert m.str_value(m.recipient+0xD8) == 'DraftRecipient'
    names = ['qweqw', 'q1qwe', 'asd1', '121asa', 'zxc23', 'RecipientLongerThanSSO', 'LastFriend']
    m.history(names)
    for row in [0, 4, 5, 6, len(names)]:
        m.open_history()
        assert m.labels == names + ['']
        assert m.r(m.popup) == 0x1034B94
        assert (m.r(m.popup+0x14), m.r(m.popup+0x18)) == (112, 80)
        assert (m.r(m.popup+0x1C), m.r(m.popup+0x20)) == (66, 316)
        m.pick_history(row)
        assert m.str_value(m.recipient+0xD8) == (names[row] if row < len(names) else '')
        assert not m.popup and not m.commands
        assert m.str_value(m.r(m.parent+0xBC)+0xD8) == 'Unsent message'
        assert m.r(0x131F4E8+0x1A0) == m.r(m.parent+0xBC)
    # Typing within the recipient edit does not reopen its history.
    count = len(m.created)
    m.invoke(m.actions['click'], m.parent, [23, 208])
    assert len(m.created) == count and m.r(0x131F4E8+0x1A0) == m.recipient
    m.w(0x131F4E8+0x19C, m.tab); m.open_history()
    assert len(m.created) == count
    m.w(0x131F4E8+0x19C, 0)
    m.history(['OnlyFriend']); m.w(m.parent+0x20, 0); m.setsize(m.parent, 594, 60)
    m.open_history(); assert m.r(m.popup+0x20) == 0


def test_popup_handoff(exe):
    m = HistoryMachine(exe); m.history(['Friend'])
    m.right(2); assert m.labels == ['Delete Tab', 'Create New Tab']
    m.open_history(); assert m.labels == ['Friend', '']
    m.pick_history(0)
    assert m.str_value(m.recipient+0xD8) == 'Friend' and not m.commands
    m.open_history(); m.right(1)
    assert m.labels == ['Delete Tab', 'Create New Tab']
    m.select(1); assert m.commands == [(0x176, 1)]


def test_channels(exe):
    m = HistoryMachine(exe)
    names = ['Send to All', 'Send to Party', 'Send to Guild', 'Send to Allies', 'Send to Clan']
    labels = dict(zip([0x55, 0x56, 0x1B5, 0x939, 0xFC0], map(m.text_buffer, names)))
    m.stub(0xA9ED30, lambda: m.ret(0, labels[m.args(1)[0]]))  # Localization boundary.
    m.w(0x15FF838, 0)
    for row in range(5):
        m.click_control(530)
        assert m.labels == names and m.r(m.parent+0xF0) == 1
        assert (m.r(m.popup+0x14), m.r(m.popup+0x18)) == (112, 80)
        assert (m.r(m.popup+0x1C), m.r(m.popup+0x20)) == (545, 316)
        child = m.r(m.popup+0xB4)
        assert m.r(child+0xD4) == 1
        m.invoke(0x858D10, child, [10, row*16+8])
        assert m.r(0x15FF838) == row and not m.popup and not m.commands, (row, m.r(0x15FF838), m.popup, m.commands)
        assert m.str_value(m.recipient+0xD8) == 'DraftRecipient'
        assert m.str_value(m.r(m.parent+0xBC)+0xD8) == 'Unsent message'
    m.history(['Friend']); m.open_history(); m.pick_history(0)
    assert m.str_value(m.recipient+0xD8) == 'Friend' and m.r(0x15FF838) == 4
    m.right(0); m.invoke(m.actions['channel'], m.parent)
    assert m.labels == names and not m.r(m.c['state']+12)
    m.w(0x131F4E8+0x19C, m.tab); count = len(m.created)
    m.invoke(m.actions['channel'], m.parent); assert len(m.created) == count


def test_emoji_toggle(exe):
    m = IconMachine(exe); c = contract(m); parent, tab = m.setup()
    opened = []; closed = []; obj = m.window(298, 380, 0x101B634)
    def create():
        assert m.args(1) == [0x57]
        opened.append(obj); m.w(0x131F86C, obj); m.ret(4, obj)
    def close():
        assert m.args(1) == [0x57]
        closed.append(m.r(0x131F86C)); m.w(0x131F86C, 0); m.ret(4, 1)
    m.stub(0xA39340, create); m.stub(0xA2E770, close)
    m.stub(0xA47B90, lambda: m.ret(4, m.r(0x131F86C) if m.args(1) == [0x57] else 0))
    m.string('Keep draft', m.r(parent+0xBC)+0xD8)
    for expected in [obj, 0, obj, 0]:
        m.invoke(c['click'], parent, [550, 208]); assert m.r(0x131F86C) == expected
        assert m.r(0x131F4E8+0x19C) == 0
    assert len(opened) == len(closed) == 2
    assert m.str_value(m.r(parent+0xBC)+0xD8) == 'Keep draft'
    # An existing Alt+L window is toggled too, without creating a duplicate.
    m.w(0x131F86C, obj); m.invoke(c['emoji'], parent)
    assert not m.r(0x131F86C) and len(opened) == 2 and len(closed) == 3


def test_emotion_selection(exe):
    m = IconMachine(exe); c = contract(m)
    parent, tab = m.setup(); m.w(0x131F6B0, parent)
    picker = m.window(298, 380, 0x101B634)
    normal = m.window(271, 303, 0x101B03C, picker)
    provider = m.alloc(12); m.w(provider, 0xFD89D0)
    m.w(provider+4, 1000); m.w(provider+8, 2000)
    insert = m.alloc(4); m.w(insert, 0x101B120)
    for offset, value in [(0xBC, provider), (0xC0, insert)]: m.w(normal+offset, value)
    manager = m.alloc(0x100); vt = m.alloc(0x40); m.w(manager, vt); m.w(0x121333C, manager)
    sent = []; closed = []; inserted = []
    command = m.alloc(16); m.w(vt+0x18, command)
    def notify():
        sent.append(m.args(5)); m.ret(20)
    m.stub(command, notify)
    def close():
        assert m.args(1) == [0x57]
        assert sent or inserted, 'closed before the native emotion action'
        closed.append(m.r(0x131F86C)); m.w(0x131F86C, 0); m.ret(4, 1)
    m.stub(0xA2E770, close)
    # Native provider dispatches the emotion command, doubled before network.
    icon = m.window(40, 40, 0x101C1E8, normal)
    m.w(icon+0x7C, 0); m.w(icon+0x80, 23)
    m.w(0x131F86C, picker)
    m.invoke(0x791F00, icon, [8, 8])
    assert sent == [[0x1F, 23, 0, 0, 0]] and closed == [picker]
    # Native text-insertion provider still writes the /command via SetText.
    text = m.text_buffer('/smile')
    m.stub(0x591470, lambda: m.ret(8, text if m.args(2) == [0, 23] else 0))
    edit = m.r(parent+0xBC); editvt = m.alloc(0xE0)
    m.u.mem_write(editvt, bytes(m.u.mem_read(0x1028DAC, 0xE0))); m.w(edit, editvt)
    assign = m.alloc(16); m.w(editvt+0xD4, assign)
    def settext():
        inserted.append(m.cstr(m.args(1)[0])); m.ret(4)
    m.stub(assign, settext)
    m.w(0x131F86C, picker)
    m.invoke(c['normal'], normal, [icon, 0xAE, 0, 23, 0, 0])
    assert inserted == ['/smile'] and len(closed) == 2
    # Invalid IDs or a failed provider do not close the box.
    for args in [[icon, 0xAF, -1, 23, 0, 0], [icon, 0xAE, 0, 999, 0, 0]]:
        m.w(0x131F86C, picker); m.invoke(c['normal'], normal, args)
        assert m.r(0x131F86C) == picker and len(closed) == 2
    for key, table in [('recent', 0x101B12C), ('favorites', 0x101B318)]:
        grid = m.window(271, 303, table, picker); m.w(grid+0xBC, provider)
        m.w(0x131F86C, picker); m.invoke(c[key], grid, [icon, 0xAE, 0, 24, 0, 0])
        assert closed[-1] == picker and not m.r(0x131F86C)
    # Detached/unrelated grid retains stock behavior and never closes picker.
    count = len(closed); m.w(normal+0x10, 0); m.w(0x131F86C, picker)
    m.invoke(c['normal'], normal, [icon, 0xAF, 0, 25, 0, 0])
    assert len(closed) == count and sent[-1] == [0x1F, 25, 0, 0, 0]
    assert m.r(0x101B45C+0x94) == 0x78CC20, 'shop/preview flow changed'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('exe'); args = ap.parse_args()
    for test in [test_native_dropdown_clicks, test_dropdown_press_guards, test_emoji_toggle,
                 test_emotion_selection, test_history, test_popup_handoff, test_channels]:
        test(args.exe); print('PASS', test.__name__, flush=True)
    print('Offline interaction checks passed; live in-game appearance still needs acceptance.')
