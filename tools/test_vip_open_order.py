"""Replay native root-list hit selection; old VIP opens underneath HUD controls."""
import argparse
from test_vip_ui import VipMachine,snapshot
from unicorn.x86_const import UC_X86_REG_EAX

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--expect-old',action='store_true');args=ap.parse_args()
m=VipMachine(args.exe);manager=0x131F4E8

def empty_children(obj):
    head=m.alloc(12);m.w(head,head);m.w(head+4,head);m.w(obj+0x50,head)

# Register an existing HUD root covering the VIP area, like Basic Info's
# Inventory/Equipment buttons. Native A23220 performs the actual geometry hit.
hud=m.alloc(0xB4);m.w(hud,0x102FE08);m.w(hud+0x14,800);m.w(hud+0x18,420)
m.w(hud+0x1C,80);m.w(hud+0x20,80);m.w(hud+0x28,1);empty_children(hud)
m.invoke(0xA2D240,manager,(hud,))
obj=m.ready();empty_children(obj)

def hit():
    # Unique IDs remain zero in the constructor boundary; no native hover
    # enter/leave bookkeeping is needed. Root lookup and frame hit are real.
    m.invoke(0xA336D0,manager,(110,110));return m.u.reg_read(UC_X86_REG_EAX)

expected=hud if args.expect_old else obj
assert hit()==expected,(hex(hit()),hex(expected),m.window_order())
assert m.window_order()[-1]==expected
if args.expect_old:
    print('REPRODUCED: old explicit VIP open selects the covered HUD root, not VIP.')
else:
    for n in range(5):
        m.invoke(0xA39130,manager,(hud,));assert hit()==hud
        m.ready(snapshot(token=100+n));assert hit()==obj
        assert m.window_order().count(obj)==1
    # Normal refresh must not steal a deliberately selected stock window.
    m.invoke(0xA39130,manager,(hud,));m.receive(snapshot(flags=1|4|8,token=104));assert hit()==hud
    print('PASS: actual native root-list/geometry hit selects VIP over covered HUD controls on open and reopen; one root, no focus stealing on refresh.')
