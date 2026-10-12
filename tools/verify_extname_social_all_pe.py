#!/usr/bin/env python3
"""Aggregate all social native-name gates, including block lists and unwind cleanup."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_guild_position_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Block(Position):
 def __init__(self):super().__init__();self.stops={0xc7a5bf,0xc7d125,0xc7a53b,0xc7a5df}
def block_names():
 for value in (b'Short',b'B'*127,b'Percent%name'):
  for entry,flag in [(0xc7a561,0),(0xc7a605,1)]:
   n=Block();u=n.u;obj=n.alloc(24)
   if len(value)<16:u.mem_write(obj,value+bytes(16-len(value))+struct.pack('<II',len(value),15))
   else:n.setstr(obj,value)
   u.reg_write(UC_X86_REG_EDI,obj);sp=u.reg_read(UC_X86_REG_ESP);u.emu_start(entry,0,count=100000);assert u.reg_read(UC_X86_REG_EIP)==0xc7a5bf and u.reg_read(UC_X86_REG_ESP)==sp
   assert n.sent==[struct.pack('<H',0xcf)+value+bytes(128-len(value))+bytes([flag])],n.sent
 for entry,passed in [(0xc7a52e,0xc7a53b),(0xc7a5d2,0xc7a5df)]:
  for size in (23,24,127,128):
   n=Block();u=n.u;u.reg_write(UC_X86_REG_EBX,n.dialog);u.mem_write(n.dialog+0x128,struct.pack('<I',size));u.emu_start(entry,0,count=20);assert u.reg_read(UC_X86_REG_EIP)==(passed if size<=127 else 0xc7d125)
 for count in (0,1,2):
  n=Block();p=bytearray(4+128*count);struct.pack_into('<HH',p,0,0xd4,len(p))
  for i in range(count):p[4+i*128:131+i*128]=bytes([65+i])*127
  n.run(route(0xd4),p,True);assert n.messages[1:]==[bytes([65+i])*127 for i in range(count)],n.messages
 n=Block();p=bytearray(5);struct.pack_into('<HH',p,0,0xd4,5);n.run(route(0xd4),p,True);assert not n.messages
 for entry in (0xe7eb60,0xe7eb68,0xe7eb70):
  n=Modern(True);u=n.u;sp=u.reg_read(UC_X86_REG_ESP);frame=STACK+0x18000;node=n.alloc(172);u.reg_write(UC_X86_REG_EBP,frame);u.mem_write(frame-0x38,struct.pack('<I',node));u.mem_write(sp,struct.pack('<I',STOP));u.emu_start(entry,0,count=10000);assert n.freed==[(node,172)] and u.reg_read(UC_X86_REG_ESP)==sp+4
 print('PASS whisper block: allow/deny131, full native list names, input127/128 boundary and all3 owned-node unwind paths')
block_names()
