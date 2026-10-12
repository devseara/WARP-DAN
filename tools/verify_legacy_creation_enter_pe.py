#!/usr/bin/env python3
"""Legacy creation Enter-key reentry plus rename Enter-key routing."""
from verify_extname_oldcreate_pe import Native as OldNative,dw,H,STOP
from verify_extname_character_rename_pe import Native as RenameNative
import struct
from unicorn.x86_const import *
for cls,entry,offset,size in ((OldNative,0x884f00,0x124,0x344),(RenameNative,0x8fa8d0,0x130,0x1dc)):
 for name in (b'ShortName',b'N'*127,('é'*63+'x').encode(),b'Percent%name',b'X'*128):
  n=cls(name);u=n.u;u.mem_write(n.owner,struct.pack('<I',H+0x1200));u.mem_write(H+0x1294,struct.pack('<I',entry));u.mem_write(n.owner+0x8c,struct.pack('<I',0xb8))
  u.mem_write(n.sp,struct.pack('<7I',STOP,0,0,0,0,0,0));u.reg_write(UC_X86_REG_ECX,n.owner);n.execute(entry)
  assert u.reg_read(UC_X86_REG_ESP)==n.sp+28
  if cls is OldNative:
   assert u.mem_read(n.owner+size,8)==b'OWNEREND'
   assert any(e[0]==0x2715 for e in n.events)==(len(name)<128)
  else:
   assert u.mem_read(n.owner+size,8)==b'CANARY!!'
   assert bool(n.sent)==(len(name)<128)
  if len(name)<128:assert n.z(n.owner+offset)==name
 print('PASS Enter-key native reentry:',hex(entry),'full names, byte bound, owner and stack guards')
