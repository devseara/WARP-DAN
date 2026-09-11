#!/usr/bin/env python3
"""Run native guild/clan parsers from the final PE; stub only external allocation/UI services."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument("--pe",required=True);ap.add_argument("--deps",required=True);args=ap.parse_args()
sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(args.pe);base=pe.OPTIONAL_HEADER.ImageBase
B=0x15e8198;HEAP=0x40000000;STACK=0x60000000;STOP=0x61000000;STRCPY=STOP+0x100
def dw(u,p,n=1):return struct.unpack("<"+"I"*n,bytes(u.mem_read(p,n*4)))
class Native:
 def __init__(self):
  self.u=u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,0x1000)
  u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
  u.mem_map(HEAP,0x40000);u.mem_map(STACK,0x20000);u.mem_map(STOP,0x1000)
  u.reg_write(UC_X86_REG_ESP,STACK+0x10000);u.reg_write(UC_X86_REG_EBP,STACK+0x18000);u.reg_write(UC_X86_REG_EDI,HEAP+0x30000)
  self.cursor=HEAP+0x4000;self.cache={};self.assigned=[];self.members=[];self.messages=[];self.message_format=b'Friend notification (%s).'
  self.clan=HEAP+0x1000;self.sentinel=HEAP+0x2000;self.tree=HEAP+0x2100
  u.mem_write(0x159c07c,struct.pack("<I",self.clan));self.reset_clan()
  u.mem_write(0x159c284,struct.pack("<II",self.tree,0));u.mem_write(self.tree,struct.pack("<III",self.tree,self.tree,self.tree));u.mem_write(self.tree+13,b"\x01")
  u.mem_write(0xfc1b5c,struct.pack("<I",STRCPY))
  u.hook_add(UC_HOOK_CODE,self.hook)
 def alloc(self,n):
  p=self.cursor;self.cursor+=(n+31)&~31;assert self.cursor<HEAP+0x30000;return p
 def z(self,p):
  for n in range(1024):
   if self.u.mem_read(p+n,1)==b"\0":return bytes(self.u.mem_read(p,n))
  raise AssertionError("Unterminated native string")
 def getstr(self,p):
  length,cap=dw(self.u,p+16,2);ptr=dw(self.u,p)[0] if cap>=16 else p
  return bytes(self.u.mem_read(ptr,length))
 def setstr(self,p,value):
  ptr=self.alloc(len(value)+1);self.u.mem_write(ptr,value+b"\0")
  self.u.mem_write(p,struct.pack("<I",ptr)+bytes(12)+struct.pack("<II",len(value),max(len(value),16)))
 def reset_clan(self):
  self.u.mem_write(self.clan,bytes(0x100))
  for x in (4,28,64):self.u.mem_write(self.clan+x+20,struct.pack("<I",15))
  self.u.mem_write(self.clan+96,struct.pack("<II",self.sentinel,0))
  self.u.mem_write(self.sentinel,struct.pack("<II",self.sentinel,self.sentinel))
 def ret(self,n=0,value=0):
  sp=self.u.reg_read(UC_X86_REG_ESP);pc=dw(self.u,sp)[0]
  self.u.reg_write(UC_X86_REG_ESP,sp+4+n*4);self.u.reg_write(UC_X86_REG_EAX,value);self.u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,_):
  if pc in (STOP,0xc9e1dd,0xc9e1d7):u.emu_stop();return
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc==0xa9ed30:
   p=self.alloc(len(self.message_format)+1);u.mem_write(p,self.message_format+b"\0");self.ret(0,p);return
  if pc==0x59cdf0:
   dst,cap,count,fmt,value=dw(u,sp+4,5)
   assert cap in (24,512) and count==0xffffffff
   output=self.z(fmt).replace(b"%s",self.z(value))[:cap-1];u.mem_write(dst,output+b"\0");self.ret(0,len(output));return
  if pc==0xa4ad20:
   kind,ptr=dw(u,sp+4,2)
   if ptr:self.messages.append(self.z(ptr))
   self.ret(5);return
  if pc==0xc99560:
   u.mem_write(ecx,bytes(80));self.setstr(ecx+12,b"");self.ret(0,ecx);return
  if pc==0x7007e0:self.ret();return
  if pc==0x4f1940:
   ptr,n=dw(u,sp+4,2);v=bytes(u.mem_read(ptr,n));self.assigned.append((ecx,v));self.setstr(ecx,v);self.ret(2,ecx);return
  if pc==0x4e5330:self.setstr(ecx,self.z(dw(u,sp+4)[0]));self.ret(1,ecx);return
  if pc==0x4e52a0:self.setstr(ecx,self.getstr(dw(u,sp+4)[0]));self.ret(1,ecx);return
  if pc==0x5e7260:self.ret(1,0);return
  if pc==0xc9c280:
   key=dw(u,sp+4)[0];self.cache[key]=self.getstr(sp+8).split(b"\0",1)[0];self.ret();return
  if pc==0x5e6df0:
   out,key=dw(u,sp+4,2);self.setstr(out,self.cache[key]);self.ret(0,out);return
  if pc==0xd7fe40:
   p=self.alloc(10);u.mem_write(p,b"SelfName\0");self.ret(0,p);return
  if pc==0x4dcc30:self.ret(0,0);return
  if pc in (0xdbbc4f,0x4f10a0):self.ret(0,self.alloc(dw(u,sp+4)[0]));return
  if pc==0xe07d4b:
   dst,src,n=dw(u,sp+4,3);u.mem_write(dst,bytes(u.mem_read(src,n)));self.ret(0,dst);return
  if pc==0xa7e120:self.reset_clan();self.ret();return
  if pc==0x5a2650:self.ret(7);return
  if pc==0xd54940:
   p=dw(u,sp+4)[0];self.members.append((dw(u,p+4,2),self.getstr(p+12)));self.ret(1);return
  if pc==0xa82e60:
   p=dw(u,sp+4)[0];self.members.append((dw(u,p,2),self.getstr(p+8).split(b"\0",1)[0]));self.ret(1);return
  if pc==0x513510:
   parent,left,node=dw(u,sp+4,3);u.mem_write(node,struct.pack("<III",self.tree,parent,self.tree))
   if parent==self.tree:u.mem_write(self.tree+4,struct.pack("<I",node))
   else:u.mem_write(parent+(0 if left else 8),struct.pack("<I",node))
   u.mem_write(0x159c288,struct.pack("<I",dw(u,0x159c288)[0]+1));self.ret(3,node);return
  if pc==STRCPY:
   dst,cap,src=dw(u,sp+4,3);v=self.z(src);assert len(v)<cap,("strcpy_s range",len(v),cap)
   u.mem_write(dst,v+b"\0");self.ret();return
  stubs={0x4f08f0:0,0xdbbc7f:0,0xdbbbd4:0,0xa85be0:1,0x61ddc0:2,0xa38190:0,0xa83100:0,0xd56220:0,0xd76570:0}
  if pc in stubs:self.ret(stubs[pc]);return
 def run(self,entry,packet,dispatch=False):
  u=self.u;u.mem_write(B,bytes(packet));sp=u.reg_read(UC_X86_REG_ESP)
  if not dispatch:u.mem_write(sp,struct.pack("<II",STOP,B));u.reg_write(UC_X86_REG_ECX,HEAP+0x30000)
  try:u.emu_start(entry,0,count=500000)
  except Exception:
   print("Native failure EIP",hex(u.reg_read(UC_X86_REG_EIP)),"stack",list(map(hex,dw(u,u.reg_read(UC_X86_REG_ESP),6))));raise
  assert u.reg_read(UC_X86_REG_EIP) in (STOP,0xc9e1d7,0xc9e1dd)
  assert u.reg_read(UC_X86_REG_ESP)==sp+(0 if dispatch else 8),"Native stack imbalance"
def guild():
 n=Native();p=bytearray(326);struct.pack_into("<H",p,0,0xb7b)
 for i in range(11):struct.pack_into("<I",p,2+4*i,i+1)
 p[46:174]=b"G"*127+b"\0";p[174:187]=b"prontera.gat\0\0";struct.pack_into("<II",p,190,12,987);p[198:326]=b"M"*127+b"\0"
 n.run(0xce1f40,p)
 assert n.getstr(0x159c188)==b"G"*127
 assert n.getstr(0x159c1a0)==b"M"*127
 assert dw(n.u,0x159c230)[0]==1 and dw(n.u,0x159c1e8)[0]==2
 assert dw(n.u,0x159c258)[0]==987
 print("PASS guild: full names and original scalar fields")
def roster():
 n=Native();p=bytearray(4+2*162);struct.pack_into("<HH",p,0,0xb7d,len(p));wanted=[]
 for i in range(2):
  at=4+i*162;struct.pack_into("<II",p,at,100+i,200+i);v=bytes([65+i])*127;p[at+34:at+162]=v+b"\0";wanted.append(((100+i,200+i),v))
 n.run(0xce37c0,p);assert n.members==wanted,n.members
 print("PASS guild roster: two full-name records, matching IDs and stride")
def positions():
 n=Native();p=bytearray(4+2*28);struct.pack_into("<HH",p,0,0x166,len(p))
 for i in range(2):
  at=4+i*28;struct.pack_into("<I",p,at,i);p[at+4:at+28]=bytes([65+i])*23+b"\0"
 n.run(0xce5450,p)
 assert dw(n.u,0x159c288)[0]==2
 values=[v for obj,v in n.assigned if len(v)==23]
 assert values==[b"A"*23,b"B"*23],values
 print("PASS guild positions: stock labels and native map entries")
def clan():
 n=Native();p=bytearray(74+2*24);struct.pack_into("<HHI",p,0,0x98a,len(p),123)
 p[8:32]=b"C"*23+b"\0";p[32:56]=b"M"*23+b"\0";p[56:69]=b"prontera.gat\0\0";p[72:74]=bytes([1,1])
 p[74:98]=b"A"*23+b"\0";p[98:122]=b"O"*23+b"\0"
 entry=struct.unpack("<I",pe.get_data(0xcaa2e0+(0x98a-0x73)*4-base,4))[0];n.run(entry,p,True)
 assert n.getstr(n.clan+4)==b"C"*23 and n.getstr(n.clan+28)==b"M"*23
 assert n.getstr(n.clan+64)==b"prontera.gat"
 assert dw(n.u,n.clan+100)[0]==2
 node=dw(n.u,n.sentinel)[0];found=[]
 while node!=n.sentinel:
  assert len(found)<3;found.append((dw(n.u,node+8)[0],n.getstr(node+12)));node=dw(n.u,node)[0]
 assert sorted(found)==[(0,b"A"*23),(1,b"O"*23)],found
 print("PASS stock clan: 24-byte labels, map, alliance/opposition strings and native list ownership")
def friends():
 n=Native();p=bytearray(4+2*136);struct.pack_into("<HH",p,0,0x201,len(p));wanted=[]
 for i in range(2):
  at=4+i*136;value=bytes([65+i])*127
  struct.pack_into("<II",p,at,100+i,200+i);p[at+8:at+136]=value+b"\0";wanted.append(((100+i,200+i),value))
 entry=struct.unpack("<I",pe.get_data(0xcaa2e0+(0x201-0x73)*4-base,4))[0]
 n.run(entry,p,True);assert n.members==wanted,n.members
 print("PASS friends: full 127-byte names, IDs, record count, native objects")
def friend_ack():
 for value in (b"F"*127,b"Percent%name"):
  for result in range(10):
   n=Native();p=bytearray(140);struct.pack_into("<HHII",p,0,0x209,result,123,456);p[12:12+len(value)]=value
   n.run(0xcb5220,p)
   if result==0:assert n.members==[((123,456),value)],n.members
   else:assert not n.members
   if result in (0,1,3,4,6,7,8):assert n.messages==[b"Friend notification ("+value+b")."],n.messages
   elif result in (5,9):assert not n.messages
 n=Native();n.message_format=b"X"*900+b"%s";p=bytearray(140);struct.pack_into("<HHII",p,0,0x209,0,123,456);p[12:139]=b"F"*127
 n.run(0xcb5220,p);assert len(n.messages[0])==511 and n.members==[((123,456),b"F"*127)]
 print("PASS friend ACK: all result routes, full/percent names, bounded notification and native objects")

def name_by_gid():
 for flag in range(6):
  n=Native();p=bytearray(136);struct.pack_into("<HHI",p,0,0xaf7,flag,456);p[8:135]=b"N"*127
  n.run(0xcb3220,p)
  if flag==3:assert n.cache[456]==b"N"*127,n.cache
  elif flag==4:assert n.cache[456]==n.message_format,n.cache
  else:assert not n.cache
 print("PASS name-by-GID: full name cache, fallback and ignored flags")

class FriendRequestNative(Native):
 def __init__(self,blocked=False):
  super().__init__();self.blocked=blocked;self.replies=[]
  self.dialog=HEAP+0x30000;self.child=HEAP+0x31000;self.vtable=HEAP+0x32000
  self.u.mem_write(self.dialog,struct.pack("<I",self.vtable));self.u.mem_write(self.dialog+0xb8,struct.pack("<I",self.child))
  self.u.mem_write(self.vtable+0x94,struct.pack("<I",0x8c4030))
  self.u.mem_write(self.child,struct.pack("<I",self.vtable+0x400))
  self.u.mem_write(self.vtable+0x400+0xdc,struct.pack("<I",STOP+0x200))
  self.u.mem_write(self.vtable+0x400+0x94,struct.pack("<I",STOP+0x210))
  self.u.mem_write(0x121333c,struct.pack("<I",self.child))
  self.u.mem_write(self.vtable+0x400+0x18,struct.pack("<I",STOP+0x220))
 def hook(self,u,pc,size,unused):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0x68ea70:self.ret(0,int(self.blocked));return
  if pc==0xa72830:self.ret(0,0);return
  if pc==0xa39340:
   assert dw(u,sp+4)[0]==0x6d;self.ret(1,self.dialog);return
  if pc==STOP+0x200:self.ret();return
  if pc==STOP+0x210:
   command,event,ptr,width,x,y=dw(u,sp+4,6)
   assert event==0x1d;self.messages.append(self.z(ptr));self.ret(6);return
  if pc==STOP+0x220:self.replies.append(dw(u,sp+4,5));self.ret(5);return
  super().hook(u,pc,size,unused)

def friend_request():
 for value in (b"R"*127,b"Percent%name",b""):
  for blocked in (False,True):
   n=FriendRequestNative(blocked);p=bytearray(138);struct.pack_into("<HII",p,0,0x207,123,456);p[10:10+len(value)]=value
   entry=struct.unpack("<I",pe.get_data(0xcaa2e0+(0x207-0x73)*4-base,4))[0];n.run(entry,p,True)
   if blocked:assert n.replies==[(0xaf,123,456,0,0)] and not n.messages
   else:
    assert n.messages==[b"Friend notification ("+value+b")."],n.messages
    assert dw(n.u,n.dialog+0xc0,2)==(123,456)
 n=FriendRequestNative();n.message_format=b"Y"*900+b"%s";p=bytearray(138);struct.pack_into("<HII",p,0,0x207,123,456);p[10:137]=b"R"*127
 n.run(0xca75b8,p,True);assert len(n.messages[0])==511
 print("PASS friend request: real dispatch/dialog, full names, IDs, auto-rejection and bounded text")

guild();roster();positions();clan();friends();friend_ack();name_by_gid();friend_request()
