#!/usr/bin/env python3
"""Verify native RTTI on cloned top-level UI vtables in a 2025-07-16 client.

The pub/vending checker calls __RTtypeid at 0x00A38CF9. This gate finds cloned
UIFrameWnd/UIWindow tables by unchanged method slots and executes the actual
VCRUNTIME140 __RTtypeid pointer-load sequence with each table. It never starts
or modifies the game. --expect-broken is a negative-control mode for old EXEs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

import pefile
import unicorn as uc
from unicorn import x86_const as x86

FAMILIES = (
    ("UIFrameWnd", 0x0102FE08, {0, 20, 25, 28, 31, 32, 33, 35, 37}),
    ("UIWindow", 0x0104AC44, {0, 20, 29, 50}),
)


def scan_clones(pe, raw):
    base = pe.OPTIONAL_HEADER.ImageBase
    def u32(va):
        data = pe.get_data(va - base, 4)
        if len(data) != 4:
            raise ValueError(f"Unmapped DWORD at {va:#x}")
        return struct.unpack("<I", data)[0]
    result = []
    for family, native_va, changed_slots in FAMILIES:
        native = [u32(native_va + i * 4) for i in range(53)]
        locator = u32(native_va - 4)
        descriptor = u32(locator + 12)
        name = pe.get_data(descriptor - base + 8, 128).split(b"\0", 1)[0].decode("ascii")
        if name != ".?AV" + family + "@@":
            raise ValueError(f"Native {family} RTTI fingerprint differs: {name}")
        needle = struct.pack("<IIII", *native[1:5])
        for section in pe.sections:
            if section.Name.rstrip(b"\0") != b".xdiff":
                continue
            data = section.get_data()
            for match in re.finditer(re.escape(needle), data):
                offset = match.start() - 4
                if offset < 4 or offset + 53 * 4 > len(data):
                    continue
                words = struct.unpack_from("<53I", data, offset)
                if any(words[i] != native[i] for i in range(53) if i not in changed_slots):
                    continue
                address = base + section.VirtualAddress + offset
                refs = []
                for ref in re.finditer(re.escape(struct.pack("<I", address)), raw):
                    if raw[ref.start() - 2:ref.start()] not in (b"\xc7\x06", b"\xc7\x07", b"\xc7\x00"):
                        continue
                    site = base + pe.get_rva_from_offset(ref.start() - 2)
                    snippet = pe.get_data(site - base, 160)
                    ids = [hex(struct.unpack("<I", m[1])[0]) for m in re.finditer(
                        rb"\xc7[\x46\x47]\x2c(....)", snippet, re.DOTALL)]
                    refs.append({"site": hex(site), "window_ids": ids})
                if not refs:
                    continue
                actual = u32(address - 4)
                result.append({"family": family, "vtable": hex(address),
                               "locator": hex(actual), "expected_locator": hex(locator),
                               "expected_descriptor": hex(descriptor), "type_name": name,
                               "locator_preserved": actual == locator, "construction_refs": refs})
    if not result:
        raise ValueError("No recognized custom top-level vtables found")
    return result


def execute_typeid_reads(pe, runtime, rows):
    export = next(s for s in runtime.DIRECTORY_ENTRY_EXPORT.symbols if s.name == b"__RTtypeid")
    # MOV EAX,[EAX]; MOV EAX,[EAX-4]; MOV EAX,[EAX+0xC]. These are the
    # original runtime's object -> vtable -> locator -> type descriptor reads.
    signature = bytes.fromhex("8b 00 8b 40 fc 8b 40 0c")
    body = runtime.get_data(export.address, 128)
    positions = [m.start() for m in re.finditer(re.escape(signature), body)]
    if len(positions) != 1:
        raise ValueError("Unsupported __RTtypeid pointer-load implementation")
    rb = runtime.OPTIONAL_HEADER.ImageBase
    start = rb + export.address + positions[0]
    for row in rows:
        machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
        for image in (pe, runtime):
            base = image.OPTIONAL_HEADER.ImageBase
            size = (image.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095
            machine.mem_map(base, size)
            machine.mem_write(base, image.get_memory_mapped_image())
        obj = 0x30000000
        machine.mem_map(obj, 4096)
        machine.mem_write(obj, struct.pack("<I", int(row["vtable"], 16)))
        machine.reg_write(x86.UC_X86_REG_EAX, obj)
        faults = []
        def invalid(m, access, address, size, value, context):
            faults.append({"instruction": hex(m.reg_read(x86.UC_X86_REG_EIP)),
                           "address": hex(address), "size": size, "access": access})
            return False
        machine.hook_add(uc.UC_HOOK_MEM_INVALID, invalid)
        try:
            machine.emu_start(start, start + len(signature), count=3)
        except uc.UcError:
            if not faults:
                raise
        actual = machine.reg_read(x86.UC_X86_REG_EAX)
        row["runtime_typeid_reads"] = {
            "entry": hex(start), "faults": faults, "descriptor": hex(actual),
            "passed": not faults and actual == int(row["expected_descriptor"], 16),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--expect-broken", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    raw = args.exe.read_bytes()
    pe = pefile.PE(data=raw)
    if pe.FILE_HEADER.Machine != 0x14C or pe.OPTIONAL_HEADER.ImageBase != 0x400000:
        raise ValueError("Expected profiled x86 client at image base 0x00400000")
    runtime = pefile.PE(str(args.runtime))
    if runtime.FILE_HEADER.Machine != 0x14C:
        raise ValueError("Expected an x86 VCRUNTIME140 DLL")
    rows = scan_clones(pe, raw)
    if args.expected_count is not None and len(rows) != args.expected_count:
        raise ValueError(f"Expected {args.expected_count} clones, found {len(rows)}")
    execute_typeid_reads(pe, runtime, rows)
    valid = sum(r["locator_preserved"] and r["runtime_typeid_reads"]["passed"] for r in rows)
    passed = valid == (0 if args.expect_broken else len(rows))
    report = {"exe": str(args.exe.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
              "runtime_sha256": hashlib.sha256(args.runtime.read_bytes()).hexdigest(),
              "expected_broken": args.expect_broken, "passed": passed,
              "clone_count": len(rows), "valid_count": valid, "clones": rows,
              "scope": "Exact native RTTI pointer-load instructions; no whole-process or live UI emulation"}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(f"{'PASS' if passed else 'FAIL'}: {valid}/{len(rows)} cloned top-level windows retain usable native RTTI"
          + (" (expected broken control)" if args.expect_broken else ""))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
