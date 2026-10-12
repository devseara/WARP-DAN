#!/usr/bin/env python3
"""Native quest parser and sole canonical-name ownership lifecycle regression.

Runs full9F8/9F9 parsers, native copy/move constructors and base destructors.
Only external CRT/UI/Lua/tree services are modeled. Rename gate runs first.
"""
from verify_extname_character_rename_pe import Native as Base,dw,H,S,STOP,pe,BASE
import struct
from unicorn.x86_const import *
B=0x15e8198;TM=STOP+1792
class Native(Base):
 def __init__(self):
  super().__init__(b'QuestFixture');self.nodes=[];self.trace=[];self.live={};self.freed=[];self.alloc_fail=False;self.reject_count=0
  self.u.mem_write(0x1254d90,struct.pack('<I',H+0xa000));self.u.mem_write(H+0xa004,struct.pack('<II',H+0xa100,0));self.u.mem_write(H+0xa100,struct.pack('<III',H+0xa100,H+0xa100,H+0xa100)+b'\0\1')
  self.u.mem_write(0xfc1b88,struct.pack('<I',TM));self.u.mem_write(H+0xa200,bytes(64))
 def hook(self,u,pc,size,data):
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc in (0xcfe83c,0xcfe850,0xcfe942,0xcfe9e6,0xcfe81d):self.trace.append((hex(pc),hex(u.reg_read(UC_X86_REG_EDI)),hex(dw(u,u.reg_read(UC_X86_REG_EBP)-0x22c)[0])))
  if pc==0xcfe4d0:self.trace.append((hex(u.reg_read(UC_X86_REG_EDI)),bytes(u.mem_read(u.reg_read(UC_X86_REG_EDI),15))))
  if pc==0xc9e1dd:u.emu_stop();return
  if pc==0x647300:self.ret(2,0);return
  if pc in (0x6471b0,):self.ret();return
  if pc==TM:self.ret(0,H+0xa200);return
  if pc in (0xdbbc4f,0x4f10a0):
   n=dw(u,sp+4)[0]
   if n==392 and self.alloc_fail:self.reject_count+=1;u.emu_stop();return
   q=self.alloc(n);self.live[q]=n;u.mem_write(q,b'\xA5'*n);self.ret(1 if pc==0x4f10a0 else 0,q);return
  if pc==0xdbbc7f:
   q,n=dw(u,sp+4,2)
   if n==392:assert q in self.live and self.live[q]==392,('double free',hex(q));self.freed.append(q);del self.live[q]
   self.ret();return
  if pc==0x4f1940:
   q,n=dw(u,sp+4,2);self.setstr(ecx,bytes(u.mem_read(q,n)));self.ret(2,ecx);return
  if pc==0x4e52a0:self.setstr(ecx,self.getstr(dw(u,sp+4)[0]));self.ret(1,ecx);return
  if pc==0x61fdd0:u.mem_write(ecx,bytes(12));self.ret(1,ecx);return
  if pc==0xa9a7d0:self.ret(0,0);return
  if pc==0x64c210:self.ret(1,0);return
  if pc==0x633ce0:
   out,key=dw(u,sp+4,2);u.mem_write(out,struct.pack('<III',H+0xa100,0,H+0xa100));self.ret(2,out);return
  if pc==0x649590:
   left,parent,node=dw(u,sp+4,3);self.nodes.append(node);self.ret(3,node);return
  if pc in (0x649d80,0x583950):self.ret();return
  if pc==0x59cdf0:
   dst,cap,count,fmt,src=dw(u,sp+4,5);assert cap==128 and count==0xffffffff
   value=self.z(src)[:127];u.mem_write(dst,value+b'\0');self.ret(0,len(value));return
  if pc==0xa94930:
   import re
   out,fmt=dw(u,sp+4,2);values=iter(dw(u,sp+12,8))
   def part(match):
    token=match[0]
    if token==b'%%':return b'%'
    v=next(values);return self.z(v) if token.endswith(b's') else str(v).encode()
   result=re.sub(rb'%[-+0-9.]*[sdu]|%%',part,self.z(fmt));self.setstr(out,result);self.ret(0,out);return
  if pc==0xa39340:self.ret(1,0);return
  if pc==0xa4ad20:self.ret(5);return
  super().hook(u,pc,size,data)
 def dispatch(self,p):
  self.u.mem_write(B,p);self.u.reg_write(UC_X86_REG_ESP,self.sp);pid=struct.unpack_from('<H',p)[0];self.execute(dw(self.u,0xcaa2e0+(pid-0x73)*4)[0]);assert self.u.reg_read(UC_X86_REG_ESP)==self.sp
 def call(self,pc,owner,*values):
  self.u.reg_write(UC_X86_REG_ECX,owner);self.u.reg_write(UC_X86_REG_ESP,self.sp);self.u.mem_write(self.sp,struct.pack('<'+'I'*(len(values)+1),STOP,*values));self.execute(pc);assert self.u.reg_read(UC_X86_REG_ESP)==self.sp+4+4*len(values),(hex(pc),'stack')
 def names(self,record):
  p=dw(self.u,record+0xe6)[0];assert p;return [self.z(p+128*i) for i in range(3)]
 def arrays(self):return [p for p,n in self.live.items() if n==392]
names=[b'Long%'+b'N'*122,b'A'+bytes.fromhex('e7958c')*42,b'NPC Objective']
def objective(i,listing):return struct.pack('<IIIhhh',123000+i,0,1002 if i==0 else 999999,1,99,3+i)+(struct.pack('<H',10+i) if listing else b'')+names[i].ljust(128,b'\0')
def listed(qid=123,count=3):return struct.pack('<IBIIH',qid,1,1000,2000,count)+b''.join(objective(i,True) for i in range(count))
for listing in (True,False):
 n=Native()
 if listing:
  r=listed()+listed(124);p=struct.pack('<HHI',0x9f8,8+len(r),2)+r
 else:p=struct.pack('<HIBIIH',0x9f9,123,1,1000,2000,3)+b''.join(objective(i,False) for i in range(3))
 n.dispatch(p);assert len(n.nodes)==(2 if listing else 1),n.nodes
 assert len(n.arrays())==len(n.nodes),('parser temporary leak',[(hex(p),dw(n.u,p,2)) for p in n.arrays()],[(hex(p),hex(dw(n.u,p+24+0xe6)[0]),bytes(n.u.mem_read(p+24+0xd2,1)),dw(n.u,p+16)[0]) for p in n.nodes],n.freed,n.trace)
 record=n.nodes[0]+24;assert n.names(record)==names
 for index,name in enumerate(names):
  out=H+0x78000+index*32;n.call(0xc85720,0,out,record,index);assert n.getstr(out).startswith(name),n.getstr(out)
 print('PASS native quest UI objective-label formatter preserves all three full names')
 assert dw(n.u,record+0xd4,3)==(1002,999999,999999)
 clone=H+0x70000;move=H+0x74000;n.u.mem_write(clone,bytes(512));n.u.mem_write(move,bytes(512));n.call(0x640780,clone,record)
 assert n.names(clone)==names and dw(n.u,clone+0xe6)[0]!=dw(n.u,record+0xe6)[0]
 n.call(0x640470,move,clone);assert dw(n.u,clone+0xe6)[0]==0 and n.names(move)==names
 n.call(0x641e10,clone);assert n.names(move)==names,'moved-from destructor damaged owner'
 for node in n.nodes:n.call(0x641a80,node+16)
 assert n.names(move)==names,'source destruction damaged deep copy'
 # Execute the compiler's actual copy-constructor unwind tail.
 frame=S+0x10000;n.u.mem_write(frame-0x10,struct.pack('<I',move));n.u.reg_write(UC_X86_REG_EBP,frame);n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.mem_write(n.sp,struct.pack('<I',STOP));n.execute(0xe43fd0);assert n.u.reg_read(UC_X86_REG_ESP)==n.sp+4
 assert not n.arrays(),('lifecycle leak',n.arrays())
 # Registry gate must not inspect an E6 field on unrelated180-byte base objects.
 bare=H+0x80000;n.u.mem_write(bare,bytes(180));n.u.mem_write(bare+0xe6,b'GUAR');n.call(0x641e10,bare);assert n.u.mem_read(bare+0xe6,4)==b'GUAR'
 print('PASS native quest'+(' list' if listing else ' add')+': full128 names, parser-temporary cleanup, independent clone, move, base/owner destruction and no leaked name arrays')
for kind in ('short','count','objectives','name','trailing'):
 r=bytearray(listed());p=bytearray(struct.pack('<HHI',0x9f8,8+len(r),1)+r)
 if kind=='short':p=p[:20]
 elif kind=='count':struct.pack_into('<I',p,4,999)
 elif kind=='objectives':struct.pack_into('<H',p,21,4)
 elif kind=='name':p[43:171]=b'X'*128
 else:p+=b'X'
 struct.pack_into('<H',p,2,len(p));n=Native();n.dispatch(bytes(p));assert not n.nodes and not n.arrays();print('PASS invalid quest list rejected:',kind)
n=Native();p=struct.pack('<HIBIIH',0x9f9,123,1,1000,2000,4)+bytes(438);n.dispatch(p);assert not n.nodes and not n.arrays();print('PASS invalid quest add objective count rejected')

n=Native();r=listed();n.dispatch(struct.pack('<HHI',0x9f8,8+len(r),1)+r);source=n.nodes[0]+24;clone=H+0x70000;n.alloc_fail=True;n.u.reg_write(UC_X86_REG_ECX,clone);n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.mem_write(n.sp,struct.pack('<II',STOP,source));n.execute(0x640780);assert n.reject_count==1
n.alloc_fail=False;frame=S+0x10000;n.u.mem_write(frame-0x10,struct.pack('<I',clone));n.u.reg_write(UC_X86_REG_EBP,frame);n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.mem_write(n.sp,struct.pack('<I',STOP));n.execute(0xe43fd0);assert len(n.arrays())==1 and n.names(source)==names
n.call(0x641a80,n.nodes[0]+16);assert not n.arrays();print('PASS simulated allocation failure before registration and actual unwind tail preserve source ownership')