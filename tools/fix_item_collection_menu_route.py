#!/usr/bin/env python3
"""Repair a zeroed RO Global Item Collection menu route in an already patched PE."""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
from pathlib import Path

import pefile


OPTIONAL_MOUSE_UP = re.compile(
    rb"\xA1(....)\x85\xC0\x0F\x84....\xFF\xD0"
    rb"\x33\xC0\x8B\xE5\x5D\xC2\x08\x00",
    re.DOTALL,
)

ITEM_COLLECTION_TOGGLE = re.compile(
    rb"\x9C\x60\x6A\x00\x6A\x00\x6A\x00\x6A\x01\xE8...."
    rb"\xC7\x05....\x00\x00\x00\x00"
    rb"\xC7\x05....\x00\x00\x00\x00",
    re.DOTALL,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source = args.exe.resolve()
    output = (args.output or source.with_name(
        source.stem + "_itemcollection_route_fixed" + source.suffix
    )).resolve()
    require(source != output, "output must not overwrite the source EXE")

    data = bytearray(source.read_bytes())
    pe = pefile.PE(data=bytes(data), fast_load=False)
    base = pe.OPTIONAL_HEADER.ImageBase
    require(base == 0x00400000, "unexpected image base")

    mouse_ups = list(OPTIONAL_MOUSE_UP.finditer(data))
    toggles = list(ITEM_COLLECTION_TOGGLE.finditer(data))
    require(len(mouse_ups) == 1,
            f"expected one optional Item Collection mouse-up, found {len(mouse_ups)}")
    require(len(toggles) == 1,
            f"expected one Item Collection toggle, found {len(toggles)}")

    request_cell_va = struct.unpack("<I", mouse_ups[0].group(1))[0]
    request_cell_offset = pe.get_offset_from_rva(request_cell_va - base)
    toggle_va = base + pe.get_rva_from_offset(toggles[0].start())
    current = struct.unpack_from("<I", data, request_cell_offset)[0]
    require(current in (0, toggle_va),
            f"route already targets unexpected address 0x{current:08X}")
    require(data[toggles[0].start():toggles[0].start() + 2] == b"\x9C\x60",
            "toggle does not begin with PUSHFD/PUSHAD")

    struct.pack_into("<I", data, request_cell_offset, toggle_va)
    struct.pack_into("<I", data, request_cell_offset + 4, 1)

    patched = pefile.PE(data=bytes(data), fast_load=False)
    patched.OPTIONAL_HEADER.CheckSum = patched.generate_checksum()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched.write())

    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    print(
        "ITEM_COLLECTION_ROUTE_FIXED "
        f"cell=0x{request_cell_va:08X} toggle=0x{toggle_va:08X} "
        f"sha256={digest} output={output}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, pefile.PEFormatError, RuntimeError, ValueError) as exc:
        print(f"ITEM_COLLECTION_ROUTE_FIX_FAIL {exc}")
        raise SystemExit(1)
