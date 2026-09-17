"""Execute emitted VIP x86, with explicit native/OS boundaries. Offline, not live acceptance."""
import argparse
from pathlib import Path
import struct
from PIL import Image, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_modern_chat_ui import Machine,pack
from test_gacha_ui import GachaMachine

FIELDS=('api state open receive hit draw down up move drag cursor destroy timer quest_state quest_open receiver fit plain png ctor send fallback').split()
ROOT=Path(__file__).resolve().parents[1]

def contract(m):
    data=m.pe.get_memory_mapped_image();marker=data.find(b'VipUI.v2\0');assert marker>=0
    pointer=pack(m.base+marker);positions=[];offset=0
    while (offset:=data.find(pointer,offset))>=0:positions.append(m.base+offset);offset+=1
    assert len(positions)==1
    return {key:m.r(positions[0]+4+4*i) for i,key in enumerate(FIELDS)}

def snapshot(flags=1|2|4|8,token=77,level=2):
    p=bytearray(2524)
    struct.pack_into('<HHIHHIII',p,0,0xA1C,len(p),0x55504956,2,flags,token,level,65)
    def text(off,size,value):p[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
    for off,size,value in [(24,24,'DevSeara'),(48,32,'2026-09-17 12:00'),(80,32,'2026-09-24 12:00'),
        (112,64,'325,000 / 500,000 EXP'),(176,96,'Membership active. Bonuses require active VIP.'),
        (272,64,'Next level: 7,000,000 Zeny'),(336,96,'Zeny: 157,004,940 | Account-wide VIP')]:text(off,size,value)
    first=['EXP +10% | Drop +10%','EXP +15% | Drop +15%','EXP +20% | Drop +20%',
           'EXP +25% | Drop +25%','EXP +30% | Drop +30%','EXP +20% | ATK/MATK +10',
           'EXP +30% | Drop +5% | ATK/MATK +15','EXP +30% | Drop +10% | ATK/MATK +15',
           'EXP +30% | Drop +20% | ATK/MATK +15','EXP +100% | Drop +30% | ATK/MATK +25']
    second=['Max weight +300','Max weight +600','Max weight +900','Max weight +1,200','Max weight +1,500',
            'HP +75 | SP +50 | Weight +600',
            'HP +100 | SP +75 | Weight +700','HP +100 | SP +75 | Weight +800',
            'HP +100 | SP +75 | Weight +900','HP +150 | SP +100 | Weight +1,000']
    for i in range(10):
        text(432+i*184,24,f'VIP LEVEL {i+1}'+(' (ACTIVE)' if i+1==level else ''))
        penalty=75 if i<5 else 75-(i-4)*5
        text(456+i*184,80,first[i]);text(536+i*184,80,second[i]+f' | Auto drop -{penalty}%')
    return p

class VipMachine(Machine):
    def stub(self,address,fn):
        if address in self.boundaries:self.u.hook_del(self.boundaries[address])
        self.boundaries[address]=self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:fn(),begin=address,end=address)
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    measure=GachaMachine.measure
    plain_boundaries=GachaMachine.plain_boundaries
    def __init__(self,exe):
        self.boundaries={};self.text_colors=[]
        super().__init__(exe,ROOT/'Assets/VipUI');self.c=contract(self)
        self.now=1000;self.sent=[];self.timer_calls=[];self.stock=[]
        self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
        self.plain_boundaries()
        self.stub(0xA21C90,self.measure)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x86B950,lambda:self.ret(4))
        self.stub(0xA2D240,lambda:self.ret(4))
        self.stub(0x86E240,lambda:self.ret(4))
        self.stub(0xA4B750,self.capture)
        self.stub(0x880AD0,lambda:self.forward('drag-down',2))
        self.stub(0x880BB0,lambda:self.forward('drag-up',2))
        self.stub(0x880E00,lambda:self.forward('drag-move',2))
        self.stub(0xA23470,lambda:self.ret(8))
        self.stub(0xA764A0,lambda:self.forward('cursor',1))
        self.w(0x121333C,self.alloc(64))
        self.stub(0xC9E1DD,lambda:self.ret(0))
        def fallback():self.stock.append(True);self.ret(0)
        self.stub(self.c['fallback'],fallback)
        self.stub(self.c['ctor'],lambda:self.ret(0,0x20100000))
        self.stub(self.c['send'],self.send)
        tick=self.alloc(16);self.stub(tick,lambda:self.ret(0,self.now));self.w(0xFC17B0,tick)
        timer_set=self.alloc(16);timer_kill=self.alloc(16)
        def start():
            args=self.args(4);assert args==[0,0,3000,self.c['timer']]
            self.timer_calls.append('start');self.ret(16,567)
        def stop():
            assert self.args(2)==[0,567];self.timer_calls.append('stop');self.ret(8,1)
        self.stub(timer_set,start);self.stub(timer_kill,stop)
        def module():assert self.cstr(self.args(1)[0])=='user32.dll';self.ret(4,123)
        def proc():
            mod,name=self.args(2);assert mod==123
            name=self.cstr(name);assert name in ('SetTimer','KillTimer')
            self.ret(8,timer_set if name=='SetTimer' else timer_kill)
        for off,fn in [(76,module),(80,proc)]:
            boundary=self.alloc(16);self.stub(boundary,fn);self.w(self.r(self.c['api']+off),boundary)
    def capture(self):self.w(0x131F4E8+0x19C,self.args(1)[0]);self.ret(4)
    def send(self):
        size,ptr=self.args(2);assert size==16
        data=bytes(self.u.mem_read(ptr,size));assert struct.unpack_from('<HHIHH',data)==(0xBFA,16,0x55504956,2,struct.unpack_from('<H',data,10)[0])
        self.sent.append(data);self.ret(8)
    def receive(self,p):
        self.u.mem_write(0x15E8198,bytes(p))
        entry=0xCAA2E0+(0xA1C-0x73)*4
        assert self.r(entry)==self.c['receiver']
        self.invoke(self.r(entry),0)
    def ready(self,p=None):
        self.receive(p if p is not None else snapshot())
        obj=self.r(self.c['state']);assert obj and self.r(obj+0x28)==1
        assert (self.r(obj+0x14),self.r(obj+0x18))==(736,420)
        return obj
    def click(self,obj,x,y):
        self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def preview(self,obj,path):
        self.texts=[];self.invoke(self.c['draw'],obj)
        pix,w,h=self.pixels(obj)
        Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB').save(path)
        assert self.r(self.r(obj+0x24)+0x28)&255==0,'PNG must not change opaque tile upload mode'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    m=VipMachine(args.exe);c=m.c;s=c['state'];obj=m.ready()
    assert m.timer_calls==['start']
    m.preview(obj,args.output/'vip-active.png')
    assert m.plain_calls==['DevSeara'] and m.gdi_color==0x123456
    assert any('VIP LEVEL 6' in row[0] for row in m.texts)
    assert m.r(m.r(obj)+20*4)==c['draw'] and m.r(m.r(obj)+31*4)==c['up']
    before=len(m.sent);m.click(obj,213,173);assert len(m.sent)==before,'disabled shop sent a request'
    for i in range(6):m.click(obj,716,380)
    assert m.r(s+20)==4 and len(m.sent)==before
    m.preview(obj,args.output/'vip-high-tiers.png')
    assert any('VIP LEVEL 10' in row[0] for row in m.texts)
    for i in range(6):m.click(obj,716,65)
    assert m.r(s+20)==0
    m.invoke(c['timer'],0,(0,0,567,m.now));assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==0
    m.invoke(c['down'],obj,(130,172));m.invoke(c['up'],obj,(290,50));assert len(m.sent)==before+1
    assert m.r(0x131F4E8+0x19C)==0,'outside release stranded capture'
    m.click(obj,135,172);assert struct.unpack_from('<HHIHHI',m.sent[-1])==(0xBFA,16,0x55504956,2,1,77)
    assert m.r(s+16)==1 and m.r(obj+0x28)==0 and m.timer_calls[-1]=='stop'
    before=len(m.sent);m.invoke(c['timer'],0,(0,0,567,m.now));assert len(m.sent)==before
    m.receive(snapshot(flags=1|4|8));assert m.r(obj+0x28)==0,'late refresh reopened hidden UI'
    for field,value in [(8,1),(2,20),(16,11),(20,101)]:
        bad=snapshot();struct.pack_into('<H' if field<12 else '<I',bad,field,value);m.receive(bad);assert m.r(obj+0x28)==0
    foreign=snapshot();foreign[4:8]=b'NOPE';m.receive(foreign);assert len(m.stock)==1
    m.ready(snapshot(flags=2|4,level=0));m.preview(obj,args.output/'vip-inactive.png')
    before=len(m.sent);m.click(obj,265,302);m.click(obj,240,202);assert len(m.sent)==before,'inactive upgrade/buff request'
    # Drag release and close do not steal capture owned by another window.
    m.invoke(c['down'],obj,(50,8));assert m.r(s+12)==1
    m.invoke(c['drag'],obj,(70,8));m.invoke(c['up'],obj,(70,8));assert m.r(s+12)==0
    m.w(0x131F4E8+0x19C,0x20101010);m.invoke(c['destroy'],obj,(1,));assert m.r(0x131F4E8+0x19C)==0x20101010
    assert not m.r(s) and not m.r(s+24) and m.timer_calls[-1]=='stop'
    m.w(0x131F4E8+0x19C,0);obj=m.ready(snapshot(token=91,flags=1|2|4|8|16))
    m.click(obj,205,172);assert struct.unpack_from('<HI',m.sent[-1],10)==(2,91)
    obj=m.ready(snapshot(token=93));m.click(obj,722,8);assert struct.unpack_from('<H',m.sent[-1],10)[0]==6
    assert not m.r(obj+0x28)
    print('PASS: VIP native x86 ABI, real PNGs/private name text, 10-tier bounded scrolling, independent dispatcher/stock fallback, malformed envelopes, session tokens, disabled actions, safe capture/drag, late replies, timer lifecycle, close/destroy/reopen. Offline previews saved; live acceptance pending.')

if __name__=='__main__':main()
