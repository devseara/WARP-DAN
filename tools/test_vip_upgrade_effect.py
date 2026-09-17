"""Reproduce stock self-missing level-up and validate EF_ANGEL regular routing.

Executes the actual installed handlers and actor lookups; doubles only native
effect creation. This does not send packets or claim live visual acceptance.
"""
import argparse
import struct
from unicorn.x86_const import UC_X86_REG_ECX
from test_vip_ui import VipMachine

ap=argparse.ArgumentParser();ap.add_argument('exe');args=ap.parse_args()
m=VipMachine(args.exe)
mode=m.alloc(0x100);world=m.alloc(0x100);mine=m.alloc(0x600);other=m.alloc(0x600)
head=m.alloc(12);node=m.alloc(12);m.w(head,node);m.w(head+4,node)
m.w(node,head);m.w(node+4,head);m.w(node+8,other)
m.w(mode+0xCC,world);m.w(world+0x10,head);m.w(world+0x2C,mine)
m.w(mine+0x110,1001);m.w(other+0x110,1002);m.w(0x15FB9A4,1001)
calls=[]
def attach():
    calls.append((m.u.reg_read(UC_X86_REG_ECX),m.args(5)[0]));m.ret(20)
m.stub(0xC44540,attach)
m.stub(0x68EA70,lambda:m.ret(0,0))
m.stub(0xAC12E0,lambda:m.ret(36,0)) # no ground-only Lua effect: use stock actor attachment
m.stub(0xC43230,lambda:m.ret(4,0))
m.stub(0xD8E8D0,lambda:m.ret(4,0))
packet=m.alloc(16)
for actor_id,target in ((1001,mine),(1002,other)):
    m.u.mem_write(packet,struct.pack('<HII',0x19B,actor_id,0))
    calls.clear();m.invoke(0xD05CD0,mode,(packet,))
    assert calls==([] if actor_id==1001 else [(target,371)]),calls
    m.u.mem_write(packet,struct.pack('<HII',0x1F3,actor_id,371))
    calls.clear();m.invoke(0xD059A0,mode,(packet,))
    assert calls==[(target,371)],calls
print('PASS: actual 0x019B handler skips self and finds the other actor; '
      '0x01F3/EF_ANGEL 371 resolves and attaches to both correct actors. '
      'Same angel animation, no duplicate notification needed; native rendering remains a boundary.')
