"""Native compact one-ticket upgrade window and all five paid-tier controls."""
import argparse
import struct
from pathlib import Path
from test_vip_ui import VipMachine,snapshot

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--game',type=Path)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(args.exe);c=m.c;qs=c['quest_state'];m.w(0x159C088,0)
if args.game:
    from test_vip_quest_ui import artwork
    lookups=artwork(m,args.game,items=(501,))
for target in range(6,11):
    p=snapshot(level=target-1,flags=1|2|4|8,token=target+900)
    obj=m.ready(p);before=len(m.sent);m.click(obj,315,303)
    assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==4,'Ticket Upgrade must ask the server directly'
    assert not m.r(qs+16),'No unnecessary EXP confirmation for a ticket'
    struct.pack_into('<H',p,10,1|2|4|8|32|64)
    struct.pack_into('<II',p,2272,0,target)
    p[2280:2344]=b'Obtain your next VIP ticket from the Cash Shop.'.ljust(64,b'\0')
    struct.pack_into('<III48s',p,2344,501,1,0,f'VIP {target} Ticket'.encode())
    obj=m.ready(p);q=m.r(qs);m.preview(q,args.output/f'vip-{target}-ticket.png')
    assert (m.r(q+0x14),m.r(q+0x18))==(360,174) and m.window_order()[-1]==q
    assert any(row[0]==f'VIP {target} Ticket' for row in m.texts)
    assert sum(row[0]=='Inventory:' for row in m.texts)==1,'Only one requirement box'
    pix,w,h=m.pixels(q)
    assert m.r(pix+(25*w+6)*4)==0xFFC3D4EC and m.r(pix+(73*w+6)*4)==0xFFFFFFFF,'No second row'
    before=len(m.sent);m.click(q,150,152);assert len(m.sent)==before,'Cannot submit without the ticket'
    m.click(q,210,152);assert not m.r(qs+16) and len(m.sent)==before,'Cancel does not consume a ticket'
    # Saved ticket opens directly above main and retains compact control positions.
    struct.pack_into('<H',p,10,1|2|4|8|32);obj=m.ready(p);m.click(obj,315,303);q=m.r(qs)
    assert m.r(qs+16)==2 and m.window_order()[-1]==q and len(m.sent)==before
    struct.pack_into('<H',p,10,1|2|4|8|32|64|128);struct.pack_into('<I',p,2352,1)
    obj=m.ready(p);q=m.r(qs)
    m.click(q,150,249);assert len(m.sent)==before,'Old three-row button coordinates cannot submit'
    m.click(q,150,152);assert len(m.sent)==before and m.r(qs+16)==5
    m.click(q,164,86);assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==7
    m.click(q,150,152);assert len(m.sent)==before+1,'Duplicate click'
obj=m.ready(snapshot(level=10,flags=1|2|4));before=len(m.sent);m.click(obj,315,303)
assert len(m.sent)==before and not m.r(qs+16),'Maximum VIP 10 cannot upgrade'
if args.game:assert lookups and set(lookups)=={501},'Native item helper must render the configured placeholder'
print('PASS: direct ticket requests for VIP 6-10, compact 360x174 one-box UI, exact names, missing/ready/Cancel/reopen/old-coordinate/replay gates, frontmost window and max-level lock; no live purchases.')
