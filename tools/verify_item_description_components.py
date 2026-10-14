"""Execute component panes, header capture and display wording in fresh x86."""
import struct
from verify_item_description_native import VM, WIN, ITEM, PIXELS, HITS, OFF
from verify_item_description_comparison import DualVM, COMP, COMP_PIXELS

DETAIL = 0x50103000
DETAIL_SURFACE = 0x51000000
DETAIL_PIXELS = 0x51001000


class TripleVM(DualVM):
    def __init__(self, pe, manifest):
        super().__init__(pe, manifest)
        self.u.mem_map(0x51000000, 0x200000)
        self.component = manifest['componentState']['vir']
        self.third_bar = self.component + 119344
        self.write32(DETAIL, 0x1032b84)
        self.write32(DETAIL + 0x1f8, 82)
        self.u.mem_write(DETAIL + 0x28, b'\1')
        head = 0x50128000
        self.u.mem_write(head, struct.pack('<3I', head, head, 0))
        self.write32(DETAIL + 0x50, head)
        self.set_size(DETAIL, [280, 144])
        for slot in (0, 4, 31, 37):
            self.stub(manifest['componentOriginal'][slot], {0:4, 4:8, 31:8, 37:24}[slot], self.original(slot))
        self.write32(0x159c088, 0x50109000)
        self.stub(0xa7e780, 4, lambda ecx, args: 0x50109400)
        self.stub(0xa39340, 4, lambda ecx, args: DETAIL if args[0] == 82 else 0)

    def d(self, key, value=None):
        address = self.component + OFF[key]
        if value is not None:
            self.write32(address, value)
        return self.read32(address)

    def with_scroll(self, ecx, args, fn):
        old = self.scrollbar, self.scroll_surface, self.scroll_pixels
        if ecx == getattr(self, 'third_bar', 0):
            self.scrollbar, self.scroll_surface, self.scroll_pixels = self.third_bar, 0x51180000, 0x51181000
        try:
            return super().with_scroll(ecx, args, fn)
        finally:
            self.scrollbar, self.scroll_surface, self.scroll_pixels = old

    def set_size(self, ecx, args):
        if ecx == getattr(self, 'third_bar', 0):
            return self.with_scroll(ecx, args, super().set_size)
        if ecx == DETAIL:
            w, h = args
            self.write32(ecx + 0x14, w)
            self.write32(ecx + 0x18, h)
            self.write32(ecx + 0x24, DETAIL_SURFACE)
            self.write32(DETAIL_SURFACE + 4, w)
            self.write32(DETAIL_SURFACE + 0x18, DETAIL_PIXELS)
            self.u.mem_write(DETAIL_PIXELS, b'\xff' * (w*h*4) + b'\xcd' * 64)
            return 0
        return super().set_size(ecx, args)

    def click_card(self, window=WIN):
        state = self.comparison if window == COMP else self.state
        x, y, _, _, _ = struct.unpack('<5i', self.u.mem_read(state + HITS, 20))
        self.run('Down', [x + 8, 154 + y + 8], ecx=window)
        self.run('Up', [x + 8, 154 + y + 8], ecx=window)


def checks(pe, m):
    from verify_item_description_payload import rows_response, layout_lines
    from verify_item_description_edges import long_response
    # Exact nested dispatch through the hooked component vtable, not a fake
    # callback that only records a click. Parent and child requests stay separate.
    v = TripleVM(pe, m)
    v.open(); parent_reply = v.response(); v.receive(parent_reply); v.run('Draw')
    v.write32(WIN + 0x58, 0)
    parent = bytes(v.u.mem_read(PIXELS, v.surface_size))
    before = v.fill_calls, len(v.draws)
    v.click_card()
    assert v.d('owner') == DETAIL and v.d('ready') and v.d('loading')
    assert v.read32(DETAIL + 0x14) == 360 and v.read32(DETAIL + 0x1c) == v.read32(WIN + 0x1c) + 368
    request = v.sent[-1]
    assert struct.unpack_from('<I', request, 12)[0] & 0xc0000000 == 0xc0000000
    assert struct.unpack_from('<IIHHH', request, 16) == (4001, 0, 0, 0, 0)
    assert before == (v.fill_calls, len(v.draws)) and not v.read32(WIN + 0x58)
    assert parent == bytes(v.u.mem_read(PIXELS, v.surface_size))
    reply = long_response(v)
    assert v.receive(reply) == 1 and not v.d('loading') and not v.read32(WIN + 0x58)
    v.run('Draw', ecx=DETAIL)
    assert v.d('lines') and v.d('content') > 394 and v.read32(v.third_bar) == 0x102aef4
    assert v.read32(DETAIL_PIXELS + (50*360+150)*4) != 0xffffffff, 'component header did not use its own state'
    assert bytes(v.u.mem_read(DETAIL_PIXELS + 360*560*4, 64)) == b'\xcd'*64
    v.write32(DETAIL + 0x58, 0)
    full = len([x for x in v.native_calls if x[0] == 20])
    v.run('Wheel', [-120], ecx=DETAIL); v.run('Draw', ecx=DETAIL)
    assert v.d('scroll') == 48 and not v.s('scroll')
    assert full == len([x for x in v.native_calls if x[0] == 20])
    assert parent == bytes(v.u.mem_read(PIXELS, v.surface_size))

    # Header motion only changes positions. It does not allocate/repaint, send
    # packets, parse descriptions or move the independent component's parent.
    capture = 0x131f4e8 + 0x19c
    drag_samples = 0
    for window, pixels in [(WIN, PIXELS), (DETAIL, DETAIL_PIXELS)]:
        other = DETAIL if window == WIN else WIN
        other_position = (v.read32(other + 0x1c), v.read32(other + 0x20))
        image = bytes(v.u.mem_read(pixels, 360*560*4))
        v.position(window, [100, 80]); v.write32(window + 0x58, 0)
        before = v.fill_calls, len(v.draws), len(v.sent), v.scroll_destroyed
        for point in ([150, 70], [200, 20], [250, 95]):
            v.run('Down', point, ecx=window)
            assert v.read32(capture) == window
            x, y = v.read32(window + 0x1c), v.read32(window + 0x20)
            v.run('Move', [point[0]+15, point[1]+10], ecx=window)
            assert (v.read32(window + 0x1c), v.read32(window + 0x20)) == (x+15, y+10)
            for _ in range(25):
                v.run('Move', point, ecx=window)
            v.run('Up', [-1000, 1000], ecx=window)
            assert not v.read32(capture)
            drag_samples += 1
        assert before == (v.fill_calls, len(v.draws), len(v.sent), v.scroll_destroyed)
        assert not v.read32(window + 0x58) and image == bytes(v.u.mem_read(pixels, len(image)))
        assert other_position == (v.read32(other + 0x1c), v.read32(other + 0x20))
        for point in ([20, 40], [349, 7], [292, 105], [320, 105]):
            v.run('Down', point, ecx=window); assert not v.read32(capture)
            v.run('Up', point, ecx=window)
        v.run('Down', [150, 70], ecx=window)
        v.run('Move', [5000, 5000], ecx=window)
        assert (v.read32(window + 0x1c), v.read32(window + 0x20)) == (664, 208)
        v.run('Move', [-5000, -5000], ecx=window)
        assert not v.read32(window + 0x1c) and not v.read32(window + 0x20)
        v.write32(capture, 0); v.run('Move', [180, 90], ecx=window)
        assert not v.read32(window + 0x1c), 'lost capture still moved header'
        v.run('Down', [150, 70], ecx=window)
        v.u.mem_write(window + 0x28, b'\0'); v.run('Process', ecx=window)
        assert not v.read32(capture)
        v.u.mem_write(window + 0x28, b'\1')
    v.position(DETAIL, [450, 90]); v.now += 200; v.click_card()
    assert (v.read32(DETAIL + 0x1c), v.read32(DETAIL + 0x20)) == (450, 90)
    assert v.receive(reply) == 0, 'old component token accepted after reopening'
    v.run('Destroy', [0], ecx=DETAIL)
    assert not v.d('owner') and v.s('ready') and v.receive(v.response()) == 0

    # Comparison and component share a server throttle/watch channel. Restore
    # the equipped watch without redrawing unchanged parent/comparison content.
    d = TripleVM(pe, m); right, left = d.open_pair(); d.receive(right); d.receive(left)
    d.run('Draw'); d.run('Draw', ecx=COMP)
    d.write32(WIN + 0x58, 0); d.write32(COMP + 0x58, 0)
    d.click_card(COMP); sent = len(d.sent)
    assert d.d('deferred') and sent == 2
    d.now += 159; d.run('Process', ecx=DETAIL); assert len(d.sent) == sent
    d.now += 1; d.run('Process', ecx=DETAIL); card_reply = d.response()
    d.run('Process', ecx=COMP)
    assert d.c(119532) and len(d.sent) == sent + 1
    d.now += 160; d.run('Process', ecx=COMP); watched = d.response()
    assert struct.unpack_from('<I', d.sent[-1], 12)[0] & 0xc0000000 == 0x80000000
    assert struct.unpack_from('<H', d.sent[-1], 24)[0] == 1
    assert d.receive(watched) == d.receive(card_reply) == 1
    assert not d.read32(WIN + 0x58) and not d.read32(COMP + 0x58)
    assert d.receive(left) == 0 and d.s('ready') and d.c(12) and d.d('ready')
    for _ in range(60):
        d.now += 16; d.run('Process'); d.run('Process', ecx=COMP); d.run('Process', ecx=DETAIL)
    assert len(d.sent) == sent + 2, 'watch restoration looped'
    d.run('Down', [150, 70], ecx=COMP); d.run('Move', [170, 80], ecx=COMP)
    d.run('Up', [170, 80], ecx=COMP)
    assert d.read32(COMP + 0x1c) + 368 == d.read32(WIN + 0x1c)
    assert d.read32(COMP + 0x20) == d.read32(WIN + 0x20)

    # Wording is display-only: keep raw snapshot/flags for authoritative
    # validation, and retain unknown/conditional outcomes instead of claiming Yes.
    samples = []
    for level, flag, verdict in [('0', 1, 'Yes'), ('85', 2, 'No')]:
        t = VM(pe, m); t.open()
        rows = [(10, 0, 0, 1, 0, 'Base level', level),
                (10, 0, 0, 1, 0, 'Maximum level', '99'),
                (10, 0, 0, flag, 0, 'Equip eligibility', 'Allowed at inspection' if flag == 1 else 'Requirements or restrictions not met'),
                (11, 0, 0, 0, 0, 'Trade', 'Allowed by item policy'),
                (11, 0, 0, 0, 0, 'Storage', 'Allowed by item policy'),
                (11, 0, 0, 0, 0, 'Discard', 'Yes')]
        data = rows_response(t, rows); t.receive(data); t.run('Draw')
        text = [x[-1] for x in layout_lines(t)]
        assert 'Base Level: ' + ('Any' if level == '0' else level) in text
        assert 'Equipable: ' + verdict in text and 'Drop:' in text
        assert text.count('Allowed') == 2
        assert not any('Maximum level' in x or 'Allowed by' in x or 'Discard' in x or 'Equip eligibility' in x for x in text)
        assert bytes(t.u.mem_read(t.state + OFF['snapshot'], len(data))) == bytes(data)
        samples.append(text)
    t = VM(pe, m); t.open()
    rows = [(11, 0, 0, 0, 0, 'Trade', x) for x in ('No', 'No (bound)', 'Same guild only')]
    rows += [(10, 3, 0, 4, 0, 'Job / equip rules', 'Instance and compatible equipment required')]
    t.receive(rows_response(t, rows)); t.run('Draw')
    text = [x[-1] for x in layout_lines(t)]
    assert all(x in text for x in ('No', 'No (bound)', 'Same guild only'))
    assert not any('Equipable: Yes' in x or 'Equipable: No' in x for x in text)
    return dict(passed=True, drag_samples=drag_samples, game_exe_created=False, checks=[
        'nested card dispatch opens an independent redesigned catalog pane beside its parent',
        'component header, scrolling, same-card reopen, close and late replies remain isolated',
        'free header motion changes positions without paint, requests or scrollbar work',
        'art, close and passive slot indicators excluded; edge clamp and lost/hidden capture handled',
        'shared server channel spaced at 160ms; comparison watch restored once without unchanged-pane redraw',
        'Base Level Any/85, Equipable Yes/No, hidden maximum, Allowed and Drop verified from rendered layout',
        'raw snapshots, unknown eligibility and conditional trade restrictions preserved'], wording_samples=samples)
