#!/usr/bin/env python3
"""Execute the final PE companion status handlers with isolated UI/runtime stubs."""
import argparse, struct, sys
parser=argparse.ArgumentParser()
parser.add_argument("--pe",required=True)
parser.add_argument("--deps",required=True)
args=parser.parse_args()
sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(args.pe); base=pe.OPTIONAL_HEADER.ImageBase
BUFFER=0x15e8198; STACK=0x60000000; STOP=0x61000000
def words(u,p,n): return struct.unpack("<"+"I"*n,bytes(u.mem_read(p,4*n)))
def new():
    u=Uc(UC_ARCH_X86,UC_MODE_32)
    u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
    u.mem_write(base,pe.get_memory_mapped_image())
    u.mem_map(STACK,0x20000);u.mem_map(STOP,0x1000)
    u.reg_write(UC_X86_REG_ESP,STACK+0x10000);u.reg_write(UC_X86_REG_EBP,STACK+0x18000);u.reg_write(UC_X86_REG_EDI,STACK+0x14000)
    for p in (0x131f874,0x131f8ac,0x131f8a8):u.mem_write(p,bytes(4))
    return u
def endcall(u,n=0,value=0):
    sp=u.reg_read(UC_X86_REG_ESP);pc=words(u,sp,1)[0]
    u.reg_write(UC_X86_REG_ESP,sp+4+n*4);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
def string(u,p):return bytes(u.mem_read(p,128)).split(b"\0",1)[0]
def hook(u,pc,size,data):
    if pc in (0xc9e1d7,0xc9e1dd,STOP):u.emu_stop();return
    if pc in (0xce7260,0xd70da0,0xd70d30,0xd70dd0):endcall(u);return
    if pc==0xa69eb0:endcall(u,1);return
    if pc==0x59cdf0:
        dst,cap,count,fmt,src=words(u,u.reg_read(UC_X86_REG_ESP)+4,5)
        assert cap==128,cap
        value=string(u,src)
        assert len(value)<cap
        u.mem_write(dst,value+b"\0")
        data.append(dst)
        endcall(u,0,len(value));return
for kind,size,offset in (("pet",141,2),("mer",184,22),("hom",189,2)):
    for value in (b"N"*127,b"Percent%name"):
        u=new();p=bytearray(size);p[offset:offset+len(value)]=value
        if kind=="pet":
            struct.pack_into("<H",p,0,0x1a2)
            struct.pack_into("<BHHHHH",p,130,1,99,70,999,0,1002)
            entry=0xca6657;dest=struct.unpack("<I",pe.get_data(0xca667d-base,4))[0]
            expected={0x15fb3e0:99,0x15fb3e4:70,0x15fb3ec:999,0x15fb3dc:1002}
        elif kind=="mer":
            struct.pack_into("<HI8H",p,0,0x29b,200,1,2,3,4,5,6,7,8)
            struct.pack_into("<H5IHIIH",p,150,99,100,200,300,400,123456,5,6,7,8)
            entry=0xca7b5c;dest=struct.unpack("<I",pe.get_data(0xca7ba5-base,4))[0]
            expected={0x15ffa18:99,0x15ffa0c:100,0x15ffa10:200,0x15ffa1c:300,0x15ffa20:400,0x15ffa34:123456}
        else:
            struct.pack_into("<H",p,0,0xba4)
            struct.pack_into("<B11H4I2q2H",p,130,4,99,20,900,1,2,3,4,5,6,7,8,101,202,303,404,10000,20000,15,16)
            entry=0xcd1ed0;dest=None
            sp=u.reg_read(UC_X86_REG_ESP)
            u.mem_write(sp,struct.pack("<II",STOP,BUFFER))
            expected={0x15ff960:99,0x15ff990:20,0x15ff964:101,0x15ff968:202,0x15ff96c:303,0x15ff970:404}
        u.mem_write(BUFFER,bytes(p)); destinations=[]
        u.hook_add(UC_HOOK_CODE,hook,destinations)
        u.emu_start(entry,0,count=100000)
        assert u.reg_read(UC_X86_REG_EIP) in (STOP,0xc9e1d7,0xc9e1dd)
        if kind=="hom":dest=destinations[0]
        assert string(u,dest)==value,(kind,string(u,dest),value)
        for addr,v in expected.items():assert words(u,addr,1)[0]==v,(kind,hex(addr),words(u,addr,1)[0],v)
        print(f"PASS {kind}: {len(value)} name bytes, native scalar fields correct")
print("PASS companion 128-byte name contract")
