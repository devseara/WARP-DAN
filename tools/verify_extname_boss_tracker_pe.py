#!/usr/bin/env python3
"""Actual boss-tracker native handler: full names, flags, coordinates, timing and bounds."""
import runpy,struct
from pathlib import Path
scope=runpy.run_path(str(Path(__file__).with_name('verify_character_info_pe.py')))
Native=scope['Native'];OBJECT=scope['OBJECT'];ints=scope['ints']
from unicorn.x86_const import *
class Boss(Native):
 def __init__(self,long_format=False):super().__init__();self.messages=[];self.long_format=long_format
 def hook(self,u,pc,size,unused):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0xa9ed30:
   key=ints(u,sp+4)[0]
   fmt={0x4c7:b'No boss',0x4c9:b'Alive: %s',0x4ed:b'Soon: %s',0x4c8:b'Respawn %s in %u:%u'}[key]
   if self.long_format and key!=0x4c7:fmt=b'L'*600+fmt
   p=self.cursor;self.cursor+=len(fmt)+16;u.mem_write(p,fmt+b'\0');self.ret(0,p);return
  if pc==0x529850:raise AssertionError('Unbounded boss formatter reached')
  if pc==0x59cdf0:
   dst,cap,count,fmt,ptr=ints(u,sp+4,5);assert cap==512 and count==0xffffffff
   text=self.z(fmt);values=(self.z(ptr),)+tuple(ints(u,sp+24,2)) if b'%u' in text else (self.z(ptr),)
   out=(text%values)[:511];u.mem_write(dst,out+b'\0');self.ret(0,len(out));return
  if pc==0xa4ad20:
   kind,ptr=ints(u,sp+4,2)
   if ptr:self.messages.append((kind,self.z(ptr)))
   self.ret(5);return
  super().hook(u,pc,size,unused)
def packet(name,flag,hours=2,minutes=3):
 p=bytearray(147);struct.pack_into('<HBIIHHHH',p,0,0x293,flag,123,456,hours,minutes,0,0);p[19:19+len(name)]=name;return bytes(p)
for name in (b'Zombie',b'Percent%name',b'N'*127):
 for flag in range(5):
  n=Boss();n.run(0xcb7360,packet(name,flag))
  assert ints(n.u,OBJECT+0x5c4,2)==((123,456) if flag in (1,2) else (0xffffffff,0xffffffff))
  if flag in (2,3):assert all(name in text for _,text in n.messages) and len(n.messages)==2,n.messages
  elif flag in (1,4):assert not n.messages
 print('PASS boss tracker:',len(name),'name bytes, all flags, coordinates and respawn name')
n=Boss();n.run(0xcb7360,packet(b'Z'*127,3,0,1));assert all(text==b'Soon: '+b'Z'*127 for _,text in n.messages)
n=Boss(True);n.run(0xcb7360,packet(b'Z'*127,3));assert all(len(text)==511 for _,text in n.messages)
n=Boss();p=bytearray(packet(b'X'*127,2));p[146]=88;n.run(0xcb7360,bytes(p));assert not n.messages
print('PASS boss tracker: soon branch, bounded translation, unterminated128-byte name rejected')
