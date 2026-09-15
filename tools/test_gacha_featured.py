"""Execute emitted featured-strip drawing and hit tests; offline evidence only."""
import argparse
import struct
from pathlib import Path
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_gacha_ui import GachaMachine, snapshot

OFFSETS=(656,660,664,3472,3476,3776,3780,3784)

def run(exe,preview=None,game=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    assert c['packetSize']==3788 and c['wireVersion']==9
    if game:m.client_artwork(game)
    assert s+64+OFFSETS[-1]+4==s+3852 # Rolling is after, not inside, the new snapshot.
    guard=m.r(s+3856)
    ids=[1161,1716,1715,2289,501,14003,14533,12210]
    for count in (0,1,5,8,1,0):
        p=snapshot();struct.pack_into('<I',p,52,0);p[672:1824]=bytes(1152)
        def text(off,size,value):p[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
        struct.pack_into('<I',p,3660,4);struct.pack_into('<3I',p,40,100,500,9390);struct.pack_into('<I',p,3600,10)
        for off,name in ((3528,'Epic'),(3552,'Rare'),(3576,'Common'),(3636,'Legendary')):text(off,24,name)
        for off,rate in ((432,'1.00%'),(464,'5.00%'),(496,'93.90%'),(3604,'0.10%')):text(off,32,rate)
        text(1840,96,'Legendary: 37/100 | Epic+: 3/10')
        text(528,128,'Legendary guaranteed within 100 pulls; Epic or better within 10. Pity saves per character.')
        text(112,128,'Choose a pull amount, or view the prize pools and history.')
        p[3728:3776]=b'Featured Legendary prizes'.ljust(48,b'\0')
        for i,off in enumerate(OFFSETS):struct.pack_into('<I',p,off,ids[i] if i<count else 0)
        m.receive(p);assert m.r(s)==obj
        assert m.r(s+3856)==guard and m.r(s+3852)==0
        m.texts=[];m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj)
        assert (w,h)==(760,440)
        for i,off in enumerate(OFFSETS):
            assert m.r(s+64+off)==(ids[i] if i<count else 0)
            x=22+i*35
            assert x+31<=298 # No overlap with the rate panel at x=310.
            expected=0xffe7edf8 if i<count else 0xfff4fbfd
            assert m.r(pix+4*(104*w+x+2))==expected,(count,i,'stale/empty featured box')
            for xy in ((x,88),(x+30,117),(x+15,102)):
                m.invoke(c['itemHit'],obj,xy)
                assert m.u.reg_read(UC_X86_REG_EAX)==(s+64+off if i<count else 0),(count,i,xy)
            m.right(obj,(x+15,102));assert m.r(s+c['rightOffset'])==(s+64+off if i<count else 0)
            assert m.r(0x131F4E8+0x19c)==0
            # A new snapshot invalidates the held right click, including slots 6..8.
            m.receive(p);assert m.r(s+c['rightOffset'])==0
        assert not m.sent
        if preview and count in (0,1,5,8):
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+f'-{count}.png'))
    # Old/truncated snapshots must not corrupt the state or reset a live roll.
    m.w(s+3852,2)
    for length,version in ((3776,8),(3776,9),(3788,8)):
        p=snapshot()[:length];struct.pack_into('<HH',p,0,0xbf6,length);struct.pack_into('<H',p,8,version)
        before=bytes(m.u.mem_read(s,3860));m.receive(p);assert bytes(m.u.mem_read(s,3860))==before
    print('PASS: 0/1/5/8 featured boxes, stale-box clearing, eight bounded hit targets, right-click safety, append-only copy/state canary, v8/truncated rejection and unchanged window geometry')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--preview',type=Path);ap.add_argument('--game',type=Path)
    args=ap.parse_args();run(args.exe,args.preview,args.game)
