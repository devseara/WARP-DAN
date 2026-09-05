"""Reproduce the pulled dual-weapon patch's scope from bytes, not handoff claims.

Uses pefile, capstone and unicorn from the project's Python environment.
Native ACT calls are deterministic stubs; the test proves control flow and
resource-role selection, NOT rendered geometry or live visual acceptance.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/dual_weapon_formats"))
from rig_tables import parse_rig_bytes

CORE_SHA256 = "233f65b298bfec24ac1e79df2be487c4468d2bfddf69f84314c8b45eba3fc4a5"
ENVELOPE_SHA256 = "e2907b79240e3a9341f84f1f7a58948576c23e2626fe95bc1f482849a4149f80"
HOOKS = {
    "equipment": (0xD403A0, "55 8b ec 6a ff"),
    "capture": (0x605D41, "89 45 94 8b 45 0c 89 45 c8"),
    "final_draw": (0xC4A0D0, "55 8b ec 83 ec 50"),
    "depth": (0xC4A647, "a1 f8 15 25 01"),
    "stock_action_call": (0xD36EE4, "e8 c7 85 9d ff"),
    "pair_mapper": (0xD39130, "55 8b ec 8b 55 08"),
}
PAIR_TYPES = {25: (1, 1), 26: (2, 2), 27: (6, 6),
              28: (2, 1), 29: (6, 1), 30: (6, 2)}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def payload(source, name):
    match = re.search(r"const " + re.escape(name) + r'Hex = "([0-9A-Fa-f ]+)";', source)
    if not match:
        raise ValueError(f"missing unique payload: {name}")
    return bytes.fromhex(match[1])

def core_scope_case(core, relocs, rig, pair, main_type, off_type, action, frame, gender=0):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP
    # All code and data are private emulator memory. No live process is opened.
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    cb, db, sb, stop = 0x100000, 0x200000, 0x300000, 0x120000
    uc.mem_map(cb, 0x30000)
    uc.mem_map(db, 0x20000)
    uc.mem_map(sb, 0x10000)
    relocated = bytearray(core)
    for offset, target in relocs:
        if not 0 <= offset <= len(core)-4 or not 0 <= target < len(core):
            raise ValueError("core relocation outside payload")
        struct.pack_into("<I", relocated, offset, cb + target)
    uc.mem_write(cb, bytes(relocated))
    actor, packet, capture, ctx = db, db+0x1000, db+0x1100, db+0x1200
    registry, rig_addr = db+0x2000, db+0x8000
    layer, act_frame = db+0x1400, db+0x1500
    frame_stub, layer_stub, draw_stub = cb+0x20010, cb+0x20020, cb+0x20030
    w = lambda addr, *values: uc.mem_write(addr, struct.pack("<" + "I"*len(values), *values))
    w(actor+0x38, action, frame)
    channel = 6 if 88 <= action <= 95 and frame in (3,4,6,7) else 5
    image = db+0x1600
    w(packet+0x2c, image)
    w(capture, actor, channel, image, layer)
    w(ctx, registry, capture, rig_addr, frame_stub, layer_stub, 0x38, 0x3c, 256,
      0, 0, 0, 0x440, 0x444, 0, 0, 0, 0)
    resources = [db+0x1800+i*0x100 for i in range(10)]
    row = registry + ((actor >> 4) & 255)*60
    w(row, actor, *resources, pair, main_type, off_type, gender)
    uc.mem_write(rig_addr, rig)
    # The exact family discriminator from the embedded DWR3, action 32/frame 0.
    x, y, sprite = struct.unpack_from("<hhH", rig, 24)
    mirror = rig[22] & 1
    w(layer, x & 0xffffffff, y & 0xffffffff, sprite, mirror)
    w(act_frame+0x20, layer, layer+40)
    uc.mem_write(frame_stub, b"\xc2\x08\x00")
    uc.mem_write(layer_stub, b"\xc2\x04\x00")
    uc.mem_write(draw_stub, b"\xc2\x18\x00")
    esp = sb+0xf000
    w(esp, stop, actor, packet, 0, 0, 0, 0, 0, ctx, draw_stub)
    uc.reg_write(UC_X86_REG_ESP, esp)
    trace = []
    calls = []
    result = {"pair": pair, "main_type": main_type, "off_type": off_type,
              "action": action, "frame": frame, "gender": gender}
    def hook(machine, address, size, _):
        if cb <= address < cb+len(core):
            trace.append(address-cb)
        if address == frame_stub:
            calls.append({"kind": "frame", "resource": machine.reg_read(UC_X86_REG_ECX)})
            machine.reg_write(UC_X86_REG_EAX, act_frame)
        elif address == layer_stub:
            machine.reg_write(UC_X86_REG_EAX, layer)
        elif address == cb+0x43ad:
            # Family passed. Stop before pose preparation; do not invent renderer inputs.
            result["outcome"] = "family_gate_passed"
            stack = machine.reg_read(UC_X86_REG_ESP)
            result["physical_hand_resources"] = {
                "sword_spr": struct.unpack("<I", machine.mem_read(stack+0x4e8,4))[0],
                "dagger_spr": struct.unpack("<I", machine.mem_read(stack+0x4b4,4))[0],
            }
            machine.emu_stop()
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(cb, stop, count=100000)
    if "outcome" not in result:
        if uc.reg_read(UC_X86_REG_EIP) != stop:
            raise AssertionError("emulation stopped without reaching return")
        result["outcome"] = "stock_fallback"
        result["return_eax"] = uc.reg_read(UC_X86_REG_EAX)
        assert result["return_eax"] == 0
    result["family_pair_gate_seen"] = 0x407b in trace
    result["family_pair_rejection_taken"] = 0x407f in trace and 0x4112 in trace
    result["act_frame_calls"] = len(calls)
    result["tail_offsets"] = [f"0x{x:04x}" for x in trace[-10:]]
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT/"Outputs/dual_weapon_audit_20260905")
    parser.add_argument("--stock", type=Path, default=ROOT/"2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe")
    parser.add_argument("--exe", type=Path, help="Optional newly built candidate to inspect")
    parser.add_argument("--grf", type=Path, help="Optional resource corpus; not assumed active in the client")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    qjs = ROOT/"Scripts/Patches/AllowDualCustomWeaponSprites.qjs"
    raw_source = qjs.read_bytes()
    source = raw_source.decode("utf-8")
    assert raw_source.startswith(b"/*") and not re.search(rb"(?<!\r)\n",raw_source)
    core = payload(source, "DualWeaponAuthoredCore")
    rig_bytes = payload(source, "DualWeaponAuthoredRig")
    envelope = payload(source, "DualWeaponCharacterEnvelopeCore")
    assert sha(core) == CORE_SHA256, "Core changed: re-profile emulation offsets before running"
    assert sha(envelope) == ENVELOPE_SHA256, "Protected depth helper changed"
    relocs = json.loads(re.search(r"const DualWeaponAuthoredCoreRelocs = (\[.*?\]);",source)[1])
    rig = parse_rig_bytes(rig_bytes)
    assert zlib.crc32(rig_bytes[20:]) & 0xffffffff == rig["crc32"], "Rig CRC mismatch"
    assert {r["state"] for r in rig["records"]} == {9,10}, "Embedded scope changed"
    counts = collections.Counter((r["gender"],r["state"],r["phase"]) for r in rig["records"])
    canonical = parse_rig_bytes((ROOT/"Inputs/DualWeaponAuthored/rigs/female-assassin-canonical.dwr3").read_bytes())
    # Execute the original core for all six pair types, both mixed orders,
    # 8 directions x (6 held + 8 attack) frames. Family-pass != visual pass.
    matrix = []
    for pair,(mt,ot) in PAIR_TYPES.items():
        orders = [(mt,ot)] if mt==ot else [(mt,ot),(ot,mt)]
        for m,o in orders:
            for phase in (0,1):
                for direction in range(8):
                    for frame in range(6 if phase==0 else 8):
                        r = core_scope_case(core,relocs,rig_bytes,pair,m,o,
                                            (32 if phase==0 else 88)+direction,frame)
                        expected = "family_gate_passed" if pair==28 else "stock_fallback"
                        assert r["outcome"] == expected, r
                        if pair==28:
                            slot = 0 if (32 <= r["action"] <= 39 or frame not in (3,4,6,7)) else 2
                            sword_index = slot if m==2 else slot+4
                            dagger_index = slot+4 if m==2 else slot
                            assert r["physical_hand_resources"] == {
                                "sword_spr": 0x201800+sword_index*0x100,
                                "dagger_spr": 0x201800+dagger_index*0x100,
                            }, r
                        matrix.append(r)
    # Explicit gender-negative case.
    populated_pair25 = core_scope_case(core,relocs,canonical["bytes"],25,1,1,32,0)
    assert populated_pair25["outcome"]=="stock_fallback"
    assert populated_pair25["family_pair_rejection_taken"]
    male = core_scope_case(core,relocs,rig_bytes,28,2,1,32,0,gender=1)
    assert male["outcome"] == "stock_fallback"
    import capstone
    import pefile
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    windows = [(0x3fbd,0x4036),(0x4060,0x4112),(0x4320,0x4369),(0xf19c,0xf1a9)]
    excerpt=[]
    for lo,hi in windows:
        excerpt += [f"core+0x{i.address:04X}: {i.bytes.hex(' '):28} {i.mnemonic} {i.op_str}"
                    for i in md.disasm(core[lo:hi],lo)]
    (args.out/"core-scope.disasm.txt").write_text("\n".join(excerpt)+"\n")
    binaries=[]
    for name,path in [("stock",args.stock)]+([("candidate",args.exe)] if args.exe else []):
        data=path.read_bytes()
        pe=pefile.PE(data=data,fast_load=True)
        assert pe.FILE_HEADER.Machine==0x14c and pe.OPTIONAL_HEADER.ImageBase==0x400000
        sites={}
        for key,(va,expected) in HOOKS.items():
            exp=bytes.fromhex(expected); off=pe.get_offset_from_rva(va-0x400000)
            actual=data[off:off+len(exp)]
            site={"va":hex(va),"file_offset":hex(off),"bytes":actual.hex(" "),"stock":actual==exp}
            if name=="stock": assert actual==exp,(key,site)
            if actual[0] in (0xe8,0xe9):
                site["rel32_target"]=hex(va+5+struct.unpack_from("<i",actual,1)[0])
            sites[key]=site
        if name=="candidate":
            for key in ("equipment","capture","final_draw","depth"):
                assert not sites[key]["stock"], f"{key} hook absent"
            assert sites["stock_action_call"]["stock"], "Rejected native-slot action bridge present"
            for label,blob in (("rig",rig_bytes),("core",core),("envelope",envelope)):
                if label in ("core", "envelope"):
                    # Check all relocated code bytes, not only the entry signature.
                    pos=data.find(blob[:64])
                    assert pos>=0 and data.find(blob[:64],pos+1)<0, "Core absent/ambiguous"
                    core_va=0x400000+pe.get_rva_from_offset(pos)
                    expected_core=bytearray(blob)
                    checked_relocs = relocs if label=="core" else json.loads(
                        re.search(r"const DualWeaponCharacterEnvelopeCoreRelocs = (\[.*?\]);",source)[1])
                    for offset,target in checked_relocs:
                        struct.pack_into("<I",expected_core,offset,core_va+target)
                    assert data[pos:pos+len(blob)]==expected_core, "Relocated core mismatch"
                    sites[label+"_payload"]={"va":hex(core_va),"file_offset":hex(pos),
                                           "verified_bytes":len(blob),"verified_relocations":len(checked_relocs)}
                    continue
                assert data.count(blob)==1,(label,"payload missing or duplicated")
        binaries.append({"role":name,"path":str(path),"sha256":sha(data),"sites":sites})
    for name,data in (("runtime.bin",core),("rig.dwr3",rig_bytes),("depth.bin",envelope)):
        (args.out/name).write_bytes(data)
    examples=[next(r for r in matrix if r["pair"]==pair and r["action"]==32 and r["frame"]==0)
              for pair in PAIR_TYPES]
    report={
        "schema":1, "scope":"Byte audit and deterministic x86 family-gate execution; no live rendering",
        "source_sha256":sha(raw_source),"source_size":len(raw_source),
        "payloads":{"core":{"size":len(core),"sha256":sha(core),"relocations":len(relocs)},
                    "rig":{"size":len(rig_bytes),"sha256":sha(rig_bytes),"crc32_stored":hex(rig["crc32"]),
                           "crc32_payload":hex(zlib.crc32(rig_bytes[20:])&0xffffffff)},
                    "envelope":{"size":len(envelope),"sha256":sha(envelope)}},
        "embedded_records":[{"gender":g,"state":s,"phase":p,"records":n} for (g,s,p),n in sorted(counts.items())],
        "external_canonical_records_by_state":dict(sorted(collections.Counter(r["state"] for r in canonical["records"]).items())),
        "registry":{"rows":256,"row_bytes":60,"start_offset":0x1000,"end_offset":0x4c00,"allocation_bytes":0x5000,"overrun":False},
        "emulation":{"cases":len(matrix),"outcomes":dict(collections.Counter(r["outcome"] for r in matrix)),
                     "examples":examples,"male_pair28":male,"populated_pair25_still_rejected":populated_pair25},
        "binaries":binaries
    }
    if args.grf:
        from grf_reader import GrfFile
        from act_reader import parse_act
        prefix="data/sprite/인간족/어세신/어세신_여_"
        g=GrfFile(args.grf)
        assets=[]
        try:
            for suffix in ("단검_단검","단검_검","1238","13412"):
                entry=prefix+suffix+".act"
                raw=g.read(entry)
                if raw is None:
                    assets.append({"entry":entry,"missing":True})
                    continue
                act=parse_act(raw)
                cells=[]
                for action in (32,80,88):
                    for fi,frame in enumerate(act["actions"][action].frames):
                        cells.append({"action":action,"frame":fi,"layers":[
                            {"x":l.x,"y":l.y,"sprite":l.sprite_index,"mirror":l.mirror,"rotation":l.rotation}
                            for l in frame.layers]})
                assets.append({"entry":entry,"sha256":sha(raw),"cells":cells})
        finally:
            g.close()
        report["asset_corpus"]={"path":str(args.grf),
            "scope":"Specific archive entries only; client archive/loose-file resolution is not verified",
            "assets":assets}
    (args.out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"source_sha256":report["source_sha256"],"embedded_records":report["embedded_records"],
                      "emulation_cases":len(matrix),"outcomes":report["emulation"]["outcomes"],
                      "report":str(args.out/"report.json")},indent=2))

if __name__ == "__main__":
    main()
