#!/usr/bin/env python3
"""Verify the 2025 Ragexe text-extent bridge cannot call an empty callback."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import capstone
import pefile


IMAGE_BASE = 0x00400000
EXTENT_CALL_SITE = 0x0054758D


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    args = parser.parse_args()

    data = args.exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=False)
    require(pe.OPTIONAL_HEADER.ImageBase == IMAGE_BASE, "unexpected image base")

    def offset(va: int) -> int:
        return pe.get_offset_from_rva(va - IMAGE_BASE)

    def direct_call(site: int) -> int:
        site_offset = offset(site)
        require(data[site_offset] == 0xE8, f"0x{site:08X} is not CALL rel32")
        return site + 5 + struct.unpack_from("<i", data, site_offset + 1)[0]

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def direct_calls(function: int, maximum: int) -> list[int]:
        result: list[int] = []
        start = offset(function)
        for instruction in md.disasm(data[start:start + maximum], function):
            if instruction.mnemonic == "ret":
                break
            if instruction.mnemonic == "call" and instruction.op_str.startswith("0x"):
                result.append(int(instruction.op_str, 16))
        return result

    extent_bridge = direct_call(EXTENT_CALL_SITE)
    extent_calls = direct_calls(extent_bridge, 0x300)
    require(extent_calls, "extent bridge has no direct findWide call")
    find_wide = extent_calls[0]
    find_calls = direct_calls(find_wide, 0x180)
    require(find_calls, "findWide has no direct lookup callback")
    lookup = find_calls[-1]
    lookup_bytes = data[offset(lookup):offset(lookup) + 16]
    require(any(lookup_bytes), f"lookup callback 0x{lookup:08X} is all zero")
    require(
        lookup_bytes.startswith(bytes.fromhex("55 8B EC"))
        or lookup_bytes.startswith(bytes.fromhex("33 C0 C2 08 00")),
        f"lookup callback 0x{lookup:08X} has an invalid prologue: {lookup_bytes.hex(' ')}",
    )

    print(
        "SHARED_TEXT_CALLBACKS_OK "
        f"extent=0x{extent_bridge:08X} findWide=0x{find_wide:08X} "
        f"lookup=0x{lookup:08X} prologue={lookup_bytes[:6].hex(' ')}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, pefile.PEFormatError, RuntimeError) as exc:
        print(f"SHARED_TEXT_CALLBACKS_FAIL {exc}")
        raise SystemExit(1)
