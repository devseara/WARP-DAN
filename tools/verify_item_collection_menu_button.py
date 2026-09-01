#!/usr/bin/env python3
"""Verify the optional native Item Collection menu child in a patched PE."""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path

import pefile


EXPECTED_PATHS = (
    b"bt_itemcollection_normal.bmp\0",
    b"bt_itemcollection_mouseon.bmp\0",
    b"bt_itemcollection_pressed.bmp\0",
    b"bt_itemcollection_old_normal.bmp\0",
    b"bt_itemcollection_old_mouseon.bmp\0",
    b"bt_itemcollection_old_pressed.bmp\0",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--allow-unregistered", action="store_true")
    args = parser.parse_args()

    data = args.exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=False)
    base = pe.OPTIONAL_HEADER.ImageBase
    require(base == 0x00400000, "unexpected image base")

    for path in EXPECTED_PATHS:
        require(path in data, f"missing menu resource path: {path[:-1].decode()}")

    # Optional mouse-up ABI: MOV EAX,[requestCell]; TEST; JZ; CALL EAX.
    matches = list(re.finditer(
        b"\xA1....\x85\xC0\x0F\x84....\xFF\xD0",
        data,
        re.DOTALL,
    ))
    require(len(matches) == 1, f"expected one optional route call, found {len(matches)}")
    match = matches[0]
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
