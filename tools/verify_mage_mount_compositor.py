"""Execute actual compositor callers, native ACT selection/anchors and weapon setter.

Fixtures are exact installed resources, including the live character's hair9.
File-system/item DB/allocator boundaries are explicit doubles; native ACT lookup,
head selection, attachment subtraction and std::string assignment execute.
"""

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
import first_job_hd_sprites as h
from verify_all_riding_combat import CPU

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Outputs/mage-mounted-runtime-v46'


class Engine(CPU):
    def __init__(self, path):
        super().__init__(path)
        self.u.mem_map(0x51000000, 0x400000)
        self.next = 0x51000000
        self.wrapper = self.alloc(0x200)
        self.w(self.wrapper + 0x3C, self.actor)
        self.acts = {}
        self.layers = {}
        self.frames = {}
        self.calls = []
        self.loads = []
        self.u.hook_add(UC_HOOK_CODE, self.boundary)

    def alloc(self, n):
        result = self.next
        self.next += (n + 15) & ~15
        assert self.next < 0x51400000
        return result

    def args(self, n):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        return [self.d(sp + 4 + 4 * i) for i in range(n)]

    def string(self, pointer):
        raw = bytes(self.u.mem_read(pointer, 512)).split(b'\0')[0]
        return raw.decode('cp949')

    def boundary(self, uc, pc, size, unused):
        if pc == 0x70F4B0:
            self.calls.append((uc.reg_read(UC_X86_REG_ECX), *self.args(2)))
        elif pc == 0xDBBC4F:
            self.ret(self.alloc(self.args(1)[0]))
        elif pc in [0xE07D4B, 0xE07D7B]:
            dest, source, count = self.args(3)
            self.u.mem_write(dest, bytes(self.u.mem_read(source, count)))
            self.ret(dest)
        elif pc == 0xD8A1D0:
            self.ret(1 if self.args(1)[0] == 1201 else 0, 4)
        elif pc == 0xA90350:
            self.ret(0x51000000)
        elif pc in [0xA72830, 0xA9ECF0]:
            self.ret(0)  # cdecl: special preview account checks
        elif pc == 0xA8D4A0:
            self.ret(0, 4)  # empty initial resource
        elif pc in [0xA8E800, 0xA8F910]:
            self.ret(0)
        elif pc == 0xA8E500:
            name = self.string(self.args(1)[0])
            self.calls.append(('file-exists', name))
            assert name == self.expected['act'], name
            self.ret(1, 4)
        elif pc in [0xD3D7C0, 0xD3FD90]:
            slot, pointer = self.args(2)
            name = self.string(pointer)
            if name:
                ext = 'act' if pc == 0xD3D7C0 else 'spr'
                assert slot == 5 and name == self.expected[ext], (slot, name)
                self.loads.append((ext, name))
                self.w(self.slots[ext] + 5 * 4, self.acts['weapon'] if ext == 'act' else 0x51001000)
            self.ret(0, 8)

    def actor_state(self, mounted=1, visible=2, body=2, sex=0, original=0, weapon=1201, left=0):
        for off, value in [
            (0, 0x1094810),
            (0x25C, visible),
            (0x4C8, body),
            (0x260, sex),
            (0x2C0, original),
            (0x440, weapon),
            (0x444, left),
        ]:
            self.w(self.actor + off, value)
        self.u.mem_write(self.actor + 0x2CC, bytes([mounted]))

    def act(self, name, act):
        pointer = self.alloc(0x200)
        actions = self.alloc(len(act.actions) * 12)
        self.w(pointer + 0x110, actions)
        self.w(pointer + 0x114, actions + len(act.actions) * 12)
        for ai, sequence in enumerate(act.actions):
            begin = self.alloc(len(sequence) * 68)
            for off, value in [
                (0, begin),
                (4, begin + len(sequence) * 68),
                (8, begin + len(sequence) * 68),
            ]:
                self.w(actions + ai * 12 + off, value)
            for fi, frame in enumerate(sequence):
                fp = begin + fi * 68
                self.frames[name, ai, fi] = fp
                layers = self.alloc(max(1, len(frame.layers)) * 36)
                for li, layer in enumerate(frame.layers):
                    lp = layers + li * 36
                    self.layers[name, ai, fi, li] = lp
                    self.u.mem_write(
                        lp,
                        struct.pack(
                            '<4iI2f2i',
                            layer.x,
                            layer.y,
                            layer.index,
                            layer.mirror,
                            int.from_bytes(bytes(layer.color), 'little'),
                            layer.sx,
                            layer.sy,
                            layer.angle,
                            layer.kind,
                        ),
                    )
                for off, value in [
                    (0x20, layers),
                    (0x24, layers + len(frame.layers) * 36),
                    (0x28, layers + len(frame.layers) * 36),
                    (0x2C, len(frame.layers)),
                ]:
                    self.w(fp + off, value)
                anchors = self.alloc(max(1, len(frame.anchors)) * 12)
                for index, anchor in enumerate(frame.anchors):
                    self.u.mem_write(anchors + index * 12, anchor[4:16])
                for off, value in [
                    (0x34, anchors),
                    (0x38, anchors + len(frame.anchors) * 12),
                    (0x3C, anchors + len(frame.anchors) * 12),
                    (0x40, len(frame.anchors)),
                ]:
                    self.w(fp + off, value)
        self.acts[name] = pointer
        return pointer

    def invoke(self, address, args, ecx):
        self.w(self.sp, 0x50003000)
        for i, value in enumerate(args):
            self.w(self.sp + 4 + i * 4, value)
        self.u.reg_write(UC_X86_REG_ESP, self.sp)
        self.u.reg_write(UC_X86_REG_ECX, ecx)
        self.u.emu_start(address, 0x50003000, count=10000)
        assert self.u.reg_read(UC_X86_REG_EIP) == 0x50003000
        assert self.u.reg_read(UC_X86_REG_ESP) == self.sp + 4 + len(args) * 4
        return self.u.reg_read(UC_X86_REG_EAX)

    def select(self, name, ai, fi, part):
        self.w(self.actor + 0x38, ai)
        self.w(self.actor + 0x3C, fi)
        self.w(self.bp - 0x4C, self.acts[name])
        for off in [-0x68, -0x48, -0x5C]:
            self.w(self.bp + off, 0)
        self.u.reg_write(UC_X86_REG_ESP, self.sp)
        self.u.reg_write(UC_X86_REG_EBP, self.bp)
        self.u.reg_write(UC_X86_REG_EDI, self.wrapper)
        self.u.reg_write(UC_X86_REG_ESI, part)
        self.u.reg_write(UC_X86_REG_ECX, ai)
        skipped = []

        def stop(uc, pc, size, unused):
            if pc == 0x604532:
                skipped.append(True)
                uc.emu_stop()

        hook = self.u.hook_add(UC_HOOK_CODE, stop)
        self.u.emu_start(0x6043B7, 0x6043ED, count=10000)
        self.u.hook_del(hook)
        if skipped:
            return None, None
        assert self.u.reg_read(UC_X86_REG_EIP) == 0x6043ED
        assert self.u.reg_read(UC_X86_REG_ESP) == self.sp
        return self.u.reg_read(UC_X86_REG_EAX), [
            self.d(self.bp - 0x68),
            self.d(self.bp - 0x48),
            self.d(self.bp - 0x5C) & 255,
        ]


def verify(candidate, native_rod_family=False):
    m = Engine(candidate)
    fixtures = WORK / 'fixtures'
    resource_record = json.loads((fixtures / 'resources.json').read_text(encoding='utf-8'))
    for row in resource_record['resources']:
        assert hashlib.sha256((fixtures / row['fixture']).read_bytes()).hexdigest() == row['sha256']
    acts = {
        name: h.base.read_act((fixtures / (name + '.act')).read_bytes())
        for name in ['body', 'head', 'weapon']
    }
    for name, act in acts.items():
        m.act(name, act)
    hat = copy.deepcopy(acts['head'])
    for ai in range(len(hat.actions)):
        hat.actions[ai] = [copy.deepcopy(acts['head'].actions[ai % 8][0])]
    m.act('one_frame_hat', hat)
    m.slots = {kind: m.alloc(9 * 4) for kind in ['act', 'spr']}
    for off, kind in [(0x4B8, 'act'), (0x4AC, 'spr')]:
        m.w(m.actor + off, m.slots[kind])
        m.w(m.actor + off + 4, m.slots[kind] + 9 * 4)
    for slot, name in [(0, 'body'), (1, 'head'), (5, 'weapon')]:
        m.w(m.slots['act'] + slot * 4, m.acts[name])
    m.actor_state()
    selected = []
    anchor_cases = 0
    output = m.alloc(16)
    for ai, sequence in enumerate(acts['body'].actions):
        for fi in range(len(sequence)):
            frame, overrides = m.select('head', ai, fi, 1)
            remap = ai // 8 in [4, 5, 9, 10, 11, 12]
            hai, hfi = (ai % 8, 0) if remap else (ai, fi)
            assert frame == m.frames['head', hai, hfi], (ai, fi, hex(frame or 0))
            assert overrides == ([hai, hfi, 1] if remap else [0, 0, 0]), (ai, fi, overrides)
            hf = acts['head'].actions[hai][hfi]
            li = next(i for i, l in enumerate(hf.layers) if l.index >= 0)
            args = [
                output,
                1,
                m.layers['head', hai, hfi, li],
                li,
                0xFE6850,
                0,
                m.acts['head'],
                frame,
                0,
                *overrides,
            ]
            m.invoke(0x605170, args, m.wrapper)
            x, y = struct.unpack('<ii', bytes(m.u.mem_read(output + 8, 8)))
            expected = tuple(
                a - b
                for a, b in zip(h.base.anchor(acts['body'].actions[ai][fi]), h.base.anchor(hf))
            )
            assert (y, x) == expected, (ai, fi, (y, x), expected)
            assert m.d(m.actor + 0x38) == ai and m.d(m.actor + 0x3C) == fi
            selected.append(
                dict(
                    action=ai,
                    frame=fi,
                    head_action=hai,
                    head_frame=hfi,
                    anchor_delta=list(expected),
                )
            )
            anchor_cases += 1
    scope_cases = 0
    for kwargs in [dict(mounted=0), dict(visible=1), dict(body=1), dict(sex=1), dict(original=2)]:
        m.actor_state(**kwargs)
        for ai, fi in [(33, 5), (42, 2), (82, 8), (94, 7), (101, 4)]:
            frame, override = m.select('head', ai, fi, 1)
            remap = kwargs == dict(original=2)
            assert frame == m.frames['head', ai % 8 if remap else ai, 0 if remap else fi]
            scope_cases += 1
    m.actor_state()
    gear_cases = 0
    for ai, sequence in enumerate(acts['body'].actions):
        if ai // 8 not in [4, 5, 9, 10, 11, 12]:
            continue
        for fi in range(len(sequence)):
            for part in [2, 3, 4]:
                frame, overrides = m.select('one_frame_hat', ai, fi, part)
                assert frame == m.frames['one_frame_hat', ai % 8, 0]
                assert overrides == [ai % 8, 0, 1]
                # Native later phase-ratio call must not replace the headgear's
                # neutral pose with a combat pose after the primary selector.
                m.w(m.sp, ai)
                m.w(m.sp + 4, fi * 2)
                m.u.reg_write(UC_X86_REG_ESP, m.sp)
                m.u.reg_write(UC_X86_REG_ECX, m.acts['one_frame_hat'])
                m.u.emu_start(0x6044D9, 0x6044DE, count=1000)
                assert m.u.reg_read(UC_X86_REG_EAX) == frame
                assert m.u.reg_read(UC_X86_REG_ESP) == m.sp + 8
                gear_cases += 1
    weapon_cases = 0
    weapon_anchor_cases = 0
    for ai, sequence in enumerate(acts['body'].actions):
        for fi in range(len(sequence)):
            frame, _ = m.select('body', ai, fi, 0)
            assert frame == m.frames['body', ai, fi]
            frame, _ = m.select('weapon', ai, fi, 5)
            assert frame == m.frames['weapon', ai, fi]
            wf = acts['weapon'].actions[ai][fi]
            if wf.layers and wf.layers[0].index >= 0:
                m.invoke(
                    0x605170,
                    [
                        output,
                        5,
                        m.layers['weapon', ai, fi, 0],
                        0,
                        0xFE6850,
                        0,
                        m.acts['weapon'],
                        frame,
                        0,
                        0,
                        0,
                        0,
                    ],
                    m.wrapper,
                )
                assert bytes(m.u.mem_read(output + 8, 8)) == bytes(8), (
                    ai,
                    fi,
                    'unexpected weapon anchor offset',
                )
                weapon_anchor_cases += 1
            weapon_cases += 1
    draw_cases = []
    for kwargs in [
        dict(),
        dict(mounted=0),
        dict(visible=1),
        dict(body=1),
        dict(sex=1),
        dict(weapon=1601),
        dict(left=1201),
    ]:
        m.actor_state(**kwargs)
        for part in [5, 6]:
            m.u.reg_write(UC_X86_REG_EDI, m.wrapper)
            m.u.reg_write(UC_X86_REG_ESI, part)
            visited = []

            def stop(uc, pc, size, unused):
                if pc in [0x604338, 0x604540]:
                    visited.append(pc)
                    uc.emu_stop()

            hook = m.u.hook_add(UC_HOOK_CODE, stop)
            m.u.emu_start(0x604328, 0x50003000, count=1000)
            m.u.hook_del(hook)
            expected = (
                0x604338
                if kwargs == dict(mounted=0)
                or (
                    part == 5
                    and (not kwargs or (native_rod_family and kwargs == dict(weapon=1601)))
                )
                else 0x604540
            )
            assert visited == [expected], (kwargs, part, visited)
            draw_cases.append(dict(state=kwargs, part=part, drawn=expected == 0x604338))
    # Run the actual single-Knife native equipment setter from actor argument
    # unpacking through resource existence, ACT load and SPR load.
    m.actor_state()
    # Initial appearance can precede storing the incoming weapon in CPlayer.
    # Execute the real gate and class dispatch up to its virtual setter call.
    m.w(m.actor + 0x440, 0)
    m.w(m.bp + 0x14, 1201)
    m.w(m.bp + 0x18, 0)
    m.u.reg_write(UC_X86_REG_EBP, m.bp)
    m.u.reg_write(UC_X86_REG_ESP, m.sp)
    m.u.reg_write(UC_X86_REG_EDI, m.actor)
    m.u.reg_write(UC_X86_REG_EAX, 0)
    m.u.emu_start(0xD3EA1B, 0xD3EA63, count=2000)
    assert m.u.reg_read(UC_X86_REG_EIP) == 0xD3EA63
    assert [m.d(m.sp - 8), m.d(m.sp - 4)] == [1201, 0]
    assert m.u.reg_read(UC_X86_REG_ECX) == m.actor
    m.actor_state()
    m.expected = {
        ext: 'sprite\\인간족\\여우마법사\\여우마법사_여_단검.' + ext for ext in ['act', 'spr']
    }
    m.w(m.bp + 8, 1201)
    m.w(m.bp + 12, 0)
    m.u.reg_write(UC_X86_REG_EBP, m.bp)
    m.u.reg_write(UC_X86_REG_ESP, m.sp)
    m.u.reg_write(UC_X86_REG_ECX, m.actor)
    m.u.emu_start(0xD403CE, 0xD40CB3, count=20000)
    assert m.u.reg_read(UC_X86_REG_EIP) == 0xD40CB3
    assert m.loads == [('act', m.expected['act']), ('spr', m.expected['spr'])], m.loads
    assert m.d(m.slots['act'] + 20) == m.acts['weapon']
    report = dict(
        passed=True,
        client_sha256=hashlib.sha256(Path(candidate).read_bytes()).hexdigest(),
        full_native_caller_head_cases=len(selected),
        native_anchor_cases=anchor_cases,
        body_and_weapon_frames_preserved=weapon_cases,
        scope_cases=scope_cases,
        native_weapon_attachment_cases=weapon_anchor_cases,
        native_headgear_guard_and_phase_cases=gear_cases,
        cold_appearance_routes_incoming_knife=True,
        draw_gate_cases=draw_cases,
        native_weapon_setter_loads=m.loads,
        original_class_zero_matches_live=True,
        resource_record=resource_record,
        head_selections=selected,
        live_visual_acceptance=False,
        boundaries='Native ACT getters, selection caller, head anchors and std::string assignment execute; allocator, item DB, file loading and special-account checks are doubles.',
    )
    (WORK / 'compositor-verification.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    print(
        'PASS:',
        len(selected),
        'native caller + head anchor cases;',
        weapon_cases,
        'body/weapon frames; native single-Knife setter selected and loaded the mounted pair.',
    )


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', type=Path, default=WORK / 'client-r4/client.exe')
    verify(ap.parse_args().candidate)
