#!/usr/bin/env python3
"""Native modern creation validation/copy and actual140-byte packet writer.

Also runs the character-list regression module. External edit/transport services
are stubbed; the resized window copy, raw-byte guard and request writer execute.
"""
import runpy,struct
from pathlib import Path
scope=runpy.run_path(str(Path(__file__).with_name('verify_character_info_pe.py')))
Native=scope['Native'];OBJECT=scope['OBJECT'];PACKET=scope['PACKET'];STACK=scope['STACK'];STOP=scope['STOP'];record=scope['record'];ints=scope['ints']
from unicorn.x86_const import *
class Creation(Native):
 def __init__(self,value,logical_length=None):
  super().__init__();self.value=value;self.logical_length=len(value) if logical_length is None else logical_length;self.sent=[];self.exit=None
  self.u.mem_write(PACKET,value+b'\0');self.u.mem_write(OBJECT+0x328,struct.pack('<I',OBJECT+0xa000))
  self.u.mem_write(OBJECT+0x210,record(0));self.u.mem_write(OBJECT+0x3d4,b'\xac'*64)
 def hook(self,u,pc,size,unused):
  if pc in (0x7a176e,0x7a16a5,0xd25be9):self.exit=pc;u.emu_stop();return
  if pc==0x8210d0:self.ret(0,self.logical_length);return
  if pc==0x8210a0:self.ret(0,PACKET);return
  if pc==0xc14d60:self.ret(0,OBJECT+0xb000);return
  if pc==0xc14920:
   sp=u.reg_read(UC_X86_REG_ESP);length,ptr=ints(u,sp+4,2)
   assert u.reg_read(UC_X86_REG_ECX)==OBJECT+0xb000
   self.sent.append(bytes(u.mem_read(ptr,length)));self.ret(2);return
  super().hook(u,pc,size,unused)
 def copy(self):
  u=self.u;frame=STACK+0x10000
  u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_ESP,frame-0x150)
  u.reg_write(UC_X86_REG_ESI,OBJECT);u.reg_write(UC_X86_REG_EDI,0)
  u.mem_write(frame-0x3c,struct.pack('<I',OBJECT))
  # Adjacent live locals are intentionally nonzero to detect temporary overlap.
  u.mem_write(frame-0x38,b'LIVELOCALS'+bytes(6))
  u.emu_start(0x7a1695,0,count=100000)
  assert bytes(u.mem_read(OBJECT+0x3d4,64))==b'\xac'*64,'window owner overrun'
  assert bytes(u.mem_read(frame-0x38,16))==b'LIVELOCALS'+bytes(6),'name temporary clobbered live locals'
  return self.exit
 def send(self):
  u=self.u;sp=STACK+0x10000;u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EBP,sp+0x1000)
  u.emu_start(0xd25b56,0,count=100000)
  assert self.exit==0xd25be9 and u.reg_read(UC_X86_REG_ESP)==sp
for value in (b'Ordinary',b'Percent%name',b'N'*127,('é'*63+'x').encode('utf-8')):
 n=Creation(value);assert n.copy()==0x7a176e
 expected=bytearray(record(0));expected[108:108+len(value)+1]=value+b'\0'
 assert bytes(n.u.mem_read(n.selected,279))==bytes(expected)
 assert n.z(OBJECT+0x27c)==value
 n.send();assert len(n.sent)==1
 p=n.sent[0];assert len(p)==140 and p[:2]==b'\x39\x0a'
 assert p[2:130]==value+b'\0'*(128-len(value))
 assert p[130]==0 and p[139]==1
 print('PASS modern creation:',len(value),'encoded bytes, canonical279 copy,140-byte send, zero padding and stack')
for value,logical in ((b'X'*128,128),(b'X'*128,127),(('é'*127).encode('utf-8'),127)):
 n=Creation(value,logical);before=bytes(n.u.mem_read(n.selected,279));assert n.copy()==0x7a16a5
 assert bytes(n.u.mem_read(n.selected,279))==before and not n.sent
 print('PASS modern creation rejects',len(value),'raw bytes with native count',logical)
print('PASS modern character creation native name contract')
