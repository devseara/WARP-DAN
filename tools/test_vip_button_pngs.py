"""Execute all 60 native-size button PNG states, bounds and input guards."""
import argparse,json,struct,tempfile
from pathlib import Path
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine,snapshot,ROOT
from vip_design_contract import BUTTONS,bounds,button,read
from render_vip_readable_buttons import render
# Reproduce every caption from the regular-weight source exporter, so matching
# two copies of accidentally bold artwork cannot pass this regression.
assert "tahomabd.ttf" not in (ROOT/'tools/render_vip_readable_buttons.py').read_text()
with tempfile.TemporaryDirectory(prefix='vip-regular-buttons-') as temporary:
    generated=Path(temporary)/'buttons';render(generated)
    for expected in generated.glob('*.png'):
        assert expected.read_bytes()==(ROOT/'Assets/VipUI'/expected.name).read_bytes(),expected.name
ap=argparse.ArgumentParser();ap.add_argument('exe');a=ap.parse_args()
m=VipMachine(a.exe);c=m.c;obj=m.ready(snapshot(flags=1|2|4|8|16|512))
meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text());assert meta['api_size']==372
paint=c['api']-meta['exports']['VipApi']+meta['exports']['_VipPaintButton@12']
ptr,w,h=m.pixels(obj);background=bytes.fromhex('332211ff')*(w*h)
def verify(control,state,rect,want):
    x,y,cw,ch=rect;m.u.mem_write(ptr,background);m.texts=[]
    m.invoke(paint,0,(obj,control,state))
    assert read(m,obj,x,y,cw,ch).tobytes()==want.tobytes(),(control,state)
    assert not m.texts,'Captions must come from artwork'
    actual=bytes(m.u.mem_read(ptr,w*h*4));allowed=bytearray(background)
    for row in range(ch):
        offset=((y+row)*w+x)*4;allowed[offset:offset+cw*4]=actual[offset:offset+cw*4]
    assert actual==allowed,'Draw escaped its visible bounds'
    assert m.r(m.r(obj+0x24)+0x28)&255==0
for control in BUTTONS:
    for state in range(4):verify(control,state,bounds(control),button(control,state))
for control,group,rect in [(20,'close',(341,1,15,18)),(21,'yes',(150,78,28,18)),
                           (22,'no',(186,78,23,18)),(23,'upgrade',(128,240,53,18)),
                           (24,'cancel',(189,240,43,18)),(25,'purchase',(126,296,56,18))]:
    for state,name in enumerate(('out','over','press','off')):
        art=Image.open(ROOT/'Assets/VipUI'/f'{group}_{name}.png').convert('RGBA')
        want=Image.alpha_composite(Image.new('RGBA',art.size,(17,34,51,255)),art).convert('RGB')
        verify(control,state,rect,want)
def hit(x,y):
    m.invoke(c['hit'],0,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
for control in BUTTONS:
    if control in (7,8):continue
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
normal=m.load_texture('applyvip_out.png')
for offset in (0x114,0x118,0x11C):
    old=m.r(normal+offset);m.w(normal+offset,0)
    assert hit(217,127)==0,'Invalid normal button artwork must disable the action'
    m.w(normal+offset,old)
missing.add('applyvip_out.png');assert not hit(217,127)
missing.clear();assert hit(217,127)==2
hover=m.load_texture('yes_over.png');old=m.r(hover+0x114);m.w(hover+0x114,1)
for absent in (False,True):
    if absent:missing.add('yes_over.png')
    art=Image.open(ROOT/'Assets/VipUI/yes_out.png').convert('RGBA')
    want=Image.alpha_composite(Image.new('RGBA',art.size,(17,34,51,255)),art).convert('RGB')
    verify(21,1,(150,78,28,18),want)
m.w(hover+0x114,old);missing.clear()
for target,control,state in [(obj,2,-1),(obj,2,4),(obj,999,0),(0,2,0)]:
    m.u.mem_write(ptr,background);m.invoke(paint,0,(target,control,state))
    assert bytes(m.u.mem_read(ptr,w*h*4))==background
surface=m.r(obj+0x24);old=m.r(surface+4);m.w(surface+4,140)
m.invoke(paint,0,(obj,2,0));assert bytes(m.u.mem_read(ptr,w*h*4))==background;m.w(surface+4,old)
def check(state):
    m.texts=[];m.invoke(c['draw'],obj)
    assert read(m,obj,*bounds(2)).tobytes()==button(2,state).tobytes()
    assert not any(t[0]=='Apply VIP' for t in m.texts)
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
print('PASS: all 60 complete button PNGs, pixel-exact drawing, hit/paint bounds, missing/mis-sized art, fallback, capture, hover/press/off, refresh ABI.')
