"""Execute the emitted v5 UI for prices, shared allowance and reroll commands."""
import argparse,struct
from pathlib import Path
from test_daily_rewards_ui import DailyMachine,snapshot
def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=DailyMachine(args.exe);s=m.c['state'];assert m.daily_version==5
    def response(used=0,limit=3,cost=10000,zeny=200000,pending=0,claimed=False,roll=0):
        p=snapshot(seq=m.r(s+4),six=True,total=20,roll=roll);p+=struct.pack('<5I',used,limit,cost,zeny,pending);struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,5)
        for i in range(5):struct.pack_into('<II',p,592+i*420+12,0,int(claimed and i==0))
        m.receive(p);assert not m.r(s+8),'v5 response rejected'
        return p
    def refresh(**kw):m.click(815,43);return response(**kw)
    def texts(name):m.preview(args.output/name);return [t[0] for t in m.texts]
    m.invoke(m.c['toggle'],0);assert struct.unpack_from('<II',m.sent[-1],16)==(0x35555244,0x32555244);response();m.click(190,44)
    labels=texts('reroll-first.png');assert labels.count('Re-Roll')==5 and labels.count('10,000z')==5,labels
    assert any('3 / 3' in t and 'Shared' in t for t in labels)
    for used,cost in enumerate([10000,25000,50000]):
        refresh(used=used,cost=cost)
        before=len(m.sent);m.click(820,164+used*116)
        r=struct.unpack('<HHIHH5I',m.sent[-1]);assert r[3:5]==(5,6) and r[7]==used|(used<<3) and r[8:]==(cost,0),r
        m.click(820,164+used*116);assert len(m.sent)==before+1,'double click sent duplicate'
        response(used=used,cost=cost,pending=1);before=len(m.sent);m.click(820,164);assert len(m.sent)==before,'payment pending still clickable'
        m.advance(199);assert not m.r(s+8) and len(m.sent)==before,'payment polling is too fast'
        m.advance(1);assert m.r(s+8) and len(m.sent)==before+1,'payment not refreshed at 200 ms'
        assert struct.unpack_from('<H',m.sent[-1],10)[0]==1,'payment poll must only refresh'
        m.advance(200);assert len(m.sent)==before+1,'payment poll duplicated an in-flight request'
        response(used=used+1,cost=[25000,50000,0][used]);labels=texts(f'reroll-after-{used+1}.png')
        assert all('Resets at midnight' not in t for t in labels)
    assert labels.count('Limit reached')==5 and not any(t.endswith('z') for t in labels),labels
    before=len(m.sent);m.click(820,164);assert len(m.sent)==before,'exhausted reroll clickable'
    refresh(zeny=9999);before=len(m.sent);m.click(820,164);assert len(m.sent)==before,'insufficient Zeny clickable'
    refresh(claimed=True);before=len(m.sent);m.click(820,164);assert len(m.sent)==before,'claimed quest clickable'
    refresh(limit=0,cost=0);assert texts('reroll-disabled.png').count('Disabled')==5
    refresh(used=1,cost=25000);m.click(815,43);p=snapshot(seq=m.r(s+4),six=True,total=20);p+=struct.pack('<5I',1,3,25000,2147483647,0);struct.pack_into('<HH',p,0,0xbf4,9440);struct.pack_into('<H',p,8,5);m.receive(p)
    # Stale claim commands are tied to the same account allowance generation.
    m.click(820,132);assert struct.unpack_from('<HH',m.sent[-1],8)==(5,3) and struct.unpack_from('<I',m.sent[-1],20)[0]==8
    response(used=1,cost=25000)
    for values in [(101,3,0,200000,0),(0,101,10000,200000,0),(3,3,50000,200000,0),(0,3,10000,200000,2),(0,3,0xffffffff,200000,0)]:
        m.click(815,43);p=snapshot(seq=m.r(s+4),six=True,total=20)+struct.pack('<5I',*values);struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,5);m.receive(p);assert m.r(s+8),'invalid metadata accepted';response()
    # Legacy servers retain their layout, and six-prize Roll still renders in v5.
    m.click(815,43);m.reply(six=True,total=20);assert 'Re-Roll' not in texts('reroll-old-server.png')
    refresh(roll=6);m.click(338,44);labels=texts('v5-six-roll.png');assert labels.count('Received')==6
    m.click(906,11)
    # A v3 server rejects the initial v4 envelope; the timeout falls back.
    m.invoke(m.c['toggle'],0);m.advance(10000)
    assert struct.unpack_from('<H',m.sent[-1],8)[0]==1 and struct.unpack_from('<I',m.sent[-1],16)[0]==0x33555244
    m.reply(catalog=True,total=20);m.click(190,44);assert 'Re-Roll' not in texts('reroll-v3-fallback.png');m.click(906,11)
    print('PASS: emitted v5 x86, all five buttons, shared 10k/25k/50k prices, paid-pending refresh, replay click guard, exhausted/claimed/poor/disabled states, no midnight label, stale claim generation, malformed metadata, v4 compatibility and six-result rendering')
if __name__=='__main__':main()
