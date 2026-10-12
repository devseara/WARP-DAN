#!/usr/bin/env python3
"""Verify the optional native Item Collection menu child in a patched PE."""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path

import pefile


EXPECTED_PATHS = (
    b"bt_itemcollection_poring_normal.bmp\0",
    b"bt_itemcollection_poring_mouseon.bmp\0",
    b"bt_itemcollection_poring_pressed.bmp\0",
    b"bt_itemcollection_poring_old_normal.bmp\0",
    b"bt_itemcollection_poring_old_mouseon.bmp\0",
    b"bt_itemcollection_poring_old_pressed.bmp\0",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_hover(pe, entry: int) -> None:
    """Execute actual PE code; native coordinate conversion and renderer are mocked."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
    )
    import itertools

    base = pe.OPTIONAL_HEADER.ImageBase
    mapped = pe.get_memory_mapped_image()
    # Both themes, arbitrary window positions and all native visibility guards.
    cases = itertools.product(((45, 41), (32, 34)), ((20, 100), (620, 400)), (0, 1), (0, 1))
    for (width, height), (screen_x, screen_y), visible, manager in cases:
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(base, (len(mapped) + 4095) & ~4095)
        u.mem_write(base, mapped)
        u.mem_map(0x60000000, 0x10000)
        button, stack, stop = 0x60000100, 0x60008000, 0x60000000
        def read32(address):
            return struct.unpack('<I', u.mem_read(address, 4))[0]
        def write32(address, value):
            u.mem_write(address, struct.pack('<I', value & 0xFFFFFFFF))
        for offset, value in ((0x14, width), (0x18, height), (0x28, visible)):
            write32(button + offset, value)
        write32(0x0121333C, 0x60000300 if manager else 0)
        write32(stack, stop)
        write32(stack + 4, 1234)  # dispatcher coordinates must not own the anchor
        write32(stack + 8, 5678)
        u.reg_write(UC_X86_REG_ESP, stack)
        u.reg_write(UC_X86_REG_ECX, button)
        preserved = {UC_X86_REG_EBX: 0x1357, UC_X86_REG_ESI: 0x2468,
                     UC_X86_REG_EDI: 0x369A, UC_X86_REG_EBP: 0xABCD}
        for reg, value in preserved.items():
            u.reg_write(reg, value)
        u.mem_write(0x00A1EF70, bytes.fromhex('C2 08 00'))
        u.mem_write(0x00A753D0, bytes.fromhex('C2 18 00'))
        calls = []
        def step(uc, address, size, context):
            sp = uc.reg_read(UC_X86_REG_ESP)
            if address == stop:
                uc.emu_stop()
            elif address == 0x00A1EF70:
                require(uc.reg_read(UC_X86_REG_ECX) == button, 'ClientToScreen lost native child receiver')
                px, py = read32(sp + 4), read32(sp + 8)
                require((read32(px), read32(py)) == (0, 0xFFFFFFEC), 'tooltip is not anchored at child (0,-20)')
                write32(px, screen_x)
                write32(py, screen_y - 20)
            elif address == 0x00A753D0:
                args = [read32(sp + i * 4) for i in range(1, 7)]
                require(bytes(uc.mem_read(args[0], 16)) == b'Item Collection\0', 'wrong native hover label')
                require(args[1:] == [screen_x, screen_y - 20, 0xFFFFFFFF, 0, 1], 'native tooltip ABI/anchor mismatch')
                calls.append(args)
                # Native callees may clobber volatile registers.
                uc.reg_write(UC_X86_REG_EAX, 0xDEAD)
                uc.reg_write(UC_X86_REG_ECX, 0xBEEF)
        u.hook_add(UC_HOOK_CODE, step)
        u.emu_start(entry, 0, count=1000)
        require(len(calls) == int(bool(visible and manager)), 'hidden/null-manager tooltip guard failed')
        require(u.reg_read(UC_X86_REG_ESP) == stack + 12, 'hover RET 8 stack mismatch')
        for reg, value in preserved.items():
            require(u.reg_read(reg) == value, 'hover clobbered nonvolatile register')
    print(f'ITEM_COLLECTION_HOVER_OK entry=0x{entry:08X} cases=16 nativeAnchor=(0,-20)')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--allow-unregistered", action="store_true")
    parser.add_argument("--check-hover", action="store_true",
                        help="execute the emitted tooltip bridge with mocked native boundaries")
    args = parser.parse_args()

    data = args.exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=False)
    base = pe.OPTIONAL_HEADER.ImageBase
    require(base == 0x00400000, "unexpected image base")

    for path in EXPECTED_PATHS:
        require(path in data, f"missing menu resource path: {path[:-1].decode()}")

    # Newer menus contain several optional routes. Resolve this child by its
    # unique native window ID, then read its vtable's mouse-up slot.
    constructors = list(re.finditer(
        rb"\x81\x3F(....)\x0F\x85....\x81\x7F\x2C\xF4\x03\x00\x00",
        data, re.DOTALL,
    ))
    require(len(constructors) == 1,
            f"expected one Item Collection child constructor, found {len(constructors)}")
    vtable = struct.unpack("<I", constructors[0].group(1))[0]
    vtable_offset = pe.get_offset_from_rva(vtable - base)
    mouse_up = struct.unpack_from("<I", data, vtable_offset + 31 * 4)[0]
    mouse_up_offset = pe.get_offset_from_rva(mouse_up - base)
    require(data[mouse_up_offset:mouse_up_offset + 3] == bytes.fromhex("55 8B EC"),
            "Item Collection mouse-up frame prologue mismatch")
    match = re.compile(rb"\xA1....\x85\xC0\x0F\x84....\xFF\xD0", re.DOTALL).match(data, mouse_up_offset + 3)
    require(match is not None, "Item Collection mouse-up is not the optional native route")
    request_cell = struct.unpack_from("<I", data, match.start() + 1)[0]
    cell_offset = pe.get_offset_from_rva(request_cell - base)
    request_target = struct.unpack_from("<I", data, cell_offset)[0]
    if request_target == 0:
        require(args.allow_unregistered, "Item Collection request route is unregistered")
    else:
        target_offset = pe.get_offset_from_rva(request_target - base)
        require(
            data[target_offset:target_offset + 2] == bytes.fromhex("9C 60"),
            f"request route 0x{request_target:08X} is not the PUSHFD/PUSHAD toggle",
        )

    # Ensure code contains the unique custom child ID 0x3F4 and does not reuse
    # Item Collection's top-level frame ID 0x3F3 or Auto Hunt child 0x3F2.
    child_id = struct.pack("<I", 0x3F4)
    require(data.count(child_id) >= 2, "Item Collection child ID 0x3F4 is absent")

    if args.check_hover:
        hover = struct.unpack_from("<I", data, vtable_offset + 28 * 4)[0]
        verify_hover(pe, hover)

    print(
        "ITEM_COLLECTION_MENU_OK "
        f"requestCell=0x{request_cell:08X} toggle=0x{request_target:08X} "
        "states=6 childId=0x3F4"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, pefile.PEFormatError, RuntimeError) as exc:
        print(f"ITEM_COLLECTION_MENU_FAIL {exc}")
        raise SystemExit(1)
