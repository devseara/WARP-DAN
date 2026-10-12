#!/usr/bin/env python3
"""Repair final EXE bridge operands after WARP relocates custom imports.

WARP's CustomDLL patch can move the generated import table during final output
post-processing. Static bridge patches that embed CALL/JMP [custom_iat] operands
must therefore be corrected against the final PE import table on disk.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path

import pefile


X86_ABS_INDIRECT_OPS = {b"\xff\x15", b"\xff\x25"}  # CALL/JMP dword ptr [imm32]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch stale x86 CALL/JMP [custom DLL IAT] operands in a final PE."
    )
    parser.add_argument("exe", type=Path, help="Patched 32-bit client EXE to repair")
    parser.add_argument(
        "--dll",
        required=True,
        help="Custom DLL import descriptor to inspect or repair",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes in place. Without this flag, only reports matches.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create <exe>.bridge-iat.bak before writing.",
    )
    return parser.parse_args()


class BridgeIatFixer:
    def __init__(self, path: Path, dll_name: str) -> None:
        self.path = path
        self.dll_name = dll_name.lower()
        self.data = bytearray(path.read_bytes())
        self.pe = pefile.PE(data=bytes(self.data), fast_load=False)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.size = self.pe.OPTIONAL_HEADER.SizeOfImage
        self.final_iat = self._collect_final_iat()

    def _collect_final_iat(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for desc in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", []):
            dll = desc.dll.decode("ascii", errors="replace").lower()
            if dll != self.dll_name:
                continue
            for imp in desc.imports:
                if imp.name:
                    result[imp.name.decode("ascii", errors="replace")] = imp.address
        if not result:
            raise SystemExit(f"import descriptor not found for {self.dll_name}")
        return result

    def va_to_offset(self, va: int) -> int | None:
        if not (self.base <= va < self.base + self.size):
            return None
        try:
            return self.pe.get_offset_from_rva(va - self.base)
        except pefile.PEFormatError:
            return None

    def offset_to_va(self, offset: int) -> int:
        return self.base + self.pe.get_rva_from_offset(offset)

    def import_name_at_thunk_slot(self, slot_va: int) -> str | None:
        slot_off = self.va_to_offset(slot_va)
        if slot_off is None or slot_off + 4 > len(self.data):
            return None

        name_rva = struct.unpack_from("<I", self.data, slot_off)[0]
        if name_rva & 0x80000000:
            return None

        name_off = self.va_to_offset(self.base + name_rva)
        if name_off is None or name_off + 3 > len(self.data):
            return None

        end = self.data.find(b"\x00", name_off + 2)
        if end < 0 or end - (name_off + 2) > 128:
            return None

        try:
            name = self.data[name_off + 2 : end].decode("ascii")
        except UnicodeDecodeError:
            return None

        return name if name in self.final_iat else None

    def find_fixes(self) -> list[tuple[int, int, bytes, int, str, int]]:
        fixes: list[tuple[int, int, bytes, int, str, int]] = []
        for off in range(2, len(self.data) - 4):
            op = bytes(self.data[off - 2 : off])
            if op not in X86_ABS_INDIRECT_OPS:
                continue

            slot_va = struct.unpack_from("<I", self.data, off)[0]
            name = self.import_name_at_thunk_slot(slot_va)
            if not name:
                continue

            wanted = self.final_iat[name]
            if slot_va != wanted:
                fixes.append((off, self.offset_to_va(off), op, slot_va, name, wanted))
        return fixes

    def apply(self, fixes: list[tuple[int, int, bytes, int, str, int]]) -> None:
        for off, _va, _op, _old, _name, wanted in fixes:
            struct.pack_into("<I", self.data, off, wanted)
        self.path.write_bytes(self.data)


def main() -> int:
    args = parse_args()
    fixer = BridgeIatFixer(args.exe, args.dll)
    fixes = fixer.find_fixes()

    print(f"{args.exe}")
    print(f"custom imports: {len(fixer.final_iat)} from {args.dll}")
    print(f"stale bridge operands: {len(fixes)}")
    for _off, va, op, old, name, wanted in fixes:
        print(f"  0x{va:08X}: {op.hex(' ')} 0x{old:08X} -> {name} 0x{wanted:08X}")

    if not args.write or not fixes:
        return 0

    if not args.no_backup:
        backup = args.exe.with_name(args.exe.name + ".bridge-iat.bak")
        if not backup.exists():
            shutil.copy2(args.exe, backup)
            print(f"backup: {backup}")

    fixer.apply(fixes)
    print("patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
