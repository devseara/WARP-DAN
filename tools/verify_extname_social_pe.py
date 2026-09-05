#!/usr/bin/env python3
"""Execute native social parsers and serializers from the final patched PE."""
import runpy,pathlib,struct
g=runpy.run_path(str(pathlib.Path(__file__).with_name('verify_extname_guild_clan_pe.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
class Social(Native):
 def __init__(self):
  super().__init__();self.allies=HEAP+0x2200;self.bans=HEAP+0x2300
  for ptr,glob in ((self.allies,0x159c26c),(self.bans,0x159c274)):
   self.u.mem_write(glob,struct.pack('<II',ptr,0));self.u.mem_write(ptr,struct.pack('<II',ptr,ptr))
 def hook(self,u,pc,size,_):
  sp=u.reg_read(UC_X86_REG_ESP)
  if pc==0xe07d51:
   dst,val,n=dw(u,sp+4,3);u.mem_write(dst,bytes([val&255])*n);self.ret(0,dst);return
  if pc==0x68ea70:self.ret(0,0);return
  if pc==0xce71b0:self.ret();return
  super().hook(u,pc,size,_)
def route(op):return struct.unpack('<I',pe.get_data(0xcaa2e0+(op-0x73)*4-base,4))[0]
def allies():
 for count in (0,1,2):
  n=Social();p=bytearray(4+count*136);struct.pack_into('<HH',p,0,0x14c,len(p))
  for i in range(count):struct.pack_into('<II',p,4+i*136,i,100+i);p[12+i*136:139+i*136]=bytes([65+i])*127
  n.run(route(0x14c),p,True);assert dw(n.u,0x159c270)[0]==count
  node=dw(n.u,n.allies)[0];found=[]
  while node!=n.allies:
   assert len(found)<3;found.append((dw(n.u,node+8,2),n.getstr(node+16)));node=dw(n.u,node)[0]
  assert found==[((100+i,i),bytes([65+i])*127) for i in range(count)],found
 print('PASS social alliance: complete native lists, full names, relation and IDs')
def bans():
 n=Social();p=bytearray(348);struct.pack_into('<HH',p,0,0xb7c,len(p))
 for i in range(2):
  at=4+i*172;struct.pack_into('<I',p,at,100+i);p[at+4:at+10]=b'reason';p[at+44:at+171]=bytes([65+i])*127
 n.run(route(0xb7c),p,True)
 assert n.cache=={100:b'A'*127,101:b'B'*127},n.cache
 assert dw(n.u,0x159c278)[0]==2
 print('PASS social ban list: full names, IDs, reason and 172-byte stride')
def clan_chat():
 for text in (b'N'*127+b' : Hello',b'Percent%name : hello',b'M'*1022):
  n=Social();p=bytearray(133+len(text));struct.pack_into('<HH',p,0,0x98e,len(p));p[132:132+len(text)]=text
  n.run(0xcf8860,p);assert n.messages==[text],n.messages
 n=Social();p=bytearray(132);struct.pack_into('<HH',p,0,0x98e,131);n.run(0xcf8860,p);assert not n.messages
 print('PASS clan chat: 132-byte header, full sender/message and malformed rejection')
allies();bans();clan_chat()
