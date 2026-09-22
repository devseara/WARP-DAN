"""Emitted VIP scrollbar: track, native wheel, captured thumb and cancellation."""
import argparse,json,struct
from pathlib import Path
from test_vip_ui import VipMachine,snapshot,ROOT,benefit_draws
from vip_design_contract import read

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(a.exe);c=m.c;state=c['state'];manager=0x131F4E8
meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text())
scroll=c['api']-meta['exports']['VipApi']+meta['exports']['VipScrollInput']
def packet(rows=20,flags=1|2|4|8|1024,token=77):
    p=snapshot(flags=flags,level=7,token=token);p[432:2272]=bytes(1840)
    for i in range(rows):
        start=456+(i//2)*184+(80 if i%2 else 0)
        p[start:start+80]=f'Benefit {i+1}'.encode().ljust(80,b'\0')
    return p
def position():return m.r(state+20)
def down(x,y):m.invoke(c['down'],obj,(x,y))
def up(x,y):m.invoke(c['up'],obj,(x,y))
def move(x,y,drag=True):m.invoke(c['drag'] if drag else c['move'],obj,(x,y))
def capture():return m.r(manager+0x19C)
def thumb(rows=20):
    height=max(8,50*4//rows) if rows>4 else 50
    return 278+(50-height)*position()//max(1,rows-4),height
def wheel(direction,target=None):
    target=target or obj;m.invoke(m.r(m.r(target)+35*4),target,(direction & 0xffffffff,))
obj=m.ready(packet());before=len(m.sent)
assert m.r(m.r(obj)+35*4)==c['api']-meta['exports']['VipApi']+meta['exports']['@VipWheel@12']
for i in range(19):wheel(-1);assert position()==min(i+1,16)
for i in range(19):wheel(1);assert position()==max(15-i,0)
wheel(0);assert position()==0
wheel(-0x80000000);assert position()==1
wheel(0x7fffffff);assert position()==0
assert not capture() and len(m.sent)==before

# Paging only on the track (not beyond its edges); bounded at both ends.
for expected in (4,8,12,16,16):m.click(obj,443,327);assert position()==expected
for expected in (12,8,4,0,0):m.click(obj,443,278);assert position()==expected
for x,y in ((438,305),(449,305)):
    m.click(obj,x,y);assert position()==0 and not capture()

# Click keeps the grab offset; both move routes update while captured. A
# release outside commits the clamped position and never drags the window.
original=(m.r(obj+0x1C),m.r(obj+0x20));down(443,282)
assert capture()==obj and m.r(scroll)==1 and position()==0
move(443,282);assert position()==0
wheel(-1);assert position()==0,'Wheel must not fight a captured thumb'
move(443,302);assert position()==8
move(900,900,False);assert position()==16
move(-100,-100);assert position()==0
move(443,312);assert position()==12
up(900,900);assert position()==16 and not capture() and not m.r(scroll)
move(443,278);assert position()==16,'Release left stale drag ownership'
assert (m.r(obj+0x1C),m.r(obj+0x20))==original
for expected in range(15,-1,-1):m.click(obj,443,270);assert position()==expected
for expected in range(1,17):m.click(obj,443,333);assert position()==expected
assert len(m.sent)==before
m.preview(obj,a.output/'scroll-bottom.png')
assert [r[0] for r in benefit_draws(m)]==['Benefit 17','Benefit 18','Benefit 19','Benefit 20']
top,height=thumb();assert read(m,obj,440,top,1,height).getextrema()==((157,157),(173,173),(200,200))

# Fresh same-content refresh keeps the drag; shrink/expiry/reopen cancels it.
obj=m.ready(packet());down(443,282);m.receive(packet(flags=1|4|8|1024))
assert capture()==obj and m.r(scroll)
move(443,302);assert position()==8
m.receive(packet(rows=6,flags=1|4|8|1024));assert position()==2 and not capture() and not m.r(scroll)
move(443,278);up(443,278);assert position()==2
obj=m.ready(packet());down(443,282);m.receive(packet(flags=4|1024))
assert position()==0 and not capture() and not m.r(scroll)
wheel(-1);m.click(obj,443,310);assert position()==0
for rows in (0,1,4):
    obj=m.ready(packet(rows=rows));wheel(-1);m.click(obj,443,310)
    assert position()==0 and not capture() and not m.r(scroll)
obj=m.ready(packet());down(443,282);m.receive(packet(token=99))
assert position()==0 and not capture() and not m.r(scroll)

# Native capture owned by another root is never acquired/released by VIP.
foreign=m.alloc(128);m.w(manager+0x19C,foreign)
down(443,282);up(443,310);wheel(-1)
assert position()==0 and capture()==foreign and not m.r(scroll)
m.w(manager+0x19C,0);down(443,282);m.w(manager+0x19C,foreign)
move(443,312);assert capture()==foreign and position()==0 and not m.r(scroll)
m.w(manager+0x19C,0);down(443,282);m.w(manager+0x19C,0);m.advance(100)
assert not m.r(scroll),'Timer must clear capture lost without a release event'

# Opening a popup, closing by icon/Esc, hidden state and upgrade-pending all
# suppress scrolling and clear captures. Wheel on the shared popup vtable is inert.
down(443,282);m.invoke(c['quest_open'],0,(1,));q=m.r(c['quest_state'])
assert not capture() and not m.r(scroll)
wheel(-1);wheel(-1,q);m.click(obj,443,310);assert position()==0
obj=m.ready(packet());m.w(c['interaction'],1);wheel(-1);m.click(obj,443,310)
assert position()==0 and not capture();m.w(c['interaction'],0)
obj=m.ready(packet());down(443,282)
toggle=c['api']-meta['exports']['VipApi']+meta['exports']['_VipToggleClose@0']
m.invoke(toggle,0);assert not capture() and not m.r(scroll) and not m.r(obj+0x28)
wheel(-1);assert position()==0
obj=m.ready(packet());down(443,282)
escape=c['api']-meta['exports']['VipApi']+meta['exports']['_VipEscape@12']
m.invoke(escape,0,(27,0,1));assert not capture() and not m.r(scroll)
obj=m.ready(packet());m.preview(obj,a.output/'scroll-top.png')
print('PASS: native wheel slot/ABI and directions; bounded track paging; proportional captured thumb via both move routes; release outside; refresh/expiry/modal/close/Esc/lost-capture cleanup; no foreign capture theft or scrolling packets.')
