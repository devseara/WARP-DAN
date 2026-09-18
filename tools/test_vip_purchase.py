"""Execute the native VIP duration picker and price-echo requests, without purchases."""
import argparse
import struct
from pathlib import Path
from PIL import Image
from test_vip_ui import VipMachine,snapshot,ROOT

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;qs=c['quest_state'];manager=0x131F4E8
offers=((1,500000),(3,1200000),(7,2500000),(15,5000000),(30,9000000))
def purchase_art(kind):
    art=Image.open(ROOT/'Assets/VipUI'/f'purchase_{kind}.png').convert('RGBA')
    return Image.alpha_composite(Image.new('RGBA',art.size,(244,252,255,255)),art).convert('RGB')
def open_picker(token=701):
    obj=m.ready(snapshot(flags=2|4,level=0,token=token));before=len(m.sent)
    assert not m.r(qs+16)
    m.click(obj,217,127);q=m.r(qs)
    assert m.r(qs+16)==3 and len(m.sent)==before and m.window_order()[-1]==q
    assert (m.r(q+0x14),m.r(q+0x18))==(360,320)
    assert m.r(qs+44)==0xFFFFFFFF
    return obj,q

obj,q=open_picker();before=len(m.sent)
m.preview(q,args.output/'vip-purchase-select.png')
assert Image.open(args.output/'vip-purchase-select.png').crop((126,296,182,314)).tobytes()==purchase_art('off').tobytes()
for days,cost in offers:
    assert any(row[0]==f'{days} '+('DAY' if days==1 else 'DAYS')+' VIP' for row in m.texts)
    assert any(row[0]==f'{cost:,}z' for row in m.texts)
assert not any(row[0]=='VIP Upgrade Quest' for row in m.texts)
m.click(q,150,302);assert len(m.sent)==before,'Purchase without a selection'
for index,(days,cost) in enumerate(offers):
    obj,q=open_picker(800+index);before=len(m.sent)
    m.click(q,180,45+index*48);assert m.r(qs+44)==index and len(m.sent)==before
    assert m.r(manager+0x19C)==0
    if index==4:m.preview(q,args.output/'vip-purchase-30-days.png')
    m.click(q,150,302)
    assert len(m.sent)==before+1
    assert struct.unpack('<HHIHHIII',m.sent[-1])==(0xBFA,24,0x55504956,4,8+index,800+index,days*1440,cost)
    assert not m.r(obj+0x28) and not m.r(q+0x28)
    m.click(q,150,302);assert len(m.sent)==before+1,'Double-click bought twice'

# Cancel/X and release outside a row or Purchase do not send anything.
for close_x,close_y in ((210,302),(348,8)):
    obj,q=open_picker();before=len(m.sent)
    m.invoke(c['down'],q,(180,45));m.invoke(c['up'],q,(180,93));assert m.r(qs+44)==0xFFFFFFFF
    m.click(q,180,45);m.invoke(c['down'],q,(150,302));m.invoke(c['up'],q,(270,290))
    m.click(q,close_x,close_y);assert not m.r(q+0x28) and m.r(obj+0x28) and len(m.sent)==before

# Server price edits while clicking invalidate selection; user must reselect.
for offset,value in ((2524+4,750000),(2524,2880),(2524+4,0)):
    obj,q=open_picker();m.click(q,180,45);before=len(m.sent)
    m.invoke(c['down'],q,(150,302));p=snapshot(flags=4,level=0,token=701)
    struct.pack_into('<I',p,offset,value);m.receive(p);m.invoke(c['up'],q,(150,302))
    assert len(m.sent)==before and m.r(qs+44)==0xFFFFFFFF and not m.r(manager+0x19C)

# Active or pending payment cannot open or keep the duration picker alive.
for flag in (1,256):
    obj,q=open_picker();m.click(q,180,45);before=len(m.sent)
    m.receive(snapshot(flags=4|flag,token=701));assert not m.r(qs+16)
    m.click(q,150,302);m.click(obj,217,127);assert not m.r(qs+16) and len(m.sent)==before

# Missing/mis-sized Purchase art is never an invisible clickable payment.
obj,q=open_picker();m.click(q,180,45);before=len(m.sent)
tex=m.load_texture('purchase_out.png')
for off in (0x114,0x118,0x11C):
    saved=m.r(tex+off);m.w(tex+off,0);m.click(q,150,302);assert len(m.sent)==before;m.w(tex+off,saved)

# All four Purchase states are editable complete PNGs, no generated caption.
for state in range(4):
    path=Path(m.cstr(m.r(c['api']+292+state*4)).replace('\\','/'))
    assert path.name=='purchase_'+('out','over','press','off')[state]+'.png'
    assert Image.open(ROOT/'Assets/VipUI'/path.name).size==(56,18)
for kind,action in (('out',None),('over','move'),('press','down')):
    if action:m.invoke(c[action],q,(150,302))
    m.preview(q,args.output/f'vip-purchase-{kind}.png')
    assert not any(row[0]=='Purchase' for row in m.texts),'Purchase PNG caption overlay'
    pix,w,h=m.pixels(q)
    raw=b''.join(bytes(m.u.mem_read(pix+((296+y)*w+126)*4,56*4)) for y in range(18))
    actual=Image.frombytes('RGBA',(56,18),raw,'raw','BGRA').convert('RGB')
    assert actual.tobytes()==purchase_art(kind).tobytes(),kind
m.invoke(c['up'],q,(270,290));assert len(m.sent)==before
print('PASS: five selectable script-priced duration rows; no charge on selection/Cancel; exact 24-byte echoed quote on Purchase; duplicate, changed-price, pending/active, release-outside and missing-art guards; complete Purchase PNG states and native foreground ordering.')
