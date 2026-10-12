"""Verify FloorSafeSpriteDepth statically, by cave emulation, and via real WARP exports.

The emulator executes the exported caves instruction by instruction (capstone
decode, float32 SSE semantics) for actor/non-actor vtables, the stock and
reversed 0x9C depth paths, rows above and below the anchor, and checks that
EAX/ECX and the EFLAGS consumed by the native je at 0x00C40FA4 are preserved.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import tempfile
import capstone
import numpy as np
import pefile
from build_native_act_job_ui import ROOT, ORIGINAL
from verify_native_act_job_ui_warp import fixture_at, export

QJS = ROOT / 'Scripts/Patches/FloorSafeSpriteDepth.qjs'
BODY_HOOK, BODY_RESUME, SHADOW_HOOK, SHADOW_RESUME = 0xC40F9F, 0xC40FA4, 0xC49FEE, 0xC4A004
TILT = 0x11DD47C
UNIFORM_RHW_SITE = 0xC4A5B1
NON_ACTOR_VTABLES = {'CItem': 0x10932AC, 'CCorpse': 0x1093B0C, 'CGameActor': 0x108F82C}
F32 = np.float32


def qjs_constants():
    text = QJS.read_bytes()
    assert text.startswith(b'/*') and b'\n' not in text.replace(b'\r\n', b''), 'QJS must be CRLF without BOM'
    body = re.search(rb"bodySig = 0x([0-9A-F]+);\r\nFloorSafeSpriteDepth\.bodyHex = '([0-9a-f]+)'", text)
    shadow = re.search(rb"shadowSig = 0x([0-9A-F]+);\r\nFloorSafeSpriteDepth\.shadowHex = '([0-9a-f]+)'", text)
    actors = [(m.group(1).decode(), int(m.group(2), 16), int(m.group(3), 16)) for m in
              re.finditer(rb'name: "(\w+)", vtable: 0x([0-9A-F]+), render: 0x([0-9A-F]+)', text)]
    return (int(body.group(1), 16), bytes.fromhex(body.group(2).decode()),
            int(shadow.group(1), 16), bytes.fromhex(shadow.group(2).decode()), actors)


class Image:
    def __init__(self, path):
        self.pe = pefile.PE(str(path)); self.data = Path(path).read_bytes()
        self.base = self.pe.OPTIONAL_HEADER.ImageBase

    def read(self, va, n):
        off = self.pe.get_offset_from_rva(va - self.base)
        return self.data[off:off + n]

    def u32(self, va):
        return struct.unpack('<I', self.read(va, 4))[0]

    def jmp_target(self, va):
        raw = self.read(va, 5); assert raw[0] == 0xE9, hex(va)
        return (va + 5 + struct.unpack('<i', raw[1:])[0]) & 0xFFFFFFFF


def static_gate():
    body_sig, body_hex, shadow_sig, shadow_hex, actors = qjs_constants()
    image = Image(ORIGINAL)
    assert image.read(body_sig, len(body_hex)) == body_hex, 'actor rect builder differs'
    assert image.read(shadow_sig, len(shadow_hex)) == shadow_hex, 'shadow builder differs'
    assert len(actors) == 8
    for name, vt, render in actors:
        assert image.u32(vt + 0x24) == 0xC40C20 and image.u32(vt + 0x0C) == render, name
    for name, vt in NON_ACTOR_VTABLES.items():
        assert image.u32(vt + 0x24) == 0xC40C20, name
    assert struct.unpack('<f', image.read(TILT, 4))[0] == F32(0.16)
    return dict(body_signature_bytes=len(body_hex), shadow_signature_bytes=len(shadow_hex),
                actors=[a[0] for a in actors])


class Cpu:
    """Executes only the instruction forms the two caves use."""
    def __init__(self, image, memory):
        self.image, self.mem = image, memory
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); self.md.detail = True
        self.r = dict(eax=0, ecx=0, edi=0, ebp=0)
        self.x = {}
        self.zf = 0; self.stack = []

    def load8(self, va):
        return self.mem[va] if va in self.mem else self.image.read(va, 1)[0]

    def load32(self, va):
        return sum(self.load8(va + i) << (8 * i) for i in range(4))

    def addr(self, op):
        m = op.mem
        base = self.r[self.md.reg_name(m.base)] if m.base else 0
        return (base + m.disp) & 0xFFFFFFFF

    def f32(self, va):
        return np.frombuffer(struct.pack('<I', self.load32(va)), np.float32)[0]

    def run(self, pc, stop, limit=64):
        for _ in range(limit):
            if pc in stop: return pc
            ins = next(self.md.disasm(self.image.read(pc, 16), pc))
            m, ops, nxt = ins.mnemonic, ins.operands, pc + ins.size
            if m in ('subss', 'mulss', 'minss', 'maxss'):
                d = self.md.reg_name(ops[0].reg); a = self.x[d]; b = self.f32(self.addr(ops[1]))
                self.x[d] = F32({'subss': a - b, 'mulss': a * b,
                                 'minss': a if a < b else b, 'maxss': a if a > b else b}[m])
            elif m in ('jne', 'je', 'jmp'):
                t = ops[0].imm
                if m == 'jmp' or (m == 'je') == bool(self.zf): nxt = t
            elif m == 'pushfd': self.stack.append(('flags', self.zf))
            elif m == 'popfd': kind, self.zf = self.stack.pop(); assert kind == 'flags'
            elif m == 'push': self.stack.append(('eax', self.r['eax']))
            elif m == 'pop': kind, self.r['eax'] = self.stack.pop(); assert kind == 'eax'
            elif m == 'mov': self.r['eax'] = self.load32(self.addr(ops[1]))
            elif m == 'cmp': self.zf = int(self.r['eax'] == (ops[1].imm & 0xFFFFFFFF))
            elif m == 'add': self.r['ecx'] = (self.r['ecx'] + self.r['eax']) & 0xFFFFFFFF; self.zf = int(self.r['ecx'] == 0)
            elif m == 'movzx': self.r['eax'] = self.load32(self.addr(ops[1])) & 0xFF
            else: raise AssertionError(f'unexpected instruction {m} {ins.op_str} at {pc:#x}')
            pc = nxt
        raise AssertionError('cave did not return')


def emulate(target):
    image = Image(target)
    body, shadow = image.jmp_target(BODY_HOOK), image.jmp_target(SHADOW_HOOK)
    assert image.read(SHADOW_HOOK + 5, 17) == b'\x90' * 17
    _, _, _, _, actors = qjs_constants()
    EBP, EDI, SY = 0x8000, 0x7000, F32(300.0)
    def bytes32(va, value):
        return {va + i: (value >> (8 * i)) & 0xFF for i in range(4)}
    sy_bits = struct.unpack('<I', struct.pack('<f', SY))[0]
    body_cases = 0
    vtables = [(n, v, True) for n, v, _ in actors] + [(n, v, False) for n, v in NON_ACTOR_VTABLES.items()]
    for name, vt, actor in vtables:
        for reversed_path in (False, True):
            for top, bottom in ((F32(210.0), F32(325.0)), (F32(210.0), F32(296.0)), (F32(304.0), F32(320.0))):
                cpu = Cpu(image, {**bytes32(EBP + 0x1C, sy_bits), **bytes32(EDI, vt)})
                cpu.r.update(ebp=EBP, edi=EDI, eax=0x1234)
                cpu.x.update(xmm4=F32(bottom - SY), xmm5=top)
                cpu.zf = 0 if reversed_path else 1
                assert cpu.run(body, {BODY_RESUME}) == BODY_RESUME
                clamp = actor and not reversed_path
                want4 = min(F32(bottom - SY), F32(0)) if clamp else F32(bottom - SY)
                want5 = min(F32(top - SY), F32(0)) if clamp else F32(top - SY)
                assert cpu.x['xmm4'] == want4 and cpu.x['xmm5'] == want5, (name, reversed_path, top, bottom, cpu.x)
                assert cpu.r['eax'] == 0x1234 and cpu.zf == (0 if reversed_path else 1) and not cpu.stack
                body_cases += 1
    shadow_cases = 0
    for top, bottom in ((F32(280.0), F32(320.0)), (F32(305.0), F32(330.0)), (F32(270.0), F32(295.0))):
        cpu = Cpu(image, {EDI + 0x12: 0x7F})
        cpu.r.update(edi=EDI, ecx=0x00AB00, eax=0x37)
        cpu.x.update(xmm7=F32(top - SY), xmm6=F32(bottom - SY))
        assert cpu.run(shadow, {SHADOW_RESUME}) == SHADOW_RESUME
        tilt = F32(0.16)
        assert cpu.x['xmm7'] == F32(max(F32(top - SY), F32(0)) * tilt)
        assert cpu.x['xmm6'] == F32(max(F32(bottom - SY), F32(0)) * tilt)
        assert cpu.r['ecx'] == 0x00AB37 and cpu.r['eax'] == 0x7F, cpu.r
        shadow_cases += 1
    return dict(body_cave=hex(body), shadow_cave=hex(shadow), body_cases=body_cases, shadow_cases=shadow_cases)


def native_changes(target):
    a, b = pefile.PE(str(ORIGINAL)), pefile.PE(str(target))
    out = []
    for s in a.sections:
        if not s.Characteristics & 0x20000000: continue
        before = s.get_data()[:s.Misc_VirtualSize]
        after = b.get_data(s.VirtualAddress, len(before))
        out += [0x400000 + s.VirtualAddress + i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    return out


def run(out=None):
    report = dict(static=static_gate(), cases=[], live_tested=False)
    out = out or Path(tempfile.mkdtemp(prefix='floor-safe-depth-', dir=ROOT / 'Outputs'))
    fixture = fixture_at(out)
    cases = [('depth-only', ['FloorSafeSpriteDepth']),
             ('with-rhw', ['UniformSpriteRHW', 'FloorSafeSpriteDepth']),
             ('rhw-after', ['FloorSafeSpriteDepth', 'UniformSpriteRHW']),
             ('full-stack', ['ClanBodySkins', 'AllowDualCustomWeaponSprites', 'AllHatEffectsWorldDepthOracle',
                             'UniformSpriteRHW', 'FloorSafeSpriteDepth'])]
    for name, patches in cases:
        target = export(fixture, out / name, ORIGINAL, patches)
        row = dict(case=name, patches=patches, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        row.update(emulate(target))
        image = Image(target)
        if name == 'depth-only':
            body, shadow = image.jmp_target(BODY_HOOK), image.jmp_target(SHADOW_HOOK)
            cave = min(body, shadow) - 0x10
            allowed = set(range(BODY_HOOK, BODY_HOOK + 5)) | set(range(SHADOW_HOOK, SHADOW_HOOK + 0x16))
            allowed |= set(range(cave, cave + 0xA0))
            stray = [hex(va) for va in native_changes(target) if va not in allowed]
            assert not stray, f'Unexpected native code changes: {stray[:16]}'
            assert image.read(cave, 16) == bytes(16), 'zero constant missing'
        if 'UniformSpriteRHW' in patches:
            assert image.read(UNIFORM_RHW_SITE, 5) == bytes.fromhex('0f1f440000')
        report['cases'].append(row)
        print('PASS ' + name, flush=True)
    report['status'] = 'source_emulation_and_export_verified'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-only', action='store_true')
    parser.add_argument('--exe', type=Path, help='emulate the caves inside an existing exported client')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.static_only:
        result = dict(static=static_gate(), live_tested=False)
    elif args.exe:
        result = dict(static=static_gate(), emulation=emulate(args.exe), live_tested=False)
    else:
        result = run()
    print(json.dumps(result, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2), encoding='utf8')
