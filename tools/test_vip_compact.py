"""Compact native surface/text bounds and centered popup placement, offline."""
import argparse,struct
from pathlib import Path
from PIL import ImageFont
from unicorn.x86_const import UC_X86_REG_ECX
from test_vip_ui import VipMachine,snapshot

class CompactMachine(VipMachine):
    def text(self):
        obj=self.u.reg_read(UC_X86_REG_ECX)
        x,y,ptr,length,_,height,color,bold,_=self.args(9)
        assert bold==0,'VIP text and all popup captions must use regular weight'
        value=self.cstr(ptr);value=value[:length] if length else value
        font=ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf',height)
        width=self.r(obj+0x14);surface_height=self.r(obj+0x18)
        assert x>=0 and y>=0 and x+int(font.getlength(value))<=width,(value,x,width)
        assert y+height<=surface_height,(value,y,height,surface_height)
        self.sizes.setdefault(obj,set()).add(height)
        super().text()
    def measure(self):
        assert self.args(6)[4]==0,'VIP fitting and hover must measure regular weight'
        super().measure()

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=CompactMachine(a.exe);m.sizes={};c=m.c
obj=m.ready(snapshot(level=5,flags=1|2|4|8|16|512))
m.preview(obj,a.output/'compact-active.png')
assert (m.r(obj+0x14),m.r(obj+0x18))==(460,362)
assert m.sizes[obj]=={11},m.sizes
assert m.r(obj+0x1C)+460<=800 and m.r(obj+0x20)+362<=600
for height in m.sizes[obj]:assert height<12,'Main text retained large-window font'

# Bounded server strings cannot escape the smaller fields or lower cards.
p=snapshot(level=7,flags=1|2|4|8|16|512|1024)
for offset,size in ((24,24),(48,32),(80,32),(112,64),(176,96),(272,64),(336,96)):
    p[offset:offset+size]=b'W'*size
for i in range(10):
    for offset in (456+i*184,536+i*184):p[offset:offset+80]=b'W'*80
obj=m.ready(p);m.preview(obj,a.output/'compact-long-fields.png')

p=snapshot(flags=2|4|256,level=0)
p[48:80]=b'Not recorded'.ljust(32,b'\0');p[80:112]=b'Not active'.ljust(32,b'\0')
p[176:272]=b'Payment pending confirmation. Do not buy again.'.ljust(96,b'\0')
obj=m.ready(p);m.preview(obj,a.output/'compact-payment-pending.png')
before=len(m.sent);m.click(obj,217,127)
assert len(m.sent)==before and not m.r(c['quest_state']+16)

# All five popup modes keep original readable dimensions and are centered.
for mode,height in ((1,118),(2,270),(3,320),(4,118),(5,118)):
    p=snapshot(flags=(2|4) if mode==3 else (1|2|4|8|32|128|512))
    for i in range(3):struct.pack_into('<III48s',p,2344+i*60,501+i,10,10,f'Item {i+1}'.encode())
    obj=m.ready(p)
    if mode==5:m.invoke(c['quest_open'],0,(2,))
    m.invoke(c['quest_open'],0,(mode,));q=m.r(c['quest_state'])
    assert m.r(c['quest_state']+16)==mode
    assert (m.r(q+0x14),m.r(q+0x18))==(360,height)
    assert m.r(q+0x1C)==m.r(obj+0x1C)+50
    assert m.r(q+0x20)==m.r(obj+0x20)+(362-height)//2
    m.preview(q,a.output/f'compact-popup-{mode}.png')
    assert 12 in m.sizes[q],'Popup text was shrunk with main'
assert {14,18}<=m.sizes[q],'Membership labels/prices changed font sizes'
print('PASS: 460x362 surface, 800x600 fit, compact text metrics, bounded long server fields, pending-payment gate, five centered popups with unchanged readable fonts and dimensions.')
