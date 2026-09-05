#!/usr/bin/env python3
"""Emulate the final NPC discovery ring drain, including V4 and malformed records."""
import argparse, re, struct, sys
p=argparse.ArgumentParser();p.add_argument("--pe",required=True);p.add_argument("--deps",required=True);a=p.parse_args()
sys.path.insert(0,a.deps)
import pefile,capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EBP,UC_X86_REG_EIP
pe=pefile.PE(a.pe);data=bytes(pe.__data__);base=pe.OPTIONAL_HEADER.ImageBase
sig=rb"\xa1....\x89\x45\xe4\x8b\x15....\x8b\xc8\x2b\xca\x85\xc9"
hits=list(re.finditer(sig,data,re.S));assert len(hits)==1,len(hits)
off=hits[0].start();start=base+pe.get_rva_from_offset(off)
ring=struct.unpack_from("<I",data,off+1)[0]-4
state=struct.unpack_from("<I",data,off+10)[0]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
code=[]
for i in md.disasm(data[off:off+2048],start):
    if i.mnemonic=="call":stop=i.address;break
    code.append(i)
else:raise AssertionError("NPC persistence boundary not found")
chunk=data[off:off+stop-start]
matches=list(re.finditer(rb"\xbf(....)\xbb\x00\x01\x00\x00",chunk,re.S))
assert len(matches)==1
table=struct.unpack("<I",matches[0][1])[0]
for length,type_at in [(233,232),(237,232),(773,772),(777,772),(653,652),(657,652)]:
    for kind in [0,1,2,3,4,5,6,7]:
        u=Uc(UC_ARCH_X86,UC_MODE_32)
        u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
        u.mem_map(0x60000000,0x10000);u.reg_write(UC_X86_REG_EBP,0x60008000)
        u.mem_write(table,bytes(256*12));u.mem_write(state,bytes(4));u.mem_write(ring+4,struct.pack("<I",1))
        packet=bytearray(length);struct.pack_into("<HHII",packet,0,0xbb7,length,0x4558544e,1234);packet[type_at]=kind
        u.mem_write(ring+16,struct.pack("<I",length)+bytes(packet))
        u.emu_start(start,stop,count=100000)
        assert u.reg_read(UC_X86_REG_EIP)==stop
        gid=struct.unpack("<I",u.mem_read(table,4))[0]
        assert gid==(1234 if kind==2 else 0),(length,kind,gid)
    print(f"PASS NPC ring {length}: NPC accepted, PC/mob/portal/companions excluded")
for bad in ("magic","length","zero_gid"):
    u=Uc(UC_ARCH_X86,UC_MODE_32)
    u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
    u.mem_map(0x60000000,0x10000);u.reg_write(UC_X86_REG_EBP,0x60008000)
    u.mem_write(table,bytes(256*12));u.mem_write(state,bytes(4));u.mem_write(ring+4,struct.pack("<I",1))
    packet=bytearray(657);struct.pack_into("<HHII",packet,0,0xbb7,653 if bad=="length" else 657,0 if bad=="magic" else 0x4558544e,0 if bad=="zero_gid" else 1234);packet[652]=2
    u.mem_write(ring+16,struct.pack("<I",657)+packet)
    u.emu_start(start,stop,count=100000)
    assert u.reg_read(UC_X86_REG_EIP)==stop
    assert not any(u.mem_read(table,256*12))
    print("PASS NPC ring rejects",bad)
