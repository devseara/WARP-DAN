#!/usr/bin/env python3
"""Old creation lifecycle gate; also runs the companion rename gate first.

The shared fixture stubs external UI/services while native owner setup, complete
callback, canonical record copy and sender machine code execute unchanged.
"""
from verify_extname_character_rename_pe import Native as RenameNative,dw,H,S,STOP,pe,BASE
import struct
from unicorn.x86_const import *
EVENT=STOP+1280;MBSSTR=STOP+1536
class Native(RenameNative):
 def __init__(self,name):
  super().__init__(name);u=self.u;self.events=[];self.destructed=[]
  u.mem_write(self.owner+0xb4,struct.pack('<I',H+0x1900));u.mem_write(self.owner+0xb8,self.original_bytes);u.mem_write(self.owner+0x344,b'OWNEREND')
  u.mem_write(0x121333c,struct.pack('<I',H+0x5000));u.mem_write(H+0x5000,struct.pack('<I',H+0x5100));u.mem_write(H+0x5118,struct.pack('<I',EVENT));u.mem_write(0xfc1964,struct.pack('<I',MBSSTR))
  u.mem_write(H+0x9000,struct.pack('<8I',1,2,3,4,5,6,7,8))
  self.selected=dw(u,0x8851b5)[0]
 def hook(self,u,pc,size,user):
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc==MBSSTR:self.ret(0,0);return
  if pc==0xd612c0:self.ret(6,0);return
  if pc==EVENT:
   command,param=dw(u,sp+4,2)
   if command==0x271f:param=self.z(param)
   elif command==0x2721:param=dw(u,param,8)
   self.events.append((command,param));self.ret(5,H+0x9000);return
  if pc==0x86b950:self.ret(1,ecx);return
  if pc==0xdbcba1:
   ptr,size,count,ctor,dtor=dw(u,sp+4,5);assert(size,count)==(24,5)
   for x in range(count):self.setstr(ptr+x*size,b'')
   self.ret();return
  getters={0xd5b8e0:5,0xd5bc30:5,0xd5a1f0:4,0xd5a480:4,0xd596d0:7,0xd5a390:5,0xd5a630:5}
  if pc in getters:
   out=dw(u,sp+4)[0];self.setstr(out,b'Sprite');self.ret(getters[pc],out);return
  if pc==0x4f1940:
   ptr,n=dw(u,sp+4,2);self.setstr(ecx,bytes(u.mem_read(ptr,n)));self.ret(2,ecx);return
  if pc==0xdbbc7f:self.ret();return
  if pc==0x79a840:
   assert ecx==self.owner+0x1d0,('destructor owner',hex(ecx));self.destructed.append(ecx);self.ret();return
  if pc in (0x86ca40,0x86cc00,0xa1b590):self.ret();return
  super().hook(u,pc,size,user)
 def callback(self):
  self.u.mem_write(self.sp,struct.pack('<7I',STOP,0,6,0xb8,0,0,0));self.u.reg_write(UC_X86_REG_ECX,self.owner);self.execute(0x884f00)
  assert self.u.reg_read(UC_X86_REG_ESP)==self.sp+28,'old creation callback stack imbalance'
  assert self.u.mem_read(self.owner+0x344,8)==b'OWNEREND','old creator owner overrun'
for name in (b'Player'+b'X'*121,b'Percent%name',b'NormalName',b'A'+bytes.fromhex('e7958c')*42):
 n=Native(name);n.callback();assert any(e[0]==0x2715 for e in n.events),n.events
 assert n.z(n.owner+0x124)==name and n.z(n.selected+108)==name
 actual=bytes(n.u.mem_read(n.selected,279));assert actual[:108]==n.original_bytes[:108] and actual[236:]==n.original_bytes[236:]
 assert next(e[1] for e in n.events if e[0]==0x271f)==name
 stats=next(e[1] for e in n.events if e[0]==0x2721);assert stats[:6]==tuple(n.original_bytes[236:242])
 print('PASS old creation callback279-byte selected record/footer,full name and native state events:',len(name))
for name in (b'X'*128,b'GravityUser',b'[GM]Test',b'[[GM]Test',b'XY[GM]Test'):
 n=Native(name);n.callback();assert not any(e[0]==0x2715 for e in n.events),name;print('PASS old creation reserved/oversize rejection:',name[:16])
n=Native(b'X'*128);n.reported_length=64;n.callback();assert not any(e[0]==0x2715 for e in n.events);print('PASS old creation raw-byte guard independent of IME count')
n=Native(b'Constructor');n.u.mem_write(n.sp,struct.pack('<I',STOP));n.u.reg_write(UC_X86_REG_ECX,n.owner);n.execute(0x86bc10)
assert n.u.reg_read(UC_X86_REG_ESP)==n.sp+4 and n.u.mem_read(n.owner+0x344,8)==b'OWNEREND'
assert bytes(n.u.mem_read(n.owner+0x1a4,6))==bytes([1,2,3,4,5,6])
assert dw(n.u,n.owner+0x314)[0]==15,'ctor ESI+0x144 shifted twice'
assert dw(n.u,n.owner+0x338)[0]==0,'tail fields missing'
n.u.mem_write(n.sp,struct.pack('<II',STOP,1));n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.reg_write(UC_X86_REG_ECX,n.owner);n.execute(0x86e4f0);assert n.destructed==[n.owner+0x1d0] and n.u.reg_read(UC_X86_REG_ESP)==n.sp+8
print('PASS old creator native construction/destruction, biased string owners and allocation canary')
for va in (0xa39a9e,0x86e57e,0xeedf87):assert dw(n.u,va)[0]==0x344
for va in (0xea4725,0xea505d,0xea5a1d):assert dw(n.u,va)[0]==0x1d0
assert dw(n.u,0x877647)[0]==127
print('PASS old creator factory/deleter/exception cleanup sizes and127-byte edit gate')

from verify_extname_character_rename_pe import check_exception_cookies
check_exception_cookies(Native(b'CookieTest'),0xea80a5,0x14c)
print('PASS native old-creator EH primary and relocated secondary stack cookies')