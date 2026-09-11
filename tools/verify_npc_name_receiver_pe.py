"""Execute the NPC ACK handler through its native name-cache call.
Validates long name/title arguments, not final balloon pixels.
"""
import argparse,struct
from pathlib import Path
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pe',type=Path,required=True);a=ap.parse_args()
pe=pefile.PE(str(a.pe));base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
for length in [0,1,23,24,40,63,126,127]:
 for title in [b"", b"T"*23, b"<Responsible for smelting products>", b"T"*127]:
  title_length=len(title)
  u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,image)
  u.mem_map(0,0x1000);u.mem_map(0x50000000,0x100000)
  packet=0x50001000;stack=0x50080000;manager=0x50010000;heap=[0x50090000]
  name=b'N'*length
  raw=struct.pack('<HII',0xadf,1234,0x12345678)+name.ljust(128,b'\0')+title.ljust(128,b'\0')
  u.mem_write(packet,raw);u.mem_write(stack,struct.pack('<II',0x5000f000,packet));u.reg_write(UC_X86_REG_ESP,stack);u.reg_write(UC_X86_REG_ECX,manager)
  def ints(p,n=1):return struct.unpack('<'+'I'*n,u.mem_read(p,4*n))
  def value(p):
   size,cap=ints(p+16,2);ptr=ints(p)[0] if cap>=16 else p
   return bytes(u.mem_read(ptr,size))
  def hook(u,pc,size,_):
   if pc==0x4f1940:
    sp=u.reg_read(UC_X86_REG_ESP);ret,src,n=ints(sp,3);dst=u.reg_read(UC_X86_REG_ECX)
    data=bytes(u.mem_read(src,n));ptr=dst
    if n>=16:
     ptr=heap[0];heap[0]+=0x200;u.mem_write(dst,struct.pack('<I',ptr))
    u.mem_write(ptr,data+b'\0');u.mem_write(dst+16,struct.pack('<II',n,max(n,15)))
    u.reg_write(UC_X86_REG_EAX,dst);u.reg_write(UC_X86_REG_ESP,sp+12);u.reg_write(UC_X86_REG_EIP,ret)
   elif pc==0x5a1b00:
    sp=u.reg_read(UC_X86_REG_ESP)
    assert ints(sp+4)[0]==1234
    assert value(sp+8)==name,(length,value(sp+8))
    assert value(sp+128)==title
    assert ints(sp+152)[0]==0x12345678
    assert u.reg_read(UC_X86_REG_ECX)==manager+0x160
    u.emu_stop()
  u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0xcb3aa0,0,count=20000)
  assert u.reg_read(UC_X86_REG_EIP)==0x5a1b00
  print(f'PASS native NPC ACK name={length} title={title_length}: complete cache arguments')
