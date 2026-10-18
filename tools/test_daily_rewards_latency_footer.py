"""Execute native pending-reroll timing and footer compositing boundaries."""
import argparse,struct
from pathlib import Path
from test_daily_rewards_ui import DailyMachine,snapshot

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--baseline',action='store_true');args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=DailyMachine(args.exe);s=m.c['state'];m.invoke(m.c['toggle'],0)
    def reply(pending=0,legacy=False):
        p=snapshot(seq=m.r(s+4),six=True,total=20)
        if not legacy:
            p+=struct.pack('<5I',0,3,10000,200000,pending);struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,5)
        m.receive(p);assert not m.r(s+8)
    def check_footer(label):
        m.preview(args.output/(label+'.png'));pix,w,h=m.pixels(m.r(s))
        raw=bytes(m.u.mem_read(pix,w*h*4));holes=sum(raw[(y*w+x)*4+3]!=255 for y in range(682,720) for x in range(3,917))
        if args.baseline:
            assert holes>0,'baseline does not reproduce footer transparency';print(f'REPRODUCED: {holes} transparent footer pixels after native text draw');return
        assert holes==0,(label,holes)
        assert any('Hover items' in t[0] for t in m.texts),'footer text missing'
    reply();check_footer('ready-footer')
    if args.baseline:return
    m.click(190,44);m.click(820,164);assert struct.unpack_from('<H',m.sent[-1],10)[0]==6;reply(pending=1)
    before=len(m.sent);m.advance(199);assert len(m.sent)==before
    m.advance(1);assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==1
    check_footer('waiting-footer');m.advance(2000);assert len(m.sent)==before+1,'more than one request in flight'
    reply(pending=1);check_footer('saving-footer');before=len(m.sent)
    m.advance(200);assert len(m.sent)==before+1;reply()
    # Idle polling stays at 3 s once payment is complete.
    before=len(m.sent);m.advance(2999);assert len(m.sent)==before;m.advance(1);assert len(m.sent)==before+1;reply()
    # Native GDI may zero alpha over the complete footer line rectangle.
    original=m.text
    def gdi_rectangle():
        _,y,_,_,_,height,_,_,_=m.args(9)
        if y>=682:
            obj=m.r(s);pix,w,h=m.pixels(obj);data=bytearray(m.u.mem_read(pix,w*h*4))
            for row in range(y,min(h,y+height+5)):
                for x in range(3,917):data[(row*w+x)*4+3]=0
            m.u.mem_write(pix,bytes(data))
        original()
    m.stub(0xA25A70,gdi_rectangle)
    for index in range(4):
        m.click(815,43);check_footer(f'repaint-wait-{index}');reply(pending=index%2);check_footer(f'repaint-reply-{index}')
    # Wrap-safe 200 ms deadline; no fast polling with an older server reply.
    m.now=0xfffffff0;m.click(815,43);reply(pending=1);before=len(m.sent)
    m.advance(200);assert len(m.sent)==before+1;reply(legacy=True)
    before=len(m.sent);m.advance(200);assert len(m.sent)==before;m.advance(2800);assert len(m.sent)==before+1
    m.click(906,11);before=len(m.sent);m.advance(10000);assert len(m.sent)==before,'closed window kept polling'
    print('PASS: 200 ms pending refresh, one request in flight, normal 3 s refresh, old-server cadence, tick wrap, stop on close, opaque footer on repeated native/GDI text redraws')
if __name__=='__main__':main()
