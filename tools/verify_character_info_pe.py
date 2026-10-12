#!/usr/bin/env python3
"""Execute resized native login character-list/create/delete consumers in final PE."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args()
sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(args.pe);BASE=pe.OPTIONAL_HEADER.ImageBase
OBJECT=0x40000000;PACKET=0x40010000;HEAP=0x41000000;STACK=0x60000000;STOP=0x61000000
SIZE=0x6f7c+68*104;ARRAY=0x4068;RECORD=279
def ints(u,p,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(p,4*n)))
class Native:
 def __init__(self):
  self.u=u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096)
  u.mem_map(BASE,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(BASE,pe.get_memory_mapped_image())
  for at,size in ((OBJECT,0x20000),(HEAP,0x20000),(STACK,0x20000),(STOP,4096)):u.mem_map(at,size)
  self.cursor=HEAP;self.errors=[];self.allocations=[]
  self.selected=ints(u,0xd202a3)[0]
  u.mem_write(OBJECT+SIZE,b'\xcd'*1024)
  u.mem_write(0xfc1b68,struct.pack('<I',STOP+0x100))
  u.mem_write(0xfc17fc,struct.pack('<I',STOP+0x110))
  u.mem_write(0xfc1b1c,struct.pack('<I',STOP+0x120))
  u.hook_add(UC_HOOK_CODE,self.hook)
 def z(self,p):
  for n in range(1024):
   if self.u.mem_read(p+n,1)==b'\0':return bytes(self.u.mem_read(p,n))
  raise AssertionError('Unterminated string')
 def ret(self,n=0,value=0):
  u=self.u;sp=u.reg_read(UC_X86_REG_ESP);pc=ints(u,sp)[0]
  u.reg_write(UC_X86_REG_ESP,sp+4+n*4);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,unused):
  if pc==STOP:u.emu_stop();return
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0xdbbbd4:self.ret();return
  if pc==0xe07d4b:
   dst,src,n=ints(u,sp+4,3);u.mem_write(dst,bytes(u.mem_read(src,n)));self.ret(0,dst);return
  if pc==0xe07d51:
   dst,value,n=ints(u,sp+4,3);u.mem_write(dst,bytes([value&255])*n);self.ret(0,dst);return
  if pc==STOP+0x100:
   p=ints(u,sp+4)[0];u.mem_write(p,struct.pack('<q',0));self.ret();return
  if pc==STOP+0x110:self.ret(1,ints(u,sp+4)[0]);return
  if pc==STOP+0x120:
   dst,src,n=ints(u,sp+4,3);v=self.z(src);u.mem_write(dst,(v+b'\0'*n)[:n]);self.ret(0,dst);return
  if pc==0xd999d0:self.ret(3,0);return
  if pc==0xd58cf0:self.ret(1,ints(u,sp+4)[0]);return
  if pc==0x59cdf0:
   dst,cap,count,fmt,src=ints(u,sp+4,5);v=self.z(src)[:cap-1];u.mem_write(dst,v+b'\0');self.ret(0,len(v));return
  if pc==0xa31a30:self.errors.append('invalid page');self.ret(9);return
  if pc in (0xdbc895,0xdbbc4f):
   n=ints(u,sp+4)[0];self.allocations.append(n);p=self.cursor;self.cursor+=(n+15)&~15;self.ret(0,p);return
  if pc in (0xdbc89e,0xdbbc7f):self.ret();return
 def run(self,entry,packet=None):
  u=self.u;sp=STACK+0x10000;u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_ECX,OBJECT)
  if packet is None:u.mem_write(sp,struct.pack('<I',STOP))
  else:u.mem_write(PACKET,packet);u.mem_write(sp,struct.pack('<II',STOP,PACKET))
  try:u.emu_start(entry,0,count=1500000)
  except Exception:
   print('Native failure',hex(u.reg_read(UC_X86_REG_EIP)),list(map(hex,ints(u,u.reg_read(UC_X86_REG_ESP),6))));raise
  assert u.reg_read(UC_X86_REG_EIP)==STOP
  assert u.reg_read(UC_X86_REG_ESP)==sp+(4 if packet is None else 8),'native stack imbalance'
  assert bytes(u.mem_read(OBJECT+SIZE,1024))==b'\xcd'*1024,'login owner overrun'
def record(index):
 p=bytearray(RECORD);struct.pack_into('<I',p,0,1000+index)
 p[108:236]=bytes([65+index%26])*127+b'\0';p[236:242]=bytes([1,2,3,4,5,6])
 p[242]=index;p[246:258]=b'prontera.gat';struct.pack_into('<I',p,262,300);p[278]=1
 return bytes(p)
def page(count,start=0):
 p=struct.pack('<HH',0xb72,4+RECORD*count)+b''.join(record(start+i) for i in range(count));return p
def check_records(n,count):
 for i in range(count):
  actual=bytes(n.u.mem_read(OBJECT+ARRAY+i*RECORD,RECORD));assert actual==record(i),(i,[(j,a,b) for j,(a,b) in enumerate(zip(actual,record(i))) if a!=b][:8])
for count in (0,1,2,3,68):
 n=Native();n.run(0xd205f0,page(count));check_records(n,count)
 assert ints(n.u,OBJECT+(0x1d8 if count==3 else 0x1cc))[0]==count
 assert not n.errors
 print('PASS native character page:',count,'full records, names, footer, capacity and stack')
n=Native();n.run(0xd205f0,page(3));n.run(0xd205f0,page(2,3));check_records(n,5)
assert ints(n.u,OBJECT+0x1cc)[0]==5
print('PASS paginated character list:3+2 records, no name alias or truncation')
for payload in (struct.pack('<HH',0xb72,5+RECORD)+record(0)+b'X',page(69)):
 n=Native();before=bytes(n.u.mem_read(OBJECT,SIZE));n.run(0xd205f0,payload);assert n.errors and bytes(n.u.mem_read(OBJECT,SIZE))==before
print('PASS malformed/oversized character pages rejected before owner writes')
n=Native();n.run(0xd20280,record(0));check_records(n,1)
assert bytes(n.u.mem_read(n.selected,RECORD))==record(0)
print('PASS character creation reply: full selected and login records')
n=Native();n.run(0xd205f0,page(2));n.u.mem_write(n.selected,record(0));n.run(0xd1fdc0)
assert ints(n.u,OBJECT+0x1cc)[0]==1
assert bytes(n.u.mem_read(OBJECT+ARRAY,RECORD))==record(1)
assert n.allocations==[2*RECORD]
print('PASS native deletion compaction: full279-byte records and heap capacity')
