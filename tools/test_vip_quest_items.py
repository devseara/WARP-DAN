"""VIP-only native icon centering and safe two-button item inspection regressions."""
import argparse
import struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_EIP
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from test_vip_ui import VipMachine,snapshot
from test_vip_quest_ui import quest,artwork
from test_gacha_ui import GachaMachine
from test_modern_chat_ui import pack

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--game',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;qs=c['quest_state'];manager=0x131F4E8
looks=artwork(m,args.game);obj=m.ready(quest());q=m.r(qs)
helper=m.r(c['api']+84);calls=[]
for op in Cs(CS_ARCH_X86,CS_MODE_32).disasm(bytes(m.u.mem_read(helper,512)),helper):
    if op.mnemonic=='call' and op.op_str.startswith('0x'):calls.append(int(op.op_str,16))
    if op.mnemonic=='ret':break
blits=[]
m.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:blits.append(m.args(4)),begin=calls[-1],end=calls[-1])
m.preview(q,args.output/'vip-upgrade-quest.png')
assert len(blits)==3
for index,(window,texture,x,y) in enumerate(blits):
    width,height=m.r(texture+0x114),m.r(texture+0x118)
    assert window==q and (x,y)==(13+(32-width)//2,31+index*48+(32-height)//2),(width,height,x,y)
    assert abs((x-13)-(45-x-width))<=1 and abs((y-31-index*48)-(63+index*48-y-height))<=1
assert looks[-3:]==[909,914,606]

description=m.alloc(0x100);vtable=m.alloc(0x100);dispatch=m.alloc(16)
m.w(description,vtable);m.w(vtable+0x94,dispatch)
constructed=[];destroyed=[];opened=[];factory_ok=[True]
def ctor():
    item=m.u.reg_read(UC_X86_REG_ECX);m.u.mem_write(item,bytes(0xF8));constructed.append(item);m.ret(0,item)
def dtor():destroyed.append(m.u.reg_read(UC_X86_REG_ECX));m.ret(0)
def format_item():
    dest,fmt,value=m.args(3);format=m.cstr(fmt)
    out=str(value).encode() if format=='%u' else format.replace('%s',m.cstr(value)).encode('latin1')
    m.u.mem_write(dest,out+b'\0');m.ret(0,len(out))
def factory():assert m.args(1)==[12];m.ret(4,description if factory_ok[0] else 0)
def show():
    sender,msg,item,a,b,d=m.args(6)
    assert m.u.reg_read(UC_X86_REG_ECX)==description and (sender,msg,a,b,d)==(0,24,0,0,0)
    assert item==constructed[-1] and m.r(item+0x3C)==len(m.cstr(item+0x2C))
    assert bytes(m.u.mem_read(item+0x5C,1))==b'\1'
    assert not m.r(manager+0x19C),'Description must open after releasing local left capture'
    opened.append(int(m.cstr(item+0x2C)));m.ret(24)
m.stub(0x6A1B20,ctor);m.stub(0x5A4300,dtor);m.stub(0x529850,format_item)
m.stub(0xA39340,factory);m.stub(dispatch,show)
def right(x,y,up=False):GachaMachine.right(m,q,(x,y),up)
def inspect(x,y,button):
    if button=='left':m.click(q,x,y)
    else:right(x,y);assert not m.r(manager+0x19C);right(x,y,True)

for button in ('left','right'):
    for index,item in enumerate((909,914,606)):
        inspect(29,47+index*48,button);assert opened[-1]==item
assert len(opened)==6 and constructed==destroyed and not m.sent
before=len(opened)
# Release outside/on another row; no description and no stranded capture.
m.invoke(c['down'],q,(29,47));m.invoke(c['up'],q,(29,95))
right(29,47);right(29,95,True);right(29,47);right(100,210,True)
assert len(opened)==before and not m.r(manager+0x19C)
# Same ItemId in a different slot still is not the pressed slot.
p=quest(opened=False);struct.pack_into('<I',p,2404,909);m.receive(p)
right(29,47);right(29,95,True);assert len(opened)==before
m.receive(quest(opened=False))
# Snapshot changing the identity invalidates both left and right inspection.
for button in ('left','right'):
    if button=='left':m.invoke(c['down'],q,(29,47))
    else:right(29,47)
    p=quest(opened=False);struct.pack_into('<I',p,2344,914);m.receive(p)
    if button=='left':m.invoke(c['up'],q,(29,47))
    else:right(29,47,True)
    assert len(opened)==before;m.receive(quest(opened=False))
# Another window's active drag is never stolen by item inspection.
other=m.alloc(64);m.w(manager+0x19C,other)
m.click(q,29,47)
right(29,47);right(29,47,True)
assert m.r(manager+0x19C)==other and len(opened)==before;m.w(manager+0x19C,0)
# Native description creation failure still destroys the temporary CItem.
factory_ok[0]=False;inspect(29,47,'left');assert len(opened)==before and constructed==destroyed
factory_ok[0]=True
# Empty or unknown item, hidden quest, or confirmation mode cannot inspect.
for item in (0,0xFFFFFFFF):
    p=quest(opened=False);struct.pack_into('<I',p,2344,item);m.receive(p)
    for button in ('left','right'):inspect(29,47,button)
    assert len(opened)==before
m.receive(quest(opened=False));right(29,47)
m.w(0x11E40E8,0);m.invoke(c['move'],q,(29,47));right(29,47,True);assert len(opened)==before
right(29,47);m.click(q,205,248);right(29,47,True);m.click(q,29,47);assert len(opened)==before
m.ready(snapshot());m.invoke(c['quest_open'],0,(1,));q=m.r(qs)
for button in ('left','right'):inspect(29,47,button)
assert len(opened)==before and constructed==destroyed and not m.sent
# Replay the native capture/no-capture poll that caused the historical Gacha
# item-right-click crash. Do not stub this selection or indirect call path.
obj=m.ready(quest());q=m.r(qs);right(29,47);assert m.r(qs+24)
m.w(0x11E40E4,1);m.w(0x11E40E8,0);m.w(0x11E40EC,0)
m.stub(0xA1EDD0,lambda:m.ret(0,q))
m.stub(m.r(m.r(q)+8),lambda:m.ret(0,0))
m.stub(0xA336D0,lambda:m.ret(8,0)) # following left click outside every UI
code=m.alloc(256)
prefix=(b'\x55\x8b\xec\x81\xec'+pack(0x90)+b'\x53\x56\x57\xbb'+pack(manager)+
        b'\xc7\x45\x8c'+pack(100)+b'\xc7\x45\x90'+pack(101)+b'\xe9')
m.u.mem_write(code,prefix+pack(0xA46940-(code+len(prefix)+4)))
done=code+192;m.u.mem_write(done,b'\x5f\x5e\x5b\x8b\xe5\x5d\xc3')
for site in (0xA46F4C,0xA470CC):m.stub(site,lambda:m.u.reg_write(UC_X86_REG_EIP,done))
m.u.mem_unmap(0,0x1000);m.invoke(code,q)
assert not m.r(manager+0x19C) and len(opened)==before and not m.sent
print('PASS: real client BMP centers in all 32px boxes; native right vtable dispatch and left inspection; CItem ID/identified/message24/lifetime; same-slot/release-outside/changed-ID/empty/missing/hidden/confirmation/foreign-capture guards; no quest or inventory requests.')
print('PASS: actual native capture-selection poll after right-down, with page zero unmapped; no historical A46B1C null-capture crash.')
