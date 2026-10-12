#!/usr/bin/env python3
"""Execute native whisper parser and native caller-owned packet builder."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_social_requests_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Whisper(Requests):
 def __init__(self):super().__init__();self.whispers=[];self.stops=set()
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc in self.stops:u.emu_stop();return
  if pc==0xcafd00:
   self.whispers.append((dw(u,sp+4)[0],self.getstr(sp+8),self.getstr(sp+32),dw(u,sp+56)[0]&255));self.ret(14);return
  if pc==0xc966f0:
   dst,cap,src,count=dw(u,sp+4,4);assert count<=cap;u.mem_write(dst,bytes(u.mem_read(src,count)));self.ret(0,dst);return
  super().hook(u,pc,size,_)
def whispers():
 for value in (b'W'*127,b'Percent%name'):
  n=Whisper();p=bytearray(144);struct.pack_into('<HHI',p,0,0x9de,len(p),123);p[8:8+len(value)]=value;p[136]=1;p[137:]=b'hello!\0';n.run(0xcafb10,p)
  assert n.whispers==[(123,value,b'hello!\0',1)],n.whispers
  n=Whisper();u=n.u;frame=STACK+0x18000;sp=STACK+0x6000;ptr=n.alloc(len(value)+1);u.mem_write(ptr,value+b'\0');dst=n.alloc(160)
  u.mem_write(dst,bytes([0xcc])*160);u.mem_write(frame-0x10374,struct.pack('<I',ptr));u.mem_write(frame-0x698,b'hello!\0');u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_ESI,7);u.reg_write(UC_X86_REG_EDI,dst);n.stops={0xc8be2d};u.emu_start(0xc8bdf8,0,count=100000)
  assert u.reg_read(UC_X86_REG_EIP)==0xc8be2d and u.reg_read(UC_X86_REG_ESP)==sp
  p=bytes(u.mem_read(dst,160));assert p[:4]==struct.pack('<HH',0x96,139);assert p[4:132]==value+bytes(128-len(value));assert p[132:139]==b'hello!\0';assert p[139:]==bytes([0xcc])*21
 for count in (1,127,128):
  n=Whisper();u=n.u;frame=STACK+0x18000;ptr=n.alloc(count+1);u.mem_write(ptr,b'N'*count+b'\0');u.mem_write(frame-0x10374,struct.pack('<I',ptr));u.reg_write(UC_X86_REG_EBP,frame);n.stops={0xc8bc60,0xc8be32};u.emu_start(0xc8bc34,0,count=10000);assert u.reg_read(UC_X86_REG_EIP)==(0xc8be32 if count==128 else 0xc8bc60)
 print('PASS whisper: full sender/recipient, literal percent, ID/admin/message, packet canary and input limit')
whispers()
