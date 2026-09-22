"""Execute all 60 Gacha-skinned VIP button states, captions and input guards."""
import argparse,json,struct
from pathlib import Path
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine,snapshot,ROOT
from vip_design_contract import BUTTONS,bounds,button,read
from vip_design_contract import CAPTIONS
for state in ('out','over','press','off'):
    assert (ROOT/f'Assets/VipUI/button_{state}.png').read_bytes()==(ROOT/f'Assets/GachaUI/button_10_{state}.png').read_bytes()
ap=argparse.ArgumentParser();ap.add_argument('exe');a=ap.parse_args()
m=VipMachine(a.exe);c=m.c;obj=m.ready(snapshot(flags=1|2|4|8|16|512))
meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text());assert meta['api_size']==372
paint=c['api']-meta['exports']['VipApi']+meta['exports']['_VipPaintButton@12']
ptr,w,h=m.pixels(obj);background=bytes.fromhex('332211ff')*(w*h)
def verify(control,state,rect,want):
    x,y,cw,ch=rect;m.u.mem_write(ptr,background);m.texts=[]
    m.invoke(paint,0,(obj,control,state))
    assert read(m,obj,x,y,cw,ch).tobytes()==want.tobytes(),(control,state)
    assert [t[0] for t in m.texts]==([CAPTIONS[control]] if control in CAPTIONS else []),'Captions must be native text'
    actual=bytes(m.u.mem_read(ptr,w*h*4));allowed=bytearray(background)
    for row in range(ch):
        offset=((y+row)*w+x)*4;allowed[offset:offset+cw*4]=actual[offset:offset+cw*4]
    assert actual==allowed,'Draw escaped its visible bounds'
    assert m.r(m.r(obj+0x24)+0x28)&255==0
for control in BUTTONS:
    for state in range(4):verify(control,state,bounds(control),button(control,state,(17,34,51,255)))
def hit(x,y):
    m.invoke(c['hit'],0,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
for control in BUTTONS:
    if control in (7,8) or control>=20:continue
    m.ready(snapshot(flags=2|4 if control==2 else 1|2|4|8|16|512))
    x,y,cw,ch=bounds(control)
    for px,py,want in [(x,y,control),(x+cw-1,y+ch-1,control),(x-1,y+5,0),(x+cw,y+5,0),(x+3,y+ch,0)]:
        assert hit(px,py)==want,(control,px,py)
obj=m.ready(snapshot(flags=2|4,level=0));tex=m.load_texture('vip_design.png')
for offset in (0x114,0x118,0x11C):
    old=m.r(tex+offset);m.w(tex+offset,0);assert hit(217,127)==0;m.w(tex+offset,old)
missing=set()
def texture():
    name=m.cstr(m.args(1)[0]).split('\\')[-1]
    if name in missing:m.ret(4,0)
    else:m.texture()
m.stub(0xA8D4A0,texture);missing.add('vip_design.png');assert not hit(217,127)
missing.clear();assert hit(217,127)==2
normal=m.load_texture('button_out.png')
for offset in (0x114,0x118,0x11C):
    old=m.r(normal+offset);m.w(normal+offset,0)
    assert hit(217,127)==0,'Invalid normal button artwork must disable the action'
    m.w(normal+offset,old)
missing.add('button_out.png');assert not hit(217,127)
missing.clear();assert hit(217,127)==2
hover=m.load_texture('button_over.png');old=m.r(hover+0x114);m.w(hover+0x114,1)
for absent in (False,True):
    if absent:missing.add('button_over.png')
    want=button(21,0,(17,34,51,255),caption_state=1)
    verify(21,1,(150,78,28,18),want)
m.w(hover+0x114,old);missing.clear()
for target,control,state in [(obj,2,-1),(obj,2,4),(obj,999,0),(0,2,0)]:
    m.u.mem_write(ptr,background);m.invoke(paint,0,(target,control,state))
    assert bytes(m.u.mem_read(ptr,w*h*4))==background
surface=m.r(obj+0x24);old=m.r(surface+4);m.w(surface+4,140)
m.invoke(paint,0,(obj,2,0));assert bytes(m.u.mem_read(ptr,w*h*4))==background;m.w(surface+4,old)
def check(state):
    m.texts=[];m.invoke(c['draw'],obj)
    actual=read(m,obj,*bounds(2));want=button(2,state)
    inside=(2,2,actual.width-2,actual.height-2)
    assert actual.crop(inside).tobytes()==want.crop(inside).tobytes()
    assert any(t[0]=='Apply VIP' for t in m.texts)
check(0);m.invoke(c['move'],obj,(217,127));check(1)
m.invoke(c['down'],obj,(217,127));check(2)
before=len(m.sent);m.invoke(c['move'],obj,(400,50));m.invoke(c['up'],obj,(400,50));check(0)
assert len(m.sent)==before and not m.r(0x131F4E8+0x19C)
m.w(c['state']+24,0);check(3);m.w(c['state']+24,1)
m.click(obj,217,127);assert len(m.sent)==before and m.r(c['quest_state']+16)==3
obj=m.ready(snapshot(token=123,flags=2|4,level=0));m.now+=1000;before=len(m.sent)
m.invoke(c['down'],obj,(194,329));m.invoke(c['up'],obj,(240,329))
assert len(m.sent)==before and not m.r(0x131F4E8+0x19C)
m.click(obj,194,329);assert len(m.sent)==before+1
assert struct.unpack('<HHIHHIII',m.sent[-1])==(0xBFA,24,0x55504956,4,0,123,0,0)
print('PASS: all 60 Gacha-style button states, native captions, pixel-exact drawing, hit/paint bounds, missing/mis-sized art, fallback, capture, hover/press/off, refresh ABI.')
