"""Execute emitted VIP portrait adapter, with explicit native rendering boundaries.

Checks live equipment selection, constructor ABI and bounded composition. It does
not claim to render real character SPR/ACT files or replace in-game acceptance.
"""
import argparse
import json
from pathlib import Path
import struct
from test_vip_ui import VipMachine, snapshot
from unicorn.x86_const import UC_X86_REG_ECX

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('exe');args=parser.parse_args()
m=VipMachine(args.exe)
meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text())
base=m.c['api']-meta['exports']['VipApi']
portrait=base+meta['exports']['_VipPortrait@20'];canvas_slot=base+meta['exports']['VipPortraitCanvas']
obj=m.ready();mode=m.alloc(0x100);world=m.alloc(0x40);actor=m.alloc(0x600)
m.w(mode+0xCC,world);m.w(world+0x2C,actor);m.w(actor+0x4C8,3)
m.stub(0xA75340,lambda:m.ret(0,mode));m.stub(0xD5B580,lambda:m.ret(0,7))
m.stub(0xD84760,lambda:m.ret(0,1))
for addr,value in [(0x15FB278,6),(0x15FB28C,4),(0x15FB290,5),(0x160240C,123)]:m.w(addr,value)
calls=[];draws=[];destroyed=[];canvases=[]
def construct():
    values=m.args(19);assert values[1:8]==[256,320,1,7,7,3,6],values
    assert values[12:]==[0,123,4,5,0,0,0],values
    assert values[0]!=obj,'Must never use the real Alt+Q or VIP parent as scratch'
    canvas=values[0];canvases.append(canvas)
    assert m.r(canvas+0x14)==512 and m.r(canvas+0x18)==512
    calls.append(values);m.ret(76,m.u.reg_read(UC_X86_REG_ECX))
size=[80,130]
def native_draw():
    assert m.args(1)==[0],'Native software composition mode'
    draws.append(m.u.reg_read(UC_X86_REG_ECX));canvas=canvases[-1]
    pix,w,h=m.pixels(canvas);width,height=size
    # Boundary geometry, not fake character artwork. Exercise large robes and clipping.
    for y in range(100,100+height):
        m.u.mem_write(pix+(y*w+100)*4,struct.pack('<I',0xFF123456)*width)
    m.ret(4)
def native_destroy():destroyed.append(m.u.reg_read(UC_X86_REG_ECX));m.ret(0)
m.stub(0x7AC210,construct);m.stub(0x7AC820,native_draw);m.stub(0x79A6A0,native_destroy)

def item(slot,item_id,view,costume=False):
    pos=0x15FA3C0+(0x2B30 if costume else 0x17D0)+slot*0xF8
    m.w(pos+4,item_id);m.w(pos+0x70,view)
def render(expected):
    before=bytes(m.u.mem_read(0x15FA3C0+0x17D0,0x2D00))
    m.invoke(portrait,0,(obj,20,48,92,166))
    assert calls[-1][8:12]==expected,calls[-1]
    assert len(calls)==len(draws)==len(destroyed) and draws[-1]==destroyed[-1]
    assert bytes(m.u.mem_read(0x15FA3C0+0x17D0,0x2D00))==before,'Equipment arrays mutated'

for slot,item_id,view in [(8,101,201),(9,102,202),(0,103,203),(2,104,204)]:item(slot,item_id,view)
render([203,201,202,204])
for slot,item_id,view in [(8,301,401),(9,302,402),(0,303,403),(2,304,404)]:item(slot,item_id,view,True)
render([403,401,402,404])
item(9,0,0,True);item(2,0,0,True);render([403,401,202,204])
# One costume occupying multiple head slots is drawn once, just like Alt+Q.
item(9,301,401,True);item(0,301,401,True);render([0,401,0,204])
# A real costume with no view ID intentionally hides its normal counterpart.
item(8,300,0,True);item(9,0,0,True);item(0,0,0,True);item(2,304,0,True)
render([203,0,202,0])
for slot in (0,2,8,9):item(slot,0,0,True);item(slot,0,0)
render([0,0,0,0])
# Large garment geometry fits strictly inside the 92x166 portrait region.
size[:]=[300,350]
pix,w,h=m.pixels(obj);m.u.mem_write(pix,struct.pack('<I',0xFFAABBCC)*(w*h))
render([0,0,0,0])
pixels=struct.unpack('<'+'I'*(w*h),m.u.mem_read(pix,w*h*4))
changed=[(i%w,i//w) for i,p in enumerate(pixels) if p!=0xFFAABBCC]
assert changed and all(20<=x<112 and 48<=y<214 for x,y in changed)
assert len(set(canvases))==1,'Reopening/drawing leaked preview frames'
before=len(calls);m.w(world+0x2C,0);m.invoke(portrait,0,(obj,20,48,92,166))
assert len(calls)==before,'Missing actor must not render stale character'
m.w(world+0x2C,actor)
m.invoke(m.c['destroy'],obj,(1,));assert not m.r(canvas_slot),'Portrait canvas leaked on parent destruction'
print('PASS: native x86 portrait adapter ABI; upper/mid/lower/garment views, all four costumes, '
      'normal fallback, multi-slot deduplication, zero-view costumes, body/hair/palettes, '
      'no equipment writes, bounded large-robe fit, missing actor, reuse/destruction. Live sprite acceptance pending.')
