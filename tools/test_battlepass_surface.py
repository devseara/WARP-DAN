"""Execute BP's real window sizing and stock cached-tile presentation.

Only constructor/OS/resource and GPU boundaries are doubled. Unlike an RGB
layout picture, this catches zero-alpha GDI glyphs and mode-switch overlap.
"""
import argparse
from unicorn.x86_const import UC_X86_REG_ECX
from test_battlepass_board import BoardMachine, snapshot
from test_modern_chat_ui import pack


def real_window(m):
    m.w(m.c['state'], 0)
    # The server advertises v3/v4 prefix capabilities together with the board.
    m.w(m.c['state']+32+1188, m.r(m.c['state']+32+1188)|512|32|16)
    m.stub(0xDBBC4F, lambda: m.ret(0, m.alloc(m.args(1)[0])))
    m.stub(0x86B950, lambda: m.ret(4))
    head = m.alloc(12)
    m.w(head, head); m.w(head+4, head)
    m.w(0x131F4E8+0x17C, head); m.w(0x131F4E8+0x180, 0)
    start = m.alloc(16); stop = m.alloc(16)
    m.stub(start, lambda: m.ret(16, 567))
    m.stub(stop, lambda: m.ret(8, 1))
    m.w(m.c['state']+16, start); m.w(m.c['state']+20, stop)
    m.invoke(m.c['toggle'], 0)
    m.obj = m.r(m.c['state']); m.owner = m.obj
    assert m.obj and m.r(m.obj+0x28) == 1
    assert m.r(0x131F4E8+0x180) == 1, 'native top-level registration'
    return m.obj


def verify(exe, expect_bug=False):
    m = BoardMachine(exe); obj = real_window(m)
    surface = m.r(obj+0x24)
    width, height = m.r(obj+0x14), m.r(obj+0x18)
    assert (width, height) == ((945, 560) if expect_bug else (920, 560)), 'unused cursor margin'
    assert (m.r(surface+4), m.r(surface+8)) == (width, height)
    assert m.r(surface+0x28) == 0
    pix = m.r(surface+0x18)
    m.u.mem_write(pix, pack(0xFFFF00FF)*(width*height))
    head = m.alloc(12); m.w(head, head); m.w(head+4, head)
    m.w(surface+0x20, head); m.w(surface+0x24, 0)
    textures = {}; uploads = []; draws = []
    table = m.alloc(48); upload = m.alloc(16); draw = m.alloc(16)
    m.w(table+0x20, upload); m.w(table+0x28, draw)

    def create():
        tw, th, mode, a, b = m.args(5)
        assert (a, b) == (0, 0) and mode in (0, 4)
        ptr = m.alloc(16); m.w(ptr, table); textures[ptr] = (tw, th, mode)
        m.ret(20, ptr)

    def upload_texture():
        ptr = m.u.reg_read(UC_X86_REG_ECX)
        uploads.append((textures[ptr], m.args(7))); m.ret(28)

    def draw_texture():
        ptr = m.u.reg_read(UC_X86_REG_ECX)
        draws.append((textures[ptr], m.args(5))); m.ret(20)

    m.stub(0x568620, create); m.stub(upload, upload_texture); m.stub(draw, draw_texture)

    def present():
        m.u.mem_write(surface+0x1C, b'\1')
        m.invoke(0x53EA90, surface, (0, 0, width, height, 0))

    def check():
        expected = [(x, y, min(256, width-x), min(256, height-y), 0)
                    for y in range(0, height, 256) for x in range(0, width, 256)]
        assert [tuple(args) for _, args in draws] == expected, draws
        assert len(uploads) == len(expected) == len(textures) == 12
        for ((tw, th, mode), args), (x, y, _, _, _) in zip(uploads, expected):
            assert args == [0, 0, tw, th, pix+(y*width+x)*4, 0, width], args
            assert mode == 0, 'GDI RGB must be opaque, not alpha blended'
        assert m.r(surface+0x28) == 0

    present(); check()  # Existing stock opaque tiles before board paint.
    m.draw(); uploads.clear(); draws.clear(); present()
    if expect_bug:
        assert m.r(surface+0x28) & 255 == 1
        assert m.r(pix+(559*width+944)*4) == 0xFFFF00FF
        assert all(args[2:4] == [945, 560] for _, args in uploads)
        assert all(args == [0, 0, 945, 560, 0] for _, args in draws)
        print('REPRODUCED old BP: 25px magenta margin; alpha switch uploads/draws all 12 cached tiles over each other')
        return
    check()
    for tab in (0, 1, 2, 3, 1, 0):
        m.w(m.c['state']+4, tab); m.draw()
        # Simulate native GDI's zero-alpha glyph at a known text location.
        # Mode 0 must preserve RGB and normalize it to opaque, not a hole.
        m.w(pix+(42*width+138)*4, 0x005A5A5A)
        uploads.clear(); draws.clear(); present(); check()
        assert m.r(pix+(42*width+138)*4) == 0xFF5A5A5A
        assert m.r(pix+(559*width+919)*4) == 0xFFFFFFFF
        raw = bytes(m.u.mem_read(pix, width*height*4))
        assert all(raw[i:i+3] != b'\xff\x00\xff' for i in range(0, len(raw), 4)), 'unpainted magenta area'
    m.invoke(m.c['toggle'], 0); assert not m.r(obj+0x28)
    m.invoke(m.c['toggle'], 0); assert m.r(m.c['state']) == obj and m.r(obj+0x28)
    m.draw(); uploads.clear(); draws.clear(); present(); check()
    print('PASS BP: real 920x560 creation/reopen; 12 non-overlapping opaque native GPU tiles across all tabs; no margin, alpha switch or GDI holes')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('exe'); ap.add_argument('--expect-bug', action='store_true')
    args = ap.parse_args(); verify(args.exe, args.expect_bug)
