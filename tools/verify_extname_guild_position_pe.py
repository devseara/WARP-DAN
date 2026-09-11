#!/usr/bin/env python3
"""Exercise native guild position update parsers and20-row outgoing packets."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_social_edges_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Position(Edges):
 def __init__(self):super().__init__();self.positions=[];self.stops={0xc930ad};self.u.mem_write(0x159c24c,struct.pack('<I',1));self.u.mem_write(0xfc1b1c,struct.pack('<I',STOP+0x250))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==STOP+0x250:
   dst,src,count=dw(u,sp+4,3);assert count==23;u.mem_write(dst,self.z(src)[:count].ljust(count,b'\0'));self.ret(0,dst);return
  if pc==0xa83f50:
   self.positions.append((dw(u,sp+4,2),self.getstr(sp+12),dw(u,sp+36,4)));self.ret(12);return
  if pc==0x9183c0:self.ret(2);return
  if pc==0xc14920:
   size,ptr=dw(u,sp+4,2);assert 4<=size<=4096;self.sent.append(bytes(u.mem_read(ptr,size)));self.ret(2);return
  super().hook(u,pc,size,_)
def positions_stock():
 n=Position();p=bytearray(84);struct.pack_into('<HH',p,0,0x174,len(p))
 for i in range(2):
  at=4+40*i;struct.pack_into('<4I',p,at,i+1,0x111,10+i,20+i);p[at+16:at+39]=bytes([65+i])*23
 n.run(route(0x174),p,True)
 assert n.positions==[((10+i,i+1),bytes([65+i])*23,(1,1,20+i,1)) for i in range(2)],n.positions
 for count in (0,1,20):
  n=Position();u=n.u;head=HEAP+0x38000;nodes=[n.alloc(80) for _ in range(count)];u.mem_write(0x159c294,struct.pack('<II',head,count));u.mem_write(head,struct.pack('<III',nodes[0] if nodes else head,nodes[0] if nodes else head,nodes[-1] if nodes else head));u.mem_write(head+13,b'\x01')
  for i,node in enumerate(nodes):
   u.mem_write(node,struct.pack('<III',head,nodes[i-1] if i else head,nodes[i+1] if i+1<count else head));u.mem_write(node+20,struct.pack('<II',10+i,i+1));n.setstr(node+28,bytes([65+i])*23);u.mem_write(node+52,struct.pack('<4I',1,1,20+i,1))
  sp=STACK+0x10000;frame=STACK+0x18000;u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EBP,frame);u.emu_start(0xc8e92b,0,count=500000)
  assert u.reg_read(UC_X86_REG_EIP)==0xc930ad and u.reg_read(UC_X86_REG_ESP)==sp
  assert len(n.sent)==1;p=n.sent[0];assert len(p)==4+count*40 and struct.unpack_from('<HH',p)==(0x161,len(p))
  for i in range(count):
   at=4+i*40;assert struct.unpack_from('<4I',p,at)==(i+1,0x111,10+i,20+i);assert p[at+16:at+40]==bytes([65+i])*23+b'\0'
 print('PASS guild position: stock incoming labels/flags/rank/tax and0/1/20 outgoing40-byte records, stock packet capacity and stack')
positions_stock()
