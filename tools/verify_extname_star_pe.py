#!/usr/bin/env python3
"""Execute the native Star/TaeKwon target parser through each packet-consuming route."""
import argparse,struct,sys
ap=argparse.ArgumentParser();ap.add_argument('--pe',required=True);ap.add_argument('--deps',required=True);args=ap.parse_args()
sys.path.insert(0,args.deps)
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
p=pefile.PE(args.pe);base=p.OPTIONAL_HEADER.ImageBase
B=0x15e8198;STACK=0x60000000;HEAP=0x40000000;STOP=0x61000000
def dw(u,a,n=1):return struct.unpack('<'+'I'*n,bytes(u.mem_read(a,4*n)))
def z(u,a):
 for n in range(1024):
  if u.mem_read(a+n,1)==b'\0':return bytes(u.mem_read(a,n))
 raise AssertionError('unterminated string')
for name in (b'Target%'+b'Z'*120,b'Zombie'):
 for result in (0,1,10,11,20,21,22,30,40):
  u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,4096);u.mem_map(base,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,p.get_memory_mapped_image())
  u.mem_map(STACK,0x20000);u.mem_map(HEAP,0x20000);u.mem_map(STOP,4096)
  packet=bytearray(136);struct.pack_into('<H',packet,0,0x20e);packet[2:2+len(name)]=name;struct.pack_into('<IBB',packet,130,123456,2,result);u.mem_write(B,bytes(packet))
  sp=STACK+0x10000;u.reg_write(UC_X86_REG_ESP,sp);u.mem_write(sp,struct.pack('<II',STOP,B));u.reg_write(UC_X86_REG_ECX,HEAP)
  u.mem_write(HEAP+0xcc,struct.pack('<I',HEAP+0x100));u.mem_write(HEAP+0x12c,struct.pack('<I',HEAP+0x200));u.mem_write(HEAP+0x400,b'Player\0')
  checked=[]
  def ret(n=0,value=0):
   s=u.reg_read(UC_X86_REG_ESP);v=dw(u,s)[0];u.reg_write(UC_X86_REG_ESP,s+4+4*n);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,v)
  def hook(u,pc,size,_):
   s=u.reg_read(UC_X86_REG_ESP)
   if pc==0xc85650:ret(0,HEAP+0x300)
   elif pc==0xd7fe40:ret(0,HEAP+0x400)
   elif pc==0xa9ed30:
    msg=dw(u,s+4)[0]
    if result in (0,1,10,11):assert msg=={0:0x345,1:0x348,10:0x34b,11:0x34e}[result]+2;checked.append('star')
    if result==30:checked.append('reset');u.emu_stop();return
    ret(0,HEAP+0x500)
   elif pc==0xd5bb40:
    assert dw(u,s+4)[0]==123456;checked.append('id');ret(2,HEAP+0x400)
   elif pc==0x6a6570:
    assert dw(u,s+4)[0]==123456;checked.append('id');u.emu_stop()
   elif pc==0x64d510:
    assert dw(u,u.reg_read(UC_X86_REG_EBP)-0x114)[0]==123456;checked.append('hp');u.emu_stop()
   elif pc==0xa94930:
    if result in (0,1,10,11):
     assert z(u,dw(u,s+16)[0])==name;checked.append('name')
    elif result==20:
     assert z(u,dw(u,s+12)[0])==name;checked.append('name')
     assert dw(u,s+16)[0]==2;checked.append('percent')
    elif result==21:assert z(u,dw(u,s+12)[0])==name;checked.append('name')
    u.emu_stop()
   elif pc==0x6a1b20:ret()
   elif pc==STOP:raise AssertionError('unexpected early return')
  u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0xcd9650,0,count=100000)
  assert checked,(result,'native route not reached',hex(u.reg_read(UC_X86_REG_EIP)))
  print('PASS native Star route',result,'name bytes',len(name),','.join(checked))
