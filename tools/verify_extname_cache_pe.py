"""Read-only regression check for the exact 128-byte-name client PE.

Requires pefile, capstone, unicorn. No client process is launched or modified.
Example: python verify_extname_cache_pe.py client.exe --deps ../diagnostic-deps
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--deps", type=Path)
    args = parser.parse_args()
    if args.deps:
        sys.path.insert(0, str(args.deps.resolve()))
    import capstone
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP

    pe = pefile.PE(str(args.exe))
    data = bytes(pe.__data__)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    cs.detail = True
    failed = []

    def check(label, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'} {label}: {detail}")
        if not ok:
            failed.append(label)

    def va(offset):
        return image_base + pe.get_rva_from_offset(offset)

    def decode(offset, size=32):
        return list(cs.disasm(data[offset:offset + size], va(offset)))

    print(f"PE {args.exe}\nSHA256 {hashlib.sha256(data).hexdigest()}")
    # Locate the key/value copy tail, independent of code-cave relocation.
    store_matches = list(re.finditer(rb"\x68\x00\x03\x00\x00\x53\x8d(?:\x47\x90|\x87\x90\x00\x00\x00)\x50", data))
    if len(store_matches) != 1:
        raise RuntimeError(f"Expected one MapPut value-copy tail; found {len(store_matches)}")
    store_offset = store_matches[0].start()
    value_lea = decode(store_offset)[2]
    check("MapPut value uses +144", value_lea.operands[1].mem.disp == 144,
          f"{value_lea.address:#x}: {value_lea.mnemonic} {value_lea.op_str}")

    render_matches = list(re.finditer(rb"\x6a\xff\x8d(?:\x46\x90|\x86\x90\x00\x00\x00)\x50\x6a\x00\x68\xe9\xfd\x00\x00", data))
    check("draw/extent value references found", len(render_matches) >= 2, str(len(render_matches)))
    for match in render_matches:
        insn = decode(match.start())[1]
        check(f"render value {insn.address:#x}", insn.operands[1].mem.disp == 144,
              f"{insn.mnemonic} {insn.op_str}")

    prologue = bytes.fromhex("55 8b ec 83 ec 0c 53 56 57 8b 75 08 8b 5d 0c")
    put_offset = data.rfind(prologue, max(0, store_offset - 512), store_offset)
    if put_offset < 0:
        raise RuntimeError("MapPut entry not found")
    put_va = va(put_offset)
    prefix = decode(put_offset, store_offset - put_offset)
    table_va = next(i.operands[1].imm for i in prefix
                    if i.mnemonic == "mov" and i.op_str.startswith("edi, 0x"))
    print(f"MapPut {put_va:#x}; table {table_va:#x}")

    # The V3 final title put must jump over V4 parsing. Otherwise a 777-byte
    # legacy record is parsed again using the incompatible 657-byte offsets.
    final_v3 = list(re.finditer(bytes.fromhex("8d 83 ec 02 00 00 50 e8") + rb"....", data, re.DOTALL))
    final_v3 = [m for m in final_v3 if
                va(m.start() + 12) + struct.unpack_from("<i", data, m.start() + 8)[0] == put_va]
    check("V3 title mapping located", len(final_v3) == 1, str(len(final_v3)))
    if len(final_v3) == 1:
        next_insn = decode(final_v3[0].end())[0]
        check("V3 skips V4 parser", next_insn.mnemonic == "jmp",
              f"{next_insn.address:#x}: {next_insn.mnemonic} {next_insn.op_str}")

    def fnv(value):
        result = 0x811c9dc5
        for byte in value:
            result = ((result ^ byte) * 0x01000193) & 0xffffffff
        return result or 1

    # Deliberately select bucket zero: a negative displacement writes outside
    # the entire allocation, which a nearby-record-only test could miss.
    key = next(f"guard{i}".encode() for i in range(100000)
               if fnv(f"guard{i}".encode()) & 2047 == 0)
    stack_base, heap_base, stop = 0x60000000, 0x61000000, 0x62000000
    table_size, entry_size = 2048 * 912, 912
    for label, key_data, value_data, key_arg, value_arg in [
        ("bucket-zero short value", key, b"Zombie", True, True),
        ("127-byte key and 511-byte composed value", b"K" * 127, b"V" * 511, True, True),
        ("empty-key guard", b"", b"value", True, True),
        ("empty-value guard", key, b"", True, True),
        ("null-key guard", key, b"value", False, True),
        ("null-value guard", key, b"value", True, False),
    ]:
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(image_base, (len(image) + 4095) & ~4095)
        uc.mem_write(image_base, image)
        uc.mem_map(stack_base, 0x10000)
        uc.mem_map(heap_base, 0x10000)
        uc.mem_map(stop, 0x1000)
        uc.mem_write(table_va - 128, b"\xa5" * 128)
        uc.mem_write(table_va, b"\x00" * table_size)
        uc.mem_write(heap_base, key_data + b"\0")
        uc.mem_write(heap_base + 1024, value_data + b"\0")
        stack = stack_base + 0xf000
        uc.mem_write(stack, struct.pack("<6I", stop, heap_base if key_arg else 0,
                                       heap_base + 1024 if value_arg else 0, 2, 3, 0x123456))
        uc.reg_write(UC_X86_REG_ESP, stack)
        writes = []

        def capture(machine, access, address, size, value, user_data):
            if table_va - 128 <= address < table_va + table_size:
                writes.append((address, size))

        uc.hook_add(UC_HOOK_MEM_WRITE, capture)
        uc.emu_start(put_va, stop, count=100000)
        if not key_arg or not value_arg or not key_data or not value_data:
            check(label, not writes, f"cache writes={len(writes)}")
        else:
            bucket = table_va + (fnv(key_data) & 2047) * entry_size
            actual_key = bytes(uc.mem_read(bucket + 16, len(key_data) + 1))
            actual_value = bytes(uc.mem_read(bucket + 144, len(value_data) + 1))
            inside = all(bucket <= address and address + size <= bucket + entry_size
                         for address, size in writes)
            guard_ok = bytes(uc.mem_read(table_va - 128, 128)) == b"\xa5" * 128
            ok = inside and guard_ok and actual_key == key_data + b"\0" and actual_value == value_data + b"\0"
            check(label, ok, f"writes confined={inside}; leading guard={guard_ok}; key intact={actual_key == key_data + bytes([0])}; value correct={actual_value == value_data + bytes([0])}")
    store_signature = bytes.fromhex("55 8b ec 53 56 57 8b 5d 08 8b 75 0c 8b 7d 10 0f b7 43 02")
    packet_stores = list(re.finditer(re.escape(store_signature), data))
    if len(packet_stores) != 1:
        raise RuntimeError(f"Expected one PacketStore, found {len(packet_stores)}")
    packet_store_va = va(packet_stores[0].start())
    for version in (4, 3):
        packet = bytearray(657 if version == 4 else 777)
        struct.pack_into("<HHII", packet, 0, 0x0bb7, len(packet), 0x4558544e, 123)
        fields = [bytes([letter]) * 127 for letter in b"NPGOT"]
        offsets = [12, 140, 268, 396, 524] if version == 4 else [36, 164, 292, 420, 548]
        for offset, value in zip(offsets, fields):
            packet[offset:offset + len(value)] = value
        if version == 3:
            short_values = [b"wire-name", b"wire-party", b"wire-guild", b"wire-position", b"wire-title"]
            for offset, value in zip([12, 676, 700, 724, 748], short_values):
                packet[offset:offset + len(value)] = value
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(image_base, (len(image) + 4095) & ~4095)
        uc.mem_write(image_base, image)
        uc.mem_map(stack_base, 0x10000)
        uc.mem_map(heap_base, 0x10000)
        uc.mem_map(stop, 0x1000)
        uc.mem_write(table_va - 128, b"\xa5" * 128)
        uc.mem_write(table_va, b"\0" * table_size)
        uc.mem_write(heap_base, bytes(packet))
        stack = stack_base + 0xf000
        uc.mem_write(stack, struct.pack("<4I", stop, heap_base, 0, 0x123456))
        uc.reg_write(UC_X86_REG_ESP, stack)
        calls = []

        def record_put(machine, address, size, user_data):
            if address == put_va:
                esp = machine.reg_read(UC_X86_REG_ESP)
                key_ptr, value_ptr = struct.unpack("<II", machine.mem_read(esp + 4, 8))
                calls.append((bytes(machine.mem_read(key_ptr, 768)).split(b"\0", 1)[0],
                              bytes(machine.mem_read(value_ptr, 768)).split(b"\0", 1)[0]))

        uc.hook_add(UC_HOOK_CODE, record_put, begin=put_va, end=put_va)
        uc.emu_start(packet_store_va, stop, count=300000)
        if version == 4:
            name, party, guild, position, title = fields
            composed = title + b" " + name + b" [" + party + b"] {" + guild + b"} (" + position + b")"
            expected = [(name, composed)] + [(field, field) for field in fields[1:]]
            check("V4 five exact full-name records", calls == expected,
                  f"calls={len(calls)}; composed bytes={len(composed)}")
            intact = True
            for key_bytes, value_bytes in expected:
                bucket = table_va + (fnv(key_bytes) & 2047) * entry_size
                # These fixtures use distinct buckets, so no probe adjustment is needed.
                intact = intact and bytes(uc.mem_read(bucket + 16, len(key_bytes) + 1)) == key_bytes + b"\0"
                intact = intact and bytes(uc.mem_read(bucket + 144, len(value_bytes) + 1)) == value_bytes + b"\0"
            check("V4 packet cache keys and values intact", intact,
                  "127-byte canonical name and 645-byte composition")
        else:
            expected_keys = [fields[0], short_values[0]] + short_values[1:]
            check("V3 packet never parsed as V4", [item[0] for item in calls] == expected_keys,
                  f"put calls={len(calls)}; expected={len(expected_keys)}")
    print(f"RESULT {'FAIL' if failed else 'PASS'} ({len(failed)} failed checks)")
    return bool(failed)


if __name__ == "__main__":
    sys.exit(main())
