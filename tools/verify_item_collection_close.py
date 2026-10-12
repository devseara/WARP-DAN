"""Verify emitted Collection close code with mocked native engine boundaries."""
from pathlib import Path
import re,struct,json,sys
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_item_collection_menu_button import verify_hover
import argparse
parser=argparse.ArgumentParser(description='Execute Collection small-close-X bounds and native ABI from a built PE.')
parser.add_argument('exe',type=Path)
exe=parser.parse_args().exe;pe=pefile.PE(str(exe));data=exe.read_bytes();base=pe.OPTIONAL_HEADER.ImageBase
read=lambda va:struct.unpack_from('<I',data,pe.get_offset_from_rva(va-base))[0]
m=list(re.finditer(rb'\x81\x3F(....)\x0F\x85....\x81\x7F\x2C\xF4\x03\x00\x00',data,re.S));assert len(m)==1
vt=struct.unpack('<I',m[0].group(1))[0];up=read(vt+31*4);off=pe.get_offset_from_rva(up-base);cell=struct.unpack_from('<I',data,off+4)[0];toggle=read(cell)
off=pe.get_offset_from_rva(toggle-base);m=re.search(rb'\x8B\x35(....)\x85\xF6\x0F\x84....\x81\x3E(....)\x0F\x84',data[off:off+150],re.S);assert m
state,frame=struct.unpack('<I',m[1])[0],struct.unpack('<I',m[2])[0]
down,move,up=[read(frame+i*4) for i in (25,28,31)]
mapped=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,(len(mapped)+4095)&~4095);u.mem_write(base,mapped);u.mem_map(0x60000000,0x10000)
window,stack,stop=0x60000100,0x60008000,0x60000000
r32=lambda x:struct.unpack('<I',u.mem_read(x,4))[0]
def w32(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
for addr,pop in ((0x880AD0,8),(0x880BB0,8),(0x880CB0,8),(0xA4B760,4),(0xA33100,0),(0xA32E00,0),(0xA482E0,0)):
 u.mem_write(addr,b'\x31\xC0\xC2'+struct.pack('<H',pop))
seen=[]
def step(uc,address,size,context):
 if address==stop:uc.emu_stop()
 elif address==0x880AD0:seen.append('drag')
u.hook_add(UC_HOOK_CODE,step)
preserved={UC_X86_REG_EBX:0x1357,UC_X86_REG_ESI:0x2468,UC_X86_REG_EDI:0x369A,UC_X86_REG_EBP:0xABCD}
def reset():
 u.mem_write(state,bytes(132));u.mem_write(window,bytes(0x200));w32(window,frame);w32(window+0x28,1);w32(window+0x38,0xFF);w32(state,window);seen.clear()
def run(entry,x,y):
 w32(stack,stop);w32(stack+4,x);w32(stack+8,y);u.reg_write(UC_X86_REG_ESP,stack);u.reg_write(UC_X86_REG_ECX,window)
 for reg,val in preserved.items():u.reg_write(reg,val)
 u.emu_start(entry,0,count=20000)
 assert u.reg_read(UC_X86_REG_ESP)==stack+12,'RET 8 mismatch'
 for reg,val in preserved.items():assert u.reg_read(reg)==val,'nonvolatile clobber'
points=[(744,3),(754,13),(749,8),(743,8),(755,8),(749,2),(749,14),(741,0)]
for x,y in points:
 inside=744<=x<755 and 3<=y<14;reset();run(move,x,y);assert (r32(state+72)==1)==inside,(x,y,'hover')
 run(down,x,y);assert (r32(state+68)==1)==inside,(x,y,'press');run(up,x,y);assert (r32(window+0x28)==0)==inside,(x,y,'close')
 if not inside:assert 'drag' in seen,(x,y,'title drag')
for x,y in points[3:]:
 reset();run(down,749,8);run(up,x,y);assert r32(window+0x28)==1,'outside release closed window'
print('NATIVE_CLOSE_OK 13 cases: exact 11x11 hitbox, hover/press/release, outside cancel, title drag, RET 8')
for name in ('sys_close_off.bmp','sys_close_on.bmp','bt_itemcollection_poring_normal.bmp','bt_itemcollection_poring_old_normal.bmp'):
 assert name.encode()+b'\0' in data,name
verify_hover(pe,read(vt+28*4))
