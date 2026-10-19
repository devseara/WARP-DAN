"""Execute native reversed RHW production with scoped corpse-depth correction."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from unicorn.x86_const import *
from verify_all_riding_combat import CPU


def bits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def native(
    m,
    action=64,
    mounted=1,
    sex=0,
    visible=2,
    body=2,
    vtable=0x1094810,
    reversed=1,
    top=210.0,
    bottom=325.0,
):
    for off, value in [
        (0, vtable),
        (0x38, action),
        (0x25C, visible),
        (0x4C8, body),
        (0x260, sex),
        (0x80, 0),
    ]:
        m.w(m.actor + off, value)
    m.u.mem_write(m.actor + 0x2CC, bytes([mounted]))
    m.u.mem_write(m.actor + 0x9C, bytes([reversed]))
    for a, value in [
        (m.bp + 0x1C, bits(300.0)),
        (m.bp + 0x20, 0x50002000),
        (0x50002008, bits(200.0)),
        (m.bp + 0xC, 0),
        (m.bp - 4, 0),
        (m.bp + 0x34, 0x50002100),
        (m.bp + 0x2C, 0x50002200),
    ]:
        m.w(a, value)
    for r, value in [
        (UC_X86_REG_EBP, m.bp),
        (UC_X86_REG_ESP, m.sp),
        (UC_X86_REG_EDI, m.actor),
        (UC_X86_REG_EDX, 0x50002300),
        (UC_X86_REG_XMM6, bits(top)),
        (UC_X86_REG_XMM7, bits(bottom)),
        (UC_X86_REG_XMM3, bits(1.0)),
    ]:
        m.u.reg_write(r, value)
    m.u.emu_start(0xC40F7B, 0xC41092, count=1000)
    assert m.u.reg_read(UC_X86_REG_EIP) == 0xC41092
    assert m.u.reg_read(UC_X86_REG_ESP) == m.sp
    assert m.u.reg_read(UC_X86_REG_EDI) == m.actor
    return [struct.unpack('<f', bytes(m.u.mem_read(p, 4)))[0] for p in [0x50002200, 0x50002300]]


def verify(baseline, candidate, output):
    old, new = CPU(baseline), CPU(candidate)
    rows = []
    for action in range(64, 72):
        for top, bottom in [(210.0, 325.0), (270.0, 340.0), (304.0, 320.0)]:
            a = native(old, action=action, top=top, bottom=bottom)
            b = native(new, action=action, top=top, bottom=bottom)
            bias = np.float32(3) * np.float32(9e-6)
            expected = [
                np.float32(
                    np.float32(1) / np.float32(200 - np.float32(max(v - 300, 0)) * np.float32(0.16))
                )
                + bias
                for v in [top, bottom]
            ]
            assert np.allclose(b, expected, rtol=1e-6, atol=1e-9), (action, a, b, expected)
            if top < 300:
                assert a[0] < 0.005 and b[0] >= 0.005, 'upper corpse row still behind flat ground'
            rows.append(dict(action=action, top=top, bottom=bottom, before=a, after=b))
    controls = [
        dict(mounted=0),
        dict(sex=1),
        dict(visible=1),
        dict(body=1),
        dict(action=63),
        dict(action=72),
        dict(vtable=0x10939D4),
        dict(vtable=0x1093B0C),
    ]
    for kw in controls:
        for reversed in [0, 1]:
            assert native(old, reversed=reversed, **kw) == native(new, reversed=reversed, **kw), kw
    # Existing living positive-depth path stays byte-for-byte equivalent.
    assert native(old, reversed=0) == native(new, reversed=0)
    result = dict(
        passed=True,
        native_rhw_cases=len(rows),
        unsupported_controls=17,
        native_range=['0xC40F7B', '0xC41092'],
        upper_rows_no_longer_behind_flat_ground=True,
        source_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
        client_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        cases=rows,
        GPU_terrain_collision_not_executed=True,
        live_visual_acceptance=False,
    )
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS24 native reversed corpse RHW cases and17 unchanged actor/action/path controls.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline', 'candidate', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    verify(a.baseline, a.candidate, a.output)
