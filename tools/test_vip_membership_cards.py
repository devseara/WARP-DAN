"""Reference-style native membership cards, crowns and live price alignment."""
import argparse
import struct
from pathlib import Path
from PIL import Image,ImageFont
from test_vip_ui import VipMachine,snapshot,ROOT

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c
def open_cards(p=None):
    obj=m.ready(p if p is not None else snapshot(flags=2|4,level=0));m.click(obj,130,173)
    return m.r(c['quest_state'])
q=open_cards();m.preview(q,args.output/'vip-membership-cards.png')
assert Path(m.cstr(m.r(c['api']+312)).replace('\\','/')).name=='membership_crown.png'
assert Image.open(ROOT/'Assets/VipUI/membership_crown.png').getchannel('A').getextrema()==(0,255)
font=ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf',18)
for i,cost in enumerate((500000,1200000,2500000,5000000,9000000)):
    rows=[r for r in m.texts if r[0]==f'{cost:,}z'];assert len(rows)==1
    value,x,y=rows[0][:3];assert x+int(font.getlength(value))==341 and y==36+i*48
    label=[r for r in m.texts if r[0].endswith(' VIP') and r[2]==40+i*48]
    assert len(label)==1 and label[0][1]==54
    pix,w,h=m.pixels(q)
    assert m.r(pix+((25+i*48)*w+6)*4)==0xFFFFFFFF,'Rounded corner must blend into the white popup'
    assert m.r(pix+((45+i*48)*w+3)*4)==0xFFFFFFFF,'Card side margin must remain white'
    assert m.r(pix+((70+i*48)*w+190)*4)==0xFFFFFFFF,'Gap below each card must remain white'
    assert m.r(pix+((27+i*48)*w+190)*4)==0xFF6D6D6B,'Unselected gray card'
    assert any(m.r(pix+((33+i*48+y)*w+16+x)*4)!=0xFF6D6D6B for y in range(28) for x in range(28)),'Missing crown'
before=len(m.sent);m.click(q,170,45);m.preview(q,args.output/'vip-membership-selected.png')
assert len(m.sent)==before
pix,w,h=m.pixels(q)
left=m.r(pix+(28*w+80)*4);right=m.r(pix+(28*w+330)*4)
assert left!=right and (left>>16&255)>(left&255) and (right>>16&255)>(right&255),'Selected cream/gold gradient'
# Prices remain server-provided and fully right-aligned even at the allowed cap.
p=snapshot(flags=2|4,level=0);struct.pack_into('<I',p,2528,1000000000);q=open_cards(p)
m.preview(q,args.output/'vip-membership-max-price.png')
rows=[r for r in m.texts if r[0]=='1,000,000,000z'];assert len(rows)==1
assert rows[0][1]>=193 and rows[0][1]+int(font.getlength(rows[0][0]))==341
print('PASS: five gray rounded cards on a white popup, shared transparent crown, cream/gold selection, left bold day labels, right-aligned complete server prices through 1,000,000,000z; selection never pays.')
