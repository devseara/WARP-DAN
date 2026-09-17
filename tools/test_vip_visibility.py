"""Run emitted x86: fitted controls, earned crowns, active benefits and full-thickness EXP."""
import argparse
from pathlib import Path
import struct
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine, snapshot, ROOT, benefit_draws

parser=argparse.ArgumentParser();parser.add_argument('exe');parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c
crown=Image.open(ROOT/'Assets/VipUI/membership_crown.png').convert('RGBA')
expected_crown=[]
for y in range(24):
    for x in range(24):
        r,g,b,a=crown.getpixel((x*crown.width//24,y*crown.height//24))
        if (r,g,b)==(255,0,255):a=0
        rgb=tuple((s*a+d*(255-a)+127)//255 for s,d in zip((r,g,b),(244,248,255)))
        expected_crown.append(0xFF000000|(rgb[0]<<16)|(rgb[1]<<8)|rgb[2])
def render(level,flags=1|2|4,experience=None,percent=0,name=None):
    if not level:flags&=~1
    p=snapshot(level=level,flags=flags);struct.pack_into('<I',p,20,percent)
    if experience is not None:p[112:176]=experience.encode().ljust(64,b'\0')
    if not flags&1:p[176:272]=b'Membership inactive. Renew to use VIP benefits.'.ljust(96,b'\0')
    obj=m.ready(p);m.texts=[]
    if name:m.preview(obj,args.output/name)
    else:m.invoke(c['draw'],obj)
    return obj,m.pixels(obj)

for level in range(11):
    obj,(pix,w,h)=render(level,experience='0 / 0 EXP' if not level else '0 / 500,000 EXP',
        name=f'vip-level-{level}.png' if level in (0,1,5,10) else None)
    for i in range(10):
        actual=[m.r(pix+((326+y)*w+25+i*32+x)*4) for y in range(24) for x in range(24)]
        assert actual==(expected_crown if i<level else [0xFFF4F8FF]*(24*24)),(level,i)
    assert any(s==f'Vip Level : {level}' for s,*_ in m.texts)
    assert not any(s==f'VIP LEVEL {level}/10' for s,*_ in m.texts)
    titles=[s for s,*_ in m.texts if s.startswith('VIP LEVEL ') and '/' not in s]
    assert not titles,titles
    p=snapshot(level=level)
    effects=[]
    if level:
        for start in (456+(level-1)*184,536+(level-1)*184):
            effects.extend(s.strip() for s in p[start:start+80].split(b'\0',1)[0].decode().split('|') if s.strip())
    assert [row[0] for row in benefit_draws(m)]==effects[:5]
    if not level:assert not any('0 / 0 EXP'==s for s,*_ in m.texts)
    for x,y in [(781,117),(781,352)]:
        before=len(m.sent);m.click(obj,x,y)
        assert len(m.sent)==before and m.r(c['state']+20)==(0 if y==117 or len(effects)<=5 else 1)

# Expired VIP retains earned level but no active benefits/placeholder reward cards.
for flags in (2|4,1|2): # Membership expired; or tier system disabled.
    obj,(pix,w,h)=render(7,flags=flags,name=f'vip-no-benefits-{flags}.png')
    assert not any(s.startswith('VIP LEVEL ') and '/' not in s for s,*_ in m.texts)
    assert m.r(pix+(120*w+450)*4)==0xFFF2F8FF,'Stale active card after expiry'
obj,(pix,w,h)=render(2,experience='0/0 EXP')
assert not any(s=='0/0 EXP' for s,*_ in m.texts)

# Uniform four-pixel track reaches the last column, with no stretched alpha cap.
obj,(pix,w,h)=render(2,experience='0 / 500,000 EXP',percent=0)
track=[m.r(pix+((272+y)*w+24+x)*4) for y in range(4) for x in range(322)]
assert set(track)=={0xFFCBD4EB},set(map(hex,track))
obj,(pix,w,h)=render(2,experience='500,000 / 500,000 EXP',percent=100,flags=1|2|4|8)
fill=[m.r(pix+((272+y)*w+24+x)*4) for y in range(4) for x in range(322)]
assert set(fill)=={0xFFD6AB35},set(map(hex,fill))

# All four complete PNGs retain fitted text + 4px padding per side; clicks outside
# the visible border/gap must not trigger actions or a hand cursor.
obj,(pix,w,h)=render(2,flags=1|2|4|8|16|512,name='vip-fitted-buttons.png')
expected={2:('Apply VIP',122,166),3:('Open Store',188,166),4:('Open Storage',122,192),5:('VIP Buffs',209,192)}
def hit(x,y):
    m.invoke(c['hit'],0,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
for control,(label,x,y) in expected.items():
    width=int(m.font.getlength(label))+8
    for px,py in [(x,y),(x+width-1,y+17)]:
        assert hit(px,py)==(0 if control==2 else control),(label,px,py)
    assert hit(x+width,y+8)==0,label
    assert not any(r[0]==label for r in m.texts),'Button captions must come only from PNGs'
    filename={2:'applyvip',3:'openstore',4:'openstorage',5:'vipbuffs'}[control]+('_off.png' if control==2 else '_out.png')
    source=Image.open(ROOT/'Assets/VipUI'/filename).convert('RGB')
    assert source.size==(width,18)
    pixels=b''.join(bytes(m.u.mem_read(pix+((y+row)*w+x)*4,width*4)) for row in range(18))
    actual=Image.frombytes('RGBA',(width,18),pixels,'raw','BGRA').convert('RGB')
    assert actual.tobytes()==source.tobytes(),filename
assert {'scroll_top.png','scroll_bot.png'} <= {Path(k.replace('\\','/')).name for k in m.textures}
assert 'star_on.png' not in {Path(k.replace('\\','/')).name for k in m.textures},'Legacy star still rendered'
print('PASS: levels 0..10 have exactly earned crown pixels; no legacy stars; current active tier only; expired/disabled benefits clear; '
      '0/0 EXP hidden; uniform four-pixel image bar through final column; gold ready fill; '
      'four fitted complete-PNG button bounds with no text overlay; supplied scroll arrows disabled without extra content.')
