"""Native VIP Yes/No buffs popup and server-authoritative hourly gate, offline."""
import argparse
import struct
from pathlib import Path
from PIL import Image,ImageFont
from test_vip_ui import VipMachine,snapshot,ROOT
from vip_design_contract import X,Y

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;qs=c['quest_state'];manager=0x131F4E8
def packet(remaining=0,flags=1|2|4|512,token=971):
    p=snapshot(flags=flags,token=token);struct.pack_into('<I',p,2564,remaining);return p
def open_popup(token=971):
    obj=m.ready(packet(token=token));before=len(m.sent)
    assert not m.r(qs+16)
    m.click(obj,353,152);q=m.r(qs)
    assert m.r(qs+16)==4 and len(m.sent)==before,'Opening confirmation sent a claim'
    assert (m.r(q+0x14),m.r(q+0x18))==(360,118) and m.window_order()[-1]==q
    return obj,q

obj,q=open_popup();m.preview(q,args.output/'vip-buffs-confirm.png')
assert any(t[0]=='VIP Buffs' for t in m.texts)
assert any(t[0]=='Receive +7 all stats for 30 minutes?' for t in m.texts)
assert any(t[0]=='Available once every hour per account.' for t in m.texts)
assert not any(t[0] in ('VIP Upgrade Quest','Zeny required:','Inventory:') for t in m.texts)
before=len(m.sent);m.click(obj,217,127)
assert m.window_order()[-1]==q and len(m.sent)==before and m.r(qs+16)==4
# No, X, and release outside do not consume a claim or start cooldown.
for x,y in ((195,86),(348,8)):
    obj,q=open_popup();before=len(m.sent)
    m.invoke(c['down'],q,(160,86));m.invoke(c['up'],q,(310,100))
    assert len(m.sent)==before and not m.r(manager+0x19C)
    m.click(q,x,y);assert not m.r(qs+16) and m.r(obj+0x28) and len(m.sent)==before
    m.click(obj,353,152);assert m.r(qs+16)==4,'No started a local cooldown'

# Exact fixed action, no arbitrary duration/stat values or NPC dialogue.
obj,q=open_popup();before=len(m.sent);m.click(q,160,86)
assert len(m.sent)==before+1
assert struct.unpack('<HHIHHIII',m.sent[-1])==(0xBFA,24,0x55504956,4,5,971,0,0)
assert not m.r(q+0x28) and not m.r(obj+0x28)
m.click(q,160,86);assert len(m.sent)==before+1,'Double Yes sent twice'

# The server reply/refresh alone enables the button; client tick never unlocks it.
for remaining,label in ((3600,'01:00:00'),(3599,'00:59:59'),(1,'00:00:01')):
    obj=m.ready(packet(remaining,flags=1|2|4));before=len(m.sent)
    m.preview(obj,args.output/f'vip-buffs-cooldown-{remaining}.png')
    countdown=[t for t in m.texts if t[0]=='Buffs: '+label]
    assert len(countdown)==1
    assert countdown[0][1]>=289 and countdown[0][2]==168
    assert countdown[0][1]+ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',11).getlength(countdown[0][0])<=417
    m.click(obj,353,152);assert not m.r(qs+16) and len(m.sent)==before
    m.now+=3600001;m.click(obj,353,152)
    assert not m.r(qs+16) and len(m.sent)==before,'Client clock bypassed server cooldown'
m.receive(packet(0,flags=1|4|512));m.click(obj,353,152)
assert m.r(qs+16)==4,'Server-confirmed cooldown expiry did not unlock'
# Non-VIP/expired, missing ready flag, and inconsistent positive wait stay disabled.
for flags,remaining in ((2|4|512,0),(1|2|4,0),(1|2|4|512,10)):
    obj=m.ready(packet(remaining,flags));before=len(m.sent);m.click(obj,353,152)
    assert not m.r(qs+16) and len(m.sent)==before
# Membership expiry/cooldown on a refresh cancels a pending Yes and releases capture.
for flags,remaining in ((4,0),(1|4,3600)):
    obj,q=open_popup();m.invoke(c['down'],q,(160,86));before=len(m.sent)
    m.receive(packet(remaining,flags));m.invoke(c['up'],q,(160,86))
    assert not m.r(qs+16) and not m.r(manager+0x19C) and len(m.sent)==before
# Caption is bounded even when the server sends an unterminated prompt.
p=packet();p[2568:2664]=b'A'*96;obj=m.ready(p);m.click(obj,353,152);q=m.r(qs)
m.preview(q,args.output/'vip-buffs-long-prompt.png')
assert m.cstr(c['state']+32+2568)=='A'*95
assert any(t[0].startswith('AAA') and len(t[0])<=95 for t in m.texts),'Bounded prompt must also fit its row'
# Yes/No use the same editable whole PNGs, no caption overlays.
obj,q=open_popup()
for kind,action in (('out',None),('over','move'),('press','down')):
    if action:m.invoke(c[action],q,(160,86))
    m.preview(q,args.output/f'vip-buffs-yes-{kind}.png')
    assert not any(t[0] in ('Yes','No') for t in m.texts)
    actual=Image.open(args.output/f'vip-buffs-yes-{kind}.png').crop((150,78,178,96)).convert('RGB')
    art=Image.open(ROOT/'Assets/VipUI'/f'yes_{kind}.png').convert('RGBA')
    want=Image.alpha_composite(Image.new('RGBA',art.size,(244,252,255,255)),art).convert('RGB')
    assert actual.tobytes()==want.tobytes(),kind
m.invoke(c['up'],q,(310,100))
# A missing normal Yes image cannot leave an invisible claim target.
tex=m.load_texture('yes_out.png');old=m.r(tex+0x114);m.w(tex+0x114,0);before=len(m.sent)
m.click(q,160,86);assert len(m.sent)==before;m.w(tex+0x114,old)
print('PASS: VIP Buffs native frontmost Yes/No popup; no claim on open/No/X, exact action 5, duplicate/stale expiry/capture guards, server-only hourly readiness/countdown, bounded prompt and complete editable button PNGs; no live claims.')
