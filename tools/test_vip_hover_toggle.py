"""Execute emitted VIP icon/keyboard hooks and bounded quest hover hints."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ECX
from test_vip_ui import VipMachine,snapshot,ROOT

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(a.exe);c=m.c;manager=0x131F4E8;shown=[];stock=[]
meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text())
base=c['api']-meta['exports']['VipApi']
def export(name):return base+meta['exports'][name]
def packet(flags=1|2|4|8|32|128):
    p=snapshot(flags=flags)
    for i in range(3):struct.pack_into('<III48s',p,2344+i*60,501+i,1000+i,300+i,f'Quest item {i+1}'.encode())
    return p
def coords():
    w=m.u.reg_read(UC_X86_REG_ECX);px,py=m.args(2)
    m.w(px,m.r(px)+m.r(w+0x1C));m.w(py,m.r(py)+m.r(w+0x20));m.ret(8)
def tooltip():
    ptr,x,y,color,style,substitute=m.args(6)
    assert (color,style,substitute)==(0xffffffff,0,0)
    shown.append((m.cstr(ptr),x,y));m.ret(24)
def reset():shown.clear();m.ret(8)
m.stub(0xA23470,reset);m.stub(0xA1EF70,coords);m.stub(0xA753D0,tooltip)
obj=m.ready(packet());m.invoke(c['quest_open'],0,(2,));q=m.r(c['quest_state'])
before=len(m.sent)
for i in range(3):
    m.invoke(c['cursor'],q,(20,40+i*48))
    assert shown==[(f'Quest item {i+1}\nRequired: {1000+i:,}\nInventory: {300+i}',
                    30+m.r(q+0x1C),16+i*48+m.r(q+0x20))],shown
assert len(m.sent)==before and not m.r(manager+0x19C),'Hover must never claim or capture'
for x,y in ((12,40),(45,40),(20,30),(20,63),(70,40)):
    m.invoke(c['cursor'],q,(x,y));assert not shown
m.w(manager+0x19C,0x20101010);m.invoke(c['cursor'],q,(20,40));assert not shown
m.w(manager+0x19C,0);m.invoke(c['down'],q,(20,40));m.invoke(c['cursor'],q,(20,40));assert not shown
m.invoke(c['up'],q,(70,40));assert len(m.sent)==before
p=packet();p[2356:2404]=b'W'*48;struct.pack_into('<II',p,2348,0xffffffff,0xffffffff)
m.receive(p);m.invoke(c['quest_open'],0,(2,));m.invoke(c['cursor'],q,(20,40))
assert shown[0][0]=='W'*47+'\nRequired: 4,294,967,295\nInventory: 4,294,967,295'
p=packet(flags=1|4|32|128);p[2344:2404]=bytes(60);m.receive(p)
m.invoke(c['cursor'],q,(20,40));assert not shown,'Empty refreshed slot retained hint'
m.receive(packet(flags=4));m.invoke(c['cursor'],q,(20,40));assert not shown

# Verify actual WM call sites target the same wrapper; it forwards all other
# input to the unchanged native manager entry, including an existing BP hook.
def call_target(site):
    assert bytes(m.u.mem_read(site,1))==b'\xe8'
    return site+5+struct.unpack('<i',m.u.mem_read(site+1,4))[0]
key=call_target(0xDB86B3);assert key==call_target(0xDB87AE) and key!=0xA471E0
native_entry=bytes(m.u.mem_read(0xA471E0,7))
assert native_entry[0] in (0x55,0xE9),'Unexpected stock/Battle Pass entry'
def fallback():
    stock.append((m.u.reg_read(UC_X86_REG_ECX),m.args(3)));m.ret(12,0)
m.stub(0xA471E0,fallback)
def press(vk=27,flags=0,receiver=manager):
    count=len(stock);m.invoke(key,receiver,(vk,flags,1));return m.u.reg_read(UC_X86_REG_EAX),len(stock)-count
obj=m.ready(packet());before=len(m.sent)
assert press(65)==(0,1) and press(flags=0x20000000)==(0,1)
assert press(receiver=manager+4)==(0,1)
m.w(manager+0x404,1);assert press()==(0,1);m.w(manager+0x404,0)
m.w(manager+0x19C,0x20101010);assert press()==(0,1);m.w(manager+0x19C,0)
other=m.alloc(0xB4);m.w(other+0x28,1)
m.invoke(0xA2D240,manager,(other,));m.invoke(0xA39130,manager,(other,))
assert press()==(0,1),'ESC stole another visible root'
m.w(other+0x28,0)
m.invoke(c['quest_open'],0,(2,));assert press()==(1,0)
assert not m.r(c['quest_state']+16) and m.r(obj+0x28) and len(m.sent)==before
assert press(flags=0x40000000)==(1,0) and m.r(obj+0x28),'Key repeat closed parent'
assert press()==(1,0) and not m.r(obj+0x28)
assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==6
assert not m.r(c['state']+2696) and not m.r(manager+0x19C)
assert press(flags=0x40000000)==(1,0)
assert press(flags=0x80000000)==(1,0) and press()==(0,1)

# Run the actual icon command and its original closed-state packet sender.
raw=[]
def wire_send():
    size,ptr=m.args(2);data=bytes(m.u.mem_read(ptr,size))
    if size==2:raw.append(data);m.ret(8)
    else:m.send()
m.stub(c['send'],wire_send)
m.stub(0xC14460,lambda:m.ret(4,2))
m.w(manager+0x464,0)
def icon():m.invoke(0x9169F0,obj,(0,6,0xC0,0,0,0))
icon();assert raw==[b'\x19\x0a'] and not m.r(obj+0x28),'Opening must await server'
m.receive(packet());before=len(m.sent);m.invoke(c['quest_open'],0,(2,));icon()
assert not m.r(obj+0x28) and not m.r(c['quest_state']+16)
assert len(m.sent)==before+1 and len(raw)==1,'Close sent a second open request'
icon();assert len(raw)==2 and not m.r(obj+0x28)
m.receive(packet());assert m.r(obj+0x28)
assert bytes(m.u.mem_read(0xA471E0,7))==native_entry,'VIP overwrote the stock/BP keyboard entry'
m.preview(obj,a.output/'vip-gold-trimmed-crowns.png')
print('PASS: three bounded item-hover hints, live refresh/empty/capture/pressed guards, no hover packets; actual icon close/open packet flow; ESC popup/main, repeats/releases, native/BP fallback, modal/foreign-root guards and cleanup.')
