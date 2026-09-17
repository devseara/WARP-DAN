"""Execute emitted VIP x86: separate active effects, bounded scrolling and refresh.

Native textures/text/OS boundaries are emulated; this is not live acceptance.
"""
import argparse
from pathlib import Path
import struct
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine, snapshot, benefit_draws

parser=argparse.ArgumentParser()
parser.add_argument('exe')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--game',type=Path,help='Use installed vipui PNGs without modifying them')
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;s=c['state']
if args.game:
    installed=list((args.game/'data/texture').glob('*/vipui/vip_status_bg.png'))
    assert len(installed)==1,installed
    m.assets=installed[0].parent

def effects(p):
    level=struct.unpack_from('<I',p,16)[0]
    if not level or struct.unpack_from('<H',p,10)[0]&5!=5:return []
    if struct.unpack_from('<H',p,10)[0]&1024:
        return [p[start:start+79].split(b'\0',1)[0].decode() for i in range(10)
                for start in (456+i*184,536+i*184) if p[start]]
    result=[]
    for start in (456+(level-1)*184,536+(level-1)*184):
        result.extend(part.strip(' \t') for part in p[start:start+79].split(b'\0',1)[0].decode().split('|') if part.strip(' \t'))
    return result

def hit(x,y):
    m.invoke(c['hit'],0,(x,y));return m.u.reg_read(UC_X86_REG_EAX)

def draw(obj,expected,offset=0,name=None):
    m.texts=[]
    if name:m.preview(obj,args.output/name)
    else:m.invoke(c['draw'],obj)
    rows=benefit_draws(m)
    fitted=[]
    for value in expected[offset:offset+5]:
        while value and int(m.font.getlength(value))>342:value=value[:-1]
        fitted.append(value)
    assert [r[0] for r in rows]==fitted,rows
    assert [r[1] for r in rows]==[413+(342-int(m.font.getlength(t)))//2 for t in fitted],'Effect text not centered'
    assert [r[2] for r in rows]==[127+i*48 for i in range(len(rows))]
    assert m.r(s+20)==offset
    pix,w,h=m.pixels(obj)
    for i in range(5):
        assert m.r(pix+((116+i*48)*w+402)*4)==(0xFFDFB355 if i<len(rows) else 0xFFF2F8FF),'Stale/missing card'
    assert hit(781,117)==(7 if offset else 0)
    assert hit(781,352)==(8 if offset<max(0,len(expected)-5) else 0)
    return pix,w,h

# Every level shows only its own effects. Page position advances one card;
# neither arrow emits packets, changes tiers, or opens another window.
for level in range(11):
    p=snapshot(level=level);want=effects(p);obj=m.ready(p)
    draw(obj,want,name=f'vip-benefits-level-{level}.png' if level in (0,1,7,10) else None)
    sent=len(m.sent);limit=max(0,len(want)-5)
    for i in range(limit+3):
        m.click(obj,781,352);assert m.r(s+20)==min(i+1,limit)
        assert len(m.sent)==sent and not m.r(c['quest_state']+16)
    draw(obj,want,limit)
    for i in range(limit+3):
        m.click(obj,781,117);assert m.r(s+20)==max(0,limit-i-1)
        assert len(m.sent)==sent and not m.r(0x131F4E8+0x19C)
    draw(obj,want)
    print(f'PASS level {level}: {len(want)} individual effects, scrolling 0..{limit}',flush=True)

p=snapshot(level=7);obj=m.ready(p);want=effects(p)
m.click(obj,781,352);m.click(obj,781,352)
pix,w,h=draw(obj,want,2,name='vip-benefits-level-7-bottom.png')
assert m.r(pix+(339*w+781)*4)==0xFF9DADC8,'Thumb does not reach bottom'
refresh=snapshot(flags=1|4|8,level=7);m.receive(refresh)
draw(obj,want,2,name='vip-benefits-level-7-refresh.png')
assert m.r(pix+(133*w+781)*4)==0xFFDDE5F2
m.receive(snapshot(level=7));draw(obj,want,0)
assert m.r(pix+(133*w+781)*4)==0xFF9DADC8,'Explicit reopen did not reset thumb'

# Release outside never scrolls. Another popup blocks the benefit arrows.
m.invoke(c['down'],obj,(781,352));m.invoke(c['up'],obj,(780,330))
draw(obj,want,0);assert not m.r(0x131F4E8+0x19C)
m.invoke(c['quest_open'],0,(1,));assert not hit(781,352)
m.receive(snapshot(level=7))

# Refresh shrinking the content clamps position; expiry while pressed cannot
# expose stale effects or leave capture/scroll state behind.
m.click(obj,781,352);m.click(obj,781,352)
smaller=snapshot(flags=1|4,level=2);m.receive(smaller);draw(obj,effects(smaller),0)
for flags,level in ((4,7),(1,7),(1|4,0)):
    m.receive(snapshot(level=7));m.click(obj,781,352)
    m.invoke(c['down'],obj,(781,352))
    m.receive(snapshot(flags=flags,level=level));m.invoke(c['up'],obj,(781,352))
    draw(obj,[],name=f'vip-benefits-empty-{flags}-{level}.png')
    assert not m.r(0x131F4E8+0x19C)

# Preserve editable script wording, trim delimiters/whitespace, skip empty
# cards, and bound both packet fields even if the server omits terminators.
def custom(first,second):
    p=snapshot(level=7)
    for start,value in ((456+6*184,first),(536+6*184,second)):
        p[start:start+80]=value.encode().ljust(80,b'\0')[:80]
    return p

for p in (custom(' | EXP +30% || \tDrop +5% | ','\t | HP +100 | | Auto drop -65% |'),
          custom('X'*80,'Y'*80),custom('A|'*40,'B|'*40),custom('','')):
    obj=m.ready(p);want=effects(p);draw(obj,want)
    # Force prior out-of-range state through the same draw clamp.
    m.w(s+20,0x7FFFFFFF);draw(obj,want,max(0,len(want)-5))
    m.w(s+20,0xFFFFFFFF);draw(obj,want,0)

# Same-size/current-row snapshots support future VIPSystem text, not just the
# old two short per-tier fields. Each string is its own card, even with a pipe.
p=snapshot(level=7,flags=1|2|4|1024);p[432:2272]=bytes(1840)
for i in range(20):
    start=456+(i//2)*184+(80 if i%2 else 0)
    p[start:start+80]=(f'Custom benefit {i+1}' if i<19 else 'Auto drop -65%').encode().ljust(80,b'\0')
obj=m.ready(p);want=effects(p);draw(obj,want,name='vip-centered-custom-benefits.png')
for i in range(17):m.click(obj,781,352)
draw(obj,want,15,name='vip-centered-custom-benefits-bottom.png')
p[456:536]=b'ATK +10 | MATK +10'.ljust(80,b'\0');obj=m.ready(p)
draw(obj,effects(p))

print('PASS: all 11 levels, five separate active effect cards, one-row scrolling '
      'and limits, real PNG backgrounds/arrows, moving thumb, no action packets, '
      'capture/modal guards, refresh/reopen, expiry/shrink, empty and bounded labels.')
