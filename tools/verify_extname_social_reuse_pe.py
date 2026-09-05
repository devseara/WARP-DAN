#!/usr/bin/env python3
"""Final aggregate, including repeated long-to-short sends on the same stack."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_social_all_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
def reuse():
 targets=[('friend',0xa2c600,2),('party',0xc8d066,2),('invite',0xc8d0d5,2),('guild',0xc8f000,6),('role',0xc8c1f3,6),('kick',0xc8c265,2),('guildinvite',0xc8f143,2)]
 for kind,entry,off in targets:
  n=Requests();u=n.u;frame=STACK+0x18000;sp=STACK+0x18000
  for value in (b'L'*127,b'Short'):
   n.value=value;ptr=n.alloc(len(value)+1);u.mem_write(ptr,value+b'\0');u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EDX,ptr);u.reg_write(UC_X86_REG_ECX,77);u.mem_write(sp,struct.pack('<II',STOP,ptr));u.mem_write(frame-0x10374,struct.pack('<I',ptr));u.emu_start(entry,0,count=100000);assert n.sent[-1][off:off+128]==value+bytes(128-len(value))
 for entry in (0xc7a561,0xc7a605):
  n=Block();u=n.u;sp=u.reg_read(UC_X86_REG_ESP);obj=n.alloc(24)
  for value in (b'L'*127,b'Short'):
   n.setstr(obj,value);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EDI,obj);u.emu_start(entry,0,count=100000);assert n.sent[-1][2:130]==value+bytes(128-len(value))
 n=Whisper();u=n.u;frame=STACK+0x18000;sp=STACK+0x6000;dst=n.alloc(160);n.stops={0xc8be2d};u.mem_write(frame-0x698,b'hello!\0')
 for value in (b'L'*127,b'Short'):
  ptr=n.alloc(len(value)+1);u.mem_write(ptr,value+b'\0');u.mem_write(frame-0x10374,struct.pack('<I',ptr));u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_ESI,7);u.reg_write(UC_X86_REG_EDI,dst);u.emu_start(0xc8bdf8,0,count=100000);assert bytes(u.mem_read(dst+4,128))==value+bytes(128-len(value))
 n=Position();u=n.u;head=HEAP+0x38000;node=n.alloc(80);frame=STACK+0x18000;sp=STACK+0x10000
 for value in (b'L'*127,b'Short'):
  u.mem_write(0x159c294,struct.pack('<II',head,1));u.mem_write(head,struct.pack('<III',node,node,node));u.mem_write(head+13,b'\x01');u.mem_write(node,struct.pack('<III',head,head,head));u.mem_write(node+20,struct.pack('<II',10,1));n.setstr(node+28,value);u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_ESP,sp);u.emu_start(0xc8e92b,0,count=100000);assert n.sent[-1][20:148]==value+bytes(128-len(value))
 print('PASS repeated social sends:11 writers reuse identical stack/packet storage, short-after-long padding remains zero')
reuse()
