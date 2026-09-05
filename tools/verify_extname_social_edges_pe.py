#!/usr/bin/env python3
"""Boundary and complete result-route checks for social names."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_rooms_party_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Edges(Rooms):
 def __init__(self):super().__init__();self.lookups=[];self.aids=[];self.formatted=[];self.u.mem_write(self.vtable+0x18,struct.pack('<I',STOP+0x240))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0x59cdf0:
   dst,cap,count,fmt,value=dw(u,sp+4,5);assert cap in (500,1024,512);assert count==0xffffffff
   source=self.z(value);self.formatted.append(source);out=self.z(fmt).replace(b'%s',source)[:cap-1];u.mem_write(dst,out+b'\0');self.ret(0,len(out));return
  if pc==0x59ce30:
   out,value,fmt=dw(u,sp+4,3);self.setstr(out,self.z(fmt).replace(b'%s',self.getstr(value)));self.ret(0,out);return
  if pc in (0xd5bd80,0xd58aa0):self.lookups.append(self.z(dw(u,sp+4)[0]));self.ret(1,0);return
  if pc==STOP+0x240:self.ret(5);return
  if pc==0xd76660:self.ret();return
  if pc==0xa69eb0:self.ret(1,0);return
  if pc==0x5aea80:self.aids.append(dw(u,sp+4)[0]);self.ret(1);return
  super().hook(u,pc,size,_)
def edges():
 for va in (0x8ab99e,0x8ac1b2,0x91df9e):
  n=Edges();n.u.reg_write(UC_X86_REG_EAX,n.child);n.u.emu_start(va,va+10,count=1);assert dw(n.u,n.child+0x88)[0]==127
 for flag in range(19):
  n=Edges();p=bytearray(134);struct.pack_into('<H',p,0,0x2c5);p[2:129]=b'A'*127;struct.pack_into('<I',p,130,flag);n.run(0xcb2d80,p);assert n.assigned[0][1]==b'A'*127
 for flag in range(4):
  n=Edges();p=bytearray(135);struct.pack_into('<HI',p,0,0x105,123);p[6:133]=b'W'*127;p[134]=flag;n.run(0xcbb5c0,p)
  if flag in (0,1):assert n.lookups==[b'W'*127,b'W'*127],(flag,n.lookups)
 seen=[];ids=[]
 for flag in range(14):
  n=Edges();p=bytearray(266);struct.pack_into('<H',p,0,0xafa);p[2:129]=b'L'*127;p[130:257]=b'P'*127;struct.pack_into('<II',p,258,777,flag);n.run(0xcd0210,p);seen+=n.formatted;ids+=n.aids
 assert b'L'*127 in seen and b'P'*127 in seen and ids==[777],(seen,ids)
 # Native trade dialog owns its entire name label before numeric-ID details.
 n=Edges();u=n.u;ptr=n.alloc(128);u.mem_write(ptr,b'T'*127+b'\0');sp=u.reg_read(UC_X86_REG_ESP);u.mem_write(sp,struct.pack('<7I',STOP,0,0x32,ptr,777,275,0));u.reg_write(UC_X86_REG_ECX,n.dialog);n.stops={0x8c099d};u.emu_start(0x8c0810,0,count=100000)
 assert u.reg_read(UC_X86_REG_EIP)==0x8c099d
 # The dynamic label is held in the native stack std::string after its UI copy.
 frame=u.reg_read(UC_X86_REG_EBP);assert b'T'*127 in n.getstr(frame-0x12c)
 print('PASS social edges: three input caps127, partyACK19/withdraw4/AFA14 result routes, full trade native label')
edges()
