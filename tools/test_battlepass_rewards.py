"""Execute BPUI v6 six-slot cards, track selection and clipped claimed stamps.

Real shipped receiver/draw/input code; native icons/fonts/transport have the
same explicit boundaries as the board suite. Pictures are offline fixtures.
"""
import argparse
from pathlib import Path
import struct
from PIL import Image
from test_battlepass_board import BoardMachine, snapshot
from test_battlepass_surface import real_window


def rewards():
    p=snapshot()+bytearray(720)
    struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,6)
    struct.pack_into('<I',p,1188,512|1024|48)
    struct.pack_into('<H',p,10,struct.unpack_from('<H',p,10)[0]|8)
    counts=((6,1,0,2,6),(6,1,0,1,0))
    states=((5,1,0,3,1),(5,3,0,1,0))
    for track in range(2):
        for col in range(5):
            offset=3536+(track*5+col)*372
            struct.pack_into('<3I',p,offset,col+1,states[track][col],counts[track][col])
            p[offset+12:offset+372]=bytes(360)
            for slot in range(counts[track][col]):
                item=offset+12+slot*72 if slot<5 else 7256+(track*5+col)*72
                struct.pack_into('<II',p,item,500+(track*5+col)*10+slot,slot+1)
                p[item+8:item+72]=f'Item {track}-{col}-{slot}'.encode().ljust(64,b'\0')
    return p


def picture(m):
    pix,width,height=m.pixels(m.obj)
    return Image.frombytes('RGBA',(width,height),bytes(m.u.mem_read(pix,width*height*4)),'raw','BGRA')


def gray(pixel):
    luminance=((pixel>>16&255)*77+(pixel>>8&255)*150+(pixel&255)*29)>>8
    return 0xFF000000|((luminance*3+224)//4)*0x010101


def pager_header(exe,output):
    m=BoardMachine(exe);p=rewards();s=m.c['state']
    struct.pack_into('<II',p,2884,1,3)
    m.receive(p);m.click(50,114)
    pix,width,_=m.pixels(m.obj)
    def pixel(x,y):return m.r(pix+(y*width+x)*4)
    for x,control in ((676,40),(706,41)):
        for phase in ('normal','hover','pressed'):
            m.invoke(m.c['move'],0,(m.obj,0 if phase=='normal' else x,147))
            if phase=='pressed':m.mouse(x,147,0)
            m.draw(output/f'pager-{control}-{phase}.png')
            for xx in range(664,720):
                assert pixel(xx,137)==0xFFE6F2FC,'button escaped above its header padding'
                assert pixel(xx,156)==0xFFE6F2FC,'button escaped below its header padding'
                assert pixel(xx,157)==0xFFD4DFE9,'button painted over the header border'
            if phase=='pressed':m.mouse(x,160,1)
        for y in (137,156,157,158,159):
            m.invoke(m.c['move'],0,(m.obj,x,y));assert m.r(s+2928)==0,'pager hitbox escaped header'
        for y in (138,155):
            m.invoke(m.c['move'],0,(m.obj,x,y));assert m.r(s+2928)==control
    n=len(m.sent);m.click(676,147);assert m.sent[-1][4:]==(20,0)
    m.click(706,147);assert len(m.sent)==n+1,'in-flight paging must remain guarded'
    m.receive(p);m.click(706,147);assert m.sent[-1][4:]==(20,2)
    for page,disabled in ((0,676),(2,706)):
        struct.pack_into('<I',p,2884,page);m.receive(p);n=len(m.sent)
        m.click(disabled,147);m.draw(output/f'pager-page-{page}.png')
        assert len(m.sent)==n,'first/last-page boundary must remain disabled'
        assert all(pixel(xx,157)==0xFFD4DFE9 for xx in range(664,720))
    # Configured titles cannot flow under the controls.
    p+=bytearray(2624);struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,7)
    p[7976+26*64:7976+27*64]=b'W'*63+b'\0'
    m.receive(p);m.draw(output/'pager-long-title.png')
    title=[row[0] for row in m.texts if row[1:3]==(132,141)]
    assert len(title)==1 and title[0].startswith('W') and m.font.getlength(title[0])<=524
    print('PASS reward pager: paint/hitboxes inside header, normal/hover/press/disabled states, title clearance, both directions and first/last/in-flight guards')


def reached_only(exe,output):
    m=BoardMachine(exe);p=rewards();s=m.c['state']
    # Deliberately inconsistent eligibility flags must not enable future levels.
    for cell in range(10):struct.pack_into('<I',p,3536+cell*372+4,5)
    m.receive(p);m.click(50,114)
    # A colored native-icon boundary proves the entire item, not only its frame,
    # is desaturated by the actual shipped renderer. This is not live artwork.
    def item():
        window,item_id,x,y=m.args(4);m.items.append((item_id,x,y))
        pix,width,_=m.pixels(window)
        for row in range(24):m.u.mem_write(pix+((y+row)*width+x)*4,struct.pack('<I',0xFFDC4628)*24)
        m.ret(16)
    m.stub(m.r(m.c['api']+32),item)
    m.draw(output/'level-two-locked.png')
    pix,width,_=m.pixels(m.obj)
    def pixel(x,y):return m.r(pix+(y*width+x)*4)
    assert pixel(230,194)==0xFFDC4628 and pixel(330,194)==0xFFDC4628
    assert pixel(630,194)==gray(0xFFDC4628),'future native icon must be gray'
    for track in range(2):
        for col in range(2,5):
            region=picture(m).crop((210+col*100,184+track*151,306+col*100,317+track*151))
            assert all(r==g==b and a==255 for r,g,b,a in region.get_flattened_data())
    assert pixel(658,163)==0xFFD8D8D8,'future level heading must be gray'
    assert pixel(326,224)==0xFFF8FCFF,'unused item slots must not leave frames'
    # Level two is selectable. All later levels in both tracks are not.
    m.click(330,300);m.draw();assert pixel(358,184)==0xFF60C789
    n=len(m.sent)
    for track in range(2):
        for col in range(2,5):
            m.mouse(230+col*100,300+track*151,0)
            assert m.r(s+8)==0 and m.r(0x131F4E8+0x19C)==0,'future card captured selection'
            m.mouse(230+col*100,300+track*151,1)
    m.draw();assert pixel(358,184)==0xFF60C789 and len(m.sent)==n
    m.click(670,502);assert m.sent[-1][4:]==(14,2),'future click changed selected claim target'
    # Hover and read-only item inspection still work in the gray sixth slot.
    m.invoke(m.c['move'],0,(m.obj,671,270));m.draw(output/'locked-sixth-tooltip.png')
    assert m.contains('Client item name') and m.contains('Quantity: 6')
    assert pixel(660,291)==0xFFFFFFDC,'tooltip must not inherit disabled gray wash'
    m.mouse(671,270,2);m.mouse(671,270,3);assert m.descriptions==[545]
    assert len(m.sent)==n+1
    m.invoke(m.c['move'],0,(m.obj,0,0))
    # At level zero there is no default selection or claim, even with bad flags.
    zero=bytearray(p);struct.pack_into('<I',zero,2892,0)
    m.receive(zero);m.draw(output/'level-zero.png')
    for track in range(2):
        for col in range(5):
            assert pixel(258+col*100,184+track*151) not in (0xFF60C789,0xFFD0A03C)
            m.click(230+col*100,300+track*151)
    n=len(m.sent);m.click(670,502);assert len(m.sent)==n
    # A future page is still browseable, with no selectable reward.
    m.receive(p);m.click(706,150);assert m.sent[-1][4:]==(20,1)
    future=bytearray(p);struct.pack_into('<I',future,2884,1)
    for track in range(2):
        for col in range(5):struct.pack_into('<I',future,3536+(track*5+col)*372,col+6)
    m.receive(future);m.draw(output/'future-page.png')
    n=len(m.sent);m.click(230,300);m.click(670,502);assert len(m.sent)==n
    assert pixel(258,184)==gray(0xFFD4DFE9)
    m.click(676,150);assert m.sent[-1][4:]==(20,0)
    m.receive(p);m.draw();assert pixel(258,184)==0xFF60C789
    # A level-up unlocks its cell; reset removes that selection immediately.
    leveled=bytearray(p);struct.pack_into('<I',leveled,2892,5)
    m.receive(leveled);m.click(630,300);m.draw(output/'level-five-unlocked.png')
    assert pixel(658,184)==0xFF60C789 and pixel(630,194)==0xFFDC4628
    m.receive(p);m.draw();assert pixel(258,184)==0xFF60C789 and pixel(658,184)==gray(0xFFD4DFE9)
    # An in-flight response must not reinterpret a held card press.
    m.mouse(330,300,0);m.receive(p);m.mouse(330,300,1);m.draw()
    assert pixel(258,184)==0xFF60C789 and pixel(358,184)==0xFFD4DFE9
    # Zero-id entries are empty slots too, even inside the advertised count.
    hole=bytearray(p);struct.pack_into('<I',hole,3536+12,0)
    m.receive(hole);m.draw();assert pixel(226,192)==0xFFF8FCFF
    assert not any(item[0]==500 for item in m.items)
    print('PASS reached-only rewards: gray icons/cards/headings; no empty slot frames; level 0/2/5; both tracks; future pages; reset/stale presses; future hover/sixth-item inspection; claim flags cannot bypass level')


def main(exe,output):
    output.mkdir(parents=True,exist_ok=True)
    pager_header(exe,output)
    m=BoardMachine(exe);s=m.c['state'];p=rewards();m.receive(p)
    real_window(m);assert m.sent[-1][3:]==(6,0,0),'real window refresh must negotiate protocol six'
    m.click(50,114)
    assert m.r(m.c['board']+4384)==505 and m.r(m.c['board']+4384+5*72)==555
    m.draw(output/'rewards-six.png');assert len(m.items)==23
    assert ('Normal',138,229) in [row[:3] for row in m.texts]
    assert ('Premium',138,380) in [row[:3] for row in m.texts]
    assert sum(row[0]=='Rewards' and row[1]==138 for row in m.texts)==2
    assert not m.contains('shown + more')
    pix,width,_=m.pixels(m.obj)
    def pixel(x,y):return m.r(pix+(y*width+x)*4)
    assert pixel(258,184)==0xFF60C789,'normal selection must be green'
    # Empty levels retain their gray outer card, without any empty item boxes.
    for track in range(2):
        yy=184+track*151
        assert pixel(458,yy)==gray(0xFFD4DFE9)
        for slot in range(6):
            x=422+slot%2*38;y=yy+4+slot//2*36
            fill=gray(0xFFFFFCF3 if track else 0xFFF8FCFF)
            assert pixel(x+4,y)==fill
            assert pixel(x+4,y+4)==fill
    # Slot six uses its own real item id/quantity and exact small hitbox.
    m.invoke(m.c['move'],0,(m.obj,271,270));m.draw(output/'sixth-tooltip.png')
    assert m.contains('Quantity: 6')
    m.mouse(271,270,2);m.mouse(271,270,3);assert m.descriptions==[505]
    m.mouse(431,270,2);m.mouse(431,270,3);assert m.descriptions==[505],'empty slot inspection'
    m.click(230,445);m.draw(output/'premium-highlight.png')
    assert pixel(258,335)==0xFFD0A03C and pixel(258,184)==0xFFD4DFE9
    assert pixel(258,163)==0xFFD0A03C,'level heading follows premium selection'
    # Exact selected level/track goes to the server, never an optimistic stamp.
    m.click(670,502);assert m.sent[-1][4:]==(15,1) and m.sent[-1][3]==6
    assert m.r(m.c['board']+664+5*372+4)==5
    m.now+=1500;m.receive(p);m.click(230,300)
    m.invoke(m.c['move'],0,(m.obj,0,0));m.draw();before=picture(m)
    m.click(670,502);assert m.sent[-1][3:]==(6,14,1)
    assert m.r(m.c['board']+664+4)==5,'stamp cannot appear before server confirms'
    claimed=bytearray(p);struct.pack_into('<I',claimed,3536+4,3)
    m.receive(claimed);m.invoke(m.c['move'],0,(m.obj,0,0));m.draw(output/'claimed-level-one.png');after=picture(m)
    for track in range(2):
        for col in range(5):
            if track==0 and col==0:continue
            box=(210+col*100,184+track*151,306+col*100,317+track*151)
            assert before.crop(box).tobytes()==after.crop(box).tobytes(),('stamp escaped its level/track',track,col)
    stamp=after.crop((211,220,305,279))
    assert sum(r<160 and b>r+35 for r,g,b,a in stamp.get_flattened_data())>200,'claimed stamp ink missing'
    assert m.contains('Claimed')
    n=len(m.sent);m.click(670,502);assert len(m.sent)==n,'claimed level cannot be claimed twice'
    # Max-six config is fail-closed. Do not offer an unseen seventh reward.
    bad=bytearray(p);struct.pack_into('<I',bad,3536+8,7)
    m.receive(bad);m.draw();assert m.contains('Config error')
    m.click(670,502);assert len(m.sent)==n
    # A v5 downgrade clears the appended slots and cannot silently claim six.
    legacy=snapshot();struct.pack_into('<I',legacy,3536+8,6)
    m.receive(legacy);assert bytes(m.u.mem_read(m.c['board']+4384,720))==bytes(720)
    m.draw();assert m.contains('Update server')
    m.click(670,502);assert len(m.sent)==n
    m.mouse(271,270,2);m.mouse(271,270,3);assert m.descriptions==[505]
    m.receive(p);old=bytes(m.u.mem_read(m.c['board'],5104))
    for length,version in [(7975,6),(7976,7),(7256,6)]:
        bad=bytearray(p);struct.pack_into('<H',bad,2,length);struct.pack_into('<H',bad,8,version)
        m.receive(bad);assert bytes(m.u.mem_read(m.c['board'],5104))==old,'malformed board mutated state'
    all_claimed=bytearray(p)
    for cell in range(10):struct.pack_into('<I',all_claimed,3536+cell*372+4,3)
    m.receive(all_claimed);m.draw(output/'all-claimed.png')
    assert m.r(m.r(m.obj+0x24)+0x28)==0,'all ten stamps must retain opaque presentation'
    print('PASS BPUI v6: six slots/items/hover per cell; empty level boxes; green/gold selection; exact level/track claims; server-confirmed stamps clipped to one cell; duplicate/overflow/downgrade/malformed guards')
    reached_only(exe,output)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();main(args.exe,args.output)
