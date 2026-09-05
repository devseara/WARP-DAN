#!/usr/bin/env python3
"""Verify full booking wire parsing plus actual native owning-name conversion."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_whisper_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Booking(Whisper):
 def __init__(self):
  super().__init__();self.records=[];self.more=None;self.u.mem_write(self.vtable+0x98,struct.pack('<I',STOP+0x200))
 def carrier(self,p):return (dw(self.u,p)[0],self.z(dw(self.u,p+4)[0]),bytes(self.u.mem_read(p+28,20)))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0xdbc895:self.ret(0,self.alloc(dw(u,sp+4)[0]));return
  if pc==0xa47b90:self.ret(1,self.dialog);return
  if pc==0xab54d0:
   ptr,count,more=dw(u,sp+4,3);self.more=more;self.records.extend(self.carrier(ptr+48*i) for i in range(count));self.ret(3);return
  if pc==0xab5260:self.records.append(self.carrier(sp+4));self.ret(12);return
  super().hook(u,pc,size,_)
def booking():
 records=[]
 for i in range(2):
  p=bytearray(152);struct.pack_into('<I',p,0,100+i);p[4:131]=bytes([65+i])*127;struct.pack_into('<I8H',p,132,123456+i,70+i,4+i,1,2,3,4,5,6);records.append(p)
 n=Booking();p=bytearray(309);struct.pack_into('<HHB',p,0,0x805,len(p),1);p[5:]=b''.join(records);n.run(route(0x805),p,True)
 expected=[(100+i,bytes([65+i])*127,bytes(records[i][132:])) for i in range(2)]
 assert n.records==expected and n.more==1,(n.records,n.more)
 n=Booking();p=bytearray(154);struct.pack_into('<H',p,0,0x809);p[2:]=records[0];n.run(0xcd0140,p);assert n.records==expected[:1]
 for size in (0,4,6,156):
  n=Booking();p=bytearray(max(size,5));struct.pack_into('<HH',p,0,0x805,size);n.run(route(0x805),p,True);assert not n.records
 # Execute the real formatter's complete name-production block separately
 # from database-dependent job/map localization and window filtering.
 for value in (b'A'*127,b'Percent%name'):
  n=Booking();u=n.u;frame=STACK+0x18000;ptr=n.alloc(len(value)+1);u.mem_write(ptr,value+b'\0');u.reg_write(UC_X86_REG_EBP,frame);u.mem_write(frame-0x21c,struct.pack('<I',ptr));n.stops={0xab4d93};u.emu_start(0xab4d4c,0,count=10000)
  assert u.reg_read(UC_X86_REG_EIP)==0xab4d93
  u.mem_write(ptr,bytes(len(value)+1))
  assert n.getstr(frame-0x1d8)==value and n.getstr(frame-0x178)==value
 print('PASS booking: 152-byte wire records, full name pointers, all footer fields, malformed rejection, owning native strings')
booking()
