"""Verify approved frame, ten crown slots and live state replaces mockup data."""
import argparse,struct
from pathlib import Path
from test_vip_ui import VipMachine,snapshot,benefit_draws
from vip_design_contract import X,Y,crop,read,button,bounds
ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
a.output.mkdir(parents=True,exist_ok=True);m=VipMachine(a.exe);c=m.c
def render(level,flags=1|2|4,experience=None,percent=0,name=None):
    if not level:flags&=~1
    p=snapshot(level=level,flags=flags);struct.pack_into('<I',p,20,percent)
    if experience is not None:p[112:176]=experience.encode().ljust(64,b'\0')
    obj=m.ready(p);m.texts=[]
    if name:m.preview(obj,a.output/name)
    else:m.invoke(c['draw'],obj)
    return obj
for level in range(11):
    obj=render(level,experience='0 / 0 EXP' if not level else '0 / 500,000 EXP',name=f'level-{level}.png' if level in (0,1,5,10) else None)
    for i in range(10):
        want=crop(33 if i<level else 349,851,59,74,X(59),Y(74))
        assert read(m,obj,X(35+i*63),Y(851),X(59),Y(74)).tobytes()==want.tobytes(),(level,i)
    assert any(t[0]==f'VIP Level : {level}' for t in m.texts)
    effects=[];p=snapshot(level=level)
    if level:
        for start in (456+(level-1)*184,536+(level-1)*184):
            effects += [s.strip() for s in p[start:start+80].split(b'\0',1)[0].decode().split('|') if s.strip()]
    assert [t[0] for t in benefit_draws(m)]==effects[:4]
    if not level:assert not any(t[0]=='0 / 0 EXP' for t in m.texts)
    for x,y in [(443,270),(443,333)]:
        count=len(m.sent);m.click(obj,x,y);assert len(m.sent)==count
        assert m.r(c['state']+20)==(0 if y==270 or len(effects)<=4 else 1)
for flags in (2|4,1|2):
    obj=render(7,flags,name=f'no-benefits-{flags}.png');assert not benefit_draws(m)
    width=X(1336)-X(733);height=Y(1039)-Y(835)
    want=crop(725,835,6,204,width,height)
    assert read(m,obj,X(733),Y(835),width,height).tobytes()==want.tobytes()
    # The empty region must be a pale panel, never stretched blue frame stripes.
    assert min(low for low,high in want.getextrema())>=235
obj=render(0,percent=65)
empty=crop(1160,653,40,28,X(1230)-X(180),Y(681)-Y(653))
assert read(m,obj,X(180),Y(653),empty.width,empty.height).tobytes()==empty.tobytes(),'Inactive EXP leaked the mockup fill'
obj=render(2,experience='0/0 EXP');assert not any(t[0]=='0/0 EXP' for t in m.texts)
obj=render(5,flags=1|2|4|8|16|512,name='approved-active.png')
assert any(t=='09-17-2026 Thursday' and color==0x358B23 for t,color,x,y in m.text_colors)
assert any(t=='09-18-2026 Friday' and color==0x3636C9 for t,color,x,y in m.text_colors)
assert all(color==0x30170C for t,color,x,y in m.text_colors if t in ('VIP Start Date: ','VIP Expiry Date: '))
for control in (2,3,4,5,6,9):
    assert read(m,obj,*bounds(control)).tobytes()==button(control,3 if control==2 else 0).tobytes()
assert not any(t[0] in ('Apply VIP','Open Store','Open Storage','VIP Buffs','Upgrade','Refresh') for t in m.texts)
frame=crop(0,0,1412,1114,460,362)
assert read(m,obj,0,0,430,20).tobytes()==frame.crop((0,0,430,20)).tobytes()
assert read(m,obj,0,50,5,300).tobytes()==frame.crop((0,50,5,350)).tobytes()
print('PASS: approved outer frame/buttons, ten earned crowns 0..10, no mockup benefit leakage, inactive clearing, 0/0 EXP suppression and independent arrow bounds.')
