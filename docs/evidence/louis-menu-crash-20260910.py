"""Read-only, hash-bound reproduction of the louis.logs menu callback crash.

Run with the repository's .venv Python and the supplied EXE as the argument.
This emulates only the mouse-up fragment with a synthetic stack; it does not
launch Ragexe, connect to a server, or reproduce the original WARP GUI session.
"""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

import pefile
import unicorn as uc
from unicorn import x86_const as x86


EXPECTED_SHA256 = "f4e3b07b0b8a8d971c68e6fd2831633eec1488921a83037b9d425dd94a3cb2aa"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    args = parser.parse_args()
    data = args.exe.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError("This incident reproduction requires the original supplied EXE")
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase

    def read(va, size):
        return pe.get_data(va - base, size)

    def u32(va):
        return struct.unpack("<I", read(va, 4))[0]

    def relative(va):
        if read(va, 1) not in (b"\xe8", b"\xe9"):
            raise RuntimeError(f"Expected CALL/JMP rel32 at {va:#x}")
        return va + 5 + struct.unpack("<i", read(va + 1, 4))[0]

    requests = []
    signature = re.compile(
        rb"\xFF\x15....\x83\xC0.\xA3....\xC7\x05....\x01\x00\x00\x00\xC3",
        re.DOTALL,
    )
    for match in signature.finditer(data):
        requests.append({
            "va": base + pe.get_rva_from_offset(match.start()),
            "pending_va": struct.unpack_from("<I", match.group(), 16)[0],
        })

    bootstraps = {}
    for name, hook in (("Auto Hunt", 0x00C74FE1), ("AutoSupport", 0x00C74FCC)):
        target = relative(hook)
        code = read(target, 128)
        matches = [r for r in requests if b"\x83\x3D" + struct.pack("<I", r["pending_va"]) + b"\0" in code]
        if len(matches) != 1:
            raise RuntimeError(f"Cannot uniquely associate {name} bootstrap with pending state")
        bootstraps[name] = {"hook": hex(hook), "bootstrap": hex(target),
                            "current_request": hex(matches[0]["va"]),
                            "pending": hex(matches[0]["pending_va"])}

    mouse_up = u32(0x02A782A4 + 0x7C)
    dead_request = relative(mouse_up + 3)
    support_mouse_up = 0x02A78D60
    support_dead_request = relative(support_mouse_up + 3)
    item_cell = 0x02A7769C
    item_target = u32(item_cell)
    if read(dead_request, 32) != bytes(32) or read(support_dead_request, 32) != bytes(32):
        raise RuntimeError("Expected dead request entry bytes are not zero")

    emu = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    emu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    emu.mem_write(base, pe.get_memory_mapped_image())
    emu.mem_map(0x00100000, 0x10000)
    stack = 0x00108000
    # Native thiscall mouse-up arguments: return address, x, y.
    # x=5 is the logged EDI; y and caller frame are synthetic, not dump data.
    emu.mem_write(stack, struct.pack("<III", 0x00A46F4C, 5, 0))
    registers = {
        x86.UC_X86_REG_ESP: stack, x86.UC_X86_REG_EBP: stack + 0x100,
        x86.UC_X86_REG_EAX: 0x02A782A4, x86.UC_X86_REG_EBX: 0x0131F4E8,
        x86.UC_X86_REG_ECX: 0x42A40880, x86.UC_X86_REG_EDX: 0x010293DC,
        x86.UC_X86_REG_ESI: 0x42A40880, x86.UC_X86_REG_EDI: 5,
    }
    for register, value in registers.items():
        emu.reg_write(register, value)
    faults = []

    def on_invalid(machine, access, address, size, value, context):
        faults.append({"eip": hex(machine.reg_read(x86.UC_X86_REG_EIP)),
                       "address": hex(address), "size": size,
                       "edi": hex(machine.reg_read(x86.UC_X86_REG_EDI)),
                       "access": access})
        return False

    emu.hook_add(uc.UC_HOOK_MEM_INVALID, on_invalid)
    error = None
    try:
        emu.emu_start(mouse_up, 0x00A46F4C, count=1000)
    except uc.UcError as exc:
        error = str(exc)
    if len(faults) != 1 or faults[0]["eip"] != "0x2872163" or faults[0]["address"] != "0x5":
        raise RuntimeError(f"Did not reproduce the reported fault: {faults}, {error}")

    report = {
        "input_sha256": digest,
        "machine": hex(pe.FILE_HEADER.Machine),
        "timestamp": hex(pe.FILE_HEADER.TimeDateStamp),
        "image_base": hex(base),
        "linker": [pe.OPTIONAL_HEADER.MajorLinkerVersion, pe.OPTIONAL_HEADER.MinorLinkerVersion],
        "auto_hunt": {"vtable": "0x2a782a4", "mouse_up": hex(mouse_up),
                      "stale_request": hex(dead_request), "entry_bytes": read(dead_request, 32).hex()},
        "autosupport": {"mouse_up": hex(support_mouse_up),
                        "stale_request": hex(support_dead_request),
                        "entry_bytes": read(support_dead_request, 32).hex()},
        "item_collection": {"route_cell": hex(item_cell), "target": hex(item_target),
                            "visible": u32(item_cell + 4), "entry_bytes": read(item_target, 16).hex()},
        "current_bootstraps": bootstraps,
        "active_slash_dispatch": hex(relative(0x00D5CDF4)),
        "old_slash_dispatch_reached_by_fallthrough": "0x2872160",
        "emulation": {"scope": "mouse-up fragment, synthetic stack; no native services called",
                      "faults": faults, "error": error,
                      "vtable_first_dword_before": hex(u32(0x02A782A4)),
                      "vtable_first_dword_after": hex(struct.unpack("<I", emu.mem_read(0x02A782A4, 4))[0])},
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
