"""Small lossless ACT 2.4 reader/writer and native SPR 2.0 true-color codec.

SPR true-color pixels are bottom-up ABGR on disk, as implemented by GRF
Editor's SprWriter._writeAsBgra32. They are NOT ordinary bottom-up BGRA.
"""
from dataclasses import dataclass
import struct
import numpy as np
from PIL import Image


@dataclass
class Layer:
    x: int
    y: int
    index: int
    mirror: int = 0
    color: tuple = (255, 255, 255, 255)
    sx: float = 1.0
    sy: float = 1.0
    angle: int = 0
    kind: int = 1

    def encode(self):
        return struct.pack('<iiii4Bffii', self.x, self.y, self.index,
                           self.mirror, *self.color, self.sx, self.sy,
                           self.angle, self.kind)


@dataclass
class Frame:
    ranges: bytes
    layers: list
    sound: int
    anchors: list


@dataclass
class Act:
    header: bytes
    actions: list
    tail: bytes
    speeds: list
    sounds: list


def read_act(data):
    assert data[:2] == b'AC'
    version = (data[3], data[2])
    assert version in ((2, 4), (2, 5)), version
    count, = struct.unpack_from('<H', data, 4)
    pos = 16
    actions = []
    for _ in range(count):
        n, = struct.unpack_from('<i', data, pos); pos += 4
        frames = []
        for _ in range(n):
            ranges = data[pos:pos+32]; pos += 32
            nl, = struct.unpack_from('<i', data, pos); pos += 4
            layers = []
            for _ in range(nl):
                v = struct.unpack_from('<iiii4Bffii', data, pos); pos += 36
                layers.append(Layer(*v[:4], tuple(v[4:8]), *v[8:]))
                if version >= (2, 5): pos += 8
            sound, na = struct.unpack_from('<ii', data, pos); pos += 8
            anchors = [data[pos+16*i:pos+16*(i+1)] for i in range(na)]
            pos += na*16
            frames.append(Frame(ranges, layers, sound, anchors))
        actions.append(frames)
    tail = data[pos:]
    ns, = struct.unpack_from('<i', tail)
    sounds = [tail[4+i*40:4+(i+1)*40].split(b'\0', 1)[0].decode('cp949') for i in range(ns)]
    speeds = list(struct.unpack_from('<'+'f'*count, tail, 4+ns*40))
    assert len(tail) == 4+ns*40+count*4
    return Act(data[:16], actions, tail, speeds, sounds)


def write_act(act):
    header = bytearray(act.header)
    header[2:4] = bytes((4, 2))
    out = bytearray(header)
    for frames in act.actions:
        out += struct.pack('<i', len(frames))
        for f in frames:
            out += f.ranges + struct.pack('<i', len(f.layers))
            for l in f.layers: out += l.encode()
            out += struct.pack('<ii', f.sound, len(f.anchors))
            out += b''.join(f.anchors)
    return bytes(out) + act.tail


def write_spr(images):
    assert 0 < len(images) < 65536
    out = bytearray(b'SP\x00\x02' + struct.pack('<HH', 0, len(images)))
    for image in images:
        a = np.asarray(image.convert('RGBA'), dtype=np.uint8)
        w, h = image.size
        out += struct.pack('<HH', w, h)
        out += a[::-1, :, [3, 2, 1, 0]].tobytes()
    return bytes(out)


def read_spr(data):
    assert data[:4] == b'SP\x00\x02'
    ni, nr = struct.unpack_from('<HH', data, 4)
    assert ni == 0
    images = []; pos = 8
    for _ in range(nr):
        w, h = struct.unpack_from('<HH', data, pos); pos += 4
        a = np.frombuffer(data, dtype=np.uint8, count=w*h*4, offset=pos).reshape(h, w, 4)
        pos += w*h*4
        images.append(Image.fromarray(a[::-1, :, [3, 2, 1, 0]].copy()))
    assert pos == len(data)
    return images


def anchor(frame):
    assert frame.anchors
    return struct.unpack_from('<ii', frame.anchors[0], 4)


def draw_layer(canvas, image, layer, origin=(80, 112)):
    """CPU preview using pixel centers; artwork is authored at native size."""
    w, h = image.size
    if layer.mirror:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if (layer.sx, layer.sy) != (1.0, 1.0):
        image = image.resize((max(1, round(w*layer.sx)), max(1, round(h*layer.sy))), Image.Resampling.NEAREST)
    if layer.angle:
        image = image.rotate(-layer.angle, resample=Image.Resampling.NEAREST, expand=True)
    if layer.color != (255, 255, 255, 255):
        a = np.array(image).astype(np.uint16)
        a = (a*np.array(layer.color, np.uint16)//255).astype(np.uint8)
        image = Image.fromarray(a)
    canvas.alpha_composite(image, (origin[0]+layer.x-image.width//2,
                                  origin[1]+layer.y-image.height//2))
