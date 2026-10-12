#!/usr/bin/env python3
"""Run native room memberships, modern party queue ownership, and trade routing."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_booking_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Rooms(Booking):
 def __init__(self):
  super().__init__();self.events=[];self.actor=HEAP+0x34000;self.chat=HEAP+0x36000;self.actorvt=HEAP+0x35000
  self.u.mem_write(self.actor,struct.pack('<I',self.actorvt));self.u.mem_write(self.actorvt+8,struct.pack('<I',STOP+0x230));self.u.mem_write(self.actor+0x268,struct.pack('<I',self.chat));self.u.mem_write(self.chat+0xbc,struct.pack('<I',10))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc==0xc9ad60:self.ret(1,dw(u,sp+4)[0]);return
  if pc==0xa69eb0:self.ret(1,self.actor);return
  if pc==STOP+0x230:self.ret(13);return
  if pc in (0xc9ab00,0xc994e0):
   u.mem_write(ecx,bytes(64));self.setstr(ecx,b'Room');self.setstr(ecx+24,b'');self.ret(1,ecx);return
  if pc==0xa39340:self.ret(1,self.dialog);return
  if pc==0x529850:
   dst,fmt,value=dw(u,sp+4,3);output=self.z(fmt).replace(b'%s',self.z(value));assert len(output)<256;u.mem_write(dst,output+b'\0');self.ret(0,len(output));return
  if pc==STOP+0x210:
   a=dw(u,sp+4,6)
   if a[1] in (0x2c,0x2d,0x2e):self.events.append((a[1],self.z(a[2]),a[3]))
   if a[1]==0x32:self.events.append((a[1],self.z(a[2]),a[3],a[4]))
   self.ret(6);return
  super().hook(u,pc,size,_)
def rooms():
 n=Rooms();p=bytearray(272);struct.pack_into('<HHI',p,0,0xdb,len(p),10)
 for i in range(2):struct.pack_into('<I',p,8+132*i,i);p[12+132*i:139+132*i]=bytes([65+i])*127
 n.run(route(0xdb),p,True);assert n.events==[(0x2c,b'A'*127,0),(0x2c,b'B'*127,1)],n.events
 for op,size,off,flag in [(0xdc,132,4,1),(0xdd,133,4,0),(0xe1,134,6,0)]:
  n=Rooms();p=bytearray(size);struct.pack_into('<H',p,0,op);p[off:off+127]=b'X'*127
  if op==0xe1:struct.pack_into('<I',p,2,flag)
  else:struct.pack_into('<H',p,2,2)
  n.run(route(op),p,True);assert n.events==[((0x2c if op==0xdc else 0x2d if op==0xdd else 0x2e),b'X'*127,flag)],n.events
 n=Rooms();p=bytearray(136);struct.pack_into('<H',p,0,0x1f4);p[2:129]=b'T'*127;struct.pack_into('<IH',p,130,123456,275);n.run(route(0x1f4),p,True);assert n.events==[(0x32,b'T'*127,123456,275)],n.events;assert n.getstr(HEAP+0x30000+0x148)==b'T'*127
 print('PASS native room list/new/leave/owner and trade: full names, flags, counts, requester ID/level and persistent key')
class Modern(Booking):
 def __init__(self,queued):
  super().__init__();self.queued=queued;self.events=[];self.freed=[];self.manager=HEAP+0x34000;self.pending=HEAP+0x35000;self.ignored=HEAP+0x35100
  self.u.mem_write(self.manager+8,struct.pack('<4I',self.pending,0,self.ignored,0))
  for ptr in (self.pending,self.ignored):self.u.mem_write(ptr,struct.pack('<II',ptr,ptr))
  self.u.mem_write(0x1318b54,struct.pack('<I',self.manager))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0xa47b90:self.ret(1,self.dialog if self.queued else 0);return
  if pc==0xa39340:self.ret(1,self.dialog);return
  if pc==0xdbbc7f:self.freed.append(dw(u,sp+4,2));self.ret();return
  if pc==STOP+0x210:
   a=dw(u,sp+4,6);ptr=a[2]
   if a[1]==0x38:self.events.append((self.z(dw(u,ptr)[0]),dw(u,ptr+24,2),struct.unpack('<HH',bytes(u.mem_read(ptr+32,4)))))
   self.ret(6);return
  super().hook(u,pc,size,_)
def modern():
 for queued in (False,True):
  for value in (b'Q'*127,b'Percent%name'):
   n=Modern(queued);u=n.u;p=bytearray(142);struct.pack_into('<HII',p,0,0xae7,111,222);p[10:10+len(value)]=value;struct.pack_into('<HH',p,138,123,234);n.run(route(0xae7),p,True)
   if queued:
    node=dw(u,n.pending)[0];assert node!=n.pending;ptr=dw(u,node+8)[0];assert ptr==node+44 and n.z(ptr)==value;u.mem_write(B,bytes(142));assert n.z(ptr)==value
    sp=u.reg_read(UC_X86_REG_ESP);u.mem_write(sp,struct.pack('<II',STOP,0));u.reg_write(UC_X86_REG_ECX,n.manager);u.emu_start(0x7815c0,0,count=100000);assert (node,172) in n.freed
   else:assert n.events==[(value,(111,222),(234,123))],n.events
 print('PASS modern party: immediate full names, queued owned128-byte strings survive packet reuse, IDs/coords and sized destruction')
rooms();modern()
