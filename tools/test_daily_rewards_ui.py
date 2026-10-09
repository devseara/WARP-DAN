"""Execute DRUI's emitted x86 with native OS/font/texture boundaries; save render evidence."""
import argparse, struct
from pathlib import Path
from PIL import Image, ImageFont, ImageDraw
from test_modern_chat_ui import Machine, pack
from test_gacha_ui import GachaMachine

FIELDS='api state toggle receive hit draw down up move drag cursor destroy timer rightdown rightup wheel receiver menu fallback'.split()
def contract(m):
    data=m.pe.get_memory_mapped_image(); pos=data.find(b'DailyRewardsUI.v2\0'); assert pos>=0
    record=data.find(pack(m.base+pos));assert record>=0
    return {name:m.r(m.base+record+4+i*4) for i,name in enumerate(FIELDS)}

def snapshot(seq=1,page=0,total=24,attpage=0,roll=0,legacy=False):
    p=bytearray(3308 if legacy else 5268)
    struct.pack_into('<HHIHH9I',p,0,0xbf4,len(p),0x49555244,1 if legacy else 2,1|(2 if roll else 0),seq,20261008,86400,attpage,page,(total+5)//6,total,2,roll)
    p[48:144]=b'Rewards are delivered by RODEX. Daily reset: midnight server time.'.ljust(96,b'\0')
    def item(off,id,qty=1):
        struct.pack_into('<II',p,off,id,qty);p[off+8:off+56]=('Reward '+str(id)).encode().ljust(48,b'\0')
    for i in range(7):
        day=attpage*7+i+1;off=144+i*64;struct.pack_into('<II',p,off,day,2 if day<=2 else 1 if day==3 else 0);item(off+8,501+i,10)
        if not legacy:
            for j in range(5):item(3308+(i*5+j)*56,502+j,j+1)
    for i,name in enumerate(['Defeat any monsters','Hunt Poring','Collect Jellopy','Use Blue Potion','Defeat players in PvP']):
        off=592+i*420;struct.pack_into('<5I',p,off,i+1,1002,20,20 if i<2 else 15,1 if i==1 else 0);p[off+20:off+84]=name.encode().ljust(64,b'\0')
        for j in range(6):item(off+84+j*56,501+j,j+1)
    for i in range(roll):item(2692+i*56,501+i,5)
    for i in range(min(6,max(0,total-page*6))):item(2972+i*56,501+page*6+i)
    return p

class DailyMachine(Machine):
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    def __init__(self,exe):
        self.text_colors=[];super().__init__(exe,Path('.'));self.c=contract(self)
        self.now=1000;self.sent=[];self.timers=[];self.stock=[];self.described=[];self.monsters=[];self.icons=[]
        self.stub(0xA21C90,self.measure)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x86B950,lambda:self.ret(4))
        self.stub(0x86E240,lambda:self.ret(4))
        self.head=self.alloc(12);self.w(self.head,self.head);self.w(self.head+4,self.head)
        self.w(0x131F4E8+0x17c,self.head);self.w(0x131F4E8+0x180,0)
        self.stub(0xDBBC7F,lambda:self.ret(0));self.stub(0xA47B90,lambda:self.ret(4,0))
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19c,self.args(1)[0]),self.ret(4)))
        for addr,label in [(0x880AD0,'dragdown'),(0x880BB0,'dragup'),(0x880E00,'dragmove')]:self.stub(addr,lambda label=label:self.forward(label,2))
        self.stub(0xA23470,lambda:self.ret(8));self.stub(0xA764A0,lambda:self.ret(4));self.w(0x121333C,self.alloc(64))
        self.stub(0xC9E1DD,lambda:self.ret(0));self.stub(0x814ACC,lambda:self.ret(0))
        self.stub(self.c['fallback'],lambda:(self.stock.append(1),self.ret(0)))
        api=self.c['api'];self.stub(self.r(api+8),lambda:self.ret(0,0x20200000));self.stub(self.r(api+12),self.send)
        self.stub(self.r(api+20),self.icon)
        self.stub(self.r(api+24),lambda:(self.described.append(self.args(1)[0]),self.ret(4)))
        self.stub(self.r(api+40),self.monster)
        tick=self.alloc(16);self.stub(tick,lambda:self.ret(0,self.now));self.w(0xFC17B0,tick)
        setter=self.alloc(16);killer=self.alloc(16)
        self.stub(setter,lambda:(self.timers.append('start'),self.ret(16,567)))
        self.stub(killer,lambda:(self.timers.append('stop'),self.ret(8,1)))
        module=self.alloc(16);proc=self.alloc(16)
        self.stub(module,lambda:self.ret(4,123))
        self.stub(proc,lambda:self.ret(8,setter if self.cstr(self.args(2)[1])=='SetTimer' else killer))
        self.w(self.r(api+28),module);self.w(self.r(api+32),proc)
    def measure(self):
        ptr,length,_,height,bold,_=self.args(6);font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',height)
        self.ret(24,int(font.getlength(self.cstr(ptr)[:length])))
    def icon(self):
        obj,item,x,y=self.args(4);pix,w,h=self.pixels(obj)
        self.icons.append((item,x,y))
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
        draw=ImageDraw.Draw(im);draw.rounded_rectangle((x+9,y+3,x+24,y+28),radius=4,fill=['#d05060','#668acf','#70ad68'][item%3],outline='#556070');draw.rectangle((x+12,y,x+20,y+6),fill='#d9d5c1')
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(16)
    def monster(self):
        from unicorn.x86_const import UC_X86_REG_ECX
        view,x,y,w,h,cycle=self.args(6);self.monsters.append((view,x,y,w,h,cycle))
        obj=self.u.reg_read(UC_X86_REG_ECX);pix,sw,sh=self.pixels(obj)
        im=Image.frombytes('RGBA',(sw,sh),bytes(self.u.mem_read(pix,sw*sh*4)),'raw','BGRA')
        draw=ImageDraw.Draw(im);draw.ellipse((x+20,y+25,x+w-20,y+h-20),fill='#e8a4b9',outline='#915775')
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(24,1)
    def send(self):
        size,ptr=self.args(2);assert size==32;self.sent.append(bytes(self.u.mem_read(ptr,size)));self.ret(8)
    def receive(self,p):
        self.u.mem_write(0x15E8198,bytes(p));self.invoke(self.r(0xCAA2E0+(0xbf4-0x73)*4),0)
    def click(self,x,y):
        obj=self.r(self.c['state']);self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def reply(self,**kw):
        seq=struct.unpack_from('<I',self.sent[-1],12)[0];p=snapshot(seq=seq,**kw);self.receive(p);return p
    def preview(self,path):
        self.texts=[];self.text_colors=[];self.icons=[];obj=self.r(self.c['state']);self.invoke(self.c['draw'],obj);pix,w,h=self.pixels(obj)
        Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB').save(path)
    def advance(self,ms):
        self.now+=ms;self.invoke(self.c['timer'],0,(0,0,567,self.now))

def tooltip_checks(m,output):
    c=m.c;obj=m.r(c['state'])
    def hover(x,y,name,detail,filename,position):
        m.invoke(c['move'],obj,(x,y));m.preview(output/filename)
        assert [t[0] for t in m.texts[-2:]]==[name,detail],m.texts[-2:]
        assert all(color==0x292929 for _,color,_,_ in m.text_colors[-2:]),'tooltip text differs from reference'
        px,py=position;pixels,w,h=m.pixels(obj)
        assert m.r(pixels+((py+37)*w+px+10)*4)==0xFFFFFFDE,'tooltip fill differs from reference'
        assert m.r(pixels+(py*w+px+10)*4)==0xFF8C847B,'tooltip border differs from reference'
        assert 4<=px and px+266<=916 and 26<=py and py+42<=678,'tooltip escaped content'
    m.click(815,43)
    p=snapshot(seq=m.r(c['state']+4))
    cases=[(1,0,10,7,'Defeat any monsters','ANY'),
           (2,1007,30,0,'Hunt Lunatic','Lunatic'),
           (3,909,50,0,'Collect Jellopy','Jellopy'),
           (4,505,50,12,'Use Blue Potion','Blue Potion'),
           (5,0,1,0,'Defeat players in PvP','PvP Player')]
    for i,(kind,target,required,progress,title,name) in enumerate(cases):
        off=592+i*420;struct.pack_into('<5I',p,off,kind,target,required,progress,0)
        p[off+20:off+84]=title.encode().ljust(64,b'\0')
    m.receive(p);sent=len(m.sent)
    for i,(_,_,required,_,_,name) in enumerate(cases):
        y=150+i*116
        hover(70,y,name,'Required: '+str(required),'tooltip-quest-'+str(i+1)+'.png',(82,y+18))
    # Hovering all objective art, including empty portrait padding, is supported.
    hover(30,120,'ANY','Required: 10','tooltip-any-padding.png',(42,138))
    old=len(m.described);m.invoke(c['rightdown'],obj,(70,270));m.invoke(c['rightup'],obj,(70,270))
    assert len(m.described)==old,'monster tooltip treated a monster ID as an item'
    hover(70,498,'Blue Potion','Required: 50','tooltip-use-item.png',(82,516))
    m.invoke(c['rightdown'],obj,(70,498));m.invoke(c['rightup'],obj,(70,498))
    assert m.described[old:]==[505],'usable item description no longer opens';m.described.clear()
    hover(710,665,'Reward 506','Quantity: 6','tooltip-quest-reward-edge.png',(650,619))
    hover(100,650,'PvP Player','Required: 1','tooltip-pvp-bottom.png',(112,604))
    assert len(m.sent)==sent,'hover or item inspection sent a quest/claim request'
    m.invoke(c['move'],obj,(480,40));m.preview(output/'tooltip-cleared.png')
    assert not any(t[0].startswith(('Required:','Quantity:')) for t in m.texts),'tooltip remained after leaving icon'
    m.click(40,44)
    hover(870,245,'Reward 506','Quantity: 5','tooltip-attendance-edge.png',(650,263))
    m.click(338,44)
    hover(650,575,'Reward 506','Quantity: 1','tooltip-roll-pool.png',(650,593))
    # Target labels/counts are in the v1 prefix; no new server packet is needed.
    m.click(190,44);m.click(815,43);m.reply(legacy=True)
    hover(70,498,'Blue Potion','Required: 20','tooltip-legacy-server.png',(82,516))
    m.invoke(c['move'],obj,(480,40));m.click(815,43);m.reply()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    m=DailyMachine(a.exe);c=m.c;s=c['state']
    # Actual patched menu/receiver/draw/input/timer functions; engine resource boundaries only are doubled.
    m.invoke(0x814EBD,0);assert len(m.sent)==1 and struct.unpack_from('<H',m.sent[-1],10)[0]==0
    assert struct.unpack_from('<I',m.sent[-1],20)[0]==0x32555244,'missing backward-compatible capability'
    m.reply();obj=m.r(s);assert (m.r(obj+0x14),m.r(obj+0x18))==(920,720)
    m.preview(a.output/'attendance.png');assert any('Day 7'==r[0] for r in m.texts) and len(m.icons)==42
    assert sum(t[0]=='Available' for t in m.texts)==1 and sum(t[0]=='Claimed' for t in m.texts)==2
    m.click(30,200);old=len(m.sent);m.click(780,365);assert len(m.sent)==old,'claimed selection sent claim'
    m.click(282,200);assert len(m.sent)==old,'selection claimed immediately'
    m.click(780,365);assert struct.unpack_from('<HH',m.sent[-1],8)==(2,2) and struct.unpack_from('<I',m.sent[-1],20)[0]==2
    old=len(m.sent);m.click(780,365);assert len(m.sent)==old,'pending claim duplicated';m.reply()
    m.click(887,89);assert struct.unpack_from('<I',m.sent[-1],24)[0]==1;m.reply(attpage=1)
    m.preview(a.output/'attendance-page2.png');assert any(r[0]=='Day 8' for r in m.texts)
    old=len(m.sent);m.click(780,365);assert len(m.sent)==old,'page change retained hidden available selection'
    m.click(789,89);m.reply()
    # Both wire versions are accepted, but a mismatched version/length is rejected.
    m.click(815,43);m.reply(legacy=True);m.preview(a.output/'attendance-legacy.png');assert len(m.icons)==7
    m.click(780,365);assert struct.unpack_from('<H',m.sent[-1],8)[0]==1;m.reply(legacy=True)
    m.click(815,43);bad=snapshot(seq=m.r(s+4));struct.pack_into('<H',bad,8,1);m.receive(bad);assert m.r(s+8);m.reply()
    m.click(190,44);m.preview(a.output/'daily-quests.png')
    assert len(m.icons)==32 and {v[0] for v in m.monsters}=={1002}
    assert any(t[0]=='15 / 20 collected' for t in m.texts) and any(t[0]=='15 / 20 used' for t in m.texts)
    tooltip_checks(m,a.output)
    m.click(808,146);assert struct.unpack_from('<H',m.sent[-1],10)[0]==3;m.reply()
    m.click(338,44);m.preview(a.output/'daily-roll-ready.png')
    assert any(t[0]=="Today's roll: Ready" for t in m.texts) and sum(t[0]=='Ready' for t in m.texts)==5
    for page in [1,2,3]:m.click(890,424);assert struct.unpack_from('<I',m.sent[-1],28)[0]==page;m.reply(page=page)
    old=len(m.sent);m.click(890,424);assert len(m.sent)==old,'end page sent request'
    m.preview(a.output/'daily-roll-page4.png');assert any(t[0]=='Page 4 / 4' for t in m.texts)
    m.click(815,43);m.reply(page=0,total=7);m.click(891,424);m.reply(page=1,total=7)
    m.preview(a.output/'daily-roll-partial.png');assert any(t[0]=='Rewards 7 - 7 of 7' for t in m.texts) and len(m.icons)==1
    m.click(815,43);m.reply(total=24);m.click(790,366);assert struct.unpack_from('<H',m.sent[-1],10)[0]==4
    m.preview(a.output/'daily-roll-spinning.png')
    old=len(m.sent);m.click(790,366);m.click(890,424)
    assert len(m.sent)==old,'pending roll allowed a duplicate roll or reward-page request'
    m.advance(6000);m.reply(roll=3);m.preview(a.output/'daily-roll-slow-reply.png')
    assert not any(t[0]=='Received' for t in m.texts),'slow server response skipped the reveal'
    m.now+=3100;m.preview(a.output/'daily-roll-revealing.png')
    assert sum(t[0]=='Received' for t in m.texts)==2 and sum(t[0]=='Rolling...' for t in m.texts)==2
    old=len(m.sent);m.click(160,370);assert len(m.sent)==old,'skip reveal sent another roll'
    m.preview(a.output/'daily-roll-result.png');assert sum(t[0]=='Received' for t in m.texts)==3 and sum(t[0]=='No reward' for t in m.texts)==2
    m.click(790,366);assert len(m.sent)==old,'claimed roll sent again'
    m.invoke(c['rightdown'],obj,(35,213));m.invoke(c['rightup'],obj,(35,213));assert m.described==[501]
    m.click(815,43);m.reply();m.click(60,370);m.click(790,366)
    m.preview(a.output/'daily-roll-motion-off-pending.png')
    assert not any(y<410 for _,x,y in m.icons),'Motion off still cycled roll item icons while waiting'
    m.reply(roll=5)
    m.preview(a.output/'daily-roll-motion-off.png');assert sum(t[0]=='Received' for t in m.texts)==5 and not any(t[0]=='Rolling...' for t in m.texts)
    m.click(60,370);m.click(815,43);m.reply();m.click(790,366);m.reply(roll=1);m.advance(5500)
    if m.r(s+8):m.reply(roll=1)
    m.preview(a.output/'daily-roll-one-result.png');assert sum(t[0]=='Received' for t in m.texts)==1
    m.advance(3001);pending=snapshot(seq=m.r(s+4));m.click(906,11);m.receive(pending);assert not m.r(s+28) and not m.r(obj+0x28),'late snapshot reopened closed UI'
    m.invoke(c['menu'],0);m.reply();assert m.r(obj+0x28) and m.timers[-1]=='start'
    foreign=snapshot();foreign[4:8]=b'NOPE';m.receive(foreign);assert m.stock
    m.click(815,43);bad=snapshot(seq=m.r(s+4));struct.pack_into('<I',bad,44,6);m.receive(bad);assert m.r(s+8),'malformed reward count accepted';m.reply()
    m.invoke(c['down'],obj,(50,8));m.invoke(c['drag'],obj,(60,8));m.invoke(c['up'],obj,(60,8));assert not m.r(0x131F4E8+0x19c)
    m.invoke(c['destroy'],obj,(1,));assert not m.r(s) and m.timers[-1]=='stop'
    print('PASS: native Attendance override, frame/input ABI, all tabs, 42 attendance slots, 30 quest rewards, objective sprite dispatch, Available/Claimed selection, v1 fallback/v2 bundles, pagination/clamps, partial page, sequential server roll/reveal including delayed replies, static Motion-off pending cards, motion/skip, duplicate guards, right-click, malformed/foreign packets, capture and close/reopen. Real font; item/monster artwork uses explicit test placeholders.')

if __name__=='__main__':main()
