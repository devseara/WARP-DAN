"""Reproduce stale text using native pane paint and native child composition.

Only GDI glyph rasterization and item-link positioning are test doubles. The
native clear, pane draw, dirty traversal, alpha compositor and installed modern
chat event/draw hooks execute. No running process or executable is modified.
"""
import argparse

from unicorn.x86_const import UC_X86_REG_ECX
from test_chat_item_icons import IconMachine, native_crt
from test_modern_chat_ui import pack


def verify(exe, expect_bug=False):
    m = IconMachine(exe)
    native_crt(m)
    # Execute native pane paint and clear, not the older layout-test doubles.
    for address in (0x851960, 0xA1CB30):
        m.u.hook_del(m._stub_handles.pop(address))
    m.stub(0x847750, lambda: m.ret(4))
    m.stub(0x847250, lambda: m.ret(4))

    def glyphs():
        obj = m.u.reg_read(UC_X86_REG_ECX)
        x, y, text, _, _, height, color, _, _ = m.args(9)
        pixels, width, rows = m.pixels(obj)
        for index, character in enumerate(m.cstr(text)):
            if character != ' ' and x + index * 3 < width and y < rows:
                m.w(pixels + (y * width + x + index * 3) * 4, color)
        m.ret(36)

    m.stub(0xA25A70, glyphs)
    parent = m.window(100, 80)
    pane = m.window(90, 40, 0x102D280, parent)
    m.w(pane + 0x1c, 5)
    m.w(pane + 0x20, 4)
    m.w(pane + 0xB8, 20)
    m.w(pane + 0x28, 1)  # Native constructor default: visible child.
    for obj in (parent, pane):
        m.w(m.r(obj + 0x24), 0xFD5CE4)
        children = m.alloc(12)
        m.w(children, children)
        m.w(children + 4, children)
        m.w(obj + 0x50, children)
    lines = m.alloc(24 * 32)
    colors = m.alloc(4 * 32)
    m.w(pane + 0x88, lines)
    m.w(pane + 0x8c, lines + 24)
    m.w(pane + 0xE4, colors)
    m.w(colors, 0x00FFFF00)
    parent_pixels, width, height = m.pixels(parent)
    backing = pack(0x80111114) * (width * height)
    m.u.mem_write(parent_pixels, backing)

    def frame(text, first_line=0):
        rows = [(text, 0x00FFFF00)] if isinstance(text, str) else text
        assert len(rows) <= 32
        for index, (message, color) in enumerate(rows):
            m.string(message, lines + index * 24)
            m.w(colors + index * 4, color)
        m.w(pane + 0x8c, lines + len(rows) * 24)
        m.w(pane + 0x98, first_line)
        m.w(pane + 0x58, 1)
        m.invoke(0xA1CE10, pane, [0])

    def parent_image():
        return bytes(m.u.mem_read(parent_pixels, width * height * 4))

    # At this coordinate LONG's tail paints a glyph, but NEW paints nothing.
    retired = parent_pixels + ((4 + 3) * width + 5 + 2 + 9 * 3) * 4
    frame('LONG MESSAGE')
    assert m.r(retired) == 0xFFFFFF00
    frame('NEW')
    stale = m.r(retired) == 0xFFFFFF00
    if expect_bug:
        assert stale, 'The installed stale-text failure was not reproduced'
        # A clean parent backing is a diagnostic control, not a runtime patch.
        m.u.mem_write(parent_pixels, backing)
        frame('NEW')
        assert m.r(retired) == 0x80111114
        print('REPRODUCED: native incremental pane redraw retains an old yellow '
              'glyph; modern chat suppresses clear event 0x74. Restoring the '
              'parent backing before composition removes the stale glyph.')
    else:
        assert not stale, 'Old chat glyph remains after a shorter message replaces it'
        assert m.r(retired) == 0x80111114, 'Message backing opacity/color changed'
        # Compare incremental updates to an independently cleared reference.
        # The same native draw/composition runs for both; only the reference
        # restores the entire parent before each draw. No GPU/text mock can
        # clear stale pixels on behalf of the incremental path.
        messages = [(('LONG DROP ANNOUNCEMENT ' * 2)[:7 + i % 25],
                     [0xFFFF00, 0x00FF00, 0x00FFFF, 0xFFFFFF][i % 4])
                    for i in range(32)]
        for iteration in range(100):
            first = iteration % 30
            rows = [] if iteration % 13 == 0 else messages
            frame(rows, first if rows else 0)
            incremental = parent_image()
            m.u.mem_write(parent_pixels, backing)
            frame(rows, first if rows else 0)
            assert incremental == parent_image(), f'Stale text in update {iteration}'
        # The message clear must not touch toolbar/frame/other child pixels.
        image = parent_image()
        for y in range(height):
            for x in range(width):
                if not (5 <= x < 95 and 4 <= y < 44):
                    offset = (y * width + x) * 4
                    assert image[offset:offset + 4] == backing[offset:offset + 4]
        check_clear_scope(m, parent, pane, parent_pixels, width, height)
        print('PASS: 100 native incremental chat updates, changing colors/lengths, '
              'scroll positions and empty history leave no stale glyphs; '
              'pane-only restoration preserves chrome and surface/cache mode')


def check_clear_scope(m, parent, pane, pixels, width, height):
    """Exercise the real installed dispatcher, including ignored notifications."""
    event = m.r(0x1037F80 + 0x94)
    surface = m.r(parent + 0x24)
    sentinel = pack(0xAD123456) * (width * height)
    initial = bytes(m.u.mem_read(pane, 0x7c))
    cached_head = m.alloc(12)
    m.w(cached_head, cached_head)
    m.w(cached_head + 4, cached_head)
    m.w(surface + 0x20, cached_head)
    m.w(surface + 0x24, 3)
    m.u.mem_write(surface + 0x28, b'\1')

    def notify(sender, expected=None):
        m.u.mem_write(pixels, sentinel)
        m.u.mem_write(surface + 0x1c, b'\0')
        cache = bytes(m.u.mem_read(surface + 0x20, 12))
        m.invoke(event, parent, [sender, 0x74, 0, 0, 0, 0])
        actual = bytes(m.u.mem_read(pixels, len(sentinel)))
        desired = bytearray(sentinel)
        if expected:
            x, y, w, h = expected
            for row in range(y, y + h):
                offset = (row * width + x) * 4
                desired[offset:offset + w * 4] = pack(0x80111114) * w
        assert actual == desired, 'Clear escaped the visible source-pane rectangle'
        assert bytes(m.u.mem_read(surface + 0x20, 12)) == cache, 'Changed cached texture state'
        assert m.u.mem_read(surface + 0x1c, 1)[0] == bool(expected)

    notify(pane, (5, 4, 90, 40))
    for x, y, w, h, expected in [
        (98, 78, 90, 40, (98, 78, 2, 2)),
        (0, 0, 1, 1, (0, 0, 1, 1)),
        (-100, 4, 90, 40, None), (5, -100, 90, 40, None),
        (100, 4, 90, 40, None), (5, 80, 90, 40, None),
        (5, 4, 0, 40, None), (5, 4, 90, 0, None),
        (5, 4, -1, 40, None), (5, 4, 90, -1, None),
    ]:
        for offset, value in [(0x1c, x), (0x20, y), (0x14, w), (0x18, h)]:
            m.w(pane + offset, value)
        notify(pane, expected)
    m.u.mem_write(pane, initial)
    for offset, value in [(0x28, 0), (0x10, 0), (0, 0x102DD44)]:
        m.w(pane + offset, value)
        notify(pane)
        m.u.mem_write(pane, initial)
    notify(0)
    m.w(parent + 0xE0, pane)
    notify(pane)  # Removed selector never clears chat or opens a popup.
    m.w(parent + 0xE0, 0)
    m.w(parent + 0x24, 0)
    notify(pane)
    m.w(parent + 0x24, surface)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe')
    parser.add_argument('--expect-bug', action='store_true')
    args = parser.parse_args()
    verify(args.exe, args.expect_bug)
