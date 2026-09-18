"""Execute emitted client x86 for the complete VIP 0 -> 1 -> ... -> 5 UI flow."""
import argparse
import struct
from pathlib import Path
from test_vip_ui import VipMachine, snapshot
from vip_design_contract import X,Y,crop,read

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;qs=c['quest_state'];m.w(0x159C088,0)

def packet(level,flags=1|2|4|8):
    p=snapshot(flags=flags,level=level,token=1000+level)
    struct.pack_into('<I',p,20,100)
    message='VIP 1 quest available with active membership' if not level else 'EXP full. Begin your upgrade quest.'
    p[112:176]=message.encode().ljust(64,b'\0')
    p[272:336]=('Begin your VIP 1 quest.' if not level else 'EXP full. Begin your upgrade quest.').encode().ljust(64,b'\0')
    return p

for current in range(5):
    obj=m.ready(packet(current));before=len(m.sent)
    m.preview(obj,args.output/f'vip-{current}-ready.png')
    assert not m.r(qs+16),'Opening the main card must never open a quest popup'
    assert any(row[0]==f'VIP Level : {current}' for row in m.texts)
    if not current:
        assert any(row[0]=='VIP 1 quest available with active membership' for row in m.texts)
        assert not any('0 / 0' in row[0] or row[0]=='VIP LEVEL 1 (ACTIVE)' for row in m.texts)
        pix,w,h=m.pixels(obj)
        empty=crop(349,851,59,74,X(59),Y(74))
        for i in range(10):
            assert read(m,obj,X(35+i*63),Y(851),X(59),Y(74)).tobytes()==empty.tobytes(),'No unearned crowns at active level zero'
        pixel=m.r(pix+(Y(653)*w+X(180))*4)
        assert (pixel>>16&255)>(pixel>>8&255)>(pixel&255),'First authorized quest uses the gold ready bar'
    m.click(obj,196,259);q=m.r(qs)
    assert m.r(qs+16)==1 and len(m.sent)==before and m.window_order()[-1]==q
    m.click(q,164,86);assert struct.unpack_from('<H',m.sent[-1],10)[0]==4
    p=packet(current,1|2|4|8|32|64)
    struct.pack_into('<II',p,2272,0 if not current else 3000000,current+1)
    for i,(item,amount,name) in enumerate(((909,51,'Jellopy'),(914,73,'Fluff'),(606,100,'Aloe Vera'))):
        struct.pack_into('<III48s',p,2344+i*60,item,amount,0,name.encode())
    obj=m.ready(p);q=m.r(qs)
    assert m.r(qs+16)==2 and m.window_order()[-1]==q
    if not current:m.preview(q,args.output/'vip-1-requirements.png')
    before=len(m.sent);m.click(q,150,249);assert len(m.sent)==before,'Incomplete requirements cannot submit'
    struct.pack_into('<H',p,10,1|2|4|8|32|64|128)
    for i in range(3):struct.pack_into('<I',p,2352+i*60,struct.unpack_from('<I',p,2348+i*60)[0])
    obj=m.ready(p);q=m.r(qs);m.click(q,150,249)
    assert len(m.sent)==before and m.r(qs+16)==5
    m.click(q,164,86)
    assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==7
    m.click(q,150,249);assert len(m.sent)==before+1,'Duplicate submit'

# Server flags alone enable the next action: expiry and Cash Shop tiers stay locked.
for level,flags in ((0,2|4),(5,1|2|4),(6,1|2|4),(10,1|2|4)):
    obj=m.ready(packet(level,flags));before=len(m.sent);m.click(obj,196,259)
    assert not m.r(qs+16) and len(m.sent)==before
for label in ('0/0 EXP','0 / 0 EXP'):
    p=packet(0);p[112:176]=label.encode().ljust(64,b'\0');obj=m.ready(p);m.texts=[];m.invoke(c['draw'],obj)
    assert not any(row[0]==label for row in m.texts),'Level-zero support must not reintroduce 0/0 EXP'
print('PASS: VIP 0-4 opens each quest for levels 1-5 through confirmation, visible first-quest text/gold bar/no crowns, ready/incomplete/replay gates, expiry and Cash Shop locks; no live items or purchases.')
