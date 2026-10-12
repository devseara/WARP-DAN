#!/usr/bin/env python3
"""Run real character-rename validation/copy/send/ACK paths from the final PE."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args()
sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(args.pe);BASE=pe.OPTIONAL_HEADER.ImageBase;H=0x40000000;S=0x60000000;STOP=0x61000000;LOWER=STOP+256;CHARCHECK=STOP+512;LOCALE=STOP+768
def dw(u,p,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(p,n*4)))
class Native:
 def __init__(self,name,confirm=True):
  self.u=u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096);u.mem_map(BASE,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(BASE,pe.get_memory_mapped_image());u.mem_map(H,0x100000);u.mem_map(S,0x40000);u.mem_map(STOP,4096)
  self.sp=S+0x30000;self.cur=H+0x10000;self.sent=[];self.messages=[];self.confirm=confirm;self.name=name;self.owner=H+0x6000;self.original=H+0x8000;self.reported_length=len(name);self.char_type=0
  self.original_bytes=bytes((i*7+3)&255 for i in range(279));u.mem_write(self.original,self.original_bytes);u.mem_write(self.original,struct.pack('<I',12345))
  u.mem_write(H+0x3000,name+b'\0');u.mem_write(self.owner+0xbc,struct.pack('<II',H+0x1900,self.original));u.mem_write(self.owner+0x1dc,b'CANARY!!')
  u.mem_write(H+0x1900,struct.pack('<I',H+0x1000));u.mem_write(H+0x10d4,struct.pack('<I',STOP+1024))
  self.format=b'Rename character to [%s]?';u.mem_write(H+0x4000,self.format+b'\0')
  for addr,target in [(0xfc1b3c,LOWER),(0xfc1954,CHARCHECK),(0xfc18b0,LOCALE)]:u.mem_write(addr,struct.pack('<I',target))
  u.reg_write(UC_X86_REG_ESP,self.sp);u.reg_write(UC_X86_REG_EBP,S+0x3a000);u.reg_write(UC_X86_REG_ECX,self.owner)
  u.hook_add(UC_HOOK_CODE,self.hook)
 def alloc(self,n):p=self.cur;self.cur+=(n+31)&~31;return p
 def z(self,p):
  for n in range(1024):
   if self.u.mem_read(p+n,1)==b'\0':return bytes(self.u.mem_read(p,n))
  raise AssertionError(('unterminated',hex(p)))
 def getstr(self,p):
  n,cap=dw(self.u,p+16,2);ptr=dw(self.u,p)[0] if cap>=16 else p;return bytes(self.u.mem_read(ptr,n))
 def setstr(self,p,v):
  q=self.alloc(len(v)+1);self.u.mem_write(q,v+b'\0');self.u.mem_write(p,struct.pack('<I',q)+bytes(12)+struct.pack('<II',len(v),max(16,len(v))))
 def ret(self,n=0,value=0):
  u=self.u;sp=u.reg_read(UC_X86_REG_ESP);pc=dw(u,sp)[0];u.reg_write(UC_X86_REG_ESP,sp+4+4*n);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,_):
  if pc in (STOP,0x79df6c,0xd27f9e,0xd2801a):u.emu_stop();return
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc==0x8210a0:self.ret(0,H+0x3000);return
  if pc==0x8210d0:self.ret(0,self.reported_length);return
  if pc==0x4e5330:self.setstr(ecx,self.z(dw(u,sp+4)[0]));self.ret(1,ecx);return
  if pc==0x7faf70:self.ret(6,0);return
  if pc==0x7fe530:self.ret(2,0xffffffff);return
  if pc in (0xa85c00,0xd71ef0):self.ret(1,1);return
  if pc==0xd70de0:self.ret(1,0);return
  if pc==0xe07d81:
   source,pattern=dw(u,sp+4,2);index=self.z(source).find(self.z(pattern));self.ret(0,source+index if index>=0 else 0);return
  if pc==LOWER:
   ptr=dw(u,sp+4)[0];u.mem_write(ptr,self.z(ptr).lower()+b'\0');self.ret(0,ptr);return
  if pc==STOP+1024:self.ret(1);return
  if pc==LOCALE:self.ret(0,932);return
  if pc==CHARCHECK:self.ret(0,self.char_type);return
  if pc==0xa9ed30:self.ret(0,H+0x4000);return
  if pc==0x59cdf0:
   dst,cap,count,fmt,name=dw(u,sp+4,5);assert cap in (300,512) and count==0xffffffff
   value=self.z(fmt).replace(b'%s',self.z(name))[:cap-1];u.mem_write(dst,value+b'\0');self.ret(0,len(value));return
  if pc==0xa31a30:
   ptr=dw(u,sp+4)[0];self.messages.append(self.z(ptr));self.ret(9,0xbb if self.confirm else 0xba);return
  if pc==0xc14d60:self.ret(0,H+0x1800);return
  if pc==0xc14460:
   pid=dw(u,sp+4)[0];assert pid==0x28f;self.ret(1,6);return
  if pc==0xc14920:
   n,p=dw(u,sp+4,2);self.sent.append(bytes(u.mem_read(p,n)));self.ret(2);return
  if pc==0xe07d51:
   dst,value,n=dw(u,sp+4,3);u.mem_write(dst,bytes([value&255])*n);self.ret(0,dst);return
  if pc==0xdbbbd4:self.ret(0,u.reg_read(UC_X86_REG_EAX));return
  if pc==0x4f08f0:self.ret();return
  if pc==0xa447d0:self.ret(1);return
 def execute(self,pc):
  try:self.u.emu_start(pc,STOP,count=1000000)
  except Exception as e:raise AssertionError(('native failure',hex(self.u.reg_read(UC_X86_REG_EIP)),str(e))) from e
 def callback(self):
  self.u.mem_write(self.sp,struct.pack('<7I',STOP,0,6,0xb8,0,0,0));self.execute(0x8fa8d0)
  assert self.u.reg_read(UC_X86_REG_ESP)==self.sp+28,'callback stack imbalance'
  assert self.u.mem_read(self.owner+0x1dc,8)==b'CANARY!!','embedded owner overrun'
 def pending(self):return dw(self.u,0xd20962)[0]
for name in (b'Player'+b'X'*121,b'Percent%name',b'NormalName',b'A'+bytes.fromhex('e7958c')*42):
 n=Native(name);n.callback();assert len(n.sent)==1
 packet=n.sent[0];assert len(packet)==134 and struct.unpack_from('<HI',packet)==(0x8fc,12345)
 assert packet[6:]==name.ljust(128,b'\0'),packet
 assert n.z(n.owner+0x130)==name and n.z(n.pending())==name
 actual=bytes(n.u.mem_read(n.owner+0xc4,279));assert actual[:108]==bytes(n.u.mem_read(n.original,108));assert actual[236:]==n.original_bytes[236:]
 assert n.messages[-1]==n.format.replace(b'%s',name)
 # Apply accepted pending name to the real279-byte record, keeping its footer.
 n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.reg_write(UC_X86_REG_EAX,n.original);n.execute(0x79df51)
 assert n.z(n.original+108)==name and bytes(n.u.mem_read(n.original+236,43))==n.original_bytes[236:]
 assert n.u.reg_read(UC_X86_REG_ESP)==n.sp-4 and dw(n.u,n.sp-4)[0]==n.original+108
 # Native ACK confirmation sends the identity-only final rename packet.
 n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.mem_write(H+0x9000,struct.pack('<HH',0x28e,1));n.u.mem_write(n.sp,struct.pack('<II',STOP,H+0x9000));n.execute(0xd20940)
 assert n.u.reg_read(UC_X86_REG_ESP)==n.sp+8 and n.sent[-1]==struct.pack('<HI',0x28f,12345)
 print('PASS full native rename callback,279-byte owner/footer,134-byte request,cache apply and6-byte ACK:',len(name))
for name in (b'X'*128,b'GravityUser',b'[GM]Test',b'[[GM]Test',b'XY[GM]Test'):
 n=Native(name);n.callback();assert not n.sent,name;print('PASS stock rename rejection preserved:',name[:16])
n=Native(b'Long'+b'X'*123,False);n.callback();assert not n.sent;print('PASS cancelled rename sends no packet')
n=Native(b'PlayerName');n.format=b'X'*800+b'%s';n.u.mem_write(H+0x4000,n.format+b'\0');n.callback();assert len(n.messages[-1])==511;print('PASS translated rename notification bounded to512 bytes')
assert dw(Native(b'X').u,0xa3ecbf)[0]==0x1dc
assert dw(Native(b'X').u,0x8db382)[0]==0x1dc
assert dw(Native(b'X').u,0x8e53ba)[0]==128
print('PASS constructor/delete sizing and128-byte edit capacity')

# Simulate an IME character count shorter than the encoded byte string.
n=Native(b'X'*128);n.reported_length=64;n.char_type=1;n.callback();assert not n.sent
print('PASS hard127-byte bound independent of IME character count')

def check_exception_cookies(n,entry,secondary_distance):
 from unicorn import UC_HOOK_CODE
 frame=S+0x20000;sp=S+0x3d000;cookie=dw(n.u,0x122b924)[0];seen=[]
 n.u.mem_write(frame-0x10,struct.pack('<I',cookie^frame))
 n.u.mem_write(frame-secondary_distance,struct.pack('<I',cookie^frame))
 n.u.mem_write(sp,struct.pack('<III',STOP,0,frame-12));n.u.reg_write(UC_X86_REG_ESP,sp)
 def checked(u,pc,size,data):
  if pc==0xdbbbd4:assert u.reg_read(UC_X86_REG_ECX)==cookie,('wrong secondary cookie',hex(entry));seen.append(pc)
  if pc==0xe07d45:u.emu_stop()
 n.u.hook_add(UC_HOOK_CODE,checked);n.execute(entry);assert len(seen)==2,seen
check_exception_cookies(Native(b'CookieTest'),0xeb9216,0x5a0)
print('PASS native rename EH primary and relocated secondary stack cookies')
n=Native(b'L'*127);n.callback();n.name=b'Short';n.reported_length=len(n.name);n.u.mem_write(H+0x3000,n.name+b'\0');n.u.reg_write(UC_X86_REG_ESP,n.sp);n.u.reg_write(UC_X86_REG_ECX,n.owner);n.callback();assert n.sent[-1][6:]==n.name.ljust(128,b'\0')
print('PASS long-to-short rename request zeroes every unused name-field byte')