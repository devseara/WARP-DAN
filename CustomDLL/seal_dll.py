#!/usr/bin/env python3
"""Seal a BOH DLL by embedding its canonical SHA-256 digest.

The DLL must link CustomDLL/src/dll_integrity/dll_integrity.cpp. The digest slot
is zeroed while computing the canonical hash so the final sealed bytes can carry
the expected digest without changing the value being checked at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


MAGIC = b"BOH_DLL_INTEGRITY_V1"
MAGIC_FIELD_SIZE = 32
DIGEST_SIZE = 32
UNSEALED_DIGEST = bytes([0xA5]) * DIGEST_SIZE


def find_unique(haystack: bytes, needle: bytes) -> int:
    first = haystack.find(needle)
    if first < 0:
        raise SystemExit(f"seal marker not found: {needle.decode('ascii')}")

    second = haystack.find(needle, first + 1)
    if second >= 0:
        raise SystemExit(
            f"seal marker is ambiguous: offsets 0x{first:X} and 0x{second:X}"
        )

    return first


def canonical_digest(data: bytes, digest_offset: int) -> bytes:
    work = bytearray(data)
    work[digest_offset : digest_offset + DIGEST_SIZE] = b"\x00" * DIGEST_SIZE
    return hashlib.sha256(work).digest()


def locate_digest(data: bytes) -> int:
    magic_offset = find_unique(data, MAGIC)
    digest_offset = magic_offset + MAGIC_FIELD_SIZE
    if len(data[digest_offset : digest_offset + DIGEST_SIZE]) != DIGEST_SIZE:
        raise SystemExit("seal digest slot is truncated")
    return digest_offset


def seal(path: Path, manifest: Path | None) -> None:
    original = path.read_bytes()
    digest_offset = locate_digest(original)
    current_digest = original[digest_offset : digest_offset + DIGEST_SIZE]

    digest = canonical_digest(original, digest_offset)
    sealed = bytearray(original)
    sealed[digest_offset : digest_offset + DIGEST_SIZE] = digest
    path.write_bytes(sealed)

    sealed_sha256 = hashlib.sha256(sealed).hexdigest().upper()
    canonical_sha256 = digest.hex().upper()

    print(f"sealed: {path}")
    print(f"canonical_sha256_excluding_seal={canonical_sha256}")
    print(f"sealed_sha256={sealed_sha256}")
    print(f"seal_offset=0x{digest_offset:X}")

    if current_digest != UNSEALED_DIGEST and current_digest != digest:
        print("warning: previous seal digest was neither unsealed nor current")

    if manifest is not None:
        manifest.write_text(
            "\n".join(
                [
                    f"file={path.name}",
                    f"canonical_sha256_excluding_seal={canonical_sha256}",
                    f"sealed_sha256={sealed_sha256}",
                    f"seal_offset=0x{digest_offset:X}",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def verify(path: Path) -> None:
    data = path.read_bytes()
    digest_offset = locate_digest(data)
    embedded_digest = data[digest_offset : digest_offset + DIGEST_SIZE]
    digest = canonical_digest(data, digest_offset)

    print(f"verified_file={path}")
    print(f"canonical_sha256_excluding_seal={digest.hex().upper()}")
    print(f"embedded_sha256={embedded_digest.hex().upper()}")
    print(f"sealed_sha256={hashlib.sha256(data).hexdigest().upper()}")
    print(f"seal_offset=0x{digest_offset:X}")

    if embedded_digest != digest:
        raise SystemExit("DLL seal verification failed")

    print("DLL seal verification passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dll", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        verify(args.dll)
    else:
        seal(args.dll, args.manifest)


if __name__ == "__main__":
    main()
