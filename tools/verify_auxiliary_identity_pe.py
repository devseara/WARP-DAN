#!/usr/bin/env python3
"""Actual adoption dialog, BG camp footer and ignored world-info route."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_social_requests_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Aux(Requests):
 def __init__(self,found=True):
  super().__init__();self.found=found;self.refreshed=[];self.game=HEAP+0x33000;self.actor=HEAP+0x35000
  self.message_format=b' wants to adopt you.'
  self.u.mem_write(self.vtable+0x94,struct.pack('<I',0x8bcc40))
  child_table=HEAP+0x34000;self.u.mem_write(self.child,struct.pack('<I',child_table))
  self.u.mem_write(child_table+0xdc,struct.pack('<I',STOP+0x200));self.u.mem_write(child_table+0x94,struct.pack('<I',STOP+0x210))
  self.u.reg_write(UC_X86_REG_EDI,self.game)
 def hook(self,u,pc,size,unused):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0xa39340:
   assert dw(u,sp+4)[0]==0x69;self.ret(1,self.dialog);return
  if pc==0xa69eb0:self.ret(1,self.actor if self.found else 0);return
  if pc==0xc72bd0:self.refreshed.append(dw(u,sp+4)[0]);self.ret(1);return
  if pc==0xc148b0:raise AssertionError('World-info reached unknown-packet stream reset')
  super().hook(u,pc,size,unused)
for value in (b'Parent',b'Percent%name',b'A'*127,('é'*63+'x').encode()):
 n=Aux();p=bytearray(138);struct.pack_into('<HII',p,0,0x1f6,123,456);p[10:10+len(value)]=value
 n.run(route(0x1f6),p,True)
 assert dw(n.u,n.game+0x28c,2)==(123,456) and dw(n.u,n.dialog+0xb4)[0]==456
 assert any(value in text for text in n.labels),n.labels
 n.u.mem_write(B,bytes(138));assert any(value in text for text in n.labels)
print('PASS adoption: real dispatch/dialog, full names, both IDs and copied labels')
n=Aux();p=bytearray(138);struct.pack_into('<HII',p,0,0x1f6,123,456);p[10:]=b'X'*128
n.run(route(0x1f6),p,True);assert not n.labels and dw(n.u,n.game+0x28c,2)==(0,0)
print('PASS adoption: unterminated128-byte name rejected before state updates')
for self_id,packet_id,found,camp in ((123,123,True,7),(123,456,True,8),(123,456,True,7),(123,456,False,8)):
 n=Aux(found);n.u.mem_write(0x15fb9a4,struct.pack('<I',self_id));n.u.mem_write(0x15fb2c4,b'\x07')
 p=bytearray(136);struct.pack_into('<HI',p,0,0x2dd,packet_id);p[6:134]=b'N'*127+b'\0';struct.pack_into('<H',p,134,camp)
 n.run(route(0x2dd),p,True)
 if self_id==packet_id:assert bytes(n.u.mem_read(0x15fb2c4,1))==bytes([camp])
 elif found:
  assert bytes(n.u.mem_read(n.actor+0xfb,1))==bytes([camp])
  assert n.refreshed==([n.actor] if camp!=7 else [])
 else:assert not n.refreshed
print('PASS BG camp: full-width packet, self/other/missing actor and correct camp offset')
n=Aux();p=bytearray(154);struct.pack_into('<H',p,0,0x979);p[26:]=b'W'*127+b'\0'
n.run(route(0x979),p,True);assert not n.labels and not n.sent
print('PASS world-info: complete154-byte packet safely ignored by client without native UI')
