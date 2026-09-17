"""Run emitted membership-dependent buttons and native window order, offline."""
import argparse
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine,snapshot

parser=argparse.ArgumentParser();parser.add_argument('exe');args=parser.parse_args()
m=VipMachine(args.exe);c=m.c
def hit(x,y):
    m.invoke(c['hit'],0,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
buttons=[(2,130,173,1),(3,205,173,2),(4,150,200,3)]
for level in (0,1,6,10):
    for active in (False,True):
        for shop in (False,True):
            flags=2|4|(1 if active else 0)|(16 if shop else 0)
            for control,x,y,action in buttons:
                obj=m.ready(snapshot(flags=flags,level=level))
                enabled=not active if control==2 else active and (shop if control==3 else True)
                assert hit(x,y)==(control if enabled else 0),(level,active,shop,control)
                before=len(m.sent);m.click(obj,x,y)
                assert len(m.sent)==before+int(enabled and control!=2),(level,active,shop,control)
                if enabled and control==2:assert m.r(c['quest_state']+16)==3
                elif enabled:assert int.from_bytes(m.sent[-1][10:12],'little')==action

# A membership change between down/up must invalidate the now-disabled action.
for control,x,y,action in buttons:
    start=2|4|(16|1 if control!=2 else 0)
    obj=m.ready(snapshot(flags=start));m.invoke(c['down'],obj,(x,y))
    finish=(start&~2)^1
    before=len(m.sent);m.receive(snapshot(flags=finish));m.invoke(c['up'],obj,(x,y))
    assert len(m.sent)==before,'Stale membership click sent an action'

# Returning to VIP/expired state also redraws with the proper file, no caption.
for active in (False,True):
    obj=m.ready(snapshot(flags=2|4|16|(1 if active else 0)))
    m.invoke(c['draw'],obj)
    for label in ('Apply VIP','Open Store','Open Storage'):
        assert not any(t[0]==label for t in m.texts),'Caption overlay returned'
print('PASS: active/expired/nonmember and levels 0/1/6/10: Apply only without VIP; '
      'Store only active/configured, Storage only active; stale down/up membership changes rejected.')
