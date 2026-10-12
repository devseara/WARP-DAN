"""Native rename -> saved map -> Lua serialization regression for 2025-07-16.

Runs the real TabCtrl edit-commit producer, modern/native parent dispatcher,
map lookup, string assignment, map iteration and chat save routine in Unicorn.
CRT formatting/file I/O, graphics and focus/edit dismissal are explicit doubles.
No live client, savedata or process is changed; live relog acceptance is separate.
"""
import argparse
import re

from lupa.lua51 import LuaRuntime
from test_chat_item_icons import IconMachine, native_crt
from test_modern_chat_ui import pack


class RenameMachine(IconMachine):
    def __init__(self, exe):
        super().__init__(exe)
        native_crt(self)
        self.u.hook_del(self._stub_handles.pop(0x8FC220))
        self.stub(0x85F1F0, lambda: self.ret(0))  # Tab text measurement/layout.
        self.stub(0x8493E0, lambda: self.ret(0))  # Hide rename edit and restore focus.
        self.stub(0xA47B90, lambda: self.ret(4, 0))  # No open filter dialog.
        self.stub(0xA1CB50, lambda: self.ret(8))  # Legacy rectangle paint only.
        self.stub(0x529850, self.format)
        self.stub(0x573750, self.open_file)
        self.stub(0x573A60, self.write_file)
        self.stub(0x573060, lambda: self.ret(0))  # Close fixture file.
        self.output = bytearray()
        self.saves = 0
        self.initial = ['Main', 'Battle', 'Party', 'Guild', 'Market']
        self.parent, self.tab = self.setup(names=self.initial)
        self.w(self.parent + 0x11C, 20)
        self.w(self.parent + 0xB4, self.parent)
        self.w(0x15BEECC, 0)
        self.nodes = self.tree(0x15FAADC, self.initial)
        self.tree(0x15FAAE4, [])
        self.u.mem_write(0x15FAAEC, b'\x01')

    def tree(self, address, names):
        head = self.alloc(0x58)
        self.u.mem_write(head + 12, b'\x01\x01')
        nodes = [self.alloc(0x58) for _ in names]
        def branch(lo, hi, parent):
            if lo == hi:
                return head
            mid = (lo + hi) // 2
            node = nodes[mid]
            self.w(node, branch(lo, mid, node))
            self.w(node + 4, parent)
            self.w(node + 8, branch(mid + 1, hi, node))
            self.w(node + 0x10, mid)
            self.string(names[mid], node + 0x14)
            self.u.mem_write(node + 0x2C, bytes((mid + i) % 2 for i in range(25)))
            return node
        self.w(head + 4, branch(0, len(nodes), head))
        self.w(head, nodes[0] if nodes else head)
        self.w(head + 8, nodes[-1] if nodes else head)
        self.w(address, head)
        self.w(address + 4, len(nodes))
        return nodes

    def format(self):
        dest, fmt = self.args(2)
        fmt = self.cstr(fmt)
        kinds = re.findall(r'%([ds])', fmt)
        args = self.args(2 + len(kinds))[2:]
        values = tuple(self.cstr(value) if kind == 's' else value
                       for kind, value in zip(kinds, args))
        data = (fmt % values).encode('latin1')
        self.u.mem_write(dest, data + b'\0')
        self.ret(0, len(data))

    def open_file(self):
        path, mode, flag, source = self.args(4)
        assert self.cstr(path) == r'SaveData\ChatWndInfo_U.lua'
        assert (mode, flag, source) == (0x1001, 1, 0)
        self.output.clear()
        self.saves += 1
        self.ret(16, 1)

    def write_file(self):
        data, size = self.args(2)
        self.output += bytes(self.u.mem_read(data, size))
        self.ret(8, size)

    def rename(self, index, name, cancel=False):
        self.w(self.tab + 0x7C, index)
        self.w(self.parent + 0x114, index)
        edit = self.r(self.tab + 0xD8)
        self.w(edit + 0x1C, 0)
        self.string(name, edit + 0xD8)
        # Native producer performs the visible rename, then emits 0x74 with
        # sender=TabCtrl, title pointer, and index. Do not synthesize that event.
        self.invoke(0x861C80, self.tab, [edit, 0, int(cancel), 0, 0, 0])

    def labels(self):
        first = self.r(self.tab + 0xB4)
        return [self.str_value(first + i * 24) for i in range(5)]

    def stored(self):
        return [self.str_value(node + 0x14) for node in self.nodes]

    def save(self):
        self.invoke(0x8F9D00, self.parent)
        return bytes(self.output).decode('latin1')


def check_saved_lua(m, expected, filters):
    # The edit commit itself must have written the file, before logout/close.
    saved = bytes(m.output).decode('latin1')
    assert saved, 'Rename did not immediately serialize ChatWndInfo_U.lua'
    assert m.save() == saved, 'Later native logout save changed the renamed records'
    assert re.findall(r'TabName = \[\[(.*?)\]\]', saved) == expected
    # A fresh Lua 5.1 VM consumes the actual native writer output. This covers
    # the persisted data contract, not the game's resource loader or live login.
    lua = LuaRuntime(encoding=None)
    lua.execute(saved.encode('latin1'))
    assert lua.globals()[b'CanDragWnd'] == 1
    for index, name in enumerate(expected):
        record = lua.globals()[f'ChatSubWnd_{index + 1}'.encode()]
        assert record[b'TabName'] == name.encode('latin1')
        assert record[b'TabState'] == b'On'
        assert bytes(record[f'option{i + 1}'.encode()] for i in range(25)) == filters[index]


def verify(exe, expect_bug=False):
    m = RenameMachine(exe)
    filters = [bytes(m.u.mem_read(node + 0x2C, 25)) for node in m.nodes]
    m.rename(0, 'qweq')
    assert m.labels()[0] == 'qweq', 'Native edit did not rename the visible tab'
    if expect_bug:
        assert m.stored() == m.initial, 'Expected stale saved names'
        saved = m.save()
        assert 'TabName = [[Main]]' in saved and '[[qweq]]' not in saved
        print('REPRODUCED: visible tab renamed to qweq, native map and saved Lua '
              'still contain Main; modern event 0x74 drops the rename notification.')
        return
    assert m.stored() == m.labels(), 'Visible name was not committed to the native saved map'
    assert m.saves == 1, 'A committed rename must save exactly once'
    expected = ['qweq', 'Battle', 'Party', 'Guild', 'Market']
    check_saved_lua(m, expected, filters)
    # Inline/heap transitions, all indices, repeated edits, spaces and UTF-8
    # bytes. Narrow the font metric only for the native size-limit acceptance.
    m.stub(0xA21C90, lambda: m.ret(24, 8))
    for index, name in [(1, 'A long custom chat tab'), (4, 'Market Prices'),
                        (2, 'Party Team'), (3, 'Guild Talk'), (0, 'My Main'),
                        (1, 'B'), (1, 'Another long chat title'),
                        (4, 'Market \u00e9'.encode('utf8').decode('latin1'))]:
        previous_saves = m.saves
        m.rename(index, name)
        assert m.saves == previous_saves + 1, 'Rename not saved immediately or saved twice'
        expected[index] = name
        assert m.labels() == m.stored() == expected
        assert [bytes(m.u.mem_read(node + 0x2C, 25)) for node in m.nodes] == filters
        check_saved_lua(m, expected, filters)
    for cancel, title in [(True, 'Cancelled rename'), (False, '')]:
        previous_saves = m.saves
        m.rename(0, title, cancel)
        assert m.labels() == m.stored() == expected
        assert m.saves == previous_saves, 'Cancelled or empty edit wrote savedata'
    # Redraw/selection notifications must never trigger disk writes.
    event = m.r(0x1037F80 + 0x94)
    pane = m.r(m.parent + 0xB4)
    previous_saves = m.saves
    for sender, code in [(0, 0x74), (pane, 0x74), (m.tab, 0x16)]:
        m.invoke(event, m.parent, [sender, code, 0, 0, 0, 0])
    assert m.saves == previous_saves, 'A non-rename event wrote savedata'
    image = m.pe.get_memory_mapped_image()
    theme = image.find(b'ModernChatUI.Theme.v1\0')
    if theme >= 0:
        descriptor = image.find(pack(m.base + theme))
        assert descriptor >= 0
        state = m.r(m.base + descriptor + 4)
        for mode, title in [(0, 'Classic rename'), (1, 'New rename')]:
            m.w(state, mode)
            previous_saves = m.saves
            m.rename(3, title)
            assert m.saves == previous_saves + 1, 'Theme bypassed immediate save'
            expected[3] = title
            assert m.labels() == m.stored() == expected
            check_saved_lua(m, expected, filters)
    print('PASS: native edit commit, all five saved tab records, short/long/UTF-8 '
          'names, repeated edits, immediate native Lua save and identical logout save; '
          'cancel/empty/redraw events do not save; '
          'filter masks preserved. Live relog/restart acceptance remains separate.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe')
    parser.add_argument('--expect-bug', action='store_true')
    args = parser.parse_args()
    verify(args.exe, args.expect_bug)
