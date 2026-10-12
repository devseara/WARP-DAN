"""Execute shipped BPUI v5 x86 with explicit OS/native-resource boundaries.

Layout images are offline renders, not live in-game acceptance. No game data.
"""
import argparse
from pathlib import Path
import struct
from PIL import Image, ImageFont
from test_modern_chat_ui import Machine, pack
from test_gacha_ui import GachaMachine
from test_vip_ui import VipMachine

ROOT=Path(__file__).resolve().parents[1]
FIELDS='base size state board api draw mouse move cursor notify cleanup portrait monster'.split()

def contract(m):
    data=m.pe.get_memory_mapped_image();marker=data.find(b'BattlepassUI.Board.v5\0');assert marker>=0
    descriptor=data.find(pack(m.base+marker));assert descriptor>=0
    result=dict(zip(FIELDS,struct.unpack_from('<13I',data,descriptor+4)))
    marker=data.find(b'BattlepassUI.Window.v5\0');assert marker>=0
    descriptor=data.find(pack(m.base+marker));assert descriptor>=0
    result.update(zip('vtable toggle drawBridge down up right rightUp cursorBridge destroy'.split(),struct.unpack_from('<9I',data,descriptor+4)))
    return result

def snapshot():
    p=bytearray(7256)
    struct.pack_into('<HHIHHII',p,0,0xBF6,len(p),0x49555042,5,16|0x3FC0,50,0)
    def text(off,size,value):p[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
    for off,size,value in [(20,24,'DevSeara'),(44,64,'Hunt Poring'),(108,64,'Poring'),(172,32,'100 Pass EXP'),(204,32,'In Progress'),(236,48,'Time left: 00:59:22'),(284,32,'2,500'),(316,32,'2 / 30'),(348,24,'Standard'),(372,48,'300,000 Zeny'),(516,64,'500 EXP to next level')]:text(off,size,value)
    for i in range(8):text(788+i*48,24,str(100+i*50));text(812+i*48,24,str(50+i*50));text(2272+i*32,32,'Available')
    struct.pack_into('<I',p,1172,50);struct.pack_into('<I',p,1188,512)
    struct.pack_into('<10I',p,2872,43200,4*86400,8*86400,0,6,2,30,500,1000,1002)
    text(2912,48,'Monthly Battle Pass')
    for i in range(6):
        struct.pack_into('<8I',p,2960+i*96,i%3,[1002,501,0][i%3],1002,[100,50,3,500,200,10][i],[100,32,1,230,135,6][i],[50,50,100,300,300,500][i],5 if i==0 else 1,900+i)
        text(2992+i*96,64,['Poring','Red Potion','Complete quests'][i%3])
    for track in range(2):
        for col in range(5):
            off=3536+(track*5+col)*372
            struct.pack_into('<3I',p,off,col+1,5 if col<2 and track==0 else 9 if track else 1,5 if col==1 else 1)
            for i in range(5 if col==1 else 1):
                struct.pack_into('<2I',p,off+12+i*72,501+i,2+i);text(off+20+i*72,64,'Reward item')
    return p

class BoardMachine(Machine):
    stub=VipMachine.stub
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    measure=VipMachine.measure
    plain_boundaries=GachaMachine.plain_boundaries
    def __init__(self,exe):
        self.boundaries={};self.text_colors=[]
        super().__init__(exe,ROOT/'Assets/BattlepassUI/client');self.c=contract(self)
        self.now=5000;self.sent=[];self.items=[];self.descriptions=[]
        self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',11);self.plain_boundaries()
        self.stub(0xA21C90,self.measure)
        self.stub(0xA75340,lambda:self.ret(0,0)) # no live CSession/character in layout fixture
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19C,self.args(1)[0]),self.ret(4)))
        self.stub(0xA336D0,lambda:self.ret(8,self.owner))
        self.stub(0xA23470,lambda:self.ret(8))
        self.stub(0xC9E1DD,lambda:self.ret(0))
        timer=self.alloc(16);self.stub(timer,lambda:self.ret(0,self.now));self.w(0xFC17B0,timer)
        a=self.c['api'];self.stub(self.r(a+12),lambda:self.ret(0,0x20100000))
        def send():
            size,ptr=self.args(2);assert size==16
            self.sent.append(struct.unpack('<HHIHHI',bytes(self.u.mem_read(ptr,size))));self.ret(8)
        self.stub(self.r(a+16),send)
        # Resource lookup/draw boundaries; layout/paging/hit testing stay native.
        def item():self.items.append(tuple(self.args(4)[1:]));self.ret(16)
        self.stub(self.r(a+32),item)
        self.stub(self.r(a+36),lambda:(self.descriptions.append(self.args(1)[0]),self.ret(4)))
        label=self.alloc(64);self.u.mem_write(label,b'Client item name\0')
        self.stub(self.r(a+44),lambda:self.ret(4,label))
        self.stub(self.r(a+40),lambda:self.ret(24,1))
        self.obj=self.window(920,560,vt=self.c['vtable']);self.owner=self.obj
        self.w(self.obj+0x28,1);self.w(self.c['state'],self.obj)
        self.receive(snapshot())
    def receive(self,p):
        self.u.mem_write(0x15E8198,bytes(p));self.invoke(self.r(0xCAD0EC),0)
    def mouse(self,x,y,mode):
        if mode>=2:GachaMachine.right(self,self.obj,(x,y),release=mode==3)
        else:self.invoke(self.r(self.r(self.obj)+(25 if mode==0 else 31)*4),self.obj,(x,y))
    def click(self,x,y):self.mouse(x,y,0);self.mouse(x,y,1)
    def draw(self,path=None):
        self.texts=[];self.items=[];self.plain_calls=[]
        self.invoke(self.r(self.r(self.obj)+20*4),self.obj)
        if path:
            pix,w,h=self.pixels(self.obj)
            Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB').save(path)
    def contains(self,value):return any(value in row[0] for row in self.texts)

def tier_headers(exe,output):
    m=BoardMachine(exe);s=m.c['state'];m.click(50,82)
    p=snapshot()
    # Normal is on cooldown for both hunt types; all other tiers available.
    struct.pack_into('<H',p,10,(16|0x3FC0)&~(1<<7)&~(1<<11))
    for kind in range(2):
        p[2272+(kind*4+1)*32:2304+(kind*4+1)*32]=b'23:15:00'.ljust(32,b'\0')
    m.receive(p)
    for kind in range(2):
        m.click(200 if kind==0 else 400,185)
        m.draw(output/f'mission-headers-{kind}.png')
        expected=[('Difficulty',150,230),('Count',335,230),('EXP',416,230),('Status',509,230)]
        for label,x,y in expected:assert sum(row[:3]==(label,x,y) for row in m.texts)==1
        m.click(200,235);assert m.r(s+2908)==0,'header must not select a tier'
        m.click(200,310);assert m.r(s+2908)==0,'cooldown row must stay disabled'
        for i,label in enumerate(('Easy','Normal','Hard','Hardcore')):
            yy=264+i*44
            values=[(label,150),(str(100+(kind*4+i)*50),335),(str(50+(kind*4+i)*50),416),('23:15:00' if i==1 else 'Available',509)]
            for value,x in values:assert sum(row[:3]==(value,x,yy) for row in m.texts)==1,(value,x,yy)
            if i!=1:
                m.click(200,yy);assert m.r(s+2908)==i+1,'tier hitbox must follow moved row'
    print('PASS Mission column headers: Difficulty/Count/EXP/Status, aligned rows for both types, cooldown text, noninteractive header, shifted hitboxes and disabled cooldown tier')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    m=BoardMachine(args.exe);s=m.c['state'];b=m.c['board']
    assert m.r(s+24)==1 and m.r(b+88+28)==900 and m.r(s+4)==0
    m.draw(args.output/'quests.png');assert m.contains('Daily Quests') and m.contains('Weekly Quests')
    assert m.plain_calls==['DevSeara'] and m.gdi_color==0x123456
    m.click(676,178);assert m.sent[-1]==(0xBF9,16,0x49555042,5,19,900)
    n=len(m.sent);m.click(676,178);assert len(m.sent)==n,'duplicate objective click'
    m.now+=1300;m.receive(snapshot());m.mouse(676,178,0);m.receive(snapshot());m.mouse(676,178,1)
    assert len(m.sent)==n,'held press survived a reset/reply'
    m.mouse(676,178,0);m.mouse(900,550,1);assert m.r(0x131F4E8+0x19C)==0
    m.click(50,82);assert m.r(s+4)==1;m.draw(args.output/'mission-select.png')
    m.click(200,185);m.click(200,270);m.click(660,494)
    assert m.sent[-1][4:]==(4,0),'Easy hunt action'
    p=snapshot();struct.pack_into('<H',p,10,17|0x3FC0);m.receive(p);m.draw(args.output/'mission.png')
    m.click(50,114);assert m.r(s+4)==2;m.draw(args.output/'rewards.png');assert len(m.items)==18
    m.invoke(m.c['move'],0,(m.obj,222,190));m.draw(args.output/'tooltip.png');assert m.contains('Client item name')
    m.owner=0;m.draw();assert not m.contains('Quantity:');m.owner=m.obj
    m.mouse(222,190,3);assert not m.descriptions,'unpaired right release'
    m.mouse(222,190,2);m.mouse(222,190,3);assert m.descriptions==[501]
    m.mouse(222,190,2);m.receive(snapshot());m.mouse(222,190,3);assert m.descriptions==[501]
    m.now+=1500;m.click(230,240);m.click(670,502);assert m.sent[-1][4:]==(14,1)
    m.now+=1500;claimed=snapshot();struct.pack_into('<I',claimed,3536+4,3)
    m.receive(claimed);m.click(230,380);n=len(m.sent);m.click(670,502);assert len(m.sent)==n,'locked premium claim'
    m.click(706,150);assert m.sent[-1][4:]==(20,1)
    m.click(50,144);m.draw(args.output/'stats.png');assert m.plain_calls==['DevSeara','DevSeara']
    old=bytes(m.u.mem_read(b,4384));bad=snapshot();struct.pack_into('<H',bad,8,6);m.receive(bad)
    assert bytes(m.u.mem_read(b,4384))==old,'malformed protocol mutated board'
    m.click(905,10);assert m.r(m.obj+0x28)==0 and m.r(s+3020)==1
    print('PASS BPUI v5: real receiver/draw/input/ABI, daily+weekly, both tracks, tooltip ownership, paired right click, claims/paging, duplicate/stale/locked guards, close; offline layout images')
    tier_headers(args.exe,args.output)

if __name__=='__main__':main()
