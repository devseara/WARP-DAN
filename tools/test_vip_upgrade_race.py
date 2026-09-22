"""Execute VIP x86 against delayed refresh replies and the existing 300ms gate.

Only the server's documented request gate is modeled; no accounts are mutated.
Raw mouse/timer calls intentionally bypass ordinary fixture settling.
"""
import argparse,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX
from test_vip_ui import VipMachine,snapshot
from test_vip_quest_ui import quest

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=VipMachine(a.exe);c=m.c;q=c['interaction'];qs=c['quest_state']

def raw_click(w,x,y):
    m.invoke(c['down'],w,(x,y));m.invoke(c['up'],w,(x,y))
def action_packet(action,opened=True,token=100):
    if action==7:return quest(ready=True,opened=opened,token=token)
    return snapshot(flags=1|4|8|(2 if opened else 0),token=token)
def confirm(action):
    obj=m.r(c['state'])
    if action==4:raw_click(obj,196,259)
    else:raw_click(m.r(qs),150,248)
    assert m.r(qs+16)==(1 if action==4 else 5)
    raw_click(m.r(qs),164,86)
    assert m.r(obj+0x28) and not m.r(qs+16),'Parent must not disappear on Yes'
    return obj
def mutations():return [p for p in m.sent if struct.unpack_from('<H',p,10)[0] in (4,7)]

for action in (4,7):
    for latency in (0,40,800,4000):
        obj=m.ready(action_packet(action));m.advance(3000)
        assert m.r(q+216)==1 and struct.unpack_from('<H',m.sent[-1],10)[0]==0
        before=len(mutations());confirm(action)
        assert m.r(q)==1 and len(mutations())==before
        raw_click(obj,196,259);raw_click(m.r(qs),164,86)
        assert len(mutations())==before,'Double click escaped queued ownership'
        m.now=(m.now+latency)&0xffffffff
        m.receive(action_packet(action,False))
        # This pessimistic gate begins at reply delivery, later than server receipt.
        busy_until=m.now+300
        m.advance(349);assert len(mutations())==before
        m.advance(1);assert len(mutations())==before+1 and m.now>=busy_until
        assert struct.unpack_from('<H',mutations()[-1],10)[0]==action and m.r(q)==2
        m.preview(obj,a.output/f'waiting-{action}-{latency}.png')
        # A late routine refresh cannot acknowledge/re-enable/resubmit an action.
        m.receive(action_packet(action,False));assert m.r(q)==2
        sent=len(m.sent);m.advance(3000);assert len(m.sent)==sent
        raw_click(obj,196,259);raw_click(m.r(qs),164,86);assert len(m.sent)==sent
        m.advance(7000);assert m.r(q)==3 and m.r(obj+0x28)
        m.preview(obj,a.output/'reply-delayed.png')
        m.advance(10000);assert len(m.sent)==sent,'Timeout retried a mutation'
        result=action_packet(action,True,101)
        m.receive(result);assert m.r(q)==0 and m.r(obj+0x28)
        print(f'PASS action {action}: refresh latency {latency}ms, one safe send, no blind retry',flush=True)

# Refresh itself must not start inside the previous reply's cooldown, including
# a fast manual Refresh or a high-latency poll arriving just before the next tick.
obj=m.ready(action_packet(4));m.receive(action_packet(4,False));before=len(m.sent)
raw_click(obj,194,329);assert len(m.sent)==before and not m.r(q+216)
m.advance(349);raw_click(obj,194,329);assert len(m.sent)==before and not m.r(q+216)
m.advance(1);raw_click(obj,194,329);assert len(m.sent)==before+1 and m.r(q+216)

# A long-open confirmation keeps refreshing its 120-second server token.
obj=m.ready(action_packet(4));raw_click(obj,196,259);assert m.r(qs+16)==1
for i in range(45):
    before=len(m.sent);m.advance(3000)
    assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==0
    m.receive(action_packet(4,False));assert m.r(qs+16)==1
print('PASS: confirmation open for 135 seconds keeps refreshing without dismissing or submitting',flush=True)

# Expiry/changed requirements while a Yes waits behind Refresh invalidates it.
for action,offset,fmt,value in ((4,10,'H',4),(4,16,'I',3),(7,10,'H',1|4|32),
                              (7,2272,'I',123),(7,2344,'I',999),(7,2348,'I',999)):
    obj=m.ready(action_packet(action));m.advance(3000);confirm(action);before=len(mutations())
    p=action_packet(action,False);struct.pack_into('<'+fmt,p,offset,value);m.receive(p)
    assert not m.r(q);m.advance(350);assert len(mutations())==before

# Explicit close cancels an unsent queue and kills the timer. No delayed action.
obj=m.ready(action_packet(4));m.advance(3000);confirm(4);before=len(mutations())
raw_click(obj,447,10);assert not m.r(q) and not m.r(obj+0x28)
m.advance(20000);assert len(mutations())==before

# Wraparound is handled with unsigned elapsed ticks, never signed wall time.
m.now=0xfffffff0;m.receive(action_packet(4));obj=m.r(c['state']);before=len(mutations())
confirm(4);m.advance(349);assert len(mutations())==before
m.advance(1);assert len(mutations())==before+1 and m.r(q)==2

# Lost refresh replies or unavailable transport are visible, never silent close.
obj=m.ready(action_packet(4));m.advance(3000);confirm(4);before=len(mutations())
m.advance(10000);assert m.r(q)==3 and len(mutations())==before and m.r(obj+0x28)
obj=m.ready(action_packet(4));m.stub(c['ctor'],lambda:m.ret(0,0));before=len(mutations())
confirm(4);assert m.r(q)==3 and len(mutations())==before and m.r(obj+0x28)
print('PASS: stale queue cancellation, explicit close, tick wrap, transport loss and delayed reply remain fail-safe; server cooldown unchanged.')
