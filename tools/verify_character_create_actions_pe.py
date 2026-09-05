#!/usr/bin/env python3
"""Creation-window action regressions beyond the name-copy fast path."""
import runpy,struct
from pathlib import Path
g=runpy.run_path(str(Path(__file__).with_name('verify_character_create_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Actions(Creation):
 def __init__(self,value):
  super().__init__(value);self.events=[];self.manager=OBJECT+0xa000;self.vtable=OBJECT+0xb000
  self.u.mem_write(OBJECT,struct.pack('<I',self.vtable));self.u.mem_write(self.manager,struct.pack('<I',self.vtable))
  self.u.mem_write(self.vtable+0x18,struct.pack('<I',STOP+0x300));self.u.mem_write(self.vtable+0x94,struct.pack('<I',STOP+0x310))
 def hook(self,u,pc,size,unused):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0x7a1db1:self.exit=pc;u.emu_stop();return
  if pc==STOP+0x300:
   event,ptr,a,b,c=ints(u,sp+4,5);assert event==0x2721
   self.events.append(tuple(ints(u,ptr,8)));self.ret(5);return
  if pc==STOP+0x310:
   self.events.append(tuple(ints(u,sp+4,6)));assert u.reg_read(UC_X86_REG_ECX)==OBJECT
   self.ret(6);return
  super().hook(u,pc,size,unused)
 def prepare(self):
  frame=STACK+0x10000;u=self.u
  u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_ESP,frame-0x150);u.reg_write(UC_X86_REG_ESI,OBJECT)
  u.mem_write(frame-0x34,struct.pack('<I',self.manager));return frame
n=Actions(b'Stats');frame=n.prepare();u=n.u
u.mem_write(OBJECT+0x2fc,bytes(range(1,7)));u.mem_write(OBJECT+0x278,struct.pack('<h',7));u.mem_write(OBJECT+0x266,struct.pack('<h',8))
u.mem_write(frame-0x30,b'\xcc'*32);u.emu_start(0x7a18ca,0,count=10000)
assert n.events==[tuple(range(1,9))],n.events
assert u.reg_read(UC_X86_REG_ESP)==frame-0x150
print('PASS modern creation stats event: all eight values remain contiguous and correct')
for value in (b'Short',b'N'*127,('é'*63+'x').encode(),b'Percent%name',b'X'*128):
 n=Actions(value);frame=n.prepare();u=n.u;u.mem_write(OBJECT+0x8c,struct.pack('<I',77))
 u.mem_write(frame-0x38,b'\xcd'*40);before=bytes(u.mem_read(OBJECT+0x27c,128))
 u.emu_start(0x7a1d52,0,count=100000)
 assert n.exit==0x7a1db1 and u.reg_read(UC_X86_REG_ESP)==frame-0x150
 assert bytes(u.mem_read(frame-0x38,40))==b'\xcd'*40,'Enter key overwrote former short stack buffer'
 if len(value)<128:
  assert n.z(OBJECT+0x27c)==value and n.events==[(0,6,77,0,0,0)]
 else:assert not n.events and bytes(u.mem_read(OBJECT+0x27c,128))==before
print('PASS modern creation Enter key: full canonical names, raw-byte bound, event arguments and stack guards')
