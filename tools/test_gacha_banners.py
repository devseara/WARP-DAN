"""Execute the real v21 x86: banners, rarity cards and continuous reels.

Offline native/transport boundary tests; never opens the game or buys rewards.
"""
import argparse
from pathlib import Path
import struct
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_gacha_ui import GachaMachine, snapshot, step_snapshot

def catalog(request=0,session=77,page=1,pages=2,active=1,count=5):
    p=snapshot(9,request,session,view=0)
    struct.pack_into('<I',p,28,active);struct.pack_into('<I',p,52,count)
    struct.pack_into('<2I',p,3480,page,pages);p[672:1824]=bytes(1152)
    for i in range(count):
        off=672+i*96;id_=(page-1)*5+i+1
        struct.pack_into('<2I',p,off,id_,[1161,2289,1716,501,12210][i])
        p[off+16:off+64]=(f'Machine {id_} - Zeny Gacha').encode().ljust(48,b'\0')
    p[3496:3528]=f'{page} / {pages}'.encode().ljust(32,b'\0')
    return p

def run(exe,preview=None,game=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready();assert c['banners']
    if game:m.client_artwork(game)
    p=snapshot()
    for off,name in ((3528,'Epic'),(3552,'Rare'),(3576,'Common'),(3636,'Legendary')):
        p[off:off+24]=name.encode().ljust(24,b'\0')
    struct.pack_into('<I',p,3660,4)
    for i in range(12):
        struct.pack_into('<3I',p,672+i*96+4,i+1,[2,1,0,3][i%4],8 if i%2==0 else 0)
    struct.pack_into('<I',p,684,9) # NEW and PITY must coexist.
    m.receive(p);m.receive(catalog());m.texts=[];m.invoke(c['draw'],obj)
    pix,w,h=m.pixels(obj);assert (w,h)==(920,440)
    assert m.r(pix+4*(55*w+10))==0xffd0a03c,'opaque banner hid selected border'
    assert any(t=='PITY' and (x,y)==(279,188) for t,x,y,_ in m.texts)
    data=m.pe.get_memory_mapped_image()
    assert b'genericsui\\gacha\\' not in data
    for name in ('common','rare','epic','legendary','arrow_on_left','arrow_on_right','arrow_off_left','arrow_off_right'):
        assert ('gachaui\\'+name+'.png').encode() in data
    for i in range(12):
        x=180+(i%4)*185;y=134+(i//4)*76
        assert any(t==['Common','Rare','Epic','Legendary'][i%4] and (tx,ty)==(x+22,y+2) for t,tx,ty,_ in m.texts)
        assert any(t==f'x{i+1}' and (tx,ty)==(x+44,y+34) for t,tx,ty,_ in m.texts)
        assert any(t=='NEW' and (tx,ty)==(x+139,y+54) for t,tx,ty,_ in m.texts)==(i%2==0)
        # Exactly 1/2/3/4 stars, in this rarity order, at stable native pixels.
        for star in range(4):
            color=m.r(pix+4*((y+55)*w+x+45+star*11+4))
            assert (color==0xffe6b647)==(star<i%4+1),(i,star,hex(color))
    if preview:
        preview.mkdir(parents=True,exist_ok=True)
        Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview/'banners-cards.png')
    def click(x,y,up=None):
        m.invoke(c['down'],obj,(x,y));m.invoke(c['up'],obj,up or (x,y))
    def hit(x,y):m.invoke(c['hit'],obj,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
    for i in range(5):assert hit(20,70+i*66)==30+i
    assert hit(20,400)==0 and hit(120,400)==36
    # Outside release cancels, pending/modal/roll lock banner input.
    before=len(m.sent);click(20,70,(170,70));assert len(m.sent)==before
    for state in (16,52,3852):m.w(s+state,1);assert hit(20,70)==0;m.w(s+state,0)
    click(20,136);assert struct.unpack('<HHIHH5I',m.sent[-1])[4:]==(9,1,77,0,2,0)
    assert hit(20,70)==0
    # New server-selected session clears stale cards/catalog and accepts only
    # the matching directory; old-session replies cannot redraw another machine.
    m.receive(snapshot(session=88));assert m.r(s+3856+16)==0
    m.receive(catalog(session=77));assert m.r(s+3856+16)==0
    m.receive(catalog(session=88,active=2));assert m.r(s+3856+28)==2
    before=bytes(m.u.mem_read(s+3856,3788))
    for off,value in ((52,6),(3480,0),(3484,0),(3484,14),(672,0),(672,0x80000000)):
        bad=catalog(session=88);struct.pack_into('<I',bad,off,value);m.receive(bad)
        assert bytes(m.u.mem_read(s+3856,3788))==before
    click(120,400);fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==10 and fields[8:]==(2,0)
    m.receive(catalog(request=m.r(s+44),session=88,page=2));assert hit(20,400)==35 and hit(120,400)==0
    # Four-tier colors/NEW never leak on prize/history screens.
    for view in (1,2,3,4,5):
        q=snapshot(view=view,session=88,admin=view==5)
        for i in range(12):struct.pack_into('<I',q,672+i*96+12,8)
        m.receive(q);m.texts=[];m.invoke(c['draw'],obj)
        assert not any(t=='NEW' for t,_,_,_ in m.texts)
        assert not any(t.startswith('Pull x') for t,_,_,_ in m.texts)
    # Existing quote/replay guards retain exact v9 request/quote semantics.
    m.receive(snapshot());click(865,395);assert struct.unpack('<HHIHH5I',m.sent[-1])[4]==1
    seq=m.r(s+44);m.receive(snapshot(3,seq,token=123));assert m.r(s+52)==1
    before=len(m.sent);click(20,70);assert len(m.sent)==before
    click(570,275);assert struct.unpack('<HHIHH5I',m.sent[-1])[4]==2
    m.receive(step_snapshot(5,m.r(s+44),12,0,1020));epoch=m.r(s+7644)
    # Remaining icons advance both while the server is pending and after each
    # reveal/delivery; animation phase never restarts at an ACK.
    for index in range(1,13):
        before=len(m.sent)
        m.now+=1020 if index==1 else 220;m.invoke(c['timer'],0,(0,0,0,0))
        assert len(m.sent)==before+1
        assert struct.unpack('<HHIHH5I',m.sent[-1])[8]==index
        m.receive(step_snapshot(7,m.r(s+44),12,index))
        phases=[];future=[]
        for dt in (100,100,100):
            m.now+=dt;m.invoke(c['timer'],0,(0,0,0,0));phases.append(m.r(s+56))
            m.lookups=[];m.invoke(c['draw'],obj);future.append(m.lookups[-(12-index):] if index<12 else [])
            assert len(m.sent)==before+1
            assert m.r(s+7644)==epoch
        assert phases[0]<phases[1]<phases[2]
        if index<12:assert future[0]!=future[1] and future[1]!=future[2]
        phase=m.r(s+56)
        m.receive(step_snapshot(6 if index<12 else 4,m.r(s+44),12,index))
        assert m.r(s+56)==phase and m.r(s+7644)==epoch
        if preview and index in (1,6,12):
            m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj)
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview/f'roll-{index}.png')
    assert m.r(s+3852)==0
    click(906,9);assert m.r(s+20)==1 and m.r(s+32)==0
    print('PASS: real v21 banners/clicks/page bounds/old-session rejection, supplied rarity skins, 1-4 stars/quantities/NEW, unchanged quote wire, all 12 ordered rewards and continuously advancing unrevealed icons across every reveal and ACK; no extra requests')

def extra_button_tests(exe):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    cases=[(snapshot(admin=True),catalog(page=2,pages=3),
            [(35,'Back',10,390,39),(36,'Next',112,390,38)]),
           (snapshot(view=5,admin=True),None,[(13,'Reset This Machine',482,292,116)]),
           (snapshot(8,token=555,view=5,admin=True),None,
            [(22,'Reset',548,264,42),(23,'Cancel',489,264,49)])]
    for packet,banners,buttons in cases:
        m.receive(packet)
        if banners:m.receive(banners)
        m.texts=[];m.invoke(c['draw'],obj)
        for id_,label,x,y,width in buttons:
            span=int(m.font.getlength(label));assert width==span+14
            assert any(t==label and (tx,ty)==(x+7,y+4) for t,tx,ty,_ in m.texts)
            for xy in ((x,y),(x+width-1,y+19)):
                m.invoke(c['hit'],obj,xy);assert m.u.reg_read(UC_X86_REG_EAX)==id_
            for xy in ((x-1,y+4),(x+width,y+4)):
                m.invoke(c['hit'],obj,xy);assert m.u.reg_read(UC_X86_REG_EAX)==0
    print('PASS: sidebar Back/Next and both administrative reset controls fit actual text plus 14px; centered labels and matching exact hit bounds')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--preview',type=Path);ap.add_argument('--game',type=Path)
    args=ap.parse_args();run(args.exe,args.preview,args.game);extra_button_tests(args.exe)
