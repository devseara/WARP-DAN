"""Execute VIP's full-PNG button renderer and input states at native x86 boundaries."""
import argparse
import json
import struct
from pathlib import Path
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine, snapshot, ROOT

parser=argparse.ArgumentParser();parser.add_argument('exe');args=parser.parse_args()
m=VipMachine(args.exe);c=m.c;obj=m.ready(snapshot(flags=1|2|4|8|16))
meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text())
assert meta['api_size']==320
base=c['api']-meta['exports']['VipApi'];paint=base+meta['exports']['_VipPaintButton@12']
groups=[('close',1,781,1,15,18),('applyvip',2,122,166,60,18),
        ('openstore',3,188,166,68,18),('openstorage',4,122,192,81,18),
        ('vipbuffs',5,209,192,57,18),('upgrade',6,293,296,53,18),
        ('refresh',9,288,375,58,18),('yes',21,150,78,28,18),
        ('no',22,186,78,23,18),('cancel',24,189,240,43,18),
        ('scroll_top',7,775,111,13,13),('scroll_bot',8,775,346,13,13)]
pix,w,h=m.pixels(obj);background=bytes.fromhex('332211ff')*(w*h)

def filename(group,state):
    return group+'.png' if group.startswith('scroll_') and state==0 else group+'_'+('out','over','press','off')[state]+'.png'

def read(x,y,width,height):
    data=b''.join(bytes(m.u.mem_read(pix+((y+row)*w+x)*4,width*4)) for row in range(height))
    return Image.frombytes('RGBA',(width,height),data,'raw','BGRA').convert('RGB')

def expected(name):
    src=Image.open(ROOT/'Assets/VipUI'/name).convert('RGBA')
    dst=Image.new('RGB',src.size)
    result=[]
    for r,g,b,a in src.getdata():
        if (r,g,b)==(255,0,255):a=0
        result.append(tuple((s*a+d*(255-a)+127)//255 for s,d in zip((r,g,b),(17,34,51))))
    dst.putdata(result);return dst

for index,(group,control,x,y,width,height) in enumerate(groups):
    for state in range(4):
        name=filename(group,state)
        assert Path(m.cstr(m.r(c['api']+96+(index*4+state)*4)).replace('\\','/')).name==name
        want=expected(name);assert want.size==(width,height),(name,want.size)
        m.u.mem_write(pix,background);m.texts=[]
        m.invoke(paint,0,(obj,control,state))
        assert read(x,y,width,height).tobytes()==want.tobytes(),name
        assert not m.texts,'Image caption was repainted by code'
        assert m.r(m.r(obj+0x24)+0x28)&255==0,'Changed native opaque upload mode'
        actual=bytes(m.u.mem_read(pix,w*h*4));allowed=bytearray(background)
        for row in range(height):
            offset=((y+row)*w+x)*4;allowed[offset:offset+width*4]=actual[offset:offset+width*4]
        assert actual==allowed,'Painting escaped button bounds'

# Main Upgrade and title-bar X shrink their hit areas together with the PNGs.
for control,x,y,width,height in [(1,781,1,15,18),(6,293,296,53,18),(9,288,375,58,18)]:
    for px,py,want in [(x,y,control),(x+width-1,y+height-1,control),
                       (x-1,y+5,0),(x+width,y+5,0),(x+3,y+height,0)]:
        m.invoke(c['hit'],0,(px,py));assert m.u.reg_read(UC_X86_REG_EAX)==want

# A custom texture must own every pixel, even where the old code wrote its text.
obj=m.ready(snapshot(flags=2|4,level=0))
tex=m.load_texture('applyvip_out.png');pointer=m.r(tex+0x11C)
original=bytes(m.u.mem_read(pointer,60*18*4));sentinel=bytes.fromhex('c08040ff')*(60*18)
m.u.mem_write(pointer,sentinel);m.texts=[];m.invoke(c['draw'],obj)
assert set(read(122,166,60,18).getdata())=={(64,128,192)}
assert not any(t[0]=='Apply VIP' for t in m.texts)
m.u.mem_write(pointer,original)

def hit():
    m.invoke(c['hit'],0,(130,173));return m.u.reg_read(UC_X86_REG_EAX)

# Missing or incorrect normal art must not leave an invisible clickable action.
assert hit()==2
for offset in (0x114,0x118,0x11C):
    old=m.r(tex+offset);m.w(tex+offset,0);assert hit()==0;m.w(tex+offset,old)
missing=set()
def texture():
    name=m.cstr(m.args(1)[0]).split('\\')[-1]
    if name in missing:m.ret(4,0)
    else:m.texture()
m.stub(0xA8D4A0,texture)
missing.add('applyvip_out.png');assert hit()==0;missing.clear();assert hit()==2

# Bad or missing optional states fall back to the normal image, never code text.
hover=m.load_texture('applyvip_over.png');old=m.r(hover+0x114);m.w(hover+0x114,1)
for absent in (False,True):
    if absent:missing.add('applyvip_over.png')
    m.u.mem_write(pix,background);m.texts=[];m.invoke(paint,0,(obj,2,1))
    assert read(122,166,60,18).tobytes()==expected('applyvip_out.png').tobytes()
    assert not m.texts
m.w(hover+0x114,old);missing.clear()

# Invalid requests and insufficient target bounds are inert.
for target,control,state in [(obj,2,-1),(obj,2,4),(obj,999,0),(0,2,0)]:
    m.u.mem_write(pix,background);m.invoke(paint,0,(target,control,state))
    assert bytes(m.u.mem_read(pix,w*h*4))==background
surface=m.r(obj+0x24);old=m.r(surface+4);m.w(surface+4,140)
m.invoke(paint,0,(obj,2,0));assert bytes(m.u.mem_read(pix,w*h*4))==background
m.w(surface+4,old)

# Actual input lifecycle chooses the same whole normal/hover/pressed/off files.
def check(state):
    m.texts=[];m.invoke(c['draw'],obj)
    im=Image.open(ROOT/'Assets/VipUI'/filename('applyvip',state)).convert('RGB')
    assert read(122,166,60,18).tobytes()==im.tobytes(),state
    assert not any(t[0]=='Apply VIP' for t in m.texts)
check(0);m.invoke(c['move'],obj,(130,173));check(1)
m.invoke(c['down'],obj,(130,173));check(2)
before=len(m.sent);m.invoke(c['move'],obj,(400,50));m.invoke(c['up'],obj,(400,50));check(0)
assert len(m.sent)==before and m.r(0x131F4E8+0x19C)==0
m.w(c['state']+24,0);check(3);m.w(c['state']+24,1)
m.click(obj,130,173);assert len(m.sent)==before and m.r(c['quest_state']+16)==3

# Refresh reuses Upgrade's rounded three-column skin without changing its ABI.
for state in ('out','over','press','off'):
    refresh=Image.open(ROOT/'Assets/VipUI'/f'refresh_{state}.png').convert('RGBA')
    upgrade=Image.open(ROOT/'Assets/VipUI'/f'upgrade_{state}.png').convert('RGBA')
    assert refresh.size==(58,18)
    assert refresh.crop((0,0,3,18)).tobytes()==upgrade.crop((0,0,3,18)).tobytes()
    assert refresh.crop((55,0,58,18)).tobytes()==upgrade.crop((50,0,53,18)).tobytes()
obj=m.ready(snapshot(token=123,flags=2|4,level=0));m.now+=1000
before=len(m.sent)
m.invoke(c['down'],obj,(310,383));m.invoke(c['up'],obj,(400,383))
assert len(m.sent)==before and not m.r(0x131F4E8+0x19C),'Refresh release outside must cancel'
m.click(obj,310,383)
assert len(m.sent)==before+1
assert struct.unpack_from('<HHIHHIII',m.sent[-1])==(0xBFA,24,0x55504956,4,0,123,0,0),'Refresh remains a read-only snapshot request'
print('PASS: all 48 complete PNG states/pixels, custom art owns caption area, no text overlay; '
      'fitted Upgrade/X/Refresh hits, matching rounded Refresh skin, bounds/upload safety, missing/mis-sized art, normal fallback, real hover/press/disabled input and action preserved.')
