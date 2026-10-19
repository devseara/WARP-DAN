"""Exercise the real client gates, native action mapper and attack serialization.

Network transmission and skill-availability queries are boundary stubs. This verifies
native CPU execution; actual game visuals/damage remain a separate live gate.
Run with .venv-target-hud/Scripts/python.exe (Unicorn is installed there).
"""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

ROOT = Path(__file__).resolve().parents[1]
QJS = ROOT / 'Scripts/Patches/AllowAllRidingCombat.qjs'
GATES = [(0xC8D6DC, 0xC8D745), (0xC8D9CE, 0xC8DA36), (0xC8DF76, 0xC8DFB3), (0xC8F7E2, 0xC8F807)]


def gates():
    raw = QJS.read_bytes()
    assert raw.startswith(b'/*') and b'\n' not in raw.replace(b'\r\n', b'')
    rows = re.findall(
        r"name:\s*'([^']+)',\s*va:\s*0x([0-9A-F]+),\s*stock:\s*'([0-9a-f]+)'", raw.decode()
    )
    assert [int(a, 16) for _, a, _ in rows] == [a for a, _ in GATES]
    return [(name, int(a, 16), bytes.fromhex(s)) for name, a, s in rows]


class CPU:
    def __init__(self, path):
        self.pe = pefile.PE(str(path), fast_load=True)
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        size = (self.pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095
        self.u.mem_map(self.base, size)
        self.u.mem_write(self.base, self.pe.get_memory_mapped_image())
        self.u.mem_map(0, 4096)  # Native FS exception record for the mapper's callees.
        self.u.mem_map(0x40000000, 0x40000)
        self.u.mem_map(0x50000000, 0x4000)
        self.bp, self.sp, self.actor = 0x40030000, 0x40010000, 0x50000000
        self.u.reg_write(UC_X86_REG_EBP, self.bp)
        self.u.reg_write(UC_X86_REG_ESP, self.sp)

    def w(self, a, value):
        self.u.mem_write(a, struct.pack('<I', value & 0xFFFFFFFF))

    def d(self, a):
        return struct.unpack('<I', self.u.mem_read(a, 4))[0]

    def ret(self, value, args=0):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        self.u.reg_write(UC_X86_REG_EAX, value)
        self.u.reg_write(UC_X86_REG_EIP, self.d(sp))
        self.u.reg_write(UC_X86_REG_ESP, sp + 4 + args)


def verify(source, candidate):
    rows = gates()
    a, b = pefile.PE(str(source), fast_load=True), pefile.PE(str(candidate), fast_load=True)
    allowed = {va + 7 for _, va, _ in rows}
    changes = []
    for s in a.sections:
        old = s.get_data()
        new = b.get_data(s.VirtualAddress, len(old))
        assert len(new) == len(old)
        for i, (x, y) in enumerate(zip(old, new)):
            if x != y:
                va = a.OPTIONAL_HEADER.ImageBase + s.VirtualAddress + i
                assert va in allowed and x == 0x74 and y == 0xEB, hex(va)
                changes.append(hex(va))
    assert len(changes) == 4
    for _, va, stock in rows:
        assert a.get_data(va - 0x400000, len(stock)) == stock
    # Input branches: compare the real stock rejection with the patched route.
    gate_cases = []
    for path, patched in [(source, False), (candidate, True)]:
        m = CPU(path)
        for (name, va, _), (_, continuation) in zip(rows, GATES):
            for mounted in [0, 1]:
                m.u.mem_write(m.actor + 0x2CC, bytes([mounted]))
                m.u.reg_write(UC_X86_REG_EAX, m.actor)
                m.u.reg_write(UC_X86_REG_EDX, 7)
                m.u.reg_write(UC_X86_REG_ECX, 0x12345678)
                # Observe the branch itself, before any denial-message calls.
                m.u.emu_start(va, va + 9, count=2)
                actual = m.u.reg_read(UC_X86_REG_EIP)
                assert actual == (continuation if patched or not mounted else va + 9)
                assert m.u.mem_read(m.actor + 0x2CC, 1) == bytes([mounted])
                assert m.u.reg_read(UC_X86_REG_ECX) == 0x12345678
                assert m.u.reg_read(UC_X86_REG_EDX) == 7
                gate_cases.append(
                    dict(gate=name, patched=patched, mounted=bool(mounted), next=hex(actual))
                )
        m.pe.close()
    # Execute the native CZ_REQUEST_ACT serializer, not a recreated packet.
    packets = []
    for path, patched in [(source, False), (candidate, True)]:
        m = CPU(path)
        sent = []

        def net(uc, address, size, unused):
            if address == 0xC14D60:
                m.ret(0x50002000)
            elif address == 0xC14460:
                assert m.d(uc.reg_read(UC_X86_REG_ESP) + 4) == 0x437
                m.ret(7, 4)
            elif address == 0xC14920:
                sp = uc.reg_read(UC_X86_REG_ESP)
                length, packet = m.d(sp + 4), m.d(sp + 8)
                sent.append(bytes(uc.mem_read(packet, length)).hex())
                m.ret(1, 8)

        m.u.hook_add(UC_HOOK_CODE, net)
        for mounted in [0, 1]:
            for action in [0, 2, 3, 7]:
                if mounted and not patched and action in [0, 7]:
                    continue  # Stock blocked, already verified above.
                sent.clear()
                m.u.mem_write(m.actor + 0x2CC, bytes([mounted]))
                m.u.reg_write(UC_X86_REG_EAX, m.actor)
                m.u.reg_write(UC_X86_REG_ECX, 0x12345678)
                m.u.reg_write(UC_X86_REG_EDX, action)
                m.u.reg_write(UC_X86_REG_EBP, m.bp)
                m.u.reg_write(UC_X86_REG_ESP, m.sp)
                m.u.emu_start(0xC8F7E2, 0xC8F849, count=100)
                expected = struct.pack('<HIB', 0x437, 0x12345678, action).hex()
                assert sent == [expected], sent
                assert m.u.reg_read(UC_X86_REG_ESP) == m.sp
                assert m.u.mem_read(m.actor + 0x2CC, 1) == bytes([mounted])
                packets.append(
                    dict(
                        patched=patched,
                        mounted=bool(mounted),
                        action=action,
                        packet=sent[0],
                        sends=1,
                    )
                )
        m.pe.close()
    # Follow both skill gates through their real packet serializers. Ordinary
    # skill availability and command-busy checks are explicit boundary stubs.
    skill_packets = []
    m = CPU(candidate)
    sent = []
    busy = 0

    def skill_net(uc, address, size, unused):
        if address == 0xC14D60:
            m.ret(0x50002000)
        elif address == 0xC14460:
            op = m.d(uc.reg_read(UC_X86_REG_ESP) + 4)
            assert op in [0x438, 0xAF4], hex(op)
            m.ret({0x438: 10, 0xAF4: 11}[op], 4)
        elif address == 0xC14920:
            sp = uc.reg_read(UC_X86_REG_ESP)
            sent.append(bytes(uc.mem_read(m.d(sp + 8), m.d(sp + 4))).hex())
            m.ret(1, 8)
        elif address == 0xC86150:
            m.ret(busy)
        elif address == 0xC7E7C0:
            m.ret(0, 16)  # Replay-mode special case, not gameplay packet output.
        elif address in [0xD8E920, 0xD8E9A0]:
            m.ret(0, 4)  # Ordinary skill, not a mount exception skill.
        elif address == 0xD9C020:
            m.ret(1, 4)  # Skill is known/available.
        elif address == 0xC892DC:
            uc.emu_stop()

    m.u.hook_add(UC_HOOK_CODE, skill_net)
    mode, world, params = 0x50001000, 0x50001800, 0x50001C00
    m.w(mode + 0xCC, world)
    m.w(world + 0x2C, m.actor)
    for mounted in [0, 1]:
        for ground in [False, True]:
            for busy in [0, 1]:
                sent.clear()
                m.u.mem_write(m.actor + 0x2CC, bytes([mounted]))
                m.u.mem_write(mode + 0x418, b'\x01')
                m.w(m.bp - 0x10374, params if ground else 19)
                m.w(m.bp - 0x10378, 0 if ground else 0x12345678)
                m.w(m.bp - 0x10380, 3)
                m.u.mem_write(params, struct.pack('<4I', 19, 48, 82, 3))
                for reg, value in [
                    (UC_X86_REG_EAX, m.actor),
                    (UC_X86_REG_EDI, mode),
                    (UC_X86_REG_EBP, m.bp),
                    (UC_X86_REG_ESP, m.sp),
                ]:
                    m.u.reg_write(reg, value)
                m.u.emu_start(
                    0xC8DF76 if ground else 0xC8D9CE, 0xC8E0F1 if ground else 0xC8DEB8, count=1000
                )
                expected = (
                    struct.pack('<5HB', 0xAF4, 3, 19, 48, 82, 0)
                    if ground
                    else struct.pack('<HHHI', 0x438, 3, 19, 0x12345678)
                )
                assert sent == ([] if busy else [expected.hex()]), sent
                assert m.u.mem_read(m.actor + 0x2CC, 1) == bytes([mounted])
                assert m.u.reg_read(UC_X86_REG_ESP) == m.sp
                skill_packets.append(
                    dict(mounted=bool(mounted), ground=ground, busy=bool(busy), packets=sent.copy())
                )
    m.pe.close()
    # Execute native mount-view resolution, the real CPlayer job resolver and
    # action-to-ACT mapping together. Mount appearance uses a different view ID.
    mappings = []
    m = CPU(candidate)
    m.w(m.actor, 0x1094810)
    for job in range(7):
        for mounted in [0, 1]:
            m.u.mem_write(m.actor + 0x2CC, bytes([mounted]))
            m.w(m.actor + 0x2C0, job)
            view_job = job
            if mounted:
                m.w(m.sp, 0x50003000)
                m.w(m.sp + 4, job)
                m.u.reg_write(UC_X86_REG_ESP, m.sp)
                m.u.reg_write(UC_X86_REG_ECX, 0x15FA3C0)
                m.u.emu_start(0xD83D60, 0x50003000, count=1000)
                assert m.u.reg_read(UC_X86_REG_EIP) == 0x50003000
                view_job = m.u.reg_read(UC_X86_REG_EAX)
                assert view_job != job, 'Native default mount did not resolve'
            m.w(m.actor + 0x25C, view_job)
            for action in range(9):
                m.w(m.sp, 0x50003000)
                m.w(m.sp + 4, action)
                m.u.reg_write(UC_X86_REG_ESP, m.sp)
                m.u.reg_write(UC_X86_REG_ECX, m.actor)
                m.u.emu_start(0xD38AD0, 0x50003000, count=2000)
                first = m.u.reg_read(UC_X86_REG_EAX)
                assert first in [0, 16, 32, 96] and m.u.reg_read(UC_X86_REG_ESP) == m.sp + 8
                assert m.u.mem_read(m.actor + 0x2CC, 1) == bytes([mounted])
                mappings.append(
                    dict(
                        job=job,
                        view_job=view_job,
                        mounted=bool(mounted),
                        action=action,
                        first_act=first,
                    )
                )
    m.pe.close()
    a.close()
    b.close()
    return dict(
        passed=True,
        source=str(source),
        candidate=str(candidate),
        sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        changed_virtual_bytes=changes,
        allocations=0,
        gate_cases=gate_cases,
        native_attack_packets=packets,
        native_skill_packets=skill_packets,
        native_action_mapping=mappings,
        live_visuals_and_damage_accepted=False,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, type=Path)
    ap.add_argument('--candidate', required=True, type=Path)
    ap.add_argument('--report', required=True, type=Path)
    args = ap.parse_args()
    report = verify(args.source, args.candidate)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, indent=2))
    print(
        'PASS: four branch bytes; 16 gate cases, native attack/skill serialization and 126 action mappings'
    )


if __name__ == '__main__':
    main()
