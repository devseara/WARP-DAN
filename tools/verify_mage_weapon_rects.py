"""Check mounted Knife hilts through the actual native CActor rectangle builder."""

import json
from pathlib import Path
import struct
from unicorn.x86_const import *
import first_job_hd_sprites as h
from verify_all_riding_combat import CPU

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Outputs/mage-mounted-death-v47'


def main():
    m = CPU(OUT / 'client/client.exe')
    m.u.mem_map(0x51000000, 0x4000)
    layer_ptr, image_ptr, renderer = 0x51000000, 0x51000100, 0x51000200
    m.w(0x12515F8, renderer)
    m.w(renderer + 0x28, 1024)
    m.w(renderer + 0x2C, 1024)
    m.u.mem_write(m.actor + 0x50, struct.pack('<f', 1.0))
    fixtures = ROOT / 'Outputs/mage-mounted-runtime-v46/fixtures'
    act = h.base.read_act((fixtures / 'weapon.act').read_bytes())
    images = h.independent_decode((fixtures / 'weapon.spr').read_bytes())
    records = json.loads(
        (
            ROOT
            / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-mounted-attachments-v45/knife-grips.json'
        ).read_text(encoding='utf-8')
    )['landmarks']
    cases = []
    for row in records:
        ai, fi = row['action'], row['frame']
        layer = act.actions[ai][fi].layers[0]
        image = images[layer.index]
        width, height = image.size
        assert not (width % 2 or height % 2) and layer.sx == layer.sy == 0.5
        # Native ACT loading converts center offsets to unscaled image-local
        # top-left offsets. This layout matches the captured live body/head
        # layer/header samples. The rectangle builder applies layer scale.
        cx = round(layer.x / layer.sx - width / 2)
        cy = round(layer.y / layer.sy - height / 2)
        m.u.mem_write(
            layer_ptr,
            struct.pack(
                '<4iI2f2i', cx, cy, layer.index, layer.mirror, 0xFFFFFFFF, layer.sx, layer.sy, 0, 1
            ),
        )
        m.u.mem_write(image_ptr, struct.pack('<2H2h', width, height, 0, 0))
        args = [0] * 17
        args[2] = struct.unpack('<I', struct.pack('<f', 2.0))[0]
        args[3] = layer_ptr
        args[4] = struct.unpack('<I', struct.pack('<f', 256.0))[0]
        args[5] = struct.unpack('<I', struct.pack('<f', 384.0))[0]
        args[10] = image_ptr
        m.w(m.sp, 0x50003000)
        for index, value in enumerate(args):
            m.w(m.sp + 4 + index * 4, value)
        m.u.reg_write(UC_X86_REG_ESP, m.sp)
        m.u.reg_write(UC_X86_REG_ECX, m.actor)
        m.u.emu_start(0xC40C20, 0xC40DCA, count=1000)
        assert m.u.reg_read(UC_X86_REG_EIP) == 0xC40DCA
        bp = m.u.reg_read(UC_X86_REG_EBP)
        x = struct.unpack('<f', bytes(m.u.mem_read(bp + 0x40, 4)))[0]
        y = struct.unpack('<f', bytes(m.u.mem_read(bp + 0x10, 4)))[0]
        gx, gy = row['hilt_source_pixel']
        # A86/A94 F2 was explicitly changed to unmirrored after the initial
        # landmark receipt. Its recorded glove/hilt target remains unchanged.
        actual = [x + (-1 if layer.mirror else 1) * (2 * gx + 1), y + 2 * gy + 1]
        target = row['target_glove_pixel']
        error = max(abs(a - b) for a, b in zip(actual, target))
        assert error <= 1, (ai, fi, actual, target)
        cases.append(dict(action=ai, frame=fi, native_hilt=actual, glove=target, error=error))
    assert len(cases) == 224
    report = dict(
        passed=True,
        cases=len(cases),
        actual_native_rectangle_builder='0xC40C20',
        all_hilts_within_one_output_pixel=True,
        source_pixels_unchanged=True,
        live_visual_acceptance=False,
        results=cases,
    )
    (OUT / 'native-weapon-rects.json').write_text(json.dumps(report, indent=2) + '\n')
    print(
        'PASS: 224 hilt/glove positions through native rectangle construction, no coordinate or artwork edits.'
    )


if __name__ == '__main__':
    main()
