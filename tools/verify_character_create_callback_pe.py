#!/usr/bin/env python3
"""Full modern creation callbacks, including Enter-key reentry and stats events."""
from verify_extname_oldcreate_pe import Native as OldNative,dw,H,S,STOP,EVENT
import struct
from unicorn.x86_const import *
class Modern(OldNative):
 def __init__(self,name):
  super().__init__(name);u=self.u
  u.mem_write(self.owner+0x210,self.original_bytes)
  u.mem_write(self.owner+0x328,struct.pack('<I',H+0x1900))
  u.mem_write(self.owner+0x330,struct.pack('<II',H+0x2500,H+0x2600))
  u.mem_write(self.owner+0x3d4,b'OWNEREND')
  u.mem_write(self.owner+0x8c,struct.pack('<I',0xb8))
  u.mem_write(self.owner,struct.pack('<I',H+0x1200))
  u.mem_write(H+0x1294,struct.pack('<I',0x7a1470))
 def callback(self,enter=False):
  self.u.mem_write(self.sp,struct.pack('<7I',STOP,0,0 if enter else 6,0xb8,0,0,0))
  self.u.reg_write(UC_X86_REG_ECX,self.owner);self.execute(0x7a1470)
  assert self.u.reg_read(UC_X86_REG_ESP)==self.sp+28
  assert self.u.mem_read(self.owner+0x3d4,8)==b'OWNEREND'
for enter in (False,True):
 for name in (b'Player'+b'X'*121,b'Percent%name',b'NormalName',b'A'+bytes.fromhex('e7958c')*42):
  n=Modern(name);n.callback(enter)
  assert any(e[0]==0x2715 for e in n.events),n.events
  assert n.z(n.owner+0x27c)==name and n.z(n.selected+108)==name
  stats=next(e[1] for e in n.events if e[0]==0x2721)
  expected=tuple(n.original_bytes[236:242])+tuple(v&0xffffffff for v in (struct.unpack_from('<h',n.original_bytes,104)+struct.unpack_from('<h',n.original_bytes,86)))
  assert stats==expected,(stats,expected)
 print('PASS full modern creator callback:', 'Enter-key reentry' if enter else 'button', 'full names, selected record, eight stats and owner/stack guards')
for name in (b'X'*128,b'GravityUser',b'[GM]Test',b'[[GM]Test',b'XY[GM]Test'):
 n=Modern(name);n.callback();assert not any(e[0]==0x2715 for e in n.events),name
print('PASS full modern creator: original reserved-name and oversized-input rejection')
