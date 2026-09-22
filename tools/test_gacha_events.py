"""Execute v22 wallet/timer/reveal controls in the emitted native client."""
import argparse
from pathlib import Path
import struct
from PIL import Image
from unicorn import UC_HOOK_MEM_READ
from unicorn.x86_const import UC_X86_REG_EAX
from test_gacha_ui import GachaMachine, snapshot, step_snapshot

def wallet(request=0, session=77, currency=0, seconds=129600, flags=1|224|256|1024):
    p=snapshot(10,request,session)
    struct.pack_into('<I',p,24,flags)
    struct.pack_into('<I',p,28,1)
    struct.pack_into('<3I',p,52,100,currency,501)
    struct.pack_into('<I',p,668,seconds)
    for off,size,value in [(64,48,'Prontera Ticket'),(112,128,''),(240,32,'54,321,000z'),(272,64,'100'),
        (336,96,'Next pull: 10 Prontera Ticket - 10 pulls: 100 Prontera Ticket' if currency else 'Next pull: 1,000,000z - 10 pulls: 10,000,000z'),
        (528,128,'100 pity: 70% Legend / 30% Epic'),(3728,48,'Every 10 pulls: Epic+')]:
        p[off:off+size]=value.encode().ljust(size,b'\0')
    return p

def run(exe,preview):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready();assert c['wallet']
    def click(x,y):m.invoke(c['down'],obj,(x,y));m.invoke(c['up'],obj,(x,y))
    def hit(x,y):m.invoke(c['hit'],obj,(x,y));return m.u.reg_read(UC_X86_REG_EAX)
    def tick(ms):m.now+=ms;m.invoke(c['timer'],0,(0,0,0,0))
    def draw():m.texts=[];m.invoke(c['draw'],obj);return [t for t,x,y,_ in m.texts]
    def request():return struct.unpack('<HHIHH5I',m.sent[-1])
    m.receive(wallet());labels=draw()
    # Native CTexture is 0x120 bytes. The private blue-Z cropped descriptor
    # must not copy allocator padding (the old boundary allocated 0x130).
    zeny=m.textures['zeny.png'];overread=[]
    guard=m.u.hook_add(UC_HOOK_MEM_READ,lambda u,access,address,size,value,data:overread.append((address,size)),begin=zeny+0x120,end=zeny+0x12f)
    draw();m.u.hook_del(guard);assert not overread,overread
    assert 'Ends in: 1d 12:00:00' in labels,labels
    assert any(t=='Ends in: 1d 12:00:00' and color==0x2020cc for t,color,x,y in m.text_colors)
    assert '100 pity: 70% Legend / 30% Epic' in labels and 'Every 10 pulls: Epic+' in labels
    assert 'Motion: on' in labels and 'Skip Reveal' in labels
    assert hit(745,395)==10 and hit(802,395)==11 and hit(870,395)==12
    assert hit(290,365)==0 and hit(200,365)==39
    for bits,enabled in [(0,()),(32,(10,)),(96,(10,11)),(224,(10,11,12))]:
        m.receive(wallet(flags=1|256|1024|bits))
        for xy,id_ in [((745,395),10),((802,395),11),((870,395),12)]:assert hit(*xy)==(id_ if id_ in enabled else 0)
    m.receive(wallet());before=bytes(m.u.mem_read(s+7648,3788))
    for p in [wallet(session=78),wallet(request=123),wallet(currency=2),wallet(flags=1)]:
        m.receive(p);assert bytes(m.u.mem_read(s+7648,3788))==before
    click(820,365);assert request()[4]==11 and request()[8]==1
    seq=m.r(s+44);m.receive(snapshot(2,seq));m.receive(wallet(seq,currency=1))
    assert 'Next pull: 10 Prontera Ticket - 10 pulls: 100 Prontera Ticket' in draw()
    # A metadata poll cannot dismiss an open confirmation or mutate results.
    click(745,395);seq=m.r(s+44);m.receive(snapshot(3,seq,token=900));m.receive(wallet(seq,currency=1));assert m.r(s+52)==1
    old=bytes(m.u.mem_read(s+64+672,1152));tick(1000);assert request()[4]==12
    m.receive(wallet(m.r(s+44),currency=1));assert m.r(s+52)==1 and bytes(m.u.mem_read(s+64+672,1152))==old
    # Countdown is relative to the server snapshot, even without a response.
    m.receive(snapshot());m.receive(wallet(seconds=2));tick(1000);assert m.r(s+11448)==1
    tick(1000);assert m.r(s+11448)==0 and not(m.r(s+64+24)&225)
    assert hit(745,395)==0
    # Motion-off retains empty boxes but does not cycle cosmetic item IDs.
    m.receive(snapshot());m.receive(wallet());click(200,365);assert m.r(s+11452)==1 and 'Motion: off' in draw()
    click(870,395);assert request()[4]==1 and request()[9]==1
    seq=m.r(s+44);m.receive(snapshot(3,seq,token=901));click(570,275);assert request()[4]==2
    def batch(message,revealed):
        p=step_snapshot(message,m.r(s+44),12,revealed,1)
        struct.pack_into('<I',p,24,struct.unpack_from('<I',p,24)[0]|4096)
        return p
    def complete():
        p=step_snapshot(4,m.r(s+44),12,12,1);struct.pack_into('<I',p,24,225|2048)
        p[112:240]=b'Roll complete - click a reward to inspect it.'.ljust(128,b'\0');m.receive(p)
    m.receive(batch(5,0));before=len(m.sent);tick(1000);assert len(m.sent)==before
    m.lookups=[];labels=draw();assert len(m.lookups)<12
    pix,w,h=m.pixels(obj)
    for i in range(12):assert m.r(pix+4*((140+i//4*76)*w+185+i%4*185))==0xffe9e9ee
    m.invoke(c['itemHit'],obj,(190,165));assert m.u.reg_read(UC_X86_REG_EAX)==0
    assert 'Rolling ... Slots stop in order. Skip to see all rewards' in labels
    complete()
    assert not m.r(s+3852) and 'Roll complete - click a reward to inspect it.' in draw()
    # Skip sends immediately, even while a slot is awaiting delivery. The new
    # sequence rejects the old slot response and batch mode needs no more steps.
    m.receive(snapshot());click(200,365);m.receive(step_snapshot(5,m.r(s+44),12,0,1020))
    tick(1020);assert request()[4]==6
    oldseq=m.r(s+44);before=len(m.sent);assert hit(290,365)==40;click(290,365);assert len(m.sent)==before+1 and request()[4]==13
    assert m.r(s+11456)==1 and m.r(s+11460)==0
    old=bytes(m.u.mem_read(s+64,3788));m.receive(step_snapshot(7,oldseq,12,1));m.receive(step_snapshot(6,oldseq,12,1));assert bytes(m.u.mem_read(s+64,3788))==old
    m.receive(batch(6,1));tick(1000);assert len(m.sent)==before+1
    assert hit(290,365)==0 and hit(820,365)==0
    labels=draw();assert any(t=='x1' for t in labels)
    complete();m.text_colors=[];draw()
    assert any(t.startswith('Roll complete') and color==0x308030 for t,color,x,y in m.text_colors)
    # Native skins and unchanged source-art crop. Items use the native database.
    m.receive(snapshot());m.receive(wallet())
    p=snapshot();struct.pack_into('<I',p,3660,4)
    p[112:240]=b'Roll complete - click a reward to inspect it. 2 reward(s) queued for mail. Check RODEX.'.ljust(128,b'\0')
    m.receive(p);m.receive(wallet());labels=draw()
    assert any('Check RODEX.' in t for t in labels)
    pix,w,h=m.pixels(obj)
    im=Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA')
    assert im.getpixel((680,368))[:3] != im.getpixel((675,368))[:3], 'Z icon not drawn'
    assert not any(t in ('Zeny','Prontera Ticket') for t in labels)
    for text,right in [('54,321,000z',788),('100',898)]:
        assert any(t==text and y==363 and x+int(m.font.getlength(t))==right for t,x,y,_ in m.texts)
    assert any(t=='Base rates' and y==54 for t,x,y,_ in m.texts)
    assert any(t=='Grand: 37/100 | Major+: 3/10' and y==54 for t,x,y,_ in m.texts)
    if preview:preview.parent.mkdir(parents=True,exist_ok=True);im.save(preview)
    print('PASS native v22: wallet validation, per-bundle affordability, ticket selection, confirmation-safe polling, countdown lock, motion-off atomic reveal, pending-safe Skip, fixed rolling/completed/mail text, local skins and Z icon crop')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exe');p.add_argument('--preview',type=Path);a=p.parse_args();run(a.exe,a.preview)
