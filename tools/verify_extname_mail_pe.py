#!/usr/bin/env python3
"""Exercise real RoDEX parser and outgoing 128-byte-name branches in a final PE.

External allocator, UI, std::string and socket services are stubbed. Native
packet field reads, name scans, vector arguments and control flow run in x86.
"""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args()
sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(args.pe);BASE=pe.OPTIONAL_HEADER.ImageBase
B=0x15e8198;H=0x40000000;S=0x60000000;STOP=0x61000000;TIME=STOP+256
def dw(u,p,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(p,n*4)))
class Native:
 def __init__(self):
  u=self.u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096)
  u.mem_map(BASE,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(BASE,pe.get_memory_mapped_image())
  u.mem_map(H,0x100000);u.mem_map(S,0x40000);u.mem_map(STOP,4096)
  self.ebp=S+0x30000;self.sp=S+0x10000;self.cur=H+0x20000;self.records=[];self.sent=[];self.names=[];self.flag=0;self.checks=0
  u.reg_write(UC_X86_REG_EBP,self.ebp);u.reg_write(UC_X86_REG_ESP,self.sp);u.reg_write(UC_X86_REG_EDI,H+0x1000)
  u.mem_write(0x131ecdc,struct.pack('<I',H));u.mem_write(0xfc1b68,struct.pack('<I',TIME))
  for offset in (32,40,48):
   sentinel=H+0x100+offset;u.mem_write(H+offset,struct.pack('<II',sentinel,0));u.mem_write(sentinel,struct.pack('<III',sentinel,sentinel,sentinel)+b'\0\1')
  u.hook_add(UC_HOOK_CODE,self.hook)
 def alloc(self,n):
  p=self.cur;self.cur+=(n+31)&~31;assert self.cur<H+0xf0000;return p
 def z(self,p):
  for n in range(1024):
   if self.u.mem_read(p+n,1)==b'\0':return bytes(self.u.mem_read(p,n))
  raise AssertionError(('unterminated',hex(p)))
 def getstr(self,p):
  n,cap=dw(self.u,p+16,2);q=dw(self.u,p)[0] if cap>=16 else p;return bytes(self.u.mem_read(q,n))
 def setstr(self,p,v):
  q=self.alloc(len(v)+1);self.u.mem_write(q,v+b'\0');self.u.mem_write(p,struct.pack('<I',q)+bytes(12)+struct.pack('<II',len(v),max(16,len(v))))
 def ret(self,n=0,value=0):
  u=self.u;sp=u.reg_read(UC_X86_REG_ESP);pc=dw(u,sp)[0];u.reg_write(UC_X86_REG_ESP,sp+4+4*n);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,_):
  if pc in (STOP,0xc9e1dd,0x7ca69b,0xc930ad):u.emu_stop();return
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc in (0xdbbc4f,0x4f10a0):self.ret(0,self.alloc(dw(u,sp+4)[0]));return
  if pc in (0xe07d4b,0xe07d7b):
   dst,src,n=dw(u,sp+4,3);u.mem_write(dst,bytes(u.mem_read(src,n)));self.ret(0,dst);return
  if pc==TIME:self.ret(0,1000);return
  if pc in (0x4e52a0,0x4e5330):
   q=dw(u,sp+4)[0];self.setstr(ecx,self.z(q) if pc==0x4e5330 else self.getstr(q));self.ret(1,ecx);return
  if pc in (0xd71ce0,0xd71d80):
   self.names.append(self.getstr(sp+4));self.checks+=1;self.ret(6,self.flag if pc==0xd71ce0 else 2);return
  if pc==0x8210a0:self.ret(0,H+0x3000);return
  if pc==0xce7f80:
   out,key=dw(u,sp+4,2);sentinel=dw(u,ecx)[0];u.mem_write(out,struct.pack('<III',sentinel,0,sentinel));self.ret(2,out);return
  if pc==0xce7960:
   src=dw(u,sp+4)[0];u.mem_write(ecx,bytes(u.mem_read(src,416)))
   for off in (12,44,68):self.setstr(ecx+off,self.getstr(src+off))
   self.records.append((dw(u,src,2),self.getstr(src+12),self.getstr(src+44),dw(u,src+40)[0],bytes(u.mem_read(src+8,2))))
   self.ret(1,ecx);return
  if pc==0xd1c670:self.ret(3,dw(u,sp+12)[0]);return
  if pc==0xc14d60:self.ret(0,H+0x1800);return
  if pc==0xc14920:
   n,ptr=dw(u,sp+4,2);self.sent.append(bytes(u.mem_read(ptr,n)));self.ret(2);return
  if pc==0x5d4140:
   q=dw(u,ecx)[0] if dw(u,ecx+20)[0]>=16 else ecx;self.ret(0,q);return
  if pc==0xd7fe40:self.ret(0,H+0x4000);return
  if pc==0x7a47d0:
   old,first,last,hint=dw(u,sp+4,4);assert last-first==276
   q=self.alloc(4096);u.mem_write(q,bytes(u.mem_read(first,last-first)));u.mem_write(ecx,struct.pack('<III',q,q+276,q+4096));self.ret(4);return
  if pc==0xc84cd0:
   out,old,first,last=dw(u,sp+4,4);assert 0<last-first<512
   q=dw(u,ecx+4)[0];u.mem_write(q,bytes(u.mem_read(first,last-first)));u.mem_write(ecx+4,struct.pack('<I',q+last-first));self.ret(4,out);return
  if pc==0x7ca740:self.names.append(self.z(dw(u,sp+4)[0]));self.ret(1);return
  if pc==0x7c7d20:self.names.append(self.z(dw(u,sp+16)[0]));self.ret(4);return
  if pc==0xa39340:u.mem_write(0x131f940,struct.pack('<I',H+0x1900));self.ret(1,H+0x1900);return
  if pc==0xa9ed30:self.ret(0,H+0x5000);return
  stubs={0xdbbbd4:0,0xdbbc7f:0,0x4f08f0:0,0xa47b90:1,0xd7f380:0,0xd7f480:0,0xa2e770:1,0x4f0550:0,0xa4ad20:5}
  if pc in stubs:self.ret(stubs[pc]);return
 def execute(self,pc):
  try:self.u.emu_start(pc,STOP,count=1000000)
  except Exception as e:raise AssertionError(('native failure',hex(self.u.reg_read(UC_X86_REG_EIP)),str(e))) from e
 def dispatch(self,packet):
  self.u.mem_write(B,packet);pid=struct.unpack_from('<H',packet)[0]
  self.execute(dw(self.u,0xcaa2e0+(pid-0x73)*4)[0])
  assert self.u.reg_read(UC_X86_REG_ESP)==self.sp,'dispatcher stack imbalance'
def record(name,title,mid=100,kind=0):
 return struct.pack('<BQBB',kind,mid,0,8)+name.ljust(128,b'\0')+struct.pack('<IH',1234,len(title)+1)+title+b'\0'
for name in (b'N'*127,b'Percent%name',b'A'):
 n=Native();r=record(name,b'Subject')+record(name[::-1],b'Another',101,2);p=struct.pack('<HHB',0xac2,5+len(r),1)+r;n.dispatch(p)
 assert len(n.records)==2,n.records
 assert n.records[0]==((100,0),name,b'Subject\0',2234,b'\0\x08'),n.records[0]
 assert n.records[1][1]==name[::-1],n.records[1]
 for pid in (0xa12,0xa51):
  n=Native();n.u.mem_write(0x131f940,struct.pack('<I',H+0x1900 if pid==0xa51 else 0))
  p=struct.pack('<H',pid)+(name.ljust(128,b'\0')+b'\1' if pid==0xa12 else struct.pack('<IHH',123,5,99)+name.ljust(128,b'\0'))
  n.dispatch(p);assert n.names==[name],n.names
 for check in (False,True):
  for flag in (0,1):
   n=Native();n.flag=flag;n.u.mem_write(H+0x3000,name+b'\0');n.u.reg_write(UC_X86_REG_EDX,H+0x3000)
   n.u.mem_write(n.ebp-0x190,struct.pack('<I',H+0x1900));n.execute(0x7ca2f9 if check else 0xc92042)
   assert n.u.reg_read(UC_X86_REG_ESP)==n.sp,'request stack imbalance'
   assert len(n.sent)==1 and len(n.sent[0])==(131 if check else 130)
   assert n.sent[0][2:130].split(b'\0')[0]==name
   if check:assert n.sent[0][130]==(1 if flag else 2)
 n=Native();inp=H+0x6000;n.u.mem_write(inp,struct.pack('<I',456));n.setstr(inp+4,name);n.setstr(inp+28,b'Subject');n.setstr(inp+52,b'Body text');n.u.mem_write(inp+76,struct.pack('<I',123456))
 n.u.mem_write(H+0x4000,name[::-1]+b'\0');n.u.mem_write(n.ebp-0x10374,struct.pack('<I',inp));n.u.mem_write(n.ebp-0xd134,struct.pack('<I',inp+52));n.u.reg_write(UC_X86_REG_EDI,inp+28);n.execute(0xc909a5)
 assert n.u.reg_read(UC_X86_REG_ESP)==n.sp,'send stack imbalance'
 assert len(n.sent)==1;npacket=n.sent[0]
 assert struct.unpack_from('<HH',npacket)==(0xa6e,294)
 assert npacket[4:132].split(b'\0')[0]==name and npacket[132:260].split(b'\0')[0]==name[::-1]
 assert struct.unpack_from('<QHHI',npacket,260)==(123456,8,10,456)
 assert npacket[276:]==b'Subject\0Body text\0'
 print('PASS RoDEX list, acknowledgments, full-name requests and send:',len(name))
for damage in ('short','titlezero','titlelong','truncated','unterminated','trail'):
 p=bytearray(struct.pack('<HHB',0xac2,151,1)+record(b'Valid',b'X'))
 if damage=='short':p=p[:20]
 if damage=='titlezero':struct.pack_into('<H',p,148,0)
 if damage=='titlelong':struct.pack_into('<H',p,148,41)
 if damage=='truncated':p=p[:-1]
 if damage=='unterminated':p[16:144]=b'X'*128
 if damage=='trail':p+=b'X'
 struct.pack_into('<H',p,2,len(p));n=Native();n.dispatch(bytes(p));assert not n.records,damage
 print('PASS malformed RoDEX list rejected:',damage)
for check in (False,True):
 n=Native();n.u.mem_write(H+0x3000,b'X'*128+b'\0');n.u.reg_write(UC_X86_REG_EDX,H+0x3000);n.u.mem_write(n.ebp-0x190,struct.pack('<I',H+0x1900));n.execute(0x7ca2f9 if check else 0xc92042);assert not n.sent
print('PASS 128-byte nonterminated input rejected without a truncated request')

for check in (False,True):
 n=Native()
 for value in (b'L'*127,b'Short'):
  n.u.mem_write(H+0x3000,value+b'\0');n.u.reg_write(UC_X86_REG_EDX,H+0x3000);n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.mem_write(n.ebp-0x190,struct.pack('<I',H+0x1900));n.execute(0x7ca2f9 if check else 0xc92042)
  assert n.sent[-1][2:130]==value.ljust(128,b'\0')
print('PASS long-to-short RoDEX requests clear every unused name-field byte')
n=Native();inp=H+0x6000
for value in (b'L'*127,b'Short'):
 n.u.mem_write(inp,struct.pack('<I',456));n.setstr(inp+4,value);n.setstr(inp+28,b'Subject');n.setstr(inp+52,b'Body text');n.u.mem_write(inp+76,struct.pack('<I',123456));n.u.mem_write(H+0x4000,value+b'\0')
 n.u.mem_write(n.ebp-0x10374,struct.pack('<I',inp));n.u.mem_write(n.ebp-0xd134,struct.pack('<I',inp+52));n.u.reg_write(UC_X86_REG_EDI,inp+28);n.u.reg_write(UC_X86_REG_ESP,n.sp);n.execute(0xc909a5)
 assert n.sent[-1][4:132]==value.ljust(128,b'\0') and n.sent[-1][132:260]==value.ljust(128,b'\0')
print('PASS long-to-short RoDEX send clears receiver and sender field padding')