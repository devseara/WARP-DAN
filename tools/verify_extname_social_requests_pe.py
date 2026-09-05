#!/usr/bin/env python3
"""Run native social invitation dialogs and full-name request writers."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_social_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Requests(Social):
 def __init__(self):
  super().__init__();self.sent=[];self.value=b'';self.dialog=HEAP+0x30000;self.child=HEAP+0x31000;self.vtable=HEAP+0x32000;self.labels=[]
  self.u.mem_write(self.dialog,struct.pack('<I',self.vtable));self.u.mem_write(self.dialog+0xb8,struct.pack('<I',self.child));self.u.mem_write(self.child,struct.pack('<I',self.vtable))
  self.u.mem_write(self.vtable+0xdc,struct.pack('<I',STOP+0x200));self.u.mem_write(self.vtable+0x94,struct.pack('<I',STOP+0x210))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  if pc in (0xc8d0ce,0xc8d135,0xc8f05d,0xc8c25e,0xc8c2ca,0xc8f19e):u.emu_stop();return
  if pc==0xc14d60:self.ret(0,HEAP+0x33000);return
  if pc==0xc14920:
   length,ptr=dw(u,sp+4,2);assert length in (130,132,134);self.sent.append(bytes(u.mem_read(ptr,length)));self.ret(2);return
  if pc==0x5d4140:
   ptr=self.alloc(len(self.value)+1);u.mem_write(ptr,self.value+b'\0');self.ret(0,ptr);return
  if pc==0x4f1610:
   ptr,count=dw(u,sp+4,2);self.setstr(ecx,self.getstr(ecx)+bytes(u.mem_read(ptr,count)));self.ret(2,ecx);return
  if pc==STOP+0x200:self.ret();return
  if pc==STOP+0x210:
   a=dw(u,sp+4,6)
   if a[1]==0x1d:self.labels.append(self.z(a[2]))
   self.ret(6);return
  super().hook(u,pc,size,_)
def outgoing():
 for kind,entry,op,size,off,end in [('friend',0xa2c600,0x202,130,2,STOP),('party',0xc8d066,0x1e8,132,2,0xc8d0ce),('invite',0xc8d0d5,0x2c4,130,2,0xc8d135),('guild',0xc8f000,0x165,134,6,0xc8f05d),('roomrole',0xc8c1f3,0xe0,134,6,0xc8c25e),('roomkick',0xc8c265,0xe2,130,2,0xc8c2ca),('guildinvite',0xc8f143,0x916,130,2,0xc8f19e)]:
  for value in (b'Short',b'N'*127,b'Percent%name',b'O'*128):
   n=Requests();n.value=value;u=n.u;ptr=n.alloc(len(value)+1);u.mem_write(ptr,value+b'\0');sp=STACK+0x18000;frame=STACK+0x18000
   u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_EDX,ptr);u.reg_write(UC_X86_REG_ECX,77);u.mem_write(sp,struct.pack('<II',STOP,ptr));u.mem_write(frame-0x10374,struct.pack('<I',ptr));u.mem_write(frame-0x10378,struct.pack('<I',1));u.mem_write(frame-0x10380,struct.pack('<I',2));u.mem_write(0x15fb9a8,struct.pack('<I',1234))
   u.emu_start(entry,0,count=100000);assert u.reg_read(UC_X86_REG_EIP)==end
   assert u.reg_read(UC_X86_REG_ESP)==sp+(8 if kind=='friend' else 0)
   if len(value)==128:assert not n.sent;continue
   assert len(n.sent)==1;p=n.sent[0];assert len(p)==size and struct.unpack_from('<H',p)[0]==op
   assert p[off:off+128]==value+bytes(128-len(value))
   if kind=='party':assert p[130:]==b'\x01\x02'
   if kind=='guild':assert struct.unpack_from('<I',p,2)[0]==1234
   if kind=='roomrole':assert struct.unpack_from('<I',p,2)[0]==77
 print('PASS outgoing social: 7 real writers, full/percent names, zero padding, flags, IDs and 128-byte rejection')
def dialogs():
 for op,entry,msg in [(0x2c6,0x8c46d0,0x38),(0x16a,0x8c4260,0x49),(0x171,0x881970,0x4a)]:
  for value in (b'V'*127,b'Percent%guild'):
   n=Requests();u=n.u;ptr=n.alloc(len(value)+1);u.mem_write(ptr,value+b'\0');sp=u.reg_read(UC_X86_REG_ESP)
   u.mem_write(sp,struct.pack('<7I',STOP,0,msg,123,ptr,0,0));u.reg_write(UC_X86_REG_ECX,n.dialog)
   u.emu_start(entry,0,count=100000);assert u.reg_read(UC_X86_REG_EIP)==STOP;assert u.reg_read(UC_X86_REG_ESP)==sp+28
   assert any(value in text for text in n.labels),n.labels;assert dw(u,n.dialog+0xb4)[0]==123
 print('PASS native party/guild/alliance dialogs: complete names, IDs, dynamic labels and stack balance')
outgoing();dialogs()
