"""Native complete-benefit tooltip ABI, bounded text, scrolling and ownership."""
import argparse,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX
from test_vip_ui import VipMachine,snapshot
from vip_design_contract import X,Y

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(a.exe);c=m.c;shown=[];resets=[]
def reset():shown.clear();resets.append(1);m.ret(8)
def coords():
    assert m.u.reg_read(UC_X86_REG_ECX)==m.r(c['state'])
    px,py=m.args(2);m.w(px,m.r(px)+20);m.w(py,m.r(py)+20);m.ret(8)
def tooltip():
    ptr,x,y,color,style,substitute=m.args(6)
    assert ptr==c['interaction']+224 and (color,style,substitute)==(0xffffffff,0,0)
    shown.append((m.cstr(ptr),x,y));m.ret(24)
m.stub(0xA23470,reset);m.stub(0xA1EF70,coords);m.stub(0xA753D0,tooltip)

long='Auto Combat/Auto Support Drop Rate Penalty -50%'
labels=['HP +75','SP +50','Weight +600',long]+[f'Additional long benefit description number {i}' for i in range(4,20)]
def packet(values=labels,flags=1|2|4|8|1024):
    p=snapshot(level=10,flags=flags);p[432:2272]=bytes(1840)
    for i,value in enumerate(values):
        pos=456+(i//2)*184+(80 if i%2 else 0);p[pos:pos+80]=value.encode()[:80].ljust(80,b'\0')
    return p
def hover(w,x,y):m.invoke(c['cursor'],w,(x,y))
obj=m.ready(packet());m.preview(obj,a.output/'clipped-benefit.png')
for i in range(3):hover(obj,X(800),Y(838+i*51)+5);assert not shown
hover(obj,X(800),Y(838+3*51)+5)
assert shown==[(long,X(800)+30,Y(838+3*51)+1)],shown
before=len(m.sent);assert not m.r(0x131F4E8+0x19C)
for x,y in ((X(735)-1,Y(838)+5),(X(735)+X(586),Y(838)+5),(20,180),(442,300)):
    hover(obj,x,y);assert not shown
for offset in range(17):
    m.w(c['state']+20,offset)
    hover(obj,X(800),Y(838+3*51)+5)
    assert shown and shown[0][0]==labels[offset+3]
assert len(m.sent)==before,'Hover sent a packet'

# Refresh, expiry and unterminated data must not expose stale/out-of-bounds text.
obj=m.ready(packet(['W'*80]));hover(obj,X(800),Y(838)+5)
assert shown[0][0]=='W'*79
hover(obj,X(800),Y(838+51)+5);assert not shown
m.receive(packet([],flags=4|1024));hover(obj,X(800),Y(838)+5);assert not shown
obj=m.ready(packet());m.w(0x131F4E8+0x19C,0x20101010)
hover(obj,X(800),Y(838+3*51)+5);assert not shown and m.r(0x131F4E8+0x19C)==0x20101010
m.w(0x131F4E8+0x19C,0);m.invoke(c['quest_open'],0,(1,))
hover(obj,X(800),Y(838+3*51)+5);assert not shown
obj=m.ready(packet());m.click(obj,447,10);hover(obj,X(800),Y(838+3*51)+5);assert not shown
obj=m.ready(packet());manager=m.r(0x121333C);m.w(0x121333C,0)
hover(obj,X(800),Y(838+3*51)+5);assert not shown
m.w(0x121333C,manager);assert resets
print('PASS: full native hover text including -50%, only clipped rows, all 20 rows, native coordinates/reset, bounded 79-byte payloads, expiry/empty/modal/capture/hidden/missing-manager guards, zero packets.')
