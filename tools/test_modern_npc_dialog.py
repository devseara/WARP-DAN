"""Execute emitted NPC frame/button hooks in Unicorn with explicit UI doubles.

Verifies scoped rendering and native callback preservation, not live acceptance.
"""
import argparse
from pathlib import Path
import struct

from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX
from test_modern_chat_ui import Machine, pack, over

ASSETS = Path(__file__).resolve().parents[1] / 'Assets' / 'ModernNpcDialog'
SAY, CHOICE, BUTTON = 0x1033094, 0x103316C, 0x1029820
CHOICE3 = 0x104ADE0


class NpcMachine(Machine):
    def __init__(self, exe):
        super().__init__(exe, ASSETS)
        self.loaded = []
        self.hidden_assets = set()
        self.stub(0x823E10, lambda: self.forward('stock-button', 0))
        self.stub(0x8B5F30, lambda: self.forward('stock-say', 0))
        self.stub(0x8B30D0, lambda: self.forward('stock-choice', 0))

    def clear(self):
        # Native CSurface::Clear 0x53E370 swaps COLORREF R/B into BGRA pixels.
        color = self.args(1)[0]
        color = (color & 0xFF00FF00) | ((color & 255) << 16) | ((color >> 16) & 255)
        pixels, width, height = self.pixels(self.u.reg_read(UC_X86_REG_ECX))
        self.u.mem_write(pixels, pack(color) * (width * height))
        self.ret(4)

    def texture(self):
        name = self.cstr(self.args(1)[0]).split('\\')[-1]
        self.loaded.append(name)
        value = 0 if name in self.hidden_assets or not (ASSETS / name).is_file() else self.load_texture(name)
        self.ret(4, value)

    def button(self, parent, name='btn_ok.bmp', state=0, disabled=False, x=10, y=10, full_path=True):
        obj = self.window(44, 18, BUTTON, parent)
        value = ('ui\\' if full_path else '') + name
        raw = value.encode('ascii')
        self.w(obj + 0xCC, len(raw))
        if len(raw) < 16:
            self.u.mem_write(obj + 0xBC, raw + b'\0')
            self.w(obj + 0xD0, 15)
        else:
            ptr = self.alloc(len(raw) + 1)
            self.u.mem_write(ptr, raw + b'\0')
            self.w(obj + 0xBC, ptr)
            self.w(obj + 0xD0, len(raw))
        self.w(obj + 0x30, state)
        self.u.mem_write(obj + 0xAC, bytes([disabled]))
        self.w(obj + 0x1C, x)
        self.w(obj + 0x20, y)
        self.w(obj + 0x2C, 0xB8)
        return obj


def contract(m, version=3):
    offset = m.pe.__data__.find(f'ModernNpcDialog.v{version}\0'.encode())
    assert offset >= 0, f'ModernNpcDialog v{version} was not applied; rebuild with the current WARP script'
    marker = m.base + m.pe.get_rva_from_offset(offset)
    data = m.pe.get_memory_mapped_image()
    locations, pos = [], 0
    while (pos := data.find(pack(marker), pos)) >= 0:
        locations.append(m.base + pos)
        pos += 1
    assert len(locations) == 1, locations
    record = locations[0]
    return {name: m.r(record + 4 + i * 4) for i, name in
            enumerate(['say', 'choice', 'lookup', 'background', 'button'])}


def pixel(m, obj, x, y):
    pixels, width, _ = m.pixels(obj)
    return m.r(pixels + 4 * (y * width + x))


def first_text_canvas_test(m):
    """Run the actual NPC Create path before any parent paint takes place."""
    m.stub(0xDBBC4F, lambda: m.ret(0, m.alloc(m.args(1)[0])))

    def text_ctor():
        obj = m.u.reg_read(UC_X86_REG_ECX)
        m.w(obj, 0x10279C0)
        m.w(obj + 0x8C, 0x00FFFFFF)
        m.w(obj + 0x94, 6)
        m.w(obj + 0x98, 3)
        m.ret(0, obj)

    def add_child():
        parent = m.u.reg_read(UC_X86_REG_ECX)
        m.w(m.args(1)[0] + 0x10, parent)
        m.ret(4)

    m.stub(0x806900, text_ctor)
    m.stub(0xA1B780, add_child)
    for width, height in [(280, 180), (440, 284), (180, 110)]:
        parent = m.window(width, height, SAY)
        m.invoke(0x8AE2E0, parent, [width, height])
        text = m.r(parent + 0xB4)
        assert m.r(text + 0x8C) == 0xFFFFF7EE, 'NPC Create still initializes a gray middle panel before the first parent draw'
        assert m.r(text + 0x10) == parent
        assert [m.r(text + off) for off in (0x14, 0x18, 0x1C, 0x20, 0x90)] == [width - 20, height - 40, 10, 10, width - 65]
        m.invoke(0x807630, text)
        assert pixel(m, text, 20, 20) == 0xFFEEF7FF, 'First native child draw must already be light blue'


def frame_tests(m, c):
    for vt, kind in [(SAY, 'say'), (CHOICE, 'choice'), (CHOICE3, 'choice')]:
        assert m.r(vt + 0x50) == c[kind], 'A live native dialog variant still uses the default frame'
    for width, height in [(280, 180), (440, 284), (180, 110)]:
        for kind, vt in [('say', SAY), ('choice', CHOICE), ('choice', CHOICE3)]:
            parent = m.window(width, height, vt)
            if kind == 'choice':
                listing = m.window(width - 24, height - 55, 0x102C1B8, parent)
                m.w(listing + 0x94, 3)  # Native selection index.
                m.w(listing + 0x98, 1)  # First visible row.
                m.w(listing + 0xB8, 16)  # Native row height.
                m.w(parent + 0xC4, listing)
                ok = m.button(parent)
                close = m.button(parent, 'btn_cancel.bmp')
                m.w(parent + 0xD0, ok)
                m.w(parent + 0xD4, close)
            else:
                text = m.window(width - 20, height - 40, 0x10279C0, parent)
                m.w(parent + 0xB4, text)
                m.w(text + 0x8C, 0xFFF2F2F2)  # Real stock constructor value.
                m.w(text + 0x90, width - 65)
                m.w(text + 0x94, 6)
                m.w(text + 0x98, 3)
            m.invoke(c[kind], parent)
            assert pixel(m, parent, 0, 0) == 0, 'Rounded outer corner must be transparent'
            assert pixel(m, parent, width // 2, 0) == 0xFFB1C7E1
            assert pixel(m, parent, 20, 20) == 0xFFEEF7FF
            assert pixel(m, parent, width // 2, height - 12) == 0xFFFFFFFF
            if kind == 'choice':
                assert (m.r(ok + 0x1C), m.r(close + 0x1C)) == ((width - 98) // 2, (width - 98) // 2 + 54)
                assert m.r(ok + 0x20) == m.r(close + 0x20) == height - 24
                assert (m.r(listing + 0x1C), m.r(listing + 0x20)) == (10, 10)
                assert (m.r(listing + 0x14), m.r(listing + 0x18), m.r(listing + 0x94), m.r(listing + 0x98)) == (width - 24, height - 55, 3, 1)
                assert m.r(listing + 0xB4) == 0, 'Native transparency mode changed'
                assert [m.r(listing + off) for off in (0x7C, 0x80, 0x84)] == [0xEE, 0xF7, 0xFF]
                assert m.r(listing + 0x58) == 1, 'Cached list must be invalidated after changing its color'
                m.w(listing + 0x58, 0)
                m.invoke(c['choice'], parent)
                assert m.r(listing + 0x58) == 0, 'Unchanged list must not be dirtied on every parent draw'
                m.invoke(0x8539C0, listing)  # Native list renderer, empty vector.
                assert pixel(m, listing, 0, 0) == 0x00EEF7FF, 'Native list color must match the blue panel'
            else:
                assert m.r(text + 0x8C) == 0xFFFFF7EE and m.r(text + 0x58) == 1
                # Execute the actual child draw, not a parent-only mock:
                # v1's frame could never hide the child's gray clear.
                m.invoke(0x807630, text)
                assert pixel(m, text, 0, 0) == 0xFFEEF7FF
                assert [m.r(text + offset) for offset in (0x14, 0x18, 0x90, 0x94, 0x98)] == [width - 20, height - 40, width - 65, 6, 3]
                m.w(text + 0x58, 0)
                m.invoke(c['say'], parent)
                assert m.r(text + 0x58) == 0, 'No continuous text canvas invalidation'
    for kind, vt in [('say', SAY), ('choice', CHOICE), ('choice', CHOICE3)]:
        tiny = m.window(30, 30, vt)
        m.invoke(c[kind], tiny)
        assert m.forwards[-1][0] == 'stock-' + kind
    # The real 2025 menu owns the same OK/Cancel native resources, but its
    # vtable differs from UIChooseWnd. Reproduce both actual owner types.
    for vt in [CHOICE, CHOICE3]:
        parent = m.window(280, 120, vt)
        for native, prefix in [('btn_ok.bmp', 'ok'), ('btn_cancel.bmp', 'clos')]:
            for state, suffix in enumerate(['out', 'over', 'press']):
                button = m.button(parent, native, state)
                before = len(m.forwards)
                m.invoke(m.r(BUTTON + 0x50), button)
                assert len(m.forwards) == before, '2025 OK/Cancel fell back to stock'
                assert m.loaded[-1] == f'{prefix}_{suffix}.png'


def button_tests(m, c):
    parent = m.window(280, 180, SAY)
    m.invoke(c['say'], parent)
    for native, image_prefix, width, height in [
            ('btn_apply.bmp', 'apply', 44, 18), ('btn_buy.bmp', 'buy', 44, 18),
            ('btn_sell.bmp', 'sell', 44, 18), ('btn_view.bmp', 'chance', 66, 18),
            ('btn_close.bmp', 'clos', 44, 18), ('btn_cancel.bmp', 'clos', 44, 18),
            ('sys_close_off.bmp', 'cls_x', 9, 9), ('btn_next.bmp', 'next2', 44, 18),
            ('btn_ok.bmp', 'ok', 44, 18)]:
        for state, suffix in enumerate(['out', 'over', 'press']):
            suffix = 'over' if image_prefix == 'cls_x' and state == 2 else suffix
            expected = image_prefix + '_' + suffix + '.png'
            button = m.button(parent, native, state, x=10, y=150)
            before = len(m.forwards)
            m.invoke(c['lookup'], button)
            assert m.u.reg_read(UC_X86_REG_EAX) != 0, native
            m.invoke(c['button'], button)
            assert len(m.forwards) == before, (native, state, m.forwards[-1:])
            assert m.loaded[-1] == expected, (native, m.loaded[-1])
            assert (m.r(button + 0x14), m.r(button + 0x18)) == (width, height)
            assert m.r(button + 0x2C) == 0xB8 and m.r(button + 0x30) == state, 'Native action/state changed'
            dest, _, _ = m.pixels(button)
            for i, source in enumerate(m.asset_pixels[expected]):
                background = pixel(m, parent, 10 + i % width, 150 + i // width)
                assert m.r(dest + 4 * i) == over(source, background), (native, state, i)
    for native, expected in [('btn_ok.bmp', 'ok_off.png'), ('btn_buy.bmp', 'buy_off.png')]:
        button = m.button(parent, native, disabled=True)
        m.invoke(c['button'], button)
        assert m.loaded[-1] == expected
    for native in ['btn_apply.bmp', 'btn_sell.bmp']:
        button = m.button(parent, native, disabled=True)
        m.invoke(c['button'], button)
        assert m.forwards[-1][0] == 'stock-button', 'Missing disabled image must keep native disabled rendering'
    button = m.button(parent, 'btn_ok.bmp')
    m.hidden_assets.add('ok_out.png')
    m.invoke(c['button'], button)
    assert m.forwards[-1][0] == 'stock-button'
    m.hidden_assets.clear()
    for bad in ['btn_unknown.bmp', 'prefix_btn_ok.bmp', 'BTN_OK.BMP']:
        button = m.button(parent, bad)
        m.invoke(c['button'], button)
        assert m.forwards[-1][0] == 'stock-button'
    for vt, native, expected in [(0x103223C, 'btn_apply.bmp', 'apply_out.png'),
                                 (0x103F660, 'btn_apply.bmp', 'apply_out.png'),
                                 (0x104B070, 'btn_view.bmp', 'chance_out.png'),
                                 (0x1032AAC, 'btn_view.bmp', 'chance_out.png')]:
        owner = m.window(280, 180, vt)
        button = m.button(owner, native)
        before = len(m.forwards)
        m.invoke(c['button'], button)
        assert len(m.forwards) == before and m.loaded[-1] == expected
        for excluded in ['btn_close.bmp', 'btn_buy.bmp', 'btn_ok.bmp',
                         'btn_apply.bmp' if native == 'btn_view.bmp' else 'btn_view.bmp']:
            button = m.button(owner, excluded)
            before = len(m.forwards)
            m.invoke(c['button'], button)
            assert len(m.forwards) == before + 1, 'Extra owner must only reskin its approved button'
    for parent_type in [0x1037F80, 0x102FE08, 0]:
        unrelated = m.window(100, 100, parent_type)
        button = m.button(unrelated)
        m.w(button + 0xBC, 0xDEAD0000)
        m.w(button + 0xCC, 9999999)
        m.invoke(c['button'], button)
        assert m.forwards[-1][0] == 'stock-button', 'Scope guard must precede resource reads'
    for length in [0, 261, 0xFFFFFFFF]:
        button = m.button(parent)
        m.w(button + 0xCC, length)
        m.invoke(c['button'], button)
        assert m.forwards[-1][0] == 'stock-button'
    # Exercise the native inline-string representation as well as heap strings.
    button = m.button(parent, full_path=False)
    m.invoke(c['button'], button)
    assert m.loaded[-1] == 'ok_out.png'
    # Clipped parent background reads for partially off-frame button positions.
    for x, y in [(-5, -4), (270, 175)]:
        button = m.button(parent, x=x & 0xFFFFFFFF, y=y & 0xFFFFFFFF)
        m.invoke(c['button'], button)


def callback_tests(m):
    expected = {0x64: 0x826E40, 0x68: 0x826BD0, 0x6C: 0x827920,
                0x70: 0x8274A0, 0x78: 0x827C70, 0x7C: 0x8271F0}
    for slot, target in expected.items():
        assert m.r(BUTTON + slot) == target, 'Native button callback changed'
    assert m.r(SAY + 0x94) == 0x8C74C0 and m.r(CHOICE + 0x94) == 0x8BEE20
    assert m.r(CHOICE3 + 0x94) == 0x8BE590 and m.r(CHOICE3 + 0x3C) == 0x8A3FC0
    calls = []
    m.stub(0xA764A0, lambda: (calls.append(m.args(1)[0]), m.ret(4)))
    m.stub(0xA23470, lambda: m.ret(8))
    parent = m.window(280, 180, SAY)
    button = m.button(parent)
    m.invoke(0x827C70, button, [1, 1])
    assert calls == [2], 'Native hand cursor not selected'
    m.u.mem_write(button + 0xAC, b'\1')
    m.invoke(0x827C70, button, [1, 1])
    assert calls == [2], 'Disabled button requested a hand cursor'
    # Real native hover/down/release and event dispatch, with only manager and
    # script-event boundaries doubled. Drawing changes must retain hit testing.
    m.stub(0xA4B750, lambda: (m.w(0x131F4E8 + 0x19C, m.args(1)[0]), m.ret(4)))
    m.stub(0xA32E00, lambda: m.ret(0, m.r(0x131F4E8 + 0x19C)))
    m.stub(0xA38B40, lambda: m.ret(8, parent))
    m.stub(0xA24BF0, lambda: m.ret(0))
    m.stub(0x8C74C0, lambda: m.forward('npc-action', 6))
    for event_id in (0xB8, 0xB9, 0x10F):
        button = m.button(parent)
        m.w(button + 0x2C, event_id)
        m.invoke(0x827920, button, [1, 1])
        assert m.r(button + 0x30) == 1
        m.invoke(0x826E40, button, [1, 1])
        assert m.r(button + 0x30) == 2 and m.r(0x131F4E8 + 0x19C) == button
        m.invoke(0x8271F0, button, [43, 17])
        assert m.forwards[-1] == ('npc-action', [button, 6, event_id, 0, 0, 0])
        assert m.r(0x131F4E8 + 0x19C) == 0 and m.r(button + 0x30) == 1
        before = len(m.forwards)
        m.invoke(0x826E40, button, [1, 1])
        m.invoke(0x8271F0, button, [44, 18])
        assert len(m.forwards) == before and m.r(button + 0x30) == 0, 'Release outside must cancel'
        m.u.mem_write(button + 0xAC, b'\1')
        m.invoke(0x826E40, button, [1, 1])
        m.invoke(0x8271F0, button, [1, 1])
        assert len(m.forwards) == before and m.r(0x131F4E8 + 0x19C) == 0


def preview(m, c, path):
    parent = m.window(280, 120, CHOICE3)
    ok = m.button(parent)
    close = m.button(parent, 'btn_cancel.bmp')
    m.w(parent + 0xD0, ok)
    m.w(parent + 0xD4, close)
    m.invoke(m.r(CHOICE3 + 0x50), parent)
    pixels, width, height = m.pixels(parent)
    im = Image.frombytes('RGBA', (width, height), bytes(m.u.mem_read(pixels, width * height * 4)), 'raw', 'BGRA')
    for button in [ok, close]:
        m.invoke(c['button'], button)
        pixels, width, height = m.pixels(button)
        child = Image.frombytes('RGBA', (width, height), bytes(m.u.mem_read(pixels, width * height * 4)), 'raw', 'BGRA')
        im.paste(child, (m.r(button + 0x1C), m.r(button + 0x20)))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def compare_accepted_choices(exe, baseline):
    def snapshots(exe, version):
        m = NpcMachine(exe)
        contract(m, version)
        result = []
        for vt in (CHOICE, CHOICE3):
            for width, height in ((280, 120), (440, 284)):
                parent = m.window(width, height, vt)
                ok = m.button(parent)
                close = m.button(parent, 'btn_cancel.bmp')
                m.w(parent + 0xD0, ok)
                m.w(parent + 0xD4, close)
                m.invoke(m.r(vt + 0x50), parent)
                pixels, w, h = m.pixels(parent)
                result.append(bytes(m.u.mem_read(pixels, w * h * 4)))
                for button in (ok, close):
                    result.append(tuple(m.r(button + off) for off in (0x1C, 0x20, 0x2C)))
                    for state in (0, 1, 2):
                        m.w(button + 0x30, state)
                        m.invoke(m.r(BUTTON + 0x50), button)
                        pixels, w, h = m.pixels(button)
                        result.append((w, h, bytes(m.u.mem_read(pixels, w * h * 4))))
        return result

    assert snapshots(exe, 3) == snapshots(baseline, 2), 'Accepted choice frames, spacing or button pixels changed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe')
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--accepted-v2', type=Path, help='Compare choice panels/buttons against the accepted v2 client')
    args = parser.parse_args()
    m = NpcMachine(args.exe)
    c = contract(m)
    first_text_canvas_test(m)
    print('PASS: actual NPC creation and first child draw initialize light blue before any parent repaint', flush=True)
    frame_tests(m, c)
    print('PASS: base/2025 choice frames and OK/Cancel, real light-blue NPC text-child draw, centered buttons and native list state', flush=True)
    button_tests(m, c)
    print('PASS: all supplied button states, exact alpha pixels, clipping, SSO/heap lookup and scoped fallbacks', flush=True)
    callback_tests(m)
    print('PASS: native hover/down/release, exact event IDs, outside/disabled cancellation and hand cursor', flush=True)
    if args.preview:
        preview(m, c, args.preview)
    if args.accepted_v2:
        compare_accepted_choices(args.exe, args.accepted_v2)
        print('PASS: accepted v2 choice frames, spacing and all OK/Close button states remain pixel-identical')
    print('Offline rendering checks only; live NPC/shop acceptance remains required.')


if __name__ == '__main__':
    main()
