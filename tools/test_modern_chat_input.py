"""Private chat-input x86 test. No client process, packets or asset edits."""
import argparse
import struct
from test_chat_item_icons import IconMachine
from test_modern_chat_ui import pack, over


def contract(m):
    tag = m.pe.__data__.find(b'ModernChatUI.Input.v1\0')
    assert tag >= 0, 'White input styling missing'
    va = m.base + m.pe.get_rva_from_offset(tag)
    data = m.pe.get_memory_mapped_image()
    positions, pos = [], 0
    while (pos := data.find(pack(va), pos)) >= 0:
        positions.append(m.base + pos)
        pos += 1
    assert len(positions) == 1
    return dict(zip(('white', 'png', 'color', 'layout', 'bottom', 'foreground'),
                    (m.r(positions[0] + 4 + i * 4) for i in range(6))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    args = ap.parse_args()
    m = IconMachine(args.exe)
    c = contract(m)
    assert c['bottom'] == 42 and c['foreground'] == 0xFFFFFF
    # Actual supplied indicator pixels; preserve texture bytes and alpha/keying.
    for name in ('icon_general.png', 'icon_pm.png'):
        tex = m.load_texture(name)
        tw, th = m.r(tex + 0x114), m.r(tex + 0x118)
        before = bytes(m.u.mem_read(m.r(tex + 0x11c), tw * th * 4))
        for width, height in ((tw + 6, th + 4), (tw, th)):
            target = m.window(width, height)
            pix, _, _ = m.pixels(target)
            for background in (0, 0x80404040, 0xFF102030):
                for function, white in ((c['white'], True), (c['png'], False)):
                    m.u.mem_write(pix, pack(background) * (width * height))
                    m.invoke(function, target, [3, 2, tex, 0])
                    expected = [background] * (width * height)
                    for y in range(min(th, height - 2)):
                        for x in range(min(tw, width - 3)):
                            source = m.asset_pixels[name][y * tw + x]
                            if white and source & 0xFFFFFF != 0xFF00FF:
                                source |= 0xFFFFFF
                            expected[(y + 2) * width + x + 3] = over(source, background)
                    assert bytes(m.u.mem_read(pix, width * height * 4)) == b''.join(map(pack, expected))
        assert bytes(m.u.mem_read(m.r(tex + 0x11c), tw * th * 4)) == before
    # Synthetic alpha/key edge cases exercise the real emitted blitter.
    tex = m.load_texture('icon_general.png')
    special = [0x00CCAA44, 0xFFFF00FF, 0x80FF00FF, 0xFF426A88, 0x80426A88, 0x01426A88, 0xFF000000]
    m.w(tex + 0x114, 7); m.w(tex + 0x118, 1)
    m.u.mem_write(m.r(tex + 0x11c), b''.join(map(pack, special)))
    target = m.window(7, 1); pix, _, _ = m.pixels(target)
    background = 0x80404040
    m.u.mem_write(pix, pack(background) * 7)
    m.invoke(c['white'], target, [0, 0, tex, 0])
    wanted = [over(p if p & 0xFFFFFF == 0xFF00FF else p | 0xFFFFFF, background) for p in special]
    assert bytes(m.u.mem_read(pix, 28)) == b''.join(map(pack, wanted))
    print('PASS: actual indicator pixels become white; alpha, magenta key, clipping, texture immutability and ordinary artwork retained.')

    m = IconMachine(args.exe)
    c = contract(m)
    draws = []
    for key in ('white', 'png'):
        def observe(key=key):
            tex = m.args(4)[2]
            draws.append((key, next(name for name, pointer in m.textures.items() if pointer == tex)))
            m.image()
        m.stub(c[key], observe)
    for width, height in ((240, 100), (594, 240), (800, 360)):
        parent, _ = m.setup(width, height)
        for active in (0, 1):
            m.u.mem_write(0x131F50C, bytes([active]))
            for recipient in ('', 'WhisperTarget'):
                m.string(recipient, m.r(parent + 0xC0) + 0xD8)
                draws.clear(); m.texts.clear()
                m.invoke(m.r(0x1037FD0), parent)
                assert ('white', 'icon_pm.png' if recipient else 'icon_general.png') in draws
                assert all(key == 'png' for key, name in draws if name not in ('icon_general.png', 'icon_pm.png'))
                for offset in (0xBC, 0xC0):
                    edit = m.r(parent + offset)
                    assert m.r(edit + 0x20) == (height - 42 if active else 0xFFFFFF9C)
                    if active:
                        assert m.r(edit + 0x18) == 16
                        m.invoke(m.r(0x1028DFC if offset == 0xBC else 0x1028EE8), edit)
                        assert m.r(edit + 0xA8) == 0xFFFFFF and m.r(edit + 0xF4) == 0
                if not active:
                    prompt = next(row for row in m.texts if row[0] == 'Enter to type a message')
                    assert prompt[1:3] == (119, height - 40)
                    pix, w, _ = m.pixels(parent)
                    assert m.r(pix + (prompt[2] * w + prompt[1]) * 4) == 0xFFFFFFFF
    print('PASS: only public/PM indicators tinted; input and hint white; both edit rows raised 2px across sizes/focus/PM modes, native inset/height unchanged.')


if __name__ == '__main__':
    main()
