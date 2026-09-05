#!/usr/bin/env python3
"""Execute real expanded prologues and their matching GS/EH cookie thunks."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args();sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(args.pe);base=pe.OPTIONAL_HEADER.ImageBase
STACK=0x60000000;STOP=0x61000000;COOKIE=0xA19B73D5
def dword(u,p):return struct.unpack('<I',bytes(u.mem_read(p,4)))[0]
cases=[('modern creator',0x7a1470,0x7a149a,0xe83c9d),
       ('old creator',0x884f00,0x884f2a,0xea80a5),
       ('rename',0x8fa8d0,0x8fa8fd,0xeb9216),
       ('friend ACK',0xcb5220,0xcb524c,0xf256b0),
       ('friend request',0x8c4030,0x8c405e,0xeb1f60),
       ('party ACK',0xcb2d80,0xcb2dad,0xf25256),
       ('clan chat',0xcf8860,0xcf888c,0xf2c280)]
for name,entry,body,handler in cases:
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096)
 u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
 u.mem_map(STACK,0x20000);u.mem_map(STOP,4096);u.mem_write(0x122b924,struct.pack('<I',COOKIE))
 u.mem_write(STACK,bytes([0xCC])*0x20000);checks=[]
 def hook(u,pc,size,unused):
  if pc in (body,0xe07d45,STOP):u.emu_stop();return
  if pc==0xdbbbd4:
   actual=u.reg_read(UC_X86_REG_ECX);assert actual==COOKIE,(name,'EH cookie mismatch',hex(actual))
   checks.append(actual);sp=u.reg_read(UC_X86_REG_ESP);ret=dword(u,sp)
   u.reg_write(UC_X86_REG_ESP,sp+4);u.reg_write(UC_X86_REG_EIP,ret)
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_X86_REG_ESP,STACK+0x10000);u.mem_write(STACK+0x10000,struct.pack('<I',STOP))
 u.emu_start(entry,0,count=10000);assert u.reg_read(UC_X86_REG_EIP)==body
 registration=dword(u,0);assert dword(u,registration+4)==handler,(name,'wrong registered handler')
 u.reg_write(UC_X86_REG_ESP,STACK+0x18000)
 u.mem_write(STACK+0x18000,struct.pack('<III',STOP,0,registration))
 u.emu_start(handler,0,count=10000)
 assert u.reg_read(UC_X86_REG_EIP)==0xe07d45 and len(checks)==2,(name,checks)
 print('PASS',name,'actual prologue + primary/secondary EH cookies')
