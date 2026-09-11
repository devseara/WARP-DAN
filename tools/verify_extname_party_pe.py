#!/usr/bin/env python3
"""Emulate the final 2025-07-16 PE party bridges and native consumers offline.

Requires pefile and unicorn. The PE is read only. Native packet/consumer code
runs unchanged; external string allocation, UI work, and deallocation are
stubbed to inspect complete names and preserve deterministic test ownership.
"""
import argparse
import struct
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pe', required=True, help='Final WARP-patched 2025-07-16 client EXE')
parser.add_argument('--deps', help='Optional directory containing pefile/unicorn packages')
args = parser.parse_args()
if args.deps:
    sys.path.insert(0, args.deps)
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

pe = pefile.PE(args.pe)
imagebase = pe.OPTIONAL_HEADER.ImageBase
assert imagebase == 0x400000, 'Expected profiled 2025-07-16 image base'
BUFFER = 0x15E8198
RETURN = 0xC9E1DD
STUB = 0x2100F000
STOP = 0x2100E000


def dwords(u, addr, count):
    return struct.unpack('<' + 'I' * count, bytes(u.mem_read(addr, 4 * count)))


def make():
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    u.mem_map(0, 0x1000)
    image_size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xfff) & ~0xfff
    assert imagebase + image_size <= 0x21000000, 'Test scratch overlaps PE'
    u.mem_map(imagebase, image_size)
    u.mem_write(imagebase, pe.get_memory_mapped_image())
    u.mem_map(0x21000000, 0x10000)
    u.mem_map(0x3000000, 0x20000)
    u.mem_map(0x4000000, 0x10000)
    u.reg_write(UC_X86_REG_ESP, 0x301F000)
    u.reg_write(UC_X86_REG_EBP, 0x301F800)
    u.reg_write(UC_X86_REG_EDI, 0x400E000)
    u.mem_write(0x15FB9A4, struct.pack('<I', 101))
    u.mem_write(0xFC1B1C, struct.pack('<I', STUB))
    return u


class NativeCalls:
    def __init__(self, u):
        self.u = u
        self.next = 0x4001000
        self.assigned = []
        self.members = []

    def ret(self, argc=0, value=0):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        target = dwords(self.u, sp, 1)[0]
        self.u.reg_write(UC_X86_REG_ESP, sp + 4 + argc * 4)
        self.u.reg_write(UC_X86_REG_EAX, value)
        self.u.reg_write(UC_X86_REG_EIP, target)

    def string(self, obj):
        length, capacity = dwords(self.u, obj + 16, 2)
        ptr = dwords(self.u, obj, 1)[0] if capacity >= 16 else obj
        return bytes(self.u.mem_read(ptr, length))

    def hook(self, u, pc, size, _):
        if pc in (RETURN, STOP):
            u.emu_stop()
            return
        sp = u.reg_read(UC_X86_REG_ESP)
        if pc == 0x4F1940:  # Native std::string::assign(ptr, count).
            ptr, length = dwords(u, sp + 4, 2)
            obj = u.reg_read(UC_X86_REG_ECX)
            assert length <= 127, 'Unexpected truncated/overread string span'
            value = bytes(u.mem_read(ptr, length))
            self.assigned.append((ptr, length, value))
            dst = self.next
            self.next += 0x200
            u.mem_write(dst, value + b'\0')
            u.mem_write(obj, struct.pack('<I', dst) + b'\0' * 12 + struct.pack('<II', length, max(length, 16)))
            self.ret(2, obj)
            return
        if pc in (STUB, 0xE07D4B):  # cdecl memcpy.
            dst, src, length = dwords(u, sp + 4, 3)
            u.mem_write(dst, bytes(u.mem_read(src, length)))
            self.ret(0, dst)
            return
        if pc == 0xD54AE0:  # Final native party member insertion.
            member = dwords(u, sp + 4, 1)[0]
            self.members.append({
                'aid': dwords(u, member + 4, 1)[0],
                'gid': dwords(u, member + 8, 1)[0],
                'name': self.string(member + 12),
                'map': self.string(member + 36),
            })
            self.ret(1)
            return
        # These callees do UI/update work outside the packet-layout contract.
        stubs = {0xD56530: 0, 0xA85BE0: 1, 0xD65E40: 0, 0xA339C0: 0,
                 0xD76660: 0, 0xDBBBD4: 0, 0xDBBC7F: 0,
                 0xD5CF50: 0, 0xA480F0: 1, 0xCAE3A0: 2}
        if pc in stubs:
            self.ret(stubs[pc])


def run_packet(u, opcode):
    native = NativeCalls(u)
    u.hook_add(UC_HOOK_CODE, native.hook)
    entry = dwords(u, 0xCAA2E0 + (opcode - 0x73) * 4, 1)[0]
    esp = u.reg_read(UC_X86_REG_ESP)
    u.emu_start(entry, 0, count=100000)
    assert u.reg_read(UC_X86_REG_EIP) == RETURN, 'Handler failed to finish'
    assert u.reg_read(UC_X86_REG_ESP) == esp, 'Unbalanced handler stack'
    return native


def test_member():
    u = make()
    packet = bytearray(297)
    struct.pack_into('<HIIIhhhhB', packet, 0, 0xAE4, 101, 202, 0, 11, 99, 10, 20, 0)
    party, name, map_name = b'P' * 127, b'N' * 127, b'prontera.gat'
    packet[23:151] = party + b'\0'
    packet[151:279] = name + b'\0'
    packet[279:279 + len(map_name)] = map_name
    packet[295:297] = b'\x01\x01'
    u.mem_write(BUFFER, bytes(packet))
    native = run_packet(u, 0xAE4)
    assert native.members == [{'aid': 101, 'gid': 202, 'name': name, 'map': map_name}]
    assert (BUFFER + 151, 127, name) in native.assigned
    assert (BUFFER + 23, 127, party) in native.assigned
    print('PASS AE4 actual native consumer: full 127-byte player/party, map, IDs, stack')


def test_list(count, malformed=0, header_length=None):
    u = make()
    packet = bytearray(132 + 158 * count + malformed)
    struct.pack_into('<HH', packet, 0, 0xAE5, len(packet) if header_length is None else header_length)
    party = b'G' * 127
    packet[4:132] = party + b'\0'
    expected = []
    for i in range(count):
        start = 132 + i * 158
        name, map_name = bytes([65 + i]) * 127, b'prontera.gat'
        struct.pack_into('<II', packet, start, 101 + i, 202 + i)
        packet[start + 8:start + 136] = name + b'\0'
        packet[start + 136:start + 136 + len(map_name)] = map_name
        struct.pack_into('<BBhh', packet, start + 152, i, 0, 11 + i, 99 - i)
        expected.append({'aid': 101 + i, 'gid': 202 + i, 'name': name, 'map': map_name})
    original = bytes(packet)
    u.mem_write(BUFFER, original)
    native = run_packet(u, 0xAE5)
    rejected = malformed or header_length is not None
    assert native.members == ([] if rejected else expected)
    assert bytes(u.mem_read(BUFFER, len(packet))) == original, 'Consumer changed borrowed packet'
    if not rejected:
        assert (BUFFER + 4, 127, party) in native.assigned
    else:
        assert not native.assigned, 'Malformed packet reached native name consumer'
    print(f'PASS AE5 actual native consumer: count={count}, rejected={bool(rejected)}, full names, borrowed view, stack')


def test_receive(available, packet_id=0xAE4, expected=297, original=89):
    u = make()
    native = NativeCalls(u)
    u.hook_add(UC_HOOK_CODE, native.hook)
    frame, receive, source, length_out = 0x301EF40, 0x400F000, 0x400A000, 0x400F100
    # Enter the actual length hook with the original reader's local layout.
    u.reg_write(UC_X86_REG_EBP, frame)
    u.reg_write(UC_X86_REG_ESP, frame - 24)
    u.reg_write(UC_X86_REG_EDI, receive)
    u.reg_write(UC_X86_REG_ESI, original)
    u.mem_write(frame - 4, struct.pack('<I', packet_id))
    u.mem_write(frame, struct.pack('<IIII', 0, STOP, BUFFER, length_out))
    u.mem_write(receive, struct.pack('<III', source, 0, available))
    u.mem_write(source, b'X' * 2048)
    u.mem_write(BUFFER, b'Y' * expected)
    u.mem_write(length_out, b'\xff\xff')
    u.emu_start(0xC14866, 0, count=10000)
    assert u.reg_read(UC_X86_REG_EIP) == STOP, 'Receive bridge failed to return'
    success = available >= expected
    assert (u.reg_read(UC_X86_REG_EAX) & 0xff) == success
    assert dwords(u, receive + 4, 1)[0] == (expected if success else 0)
    assert bytes(u.mem_read(BUFFER, expected)) == (b'X' if success else b'Y') * expected
    assert bytes(u.mem_read(length_out, 2)) == (struct.pack('<H', expected) if success else b'\xff\xff')
    assert u.reg_read(UC_X86_REG_ESP) == frame + 16
    print(f'PASS {packet_id:04X} receive: available={available}, consumed={expected if success else 0}')


test_member()
test_list(2)
test_list(0)
test_list(1, malformed=1)
test_list(0, header_length=131)
for packet_id,original,expected in ((0x95,30,134),(0x2DF,36,140),(0xA30,106,522),
        (0xADF,58,266),(0xAE4,89,297),(0x1A2,37,141),(0xBA4,85,189),
        (0x29B,80,184),(0x2F7,47,151),(0xB7B,118,326),(0x206,35,139),
        (0x207,34,138),(0x209,36,140),(0xAF7,32,136),(0x2C5,30,134),(0x2C6,30,134),(0x16A,30,134),(0x171,30,134),
        (0x105,31,135),(0x20E,32,136),(0xA12,27,131),(0xA51,34,138),(0x809,50,154),
        (0xB6F,177,281),(0x6D,177,281),(0xDC,28,132),(0xDD,29,133),(0xE1,30,134),
        (0xAE7,38,142),(0xAFA,58,266),(0x1F4,32,136),(0x9F9,143,455),(0x293,70,147),
        (0x1F6,34,138),(0x2DD,32,136),(0x979,50,154),(0x8D8,27,27),(0x8D9,30,30),
        (0x8DB,27,27),(0x8DC,26,26),(0x8DE,27,27),(0x8DF,50,50),(0x8E1,51,51),(0xBE3,34,138)):
    for available in (0,1,2,4,original,expected-1,expected,expected*2):
        test_receive(available,packet_id,expected,original)
print('PASS final PE 128-byte party contract')
