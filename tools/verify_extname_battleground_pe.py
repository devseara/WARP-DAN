#!/usr/bin/env python3
"""Verify stock BG labels/requests after removing unrelated name expansion."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args();sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
p=pefile.PE(args.pe);base=p.OPTIONAL_HEADER.ImageBase
B=0x15e8198;STACK=0x60000000;HEAP=0x40000000;STOP=0x61000000
def dw(u,a,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(a,4*n)))
class Machine:
 def __init__(self,stop=STOP):
  self.u=u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096);u.mem_map(base,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,p.get_memory_mapped_image());u.mem_map(STACK,0x20000);u.mem_map(HEAP,0x20000);u.mem_map(STOP,4096)
  self.sp=STACK+0x10000;u.reg_write(UC_X86_REG_ESP,self.sp);u.reg_write(UC_X86_REG_EBP,STACK+0x18000);u.mem_write(self.sp,struct.pack('<I',STOP));u.mem_write(0x15c43e4,struct.pack('<I',HEAP));u.mem_write(HEAP,b'\xA5'*0x200)
  u.mem_write(0xfc1b5c,struct.pack("<I",STOP+0x100));u.mem_write(0xfc1b60,struct.pack("<I",STOP+0x200))
  self.stop=stop;self.sent=[];self.sizes=[];u.hook_add(UC_HOOK_CODE,self.hook)
 def z(self,a):
  for n in range(1024):
   if self.u.mem_read(a+n,1)==b'\0':return bytes(self.u.mem_read(a,n))
  raise AssertionError('unterminated name')
 def ret(self,n=0,value=0):
  u=self.u;s=u.reg_read(UC_X86_REG_ESP);pc=dw(u,s)[0];u.reg_write(UC_X86_REG_ESP,s+4+4*n);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,_):
  if pc==self.stop:u.emu_stop();return
  s=u.reg_read(UC_X86_REG_ESP)
  if pc==0xc14d60:self.ret(0,HEAP+0x10000)
  elif pc==0xc14460:self.ret(1,{0x8d7:28,0x8da:26,0x90a:26,0x8dd:27,0x8e0:51}[dw(u,s+4)[0]])
  elif pc==0xdbbbd4:self.ret()
  elif pc in (STOP+0x100,STOP+0x200):
   dst,cap,src=dw(u,s+4,3);value=self.z(src)
   if pc==STOP+0x200:value=value[:dw(u,s+16)[0]]
   assert len(value)<cap
   u.mem_write(dst,value+b'\0');self.ret()
  elif pc==0xc14920:
   length,ptr=dw(u,s+4,2);self.sent.append(bytes(u.mem_read(ptr,length)));self.ret(2)
  elif pc==0xe07d51:
   dst,value,length=dw(u,s+4,3);u.mem_write(dst,bytes([value])*length);self.ret(0,dst)
  elif pc in (0xdbbeae,0xdbbc7f):
   self.sizes.append(dw(u,s+(4 if pc==0xdbbeae else 8))[0]);self.ret(0,HEAP)
 def run(self,pc):
  self.u.emu_start(pc,0,count=100000)
  assert self.u.reg_read(UC_X86_REG_EIP)==self.stop,hex(self.u.reg_read(UC_X86_REG_EIP))
name=b'Queue%'+b'Q'*17;lobby=b'Lobby%'+b'L'*17
for start in (0xb39d77,0xb3a107):
 n=Machine(0xb39d98 if start==0xb39d77 else 0xb3a128);u=n.u;u.reg_write(UC_X86_REG_EDI,HEAP);n.run(start)
 assert u.mem_read(HEAP+4,48)==bytes(48);assert dw(u,HEAP+0x34)[0]==0 and u.mem_read(HEAP+0x38,1)==b'\0';assert u.mem_read(HEAP+0x3c,4)==b'\xA5'*4
 print('PASS BG constructor stock arrays',hex(start))
for start,stop in ((0xb3a0e9,0xb3a0f0),(0xb3a096,0xb3a09e)):
 n=Machine(stop);n.u.reg_write(UC_X86_REG_EDI,HEAP);n.run(start);assert n.sizes==[60];print('PASS BG owner allocation/free',hex(start))
for start,offset in ((0xb3a510,4),(0xb3a530,0x1c)):
 n=Machine();u=n.u;u.mem_write(B,name+b'\0');u.mem_write(n.sp+4,struct.pack('<I',B));u.reg_write(UC_X86_REG_ECX,HEAP);n.run(start)
 assert n.z(HEAP+offset)==name;assert u.reg_read(UC_X86_REG_ESP)==n.sp+8;assert u.mem_read(HEAP+offset+24,4)==b'\xA5'*4;print('PASS BG stock setter',hex(start))
n=Machine(0xb3a649);u=n.u;u.mem_write(B+3,name+b'\0');u.reg_write(UC_X86_REG_EDI,HEAP);u.reg_write(UC_X86_REG_ESI,B);n.run(0xb3a636);assert n.z(HEAP+4)==name;assert u.reg_read(UC_X86_REG_ESP)==n.sp;print('PASS BG apply acknowledgment')
n=Machine(0xb3af71);u=n.u;u.mem_write(B+2,name+b'\0'+lobby+b'\0');u.reg_write(UC_X86_REG_EBX,HEAP);u.reg_write(UC_X86_REG_EDI,B);u.reg_write(UC_X86_REG_ESI,STOP+0x100);n.run(0xb3af56);assert n.z(HEAP+4)==name and n.z(HEAP+0x1c)==lobby;assert u.reg_read(UC_X86_REG_ESP)==n.sp;print('PASS BG lobby acknowledgment two stock labels')
n=Machine(0xb3ae31);u=n.u;u.mem_write(B+26,struct.pack('<I',54321));u.reg_write(UC_X86_REG_ESI,B);u.reg_write(UC_X86_REG_EDX,HEAP);n.run(0xb3ae28);assert dw(u,n.sp-4)[0]==54321;print('PASS BG queue-count footer')
for start,packet,length,cleanup in ((0xb3a2f0,0x8d7,28,8),(0xb3a360,0x8da,26,0),(0xb3a3d0,0x90a,26,0),(0xb3a1d0,0x8dd,27,8),(0xb3a240,0x8e0,51,4)):
 n=Machine();u=n.u;u.mem_write(HEAP+0x34,struct.pack('<I',HEAP+0x1000));u.mem_write(HEAP+0x1004,name+b'\0');u.mem_write(HEAP+0x1c,lobby+b'\0');u.mem_write(B,name+b'\0');u.reg_write(UC_X86_REG_ECX,HEAP)
 params=(2,B) if packet==0x8d7 else ((B,2) if packet==0x8dd else (2,));u.mem_write(n.sp+4,struct.pack('<'+'I'*len(params),*params));n.run(start)
 assert len(n.sent)==1 and len(n.sent[0])==length;v=n.sent[0];assert struct.unpack_from('<H',v)[0]==packet;offset=4 if packet==0x8d7 else (3 if packet in (0x8dd,0x8e0) else 2);assert v[offset:offset+24]==name+b'\0'
 if packet==0x8e0:assert v[27:]==lobby+b'\0' and u.mem_read(HEAP+0x38,1)==b'\0'
 assert u.reg_read(UC_X86_REG_ESP)==n.sp+4+cleanup;print('PASS BG outgoing stock labels and stack',hex(packet))
# Settings consumers are back to stock. Their file-stream preconditions differ
# from the removed bridge; check their guarded native bytes instead of running
# those middle-of-function instructions with the old bridge's test frame.
for va,expected in ((0xda4f21,"6a 30 8d 45 c0"),(0xda4f5b,"6a 30 8d 45 90")):
 assert p.get_data(va-base,5)==bytes.fromhex(expected)
print('PASS BG settings load retains stock code')
for start,stop,offset in ((0xd9ddf4,0xd9ddf7,4),(0xd9de8a,0xd9de8f,0x1c)):
 n=Machine(stop);n.u.reg_write(UC_X86_REG_EDX,HEAP);n.run(start);assert n.u.reg_read(UC_X86_REG_EDX)==HEAP+offset;print('PASS BG settings stock-label save pointer',hex(start))
