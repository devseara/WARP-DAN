"""Run Mission hover/map rendering through the emitted x86 draw/input code."""
import argparse
import configparser
import io
from pathlib import Path
import struct
from PIL import Image
from dual_weapon_formats.grf_reader import GrfFile
from test_battlepass_board import BoardMachine, snapshot
from test_modern_chat_ui import pack


class MissionMachine(BoardMachine):
    def __init__(self, exe):
        self.map_requests = []
        self.map_specs = {'pay_fild01': (32, 32, 0x00336622),
                          'prt_fild08': (80, 48, 0x00448855),
                          '1@tower': (1024, 1, 0x00997766),
                          'gef_fild00': (1, 1024, 0x00000000),
                          'prontera': (32, 32, 0x00FF00FF)}
        super().__init__(exe)

    def texture(self):
        path = self.cstr(self.args(1)[0])
        if '\\map\\' not in path:
            return super().texture()
        self.map_requests.append(path)
        assert path.endswith('.bmp')
        name = path.split('\\')[-1][:-4]
        if name not in self.map_specs:
            self.ret(4, 0); return
        key = 'map:'+name
        if key not in self.textures:
            width, height, color = self.map_specs[name]
            tex = self.alloc(0x130); pix = self.alloc(max(1, width*height)*4)
            self.u.mem_write(pix, pack(color)*max(1, width*height))
            self.w(tex+0x114, width); self.w(tex+0x118, height); self.w(tex+0x11C, pix)
            self.textures[key] = tex
        self.ret(4, self.textures[key])

    def move_draw(self, x, y, path=None):
        self.invoke(self.c['move'], 0, (self.obj, x, y)); self.draw(path)


def mission(names, kind=0):
    p = snapshot(); struct.pack_into('<H', p, 10, 17|0x3FC0)
    struct.pack_into('<I', p, 1196, kind)
    struct.pack_into('<II', p, 2528, 501 if kind else 1002, len(names))
    for i, name in enumerate(names):
        p[2536+i*48:2560+i*48] = name.encode()[:23].ljust(24, b'\0')
        p[2560+i*48:2584+i*48] = f'Spawn: {20-i}'.encode().ljust(24, b'\0')
    return p


def verify(exe, output):
    output.mkdir(parents=True, exist_ok=True)
    m = MissionMachine(exe); s = m.c['state']; m.w(s+4, 1)
    names = list(m.map_specs); m.receive(mission(names))
    m.move_draw(0, 0, output/'mission-maps.png')
    assert len(m.map_requests) == 5
    pix, width, _ = m.pixels(m.obj)
    for i, name in enumerate(names):
        yy = 340+i*26
        assert any(t[0] == name and t[1:3] == (174, yy+6) for t in m.texts), 'map label missing'
        assert any(t[0] == f'Spawn: {20-i}' and t[1:3] == (520, yy+6) for t in m.texts), 'population missing'
        value = m.r(pix+((yy+10)*width+150)*4)
        color = m.map_specs[name][2]
        assert value == (0xFFE8EFF9 if color == 0xFF00FF else color|0xFF000000), 'BMP thumbnail or color key'
    # Only the visible monster preview has a Mission tooltip, never labels,
    # preview borders, progress, habitat maps, buttons or the enclosing panel.
    for x, y in [(139, 176), (236, 176), (140, 278), (252, 176), (450, 223), (705, 280), (150, 350), (180, 350), (660, 490)]:
        m.move_draw(x, y); assert not any(t[0] == 'Poring' for t in m.texts), (x, y)
    for x, y in [(140, 176), (235, 277), (180, 230)]:
        m.move_draw(x, y); assert sum(t[0] == 'Poring' for t in m.texts) == 1
    m.move_draw(180, 230, output/'monster-tooltip.png')
    m.owner = 0; m.draw(); assert not any(t[0] == 'Poring' for t in m.texts); m.owner = m.obj
    m.receive(mission(names, kind=1)); m.move_draw(180, 220)
    assert not m.contains('Client item name'), 'Mission item must not show a hover tooltip'
    m.mouse(180, 220, 2); m.mouse(180, 220, 3); assert m.descriptions == [501], 'retain small-icon item inspection'
    m.mouse(400, 220, 2); m.mouse(400, 220, 3); assert m.descriptions == [501]
    # Malformed paths, missing assets and invalid texture dimensions must leave
    # text readable, never reuse a previous map image or read invalid pixels.
    bad = ['../bad', 'path\\bad', 'missing_map', 'bad_dimension', '']
    m.map_specs['bad_dimension'] = (1025, 1, 0x00123456)
    m.map_requests.clear(); m.receive(mission(bad)); m.move_draw(0, 0)
    assert [p.split('\\')[-1] for p in m.map_requests] == ['missing_map.bmp', 'bad_dimension.bmp']
    for i in range(5):assert m.r(pix+((350+i*26)*width+150)*4) == 0xFFE8EFF9
    # Other tabs retain target/reward hover labels.
    m.receive(snapshot()); m.w(s+4, 0); m.move_draw(190, 178); assert m.contains('Required: 100')
    m.w(s+4, 2); m.move_draw(222, 190); assert m.contains('Quantity: 2')
    print('PASS Mission: monster-only hover bounds/ownership; icon-only item inspection; 5 native map BMPs + names + spawn counts; missing/malformed/oversize safety; other tabs unchanged')


def client_maps(exe, game, output):
    """Read the selected installation's DATA.INI/GRFs without changing them."""
    config = configparser.ConfigParser(); config.read(game/'DATA.INI')
    archives = []
    m = MissionMachine(exe); textures = {}; requests = []
    names = ['pay_fild01', 'prt_fild08', 'gef_fild00', 'prontera', 'pay_fild11']
    try:
        for _, filename in sorted(config.items('Data'), key=lambda pair: int(pair[0])):
            archives.append(GrfFile(game/filename))
        prefix = m.cstr(m.r(m.c['api']+76))
        for name in names:
            resource = prefix+name+'.bmp'
            # Native 0xA9F030/texture manager resolve UI-relative paths below
            # data/texture; buildResourcePath deliberately omits that root.
            qualified = 'data\\texture\\'+resource
            loose = game/Path(qualified)
            key = qualified.encode('latin1').decode('cp949').replace('\\', '/').lower()
            blob = loose.read_bytes() if loose.is_file() else next((data for a in archives if (data := a.read(key)) is not None), None)
            assert blob is not None, 'Missing installed map: '+name
            with Image.open(io.BytesIO(blob)) as image:
                image = image.convert('RGBA'); width, height = image.size
                tex = m.alloc(0x130); pix = m.alloc(width*height*4)
                m.u.mem_write(pix, image.tobytes('raw', 'BGRA'))
                m.w(tex+0x114, width); m.w(tex+0x118, height); m.w(tex+0x11C, pix)
                textures[resource] = tex
        def texture():
            path = m.cstr(m.args(1)[0])
            if '\\map\\' not in path:return m.texture()
            requests.append(path); m.ret(4, textures.get(path, 0))
        m.stub(0xA8D4A0, texture); m.w(m.c['state']+4, 1)
        m.receive(mission(names)); m.move_draw(0, 0, output/'installed-map-assets.png')
        assert requests == [prefix+name+'.bmp' for name in names]
        pix, width, _ = m.pixels(m.obj)
        for i, name in enumerate(names):
            yy = 340+i*26
            pixels = {m.r(pix+((yy+y)*width+140+x)*4) for y in range(24) for x in range(24)}
            assert len(pixels) > 5 and m.contains(name), 'Installed image/name not visible'
        print('PASS actual installed map BMPs: DATA.INI priority, 5 native resource paths, distinct visible 24x24 thumbnails + names; offline resource replay only')
    finally:
        for archive in archives:archive.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('exe'); ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--game', type=Path)
    args = ap.parse_args(); verify(args.exe, args.output)
    if args.game:client_maps(args.exe, args.game, args.output)
