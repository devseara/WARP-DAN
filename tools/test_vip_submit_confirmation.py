"""Actual emitted x86 final VIP submission Yes/No, stale state and replay guards."""
import argparse
import struct
from pathlib import Path
from test_vip_ui import VipMachine
from test_vip_quest_ui import quest

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;qs=c['quest_state'];m.w(0x159C088,0)

def open_confirm():
    obj=m.ready(quest(ready=True));q=m.r(qs);count=len(m.sent)
    m.click(q,150,248)
    assert m.r(qs+16)==5 and len(m.sent)==count and m.window_order()[-1]==q
    assert (m.r(q+0x14),m.r(q+0x18))==(360,118)
    assert m.r(obj+0x28) and m.r(q+0x28)
    return obj,q,count

obj,q,count=open_confirm();m.preview(q,args.output/'vip-final-confirm.png')
assert any('Submit these requirements' in row[0] for row in m.texts)
for x,y in ((193,86),(348,8)):
    obj,q,count=open_confirm();m.click(q,x,y)
    assert m.r(qs+16)==2 and len(m.sent)==count and m.r(q+0x18)==270,'No/X must restore saved requirements'
    m.click(q,150,248);assert m.r(qs+16)==5 and len(m.sent)==count

obj,q,count=open_confirm()
m.invoke(c['down'],q,(164,86));m.invoke(c['up'],q,(250,105))
assert len(m.sent)==count and m.r(qs+16)==5 and not m.r(0x131F4E8+0x19C)
m.invoke(0xA39130,0x131F4E8,(obj,));m.click(obj,50,8)
assert m.window_order()[-1]==q and not m.r(c['state']+12),'Final confirmation behind main'
m.receive(quest(ready=True,opened=False));assert m.r(qs+16)==5,'Routine refresh dismissed unchanged confirmation'
m.click(q,164,86)
assert len(m.sent)==count+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==7
assert not m.r(q+0x28) and m.r(obj+0x28),'Parent stays visible until the authoritative server result'
m.click(q,164,86);assert len(m.sent)==count+1,'Double Yes submitted twice'

for offset,fmt,value in ((10,'H',1|4|8|32),(10,'H',4|32|128),(2272,'I',4000000),
                         (2276,'I',3),(2344,'I',501),(2348,'I',151),(16,'I',3)):
    obj,q,count=open_confirm();m.invoke(c['down'],q,(164,86))
    p=quest(ready=True,opened=False);struct.pack_into('<'+fmt,p,offset,value);m.receive(p)
    m.invoke(c['up'],q,(164,86))
    assert len(m.sent)==count and m.r(qs+16)!=5,'Stale requirements/membership press submitted'
    assert not m.r(0x131F4E8+0x19C)

# Unready quests cannot enter final confirmation even via the private entry.
obj=m.ready(quest());q=m.r(qs);count=len(m.sent)
m.click(q,150,248);m.invoke(c['quest_open'],0,(5,))
assert m.r(qs+16)==2 and len(m.sent)==count
print('PASS: final frontmost Yes/No before any submit, No/X restores saved quest, '
      'one Yes packet, double/release-outside/modal gates, unchanged refresh, '
      'stale items/quantities/cost/level/expiry/readiness cancel confirmation.')
