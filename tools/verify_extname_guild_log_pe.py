#!/usr/bin/env python3
"""Execute the native 197-byte guild-log parser and220-byte owners through growth/clear/UI."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args();sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
p=pefile.PE(args.pe);base=p.OPTIONAL_HEADER.ImageBase;B=0x15e8198;STACK=0x60000000;HEAP=0x40000000;STOP=0x61000000
def dw(u,a,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(a,4*n)))
class Native:
 def __init__(self):
  self.u=u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096);u.mem_map(base,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,p.get_memory_mapped_image());u.mem_map(STACK,0x20000);u.mem_map(HEAP,0x100000);u.mem_map(STOP,4096)
  self.sp=STACK+0x10000;u.reg_write(UC_X86_REG_ESP,self.sp);u.reg_write(UC_X86_REG_EBP,STACK+0x18000);u.reg_write(UC_X86_REG_EDI,HEAP+0xf0000);u.mem_write(0xfc1824,struct.pack('<I',STOP+0x100))
  self.cursor=HEAP;self.allocations={};self.strings=set();self.display=[];self.stop=STOP;u.hook_add(UC_HOOK_CODE,self.hook)
 def alloc(self,n):
  a=self.cursor;self.cursor+=(n+31)&~31;assert self.cursor<HEAP+0xd0000;self.allocations[a]=n;return a
 def z(self,a):
  for n in range(1024):
   if self.u.mem_read(a+n,1)==b'\0':return bytes(self.u.mem_read(a,n))
  raise AssertionError('unterminated')
 def getstr(self,a):
  length,cap=dw(self.u,a+16,2);ptr=dw(self.u,a)[0]if cap>=16 else a;return bytes(self.u.mem_read(ptr,length))
 def setstr(self,a,v):
  if len(v)<16:self.u.mem_write(a,v+bytes(16-len(v))+struct.pack('<II',len(v),15));return
  ptr=self.alloc(len(v)+1);self.strings.add(ptr);self.u.mem_write(ptr,v+b'\0');self.u.mem_write(a,struct.pack('<I',ptr)+bytes(12)+struct.pack('<II',len(v),len(v)))
 def ret(self,n=0,value=0):
  u=self.u;s=u.reg_read(UC_X86_REG_ESP);pc=dw(u,s)[0];u.reg_write(UC_X86_REG_ESP,s+4+4*n);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,_):
  if pc==self.stop or pc==0xc9e1dd:u.emu_stop();return
  s=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc==0x6a1b20:
   u.mem_write(ecx,bytes(256));self.setstr(ecx+44,b'');self.setstr(ecx+68,b'');self.ret(0,ecx)
  elif pc==0x6a2ce0:
   out=dw(u,s+4)[0];self.setstr(out,b'Full native item title '+str(dw(u,ecx+28)[0]).encode());self.ret(2,out)
  elif pc==0x4f1940:
   ptr,length=dw(u,s+4,2);self.setstr(ecx,bytes(u.mem_read(ptr,length)));self.ret(2,ecx)
  elif pc==0x4e52a0:self.setstr(ecx,self.getstr(dw(u,s+4)[0]));self.ret(1,ecx)
  elif pc in (0x4f08f0,0x4e78c0):
   if dw(u,ecx+20)[0]>=16:
    ptr=dw(u,ecx)[0];assert ptr in self.strings,('double/foreign string free',hex(ptr),hex(ecx));self.strings.remove(ptr);self.allocations.pop(ptr)
   self.setstr(ecx,b'');self.ret()
  elif pc==0xdbbc4f:self.ret(0,self.alloc(dw(u,s+4)[0]))
  elif pc==0xdbbc7f:
   ptr=dw(u,s+4)[0];assert ptr in self.allocations,('foreign sized free',hex(ptr));self.allocations.pop(ptr);self.strings.discard(ptr);self.ret()
  elif pc==STOP+0x100:
   value,out,radix=dw(u,s+4,3);assert radix==10;u.mem_write(out,str(value).encode()+b'\0');self.ret(0,out)
  elif pc==0x830ba0:self.display.append(self.z(dw(u,s+4)[0]));self.ret(1)
  elif pc==0x8308d0:self.ret(3)
  elif pc==0xa25a70:self.ret(9)
  elif pc==0xe07d51:
   dst,value,length=dw(u,s+4,3);u.mem_write(dst,bytes([value])*length);self.ret(0,dst)
  elif pc==0x529850:
   dst=dw(u,s+4)[0];u.mem_write(dst,b'1/1\0');self.ret(0,3)
  elif pc in (0x5a4300,0xdbbbd4):self.ret()
  elif pc==0xa39340:self.ret(1,0)
 def run(self,pc,argument=None,receiver=None):
  u=self.u;u.reg_write(UC_X86_REG_ESP,self.sp);u.mem_write(self.sp,struct.pack('<I',STOP));self.stop=STOP
  if argument is not None:u.mem_write(self.sp+4,struct.pack('<I',argument))
  if receiver is not None:u.reg_write(UC_X86_REG_ECX,receiver)
  try:u.emu_start(pc,0,count=2000000)
  except Exception:print('Native failure',hex(u.reg_read(UC_X86_REG_EIP)),list(map(hex,dw(u,u.reg_read(UC_X86_REG_ESP),5))));raise
  assert u.reg_read(UC_X86_REG_EIP)in(STOP,0xc9e1dd),hex(u.reg_read(UC_X86_REG_EIP))
 def rows(self,v):
  a,end,cap=dw(self.u,v,3);assert (end-a)%220==0 and cap>=end
  return [bytes(self.u.mem_read(x,220))for x in range(a,end,220)]
def packet(rows,result):
 out=bytearray(8+197*len(rows));struct.pack_into('<HHHH',out,0,0x9da,len(out),result,len(rows))
 for i,(key,name,stamp)in enumerate(rows):
  at=8+197*i;struct.pack_into('<III',out,at,key,1201,key+10);out[at+12]=key%2;struct.pack_into('<IQBH',out,at+13,7,0x1122334455667788,1,4);struct.pack_into('<IIII',out,at+28,1,2,3,4);out[at+44:at+44+len(name)]=name;out[at+172:at+172+len(stamp)]=stamp;out[at+196]=1
 return bytes(out)
n=Native();u=n.u
source=[(i,b'Player%'+b'N'*119+bytes([65+i%26]),f'2026-09-{1+i%28:02d} 12:34:56'.encode())for i in range(1,41)]
for items,flag in ((source[:20],0),(source[20:],1)):
 u.mem_write(B,packet(items,flag));n.run(0xcb1d50,B,HEAP+0xf0000)
 assert u.reg_read(UC_X86_REG_ESP)==n.sp+8,'parser stack'
all_rows=n.rows(0x15fffe0);assert len(all_rows)==40
expected={key:(name,stamp)for key,name,stamp in source}
for row in all_rows:
 key=struct.unpack_from('<I',row)[0];name,stamp=expected[key];assert row[9:137]==name+b'\0';assert row[137:161].split(b'\0')[0]==stamp;assert row[188]==1 and struct.unpack_from('<II',row,192)==(4,7);assert struct.unpack_from('<IIII',row,200)==(1,2,3,4);assert row[216]==1
assert [r[137:161]for r in all_rows]==sorted([r[137:161]for r in all_rows],reverse=True)
assert len(n.rows(0x15fffec))==20 and len(n.rows(0x15ffff8))==20
owned=[]
for v in (0x15fffe0,0x15fffec,0x15ffff8):
 begin,end,_=dw(u,v,3)
 for a in range(begin,end,220):owned.append(dw(u,a+164)[0]);assert n.getstr(a+164).startswith(b'Full native item title')
assert len(owned)==len(set(owned))==80 and set(owned)==n.strings
print('PASS native09DA40rows,197wire/220owner,128names,allfields,descendingtime,3vectors,80uniqueownedstrings')
for tab,v in enumerate((0x15fffe0,0x15fffec,0x15ffff8)):
 window=HEAP+0xf0000;u.mem_write(window,bytes(1024));n.display=[]
 for column in (0xb0,0xd8,0x100,0x128):
  for row in range(11):u.mem_write(window+column+4*row,struct.pack('<I',HEAP+0xf8000))
 for off,val in ((0x154,tab),(0x15c,1),(0x160,1),(0x164,1),(0x168,1),(0x16c,0),(0x170,1),(0x178,40),(0x17c,20),(0x180,20)):
  u.mem_write(window+off,struct.pack('<I',val))
 u.mem_write(window+0x184,struct.pack('<III',HEAP+0xf9000,HEAP+0xf9000,HEAP+0xf9100));n.run(0x90ee70,receiver=window)
 expected_names=[r[9:137].split(b'\0')[0]for r in n.rows(v)[:10]]
 assert [x for x in n.display if x.startswith(b'Player%')]==expected_names,(tab,n.display,expected_names)
 assert len(n.strings)==80,'UI leaked or stole record string';print('PASS native log UI tab',tab,'10 distinct full canonical names')
for v in (0x15fffe0,0x15fffec,0x15ffff8):n.run(0x917790,receiver=v);assert not n.rows(v)
assert not n.strings;print('PASS native vector growth/move/copy and full cleanup without duplicate or leaked item strings')
entry=struct.unpack_from('<I',p.get_memory_mapped_image(),0xcaa2e0-base+(0x9da-0x73)*4)[0]
for length,count in ((7,0),(8,1),(204,1),(205,2)):
 malformed=bytearray(max(length,8));struct.pack_into('<HHHH',malformed,0,0x9da,length,0,count);u.mem_write(B,bytes(malformed));n.run(entry);assert not n.rows(0x15fffe0)
print('PASS malformed log lengths rejected before native allocation')
legacy=struct.unpack_from('<I',p.get_memory_mapped_image(),0xcaa2e0-base+(0xb3e-0x73)*4)[0];assert legacy==0xc9e1dd
print('PASS server-unemitted CItem0B3E variant gated from widened owner')
for leaf,record,direct in ((0xf250fb,-0x600,True),(0xf25106,-0x600,False),(0xf2511c,-0x600,True),(0xf25148,-0x700,True),(0xf25153,-0x700,False),(0xf25169,-0x700,True),(0xf2518a,-0x800,False),(0xf25195,-0x800,False),(0xf251a0,-0x800,True)):
 cleanup=Native();frame=STACK+0x18000;cleanup.setstr(frame+record+164,b'Full owned title in exception cleanup');cleanup.run(leaf);assert not cleanup.strings;print('PASS native log unwind leaf',hex(leaf))
class Cookie(Native):
 def __init__(self):super().__init__();self.checked=[]
 def hook(self,u,pc,size,user):
  if pc==0xdbbbd4:
   self.checked.append(u.reg_read(UC_X86_REG_ECX));saved=u.reg_read(UC_X86_REG_EAX);self.ret(0,saved);return
  super().hook(u,pc,size,user)
check=Cookie();u=check.u;frame=STACK+0x18000;cookie=dw(u,0x122b924)[0];u.mem_write(check.sp+8,struct.pack('<I',frame-12));u.mem_write(frame-0x8c4,struct.pack('<I',cookie^frame));u.mem_write(frame-16,struct.pack('<I',cookie^frame));check.stop=0xe07d45;u.emu_start(0xf251b0,0,count=1000);assert check.checked==[cookie,cookie];assert u.reg_read(UC_X86_REG_EAX)==0x11c0930;print('PASS native expanded log-frame GS/EH cookies')
