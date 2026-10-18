"""Exercise the actual emitted Daily Rewards UI across automatic refresh frames."""
import argparse,struct
from pathlib import Path
from test_daily_rewards_ui import DailyMachine,snapshot

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--baseline',action='store_true');args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=DailyMachine(args.exe);s=m.c['state'];m.invoke(m.c['toggle'],0);w=m.r(s)
    def reply(pending=0,status=None,progress=15):
        p=snapshot(seq=m.r(s+4),six=True,total=20)+struct.pack('<5I',0,3,10000,200000,pending)
        struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,5)
        struct.pack_into('<I',p,592+2*420+12,progress)
        if status:p[48:144]=status.encode().ljust(96,b'\0')
        m.receive(p);assert not m.r(s+8),'reply rejected'
    def frame(label):
        m.preview(args.output/(label+'.png'));pix,width,height=m.pixels(w)
        data=bytes(m.u.mem_read(pix,width*height*4))
        def area(x,y,cx,cy):return b''.join(data[((y+i)*width+x)*4:((y+i)*width+x+cx)*4] for i in range(cy))
        m.w(w+0x58,0) # The native UI manager consumes the dirty flag after painting.
        return area(12,682,896,38),area(806,32,102,26)
    def cursor():m.invoke(m.c['cursor'],w,(815,43))
    reply();m.click(190,44);cursor();steady=frame('idle')
    cursor();cursor_dirty=m.r(w+0x58);m.w(w+0x58,0)
    m.advance(100);timer_dirty=m.r(w+0x58)
    if not args.baseline:
        assert not cursor_dirty,'stationary cursor requests redraw'
        assert not timer_dirty,'idle 100 ms tick requests redraw'
    m.advance(2900);assert m.r(s+8),'automatic refresh was removed'
    cursor();during=frame('automatic-refresh')
    if args.baseline:
        assert cursor_dirty and timer_dirty and steady[0]!=during[0] and steady[1]!=during[1]
        assert any(t[0]=='Waiting for the server...' for t in m.texts)
        print('REPRODUCED: idle 100 ms timer/stationary cursor redraw; automatic refresh changes footer and Refresh-button pixels')
        return
    assert during==steady,'background request changed footer or Refresh appearance'
    before=len(m.sent);m.click(820,164);m.click(820,132);assert len(m.sent)==before,'background poll allowed another request'
    m.advance(100);cursor();assert frame('automatic-wait')==steady
    reply();cursor();assert frame('automatic-reply')==steady
    for i in range(2):
        m.advance(3000);cursor();assert frame(f'poll-{i}')==steady
        m.advance(100);reply();cursor();assert frame(f'reply-{i}')==steady
    # Timer-only changes still paint the visible minute countdown.
    m.advance(1000);assert m.r(w+0x58),'countdown minute change not redrawn';frame('minute-changed')
    m.advance(100);cursor();assert not m.r(w+0x58),'idle repaint continued after minute update'
    # Explicit actions retain loading feedback and the single-request guard.
    m.click(815,43);manual=frame('manual-refresh')
    assert manual!=steady and any(t[0]=='Waiting for the server...' for t in m.texts)
    reply(status='Quest progress updated.',progress=16);frame('changed-reply')
    assert any(t[0]=='16 / 20 collected' for t in m.texts) and any(t[0]=='Quest progress updated.' for t in m.texts)
    # A genuinely slow background request becomes visible after one second.
    m.advance(3000);m.advance(999);cursor();quiet=frame('slow-before-threshold')
    assert not any(t[0]=='Waiting for the server...' for t in m.texts)
    m.advance(1);assert m.r(w+0x58);frame('slow-visible')
    assert any(t[0]=='Waiting for the server...' for t in m.texts)
    before=len(m.sent);m.advance(9000);assert len(m.sent)==before+1,'timeout recovery missing';reply()
    # Paid-reroll checks remain fast and do not flash the footer between replies.
    m.click(820,164);reply(pending=1,status='Saving re-roll...');cursor();saving=frame('reroll-saving')
    before=len(m.sent);m.advance(199);assert len(m.sent)==before
    m.advance(1);assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==1
    cursor();assert frame('reroll-poll')==saving
    reply(pending=1,status='Saving re-roll...');cursor();assert frame('reroll-reply')==saving
    m.click(906,11);before=len(m.sent);m.advance(10000);assert len(m.sent)==before
    print('PASS: stable footer/Refresh pixels through automatic polls, no idle 100 ms/stationary cursor redraw, countdown updates, explicit loading, changed replies, slow-request feedback, timeout recovery, single request and 200 ms reroll polls')
if __name__=='__main__':main()
