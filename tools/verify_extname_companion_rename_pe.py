#!/usr/bin/env python3
"""Execute companion native edit limits, request writers, and literal name/confirmation copies."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args();sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
p=pefile.PE(args.pe);base=p.OPTIONAL_HEADER.ImageBase;STACK=0x60000000;HEAP=0x40000000;STOP=0x61000000
def dw(u,a,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(a,4*n)))
def call_target(a):
 code=p.get_data(a-base,5);assert code[0]==0xe8;return a+5+struct.unpack('<i',code[1:])[0]
class Native:
 def __init__(self):
  self.u=u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096);u.mem_map(base,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,p.get_memory_mapped_image());u.mem_map(STACK,0x20000);u.mem_write(STACK,b'\xA5'*0x20000);u.mem_map(HEAP,0x20000);u.mem_map(STOP,4096)
  self.sp=STACK+0x10000;u.reg_write(UC_X86_REG_ESP,self.sp);u.reg_write(UC_X86_REG_EBP,STACK+0x18000);u.mem_write(self.sp,struct.pack('<I',STOP));self.stops={STOP};self.sent=[];u.hook_add(UC_HOOK_CODE,self.hook)
  u.mem_write(0xfc16dc,struct.pack('<I',STOP+0x300));u.mem_write(0xfc1660,struct.pack('<I',STOP+0x400))
 def z(self,a):
  for n in range(1024):
   if self.u.mem_read(a+n,1)==b'\0':return bytes(self.u.mem_read(a,n))
  raise AssertionError('unterminated native name')
 def ret(self,n=0,value=0):
  u=self.u;s=u.reg_read(UC_X86_REG_ESP);pc=dw(u,s)[0];u.reg_write(UC_X86_REG_ESP,s+4+4*n);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
 def setstr(self,a,value):
  ptr=HEAP+0x5000;self.u.mem_write(ptr,value+b'\0');self.u.mem_write(a,struct.pack('<I',ptr)+bytes(12)+struct.pack('<II',len(value),512))
 def hook(self,u,pc,size,_):
  if pc in self.stops:u.emu_stop();return
  s=u.reg_read(UC_X86_REG_ESP)
  if pc==0xc14d60:self.ret(0,HEAP+0x18000)
  elif pc==0xc14920:
   size,ptr=dw(u,s+4,2);self.sent.append(bytes(u.mem_read(ptr,size)));self.ret(2)
  elif pc==0xa33100:self.ret(0,0)
  elif pc==0x4f1940:
   src,length=dw(u,s+4,2);self.setstr(u.reg_read(UC_X86_REG_ECX),bytes(u.mem_read(src,length)));self.ret(2)
  elif pc==STOP+0x200:self.ret()
  elif pc==STOP+0x300:self.ret(3,dw(u,s+8)[0]+1)
  elif pc==STOP+0x400:self.ret(4,dw(u,s+12)[0]-1)
  elif pc==0x59cdf0:
   dst,cap,count,fmt,name=dw(u,s+4,5);assert cap==512 and count==0xffffffff;value=self.z(fmt).replace(b'%s',self.z(name))[:511];u.mem_write(dst,value+b'\0');self.ret(0,len(value))
 def run(self,pc):
  self.u.emu_start(pc,0,count=100000);assert self.u.reg_read(UC_X86_REG_EIP)in self.stops,hex(self.u.reg_read(UC_X86_REG_EIP))
names=(b'Pet%'+b'N'*123,b'100% Pet',b'Z'*128,b'')
for start,packet in ((0xc8fac3,0x1a5),(0xc9082d,0x231)):
 for name in names:
  n=Native();u=n.u;u.mem_write(HEAP,name+b'\0');u.reg_write(UC_X86_REG_EDX,HEAP);u.reg_write(UC_X86_REG_ESI,0x11112222);u.reg_write(UC_X86_REG_EDI,0x33334444);n.stops={0xc930ad};n.run(start)
  expected=struct.pack('<H',packet)+name[:127]+bytes(128-len(name[:127]));assert n.sent==[expected],(hex(packet),len(name),n.sent);assert u.reg_read(UC_X86_REG_ESP)==n.sp;assert u.reg_read(UC_X86_REG_ESI)==0x11112222 and u.reg_read(UC_X86_REG_EDI)==0x33334444
  print('PASS native companion request',hex(packet),'input bytes',len(name),'130 bytes, padding and stack')
for start in (0x879339,0x875723):
 n=Native();u=n.u;u.reg_write(UC_X86_REG_EAX,HEAP);n.stops={start+10};n.run(start);assert dw(u,HEAP+0x88)[0]==127;print('PASS companion control limit127',hex(start))
for start,accepted,rejected in ((0x886240,0x886293,0x88625e),(0x88436e,0x8843c1,0x88438e)):
 for length in (0,23,24,50,127,128):
  n=Native();u=n.u;u.mem_write(HEAP+0xb4,struct.pack('<I',HEAP+0x1000));n.setstr(HEAP+0x1000+0xd8,b'A'*length);u.reg_write(UC_X86_REG_EBX,HEAP);n.stops={accepted,rejected};n.run(start);assert u.reg_read(UC_X86_REG_EIP)==(accepted if length<128 else rejected);assert u.reg_read(UC_X86_REG_ESP)==n.sp
  print('PASS native companion input validation',hex(start),length)
for length in (24,50,127,128,200):
 n=Native();u=n.u;edit=HEAP;vtable=HEAP+0x1000;u.mem_write(edit,struct.pack('<I',vtable));u.mem_write(edit+0x88,struct.pack('<I',127));u.mem_write(vtable+0xe4,struct.pack('<I',0x830770));u.mem_write(vtable+0xd8,struct.pack('<I',STOP+0x200));u.mem_write(HEAP+0x9000,b'A'*length+b'\0');u.mem_write(n.sp+4,struct.pack('<I',HEAP+0x9000));u.reg_write(UC_X86_REG_ECX,edit);n.run(0x8303f0);assert n.z(HEAP+0x5000)==b'A'*min(length,127);assert dw(u,edit+0xe8)[0]==min(length,127);print('PASS actual native edit setter/cap',length)
for site in (0x8792f7,0x8756e1,0x8863f8,0x884522):
 n=Native();u=n.u;name=b'Literal%'+b'X'*119;u.mem_write(HEAP,name+b'\0');u.mem_write(HEAP+0x1000,b'\xA5'*140);u.mem_write(n.sp+4,struct.pack('<II',HEAP+0x1000,HEAP));n.run(call_target(site));assert n.z(HEAP+0x1000)==name;assert u.mem_read(HEAP+0x1080,12)==b'\xA5'*12;assert u.reg_read(UC_X86_REG_ESP)==n.sp+4;print('PASS literal full companion name copy',hex(site))
for site in (0x886313,0x884441):
 n=Native();u=n.u;u.mem_write(HEAP,b'Confirm %s?\0');u.mem_write(HEAP+0x1000,b'Name%'+b'X'*122+b'\0');u.mem_write(HEAP+0x2000,b'\xA5'*524);u.mem_write(n.sp+4,struct.pack('<III',HEAP+0x2000,HEAP,HEAP+0x1000));n.run(call_target(site));assert n.z(HEAP+0x2000)==b'Confirm Name%'+b'X'*122+b'?';assert u.mem_read(HEAP+0x2200,12)==b'\xA5'*12;print('PASS bounded full companion confirmation',hex(site))
