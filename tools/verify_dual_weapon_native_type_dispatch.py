"""Execute the profiled native alternate-attack selector and pair classifier.

The client PE is read-only. D72D30, D95500 and the caller's AL-to-action-base
conversion execute their original bytes. Only ItemToWeaponView and
GetRealWeaponId are stubbed; their complete fixture mappings are in the report.
This does not emulate a live actor, Lua VM, or resource loading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EFLAGS, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
JOBS = (12, 4013, 4035, 4059, 4065, 4101, 4254)
ITEM_VIEWS = {0: 0, 1238: 34, 13412: 45, 1504: 8}
REAL_VIEWS = {34: 1, 45: 2}
ALTERNATE_CLASSES = {16, 25, 26, 27, 28, 29, 30}
ITEM_CASES = ((13412, 1238, 1), (1238, 13412, 1), (1238, 1238, 1),
              (1504, 1238, 0), (1238, 1504, 0), (1504, 0, 0), (0, 1504, 0))
ANCHORS = {
    0xD72D30: '55 8b ec 83 ec 08',
    0xD72D9C: 'e8 5f 27 02 00',
    0xD72DC9: '83 fe 19',
    0xD95500: '55 8b ec 8b 55 08',
    0xD95738: '8b c6 5e 5d c2 08 00',
    0xC42CDF: 'e8 4c 00 13 00',
    0xC42CEE: '8d 14 d5 50 00 00 00',
}


class NativeSelector:
    def __init__(self, executable):
        raw = executable.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        pe = pefile.PE(data=raw)
        assert pe.FILE_HEADER.Machine == 0x14C
        assert pe.OPTIONAL_HEADER.ImageBase == 0x400000
        for address, expected in ANCHORS.items():
            value = bytes.fromhex(expected)
            assert pe.get_data(address - 0x400000, len(value)) == value, hex(address)
        self.extension_table = []
        for index, expected_address, expected_name in ((0, 0x1011578, b'act'), (1, 0x1011ED8, b'spr')):
            address = 0x1227310 + 4 * index
            value = pe.get_data(address - 0x400000, 4)
            pointer = struct.unpack('<I', value)[0]
            assert pointer == expected_address
            name = pe.get_string_at_rva(pointer - 0x400000)
            assert name == expected_name
            self.extension_table.append({'index': index, 'table_VA': hex(address),
                                         'bytes': value.hex(' '), 'string_VA': hex(pointer),
                                         'extension': name.decode('ascii')})
        self.region_hashes = {
            label: hashlib.sha256(pe.get_data(start - 0x400000, end - start)).hexdigest()
            for label, start, end in (
                ('selector_and_tables', 0xD72D30, 0xD73220),
                ('pair_mapper', 0xD95500, 0xD9573F),
                ('action_base_conversion', 0xC42CE4, 0xC42CF5),
            )
        }
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.u.mem_write(0x400000, pe.get_memory_mapped_image())
        self.u.mem_map(0x30000000, 0x20000)
        self.stack, self.stop = 0x30010000, 0x3001F000
        self.lookups = []
        self.pair_calls = []
        self.u.hook_add(UC_HOOK_CODE, self.hook)

    def read32(self, address):
        return struct.unpack('<I', self.u.mem_read(address, 4))[0]

    def hook(self, uc, address, size, unused):
        if address == 0xD95500:
            sp = uc.reg_read(UC_X86_REG_ESP)
            self.pair_calls.append([self.read32(sp + 4), self.read32(sp + 8)])
        if address not in (0xD8A1D0, 0xD5DDB0):
            return
        sp = uc.reg_read(UC_X86_REG_ESP)
        argument = self.read32(sp + 4)
        if address == 0xD8A1D0:
            assert argument in ITEM_VIEWS, ('unconfigured item lookup', argument)
            result = ITEM_VIEWS[argument]
        else:
            assert 0 <= argument <= 30 or argument in REAL_VIEWS, argument
            result = REAL_VIEWS.get(argument, argument)
        self.lookups.append({'function': hex(address), 'input': argument, 'output': result})
        uc.reg_write(UC_X86_REG_EAX, result)
        uc.reg_write(UC_X86_REG_ESP, sp + 8)
        uc.reg_write(UC_X86_REG_EIP, self.read32(sp))

    def invoke(self, job, gender, main, off):
        self.lookups, self.pair_calls = [], []
        self.u.mem_write(self.stack, struct.pack('<5I', self.stop, job, gender, main, off))
        self.u.reg_write(UC_X86_REG_ESP, self.stack)
        self.u.reg_write(UC_X86_REG_ECX, 0x15FA3C0)
        self.u.reg_write(UC_X86_REG_EFLAGS, 2)
        registers = (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)
        for i, register in enumerate(registers):
            self.u.reg_write(register, 0x777000 + i * 16)
        self.u.emu_start(0xD72D30, self.stop, count=10000)
        assert self.u.reg_read(UC_X86_REG_EIP) == self.stop
        assert self.u.reg_read(UC_X86_REG_ESP) == self.stack + 20
        for i, register in enumerate(registers):
            assert self.u.reg_read(register) == 0x777000 + i * 16
        result = self.u.reg_read(UC_X86_REG_EAX) & 255
        assert result in (0, 1)
        # Execute the real caller conversion, including TEST/SETNE and LEA.
        # Its three POPs consume synthetic saved registers, not an actor frame.
        self.u.reg_write(UC_X86_REG_EAX, result)
        self.u.reg_write(UC_X86_REG_ESP, self.stack)
        self.u.emu_start(0xC42CE4, 0xC42CF5, count=20)
        assert self.u.reg_read(UC_X86_REG_EIP) == 0xC42CF5
        base = self.u.reg_read(UC_X86_REG_EDX)
        assert base == 80 + 8 * result
        return {'job': job, 'gender': gender, 'main': main, 'off': off,
                'native_AL': result, 'action_base': base,
                'lookup_stubs': self.lookups, 'native_pair_mapper_calls': self.pair_calls}


def run(executable, output):
    native = NativeSelector(executable)
    classes, items = [], []
    for job in JOBS:
        for gender in (0, 1):
            for weapon in range(31):
                result = native.invoke(job, gender, weapon, 0)
                assert result['native_AL'] == (weapon in ALTERNATE_CLASSES), result
                classes.append(result)
            for main, off, expected in ITEM_CASES:
                result = native.invoke(job, gender, main, off)
                assert result['native_AL'] == expected, result
                items.append(result)
    report = {
        'schema': 'dual_weapon_native_type_dispatch/v1',
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'executable': str(executable.resolve()), 'exe_sha256': native.sha256,
        'native_region_sha256': native.region_hashes,
        'verified_byte_anchors': {hex(k): v for k, v in ANCHORS.items()},
        'verified_extension_table': native.extension_table,
        'fixture_item_to_view': ITEM_VIEWS, 'fixture_expansion_view_to_class': REAL_VIEWS,
        'fixture_GetRealWeaponId_default': 'identity for direct values 0 through 30',
        'class_case_count': len(classes), 'item_case_count': len(items),
        'all_cases_passed': True, 'native_selector_RET16_and_nonvolatile_registers_passed': True,
        'class_cases': classes, 'item_cases': items,
        'limits': [
            'ItemToWeaponView and GetRealWeaponId are explicit lookup stubs; the Lua VM and item database are not emulated.',
            'The actual selector, item-range pair mapper and caller AL-to-80/88 conversion execute original PE bytes.',
            'No actor resources, camera/body attachment, live frame pacing or visual acceptance are tested.',
            'No native hook or client asset is changed by this verifier.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('exe_sha256', 'class_case_count', 'item_case_count', 'all_cases_passed')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/evidence/dual-weapon-native-type-dispatch-20260905.json')
    args = parser.parse_args()
    run(args.exe, args.output)
