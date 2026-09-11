"""Execute retained player-name request/ACK fragments in a fresh 2025 PE.

Native WARP machine code runs in Unicorn. Networking/member lookup/string
construction are stubbed; no game or server is contacted. Macro request tests
exercise both isolated packet bridges and the full native UI sender, including
normal C++ message destruction. Exceptional allocation unwind remains untested.
"""
import argparse
import struct
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--pe', required=True)
p.add_argument('--deps')
a = p.parse_args()
if a.deps:
    sys.path.insert(0, a.deps)
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

pe = pefile.PE(a.pe)
BASE = pe.OPTIONAL_HEADER.ImageBase
IMAGE = pe.get_memory_mapped_image()
STACK, HEAP = 0x60000000, 0x50000000
FRAME, SP, B = STACK + 0x30000, STACK + 0x10000, 0x15e8198

def dw(u, at, n=1):
    return struct.unpack('<' + 'I' * n, u.mem_read(at, 4*n))

def z(u, at, limit=1024):
    for n in range(limit):
        if u.mem_read(at+n, 1) == b'\0':
            return bytes(u.mem_read(at, n))
    raise AssertionError('unterminated string')

class Native:
    def __init__(self):
        self.u = u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(BASE, (pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
        u.mem_write(BASE, IMAGE)
        u.mem_map(STACK, 0x40000)
        u.mem_map(HEAP, 0x10000)
        u.reg_write(UC_X86_REG_EBP, FRAME)
        u.reg_write(UC_X86_REG_ESP, SP)
        self.sent, self.acks, self.constructed, self.destroyed = [], [], [], []
        self.stops = set()
        self.read_lengths = []
        u.hook_add(UC_HOOK_CODE, self.hook)

    def ret(self, argc=0, value=0):
        u = self.u
        sp = u.reg_read(UC_X86_REG_ESP)
        target = dw(u, sp)[0]
        u.reg_write(UC_X86_REG_ESP, sp+4+argc*4)
        u.reg_write(UC_X86_REG_EAX, value)
        u.reg_write(UC_X86_REG_EIP, target)

    def hook(self, u, pc, size, _):
        sp = u.reg_read(UC_X86_REG_ESP)
        if pc in self.stops:
            u.emu_stop()
        elif pc == 0xc14d60:
            self.ret(value=HEAP+0x8000)
        elif pc == 0xc14920:
            length, ptr = dw(u, sp+4, 2)
            assert length in (134, 241)
            self.sent.append(bytes(u.mem_read(ptr, length)))
            self.ret(2, 1)
        elif pc == 0xd5d960:
            obj, identity = dw(u, sp+4, 2)
            assert identity == 777
            u.mem_write(obj, bytes(40))
            u.mem_write(obj+4, struct.pack('<I', 0x12345678))
            self.constructed.append(obj)
            self.ret(2, obj)
        elif pc == 0x7007e0:
            self.destroyed.append(u.reg_read(UC_X86_REG_ECX))
            self.ret()
        elif pc == 0x4e5330:
            value = z(u, dw(u, sp+4)[0], 128)
            obj = u.reg_read(UC_X86_REG_ECX)
            ptr = HEAP + 0x6000
            u.mem_write(ptr, value+b'\0')
            u.mem_write(obj, struct.pack('<I', ptr)+bytes(12)+struct.pack('<II', len(value), 128))
            self.constructed.append(value)
            self.ret(1, obj)
        elif pc == 0xcfd8e0:
            identity = dw(u, sp+4)[0]
            obj = sp+8
            ptr = dw(u, obj)[0]
            length = dw(u, obj+16)[0]
            self.acks.append((identity, bytes(u.mem_read(ptr, length)), dw(u, sp+32)[0]))
            self.ret(8)
        elif pc == 0xc16570:
            self.read_lengths.append(dw(u, sp+4)[0])
            u.emu_stop()

    def run(self, pc):
        self.u.emu_start(pc, 0, count=100000)
        assert self.u.reg_read(UC_X86_REG_EIP) in self.stops or self.read_lengths

values = [b'A', b'N'*23, b'N'*24, b'N'*127, ('é'*63+'x').encode(), b'%Player', b'Short']
n = Native()
u = n.u
n.stops = {0xc930ad}
u.mem_write(FRAME-0x10374, struct.pack('<I', 777))
for value in values + [b'X'*128, b'Final']:
    u.mem_write(HEAP, value+b'\0')
    u.reg_write(UC_X86_REG_EDX, HEAP)
    u.reg_write(UC_X86_REG_ESP, SP)
    before = len(n.sent)
    n.run(0xc8d634)
    assert u.reg_read(UC_X86_REG_ESP) == SP
    if len(value) >= 128:
        assert len(n.sent) == before
    else:
        assert n.sent[-1] == struct.pack('<HI',0x103,0x12345678)+value+bytes(128-len(value))
        assert n.constructed[-1] == n.destroyed[-1] == FRAME-0xe630
print('PASS party removal: 134 bytes, full name/AID, 127/128 boundary, repeated padding, native member lifetime and balanced stack')

n = Native()
u = n.u
message = b'M'*100
for value in values + [b'X'*128, b'Final']:
    u.reg_write(UC_X86_REG_ESP, SP)
    u.reg_write(UC_X86_REG_ESI, HEAP+0x1000)
    u.reg_write(UC_X86_REG_EAX, HEAP)
    u.mem_write(HEAP, value+b'\0')
    u.mem_write(HEAP+0x10e0, struct.pack('<I', HEAP+0x3000))
    packet = bytearray(137)
    struct.pack_into('<HII', packet, 0, 0xbe2, 111, 222)
    struct.pack_into('<H', packet, 34, 1)
    packet[36:136] = message
    u.mem_write(FRAME-0xb4, bytes(packet))
    n.stops = {0x9f3705}
    n.run(0x9f36ea)
    assert u.reg_read(UC_X86_REG_ESP) == SP-256
    n.stops = {0x9f380f}
    before = len(n.sent)
    n.run(0x9f37e5)
    assert u.reg_read(UC_X86_REG_ESP) == SP
    if len(value) >= 128:
        assert len(n.sent) == before
    else:
        expected = struct.pack('<HII',0xbe2,111,222)+value+bytes(128-len(value))+struct.pack('<H',1)+message+b'\0'
        assert n.sent[-1] == expected
print('PASS report request bridges: 241 bytes, both AIDs, full names, shifted type/message, rejection, repeated padding and balanced stack')

for value in values:
    for status in (0, 1, 2, 0x12345678):
        n = Native()
        u = n.u
        packet = struct.pack('<HI',0xbe3,111)+value+bytes(128-len(value))+struct.pack('<I',status)
        u.mem_write(B,packet)
        n.stops={0xc9e1d7,0xc9e1dd}
        u.reg_write(UC_X86_REG_EDI,HEAP+0x1000)
        n.run(0xcaa1eb)
        assert n.acks == [(111,value,status)]
        assert u.reg_read(UC_X86_REG_ESP) == SP
        u.mem_write(B,bytes(138))
        assert z(u,HEAP+0x6000)==value
n=Native();n.u.mem_write(B,struct.pack('<HI',0xbe3,111)+b'X'*128+bytes(4));n.stops={0xc9e1dd};n.run(0xcaa1eb)
assert not n.constructed and not n.acks
print('PASS report ACK: full owned name, correct status/AID, packet reuse, unterminated rejection and balanced stack')
n=Native();n.u.mem_write(FRAME-4,struct.pack('<I',0xbe3));n.u.mem_write(FRAME+8,struct.pack('<I',B));n.u.reg_write(UC_X86_REG_ESI,34);n.run(0xc14866)
assert n.read_lengths==[138]
print('PASS report ACK native reader consumes 138 bytes')


class FullReport(Native):
    def __init__(self):
        super().__init__()
        self.u.mem_map(0, 0x1000)
        self.u.mem_write(0xfc1b60, struct.pack('<I', HEAP+0xf000))
        self.message = b''
        self.freed = []
    def hook(self, u, pc, size, user):
        sp = u.reg_read(UC_X86_REG_ESP)
        if pc == 0x8210a0:
            self.ret(value=HEAP+0x4000)
        elif pc == 0x4f1940:
            ptr, length = dw(u, sp+4, 2)
            obj = u.reg_read(UC_X86_REG_ECX)
            value = bytes(u.mem_read(ptr,length))
            u.mem_write(obj,bytes(24))
            if length < 16:
                u.mem_write(obj,value+b'\0')
                capacity=15
            else:
                u.mem_write(HEAP+0x6000,value+b'\0')
                u.mem_write(obj,struct.pack('<I',HEAP+0x6000))
                capacity=127
            u.mem_write(obj+16,struct.pack('<II',length,capacity))
            self.constructed.append(value)
            self.ret(2,obj)
        elif pc == HEAP+0xf000:
            dest, cap, source, count = dw(u,sp+4,4)
            assert cap == 101 and count == 0xffffffff
            value=z(u,source)[:cap-1]
            u.mem_write(dest,value+b'\0')
            self.ret()
        elif pc == 0xdbbc7f:
            self.freed.append(dw(u,sp+4)[0])
            self.ret()
        elif pc == 0xa2e770:
            assert dw(u,sp+4)[0] == 0x2715
            self.ret(1)
        elif pc == 0xdbbbd4:
            assert u.reg_read(UC_X86_REG_ECX) == dw(u,0x122b924)[0]
            self.ret()
        else:
            super().hook(u,pc,size,user)

for value in (b'Short',b'N'*127,b'X'*128):
    for message in (b'',b'short',b'M'*100,b'M'*150):
        n=FullReport();u=n.u;dialog=HEAP+0x1000
        u.mem_write(dialog+0x100,struct.pack('<IH',222,1))
        u.mem_write(dialog+0x108,struct.pack('<I',HEAP))
        u.mem_write(dialog+0x118,struct.pack('<II',len(value),255))
        u.mem_write(HEAP,value+b'\0')
        u.mem_write(0x15fb9a4,struct.pack('<I',111))
        u.mem_write(dialog+0xe0,struct.pack('<I',HEAP+0x3000))
        u.mem_write(HEAP+0x3000+0x9c,struct.pack('<I',HEAP+0x3100))
        u.mem_write(HEAP+0x4000,message+b'\0')
        u.reg_write(UC_X86_REG_ECX,dialog)
        u.reg_write(UC_X86_REG_ESI,0x12345678)
        stop=STACK+0x3f000;n.stops={stop};u.mem_write(SP,struct.pack('<I',stop))
        n.run(0x9f3670)
        assert u.reg_read(UC_X86_REG_ESP)==SP+4
        assert u.reg_read(UC_X86_REG_EBP)==FRAME
        assert u.reg_read(UC_X86_REG_ESI)==0x12345678
        assert dw(u,0)[0]==0, 'native SEH chain was not restored'
        assert n.constructed==[message]
        assert n.freed==([HEAP+0x6000] if len(message)>=16 else [])
        if len(value)>=128: assert not n.sent
        else:
            tail=message[:100]
            expected=struct.pack('<HII',0xbe2,111,222)+value+bytes(128-len(value))+struct.pack('<H',1)+tail+bytes(101-len(tail))
            assert n.sent==[expected]
print('PASS complete native macro sender: short/long message ownership, 100-byte cap, normal SEH restoration, name rejection, registers and stack')
