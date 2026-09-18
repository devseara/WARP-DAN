"""Execute emitted VIP x86, with explicit native/OS boundaries. Offline, not live acceptance."""
import argparse,json
from pathlib import Path
import struct
from PIL import Image, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_modern_chat_ui import Machine,pack
from test_gacha_ui import GachaMachine
from vip_design_contract import X,Y

FIELDS=('api state open receive hit draw down up move drag cursor destroy timer quest_state quest_open receiver fit plain png ctor send fallback').split()
ROOT=Path(__file__).resolve().parents[1]

def benefit_draws(machine):
    return [row for row in machine.texts if X(735)<=row[1]<X(1344) and Y(838)<=row[2]<Y(1043)]
def contract(m):
    data=m.pe.get_memory_mapped_image();marker=data.find(b'VipUI.v4\0');assert marker>=0
    pointer=pack(m.base+marker);positions=[];offset=0
    while (offset:=data.find(pointer,offset))>=0:positions.append(m.base+offset);offset+=1
    assert len(positions)==1
    return {key:m.r(positions[0]+4+4*i) for i,key in enumerate(FIELDS)}

def snapshot(flags=1|2|4|8,token=77,level=2):
    p=bytearray(2664)
    struct.pack_into('<HHIHHIII',p,0,0xA1C,len(p),0x55504956,4,flags,token,level,65)
    def text(off,size,value):p[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
    for off,size,value in [(24,24,'DevSeara'),(48,32,'09-17-2026 Thursday'),(80,32,'09-18-2026 Friday'),
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
    for i,(days,cost) in enumerate(((1,500000),(3,1200000),(7,2500000),(15,5000000),(30,9000000))):
        struct.pack_into('<II',p,2524+i*8,days*1440,cost)
    text(2568,96,'Receive +7 all stats for 30 minutes?')
    return p

class VipMachine(Machine):
    def stub(self,address,fn):
        if address in self.boundaries:self.u.hook_del(self.boundaries[address])
        self.boundaries[address]=self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:fn(),begin=address,end=address)
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    def measure(self):
        ptr,length,style,height,bold,extra=self.args(6);value=self.cstr(ptr)
        font=ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf',height)
        self.ret(24,int(font.getlength(value[:length] if length else value)))
    plain_boundaries=GachaMachine.plain_boundaries
    def __init__(self,exe):
        self.boundaries={};self.text_colors=[]
        super().__init__(exe,ROOT/'Assets/VipUI');self.c=contract(self)
        meta=json.loads((ROOT/'Inputs/VipUI/runtime.json').read_text())
        self.c['interaction']=self.c['api']-meta['exports']['VipApi']+meta['exports']['VipInteraction']
        self.now=1000;self.sent=[];self.timer_calls=[];self.stock=[]
        self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
        self.plain_boundaries()
        # Model the private name helper's compact 10px font selection.
        def select_plain_font():
            _,height,_,_=self.args(4)
            self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',height)
            self.ret(16)
        self.stub(0x546F60,select_plain_font)
        self.stub(0xA21C90,self.measure)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x86B950,lambda:self.ret(4))
        # Execute real native add/raise/list operations, not a z-order stub.
        self.window_head=self.alloc(12)
        self.w(self.window_head,self.window_head);self.w(self.window_head+4,self.window_head)
        self.w(0x131F4E8+0x17C,self.window_head);self.w(0x131F4E8+0x180,0)
        self.stub(0xDBBC7F,lambda:self.ret(0)) # allocator delete boundary only
        # The ordinary game window registry is not constructed in this fixture.
        # Keep the actual raise/list code; model only its four stock-modal lookups.
        self.blocking_windows={}
        def window_lookup():
            kind=self.args(1)[0];assert kind in (0x116,4,0xC7,0xC8)
            self.ret(4,self.blocking_windows.get(kind,0))
        self.stub(0xA47B90,window_lookup)
        self.stub(0x86E240,lambda:self.ret(4))
        self.stub(0xA4B750,self.capture)
        self.stub(0x880AD0,lambda:self.forward('drag-down',2))
        self.stub(0x880BB0,lambda:self.forward('drag-up',2))
        self.stub(0x880E00,lambda:self.forward('drag-move',2))
        self.stub(0xA23470,lambda:self.ret(8))
        self.stub(0xA75340,lambda:self.ret(0,0)) # No live world in ordinary layout tests.
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
            args=self.args(4);assert args==[0,0,100,self.c['timer']]
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
    def window_order(self):
        order=[];node=self.r(self.window_head);previous=self.window_head
        while node!=self.window_head:
            assert len(order)<100 and self.r(node+4)==previous,'Invalid native window list'
            order.append(self.r(node+8));previous=node;node=self.r(node)
        assert self.r(self.window_head+4)==previous and len(order)==self.r(0x131F4E8+0x180)
        assert len(set(order))==len(order),'Duplicate registered root'
        return order
    def capture(self):self.w(0x131F4E8+0x19C,self.args(1)[0]);self.ret(4)
    def send(self):
        size,ptr=self.args(2);assert size==24
        data=bytes(self.u.mem_read(ptr,size));assert struct.unpack_from('<HHIHH',data)==(0xBFA,24,0x55504956,4,struct.unpack_from('<H',data,10)[0])
        self.sent.append(data);self.ret(8)
    def receive(self,p):
        self.u.mem_write(0x15E8198,bytes(p))
        entry=0xCAA2E0+(0xA1C-0x73)*4
        assert self.r(entry)==self.c['receiver']
        self.invoke(self.r(entry),0)
    def ready(self,p=None):
        self.receive(p if p is not None else snapshot())
        obj=self.r(self.c['state']);assert obj and self.r(obj+0x28)==1
        assert (self.r(obj+0x14),self.r(obj+0x18))==(460,362)
        self.now=(self.now+350)&0xFFFFFFFF # Ordinary fixtures start after the server gate.
        return obj
    def click(self,obj,x,y):
        self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
        # Ordinary behavior suites allow the short safe-send queue to settle.
        # Race-specific tests use raw down/up and control every clock/response.
        if self.r(self.c['interaction'])==1 and not self.r(self.c['interaction']+216):
            self.advance(350)
    def advance(self,ms):
        self.now=(self.now+ms)&0xFFFFFFFF
        timer=self.r(self.c['state']+2696)
        if timer:self.invoke(self.c['timer'],0,(0,0,timer,self.now))
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
    assert [row[0] for row in benefit_draws(m)]==['EXP +15%','Drop +15%','Max weight +600','Auto drop -75%']
    assert any(row[0]=='09-17-2026 Thursday' for row in m.texts)
    assert any(row[0]=='09-18-2026 Friday' for row in m.texts)
    assert m.r(m.r(obj)+20*4)==c['draw'] and m.r(m.r(obj)+31*4)==c['up']
    before=len(m.sent);m.click(obj,353,127);assert len(m.sent)==before,'disabled shop sent a request'
    for i in range(7):m.click(obj,443,333)
    assert m.r(s+20)==0 and len(m.sent)==before,'No inactive tier scrolling'
    m.ready(snapshot(level=10))
    m.preview(obj,args.output/'vip-high-tiers.png')
    assert [row[0] for row in benefit_draws(m)]==['EXP +100%','Drop +30%','ATK/MATK +25','HP +150']
    m.ready(snapshot())
    for i in range(7):m.click(obj,443,270)
    assert m.r(s+20)==0
    m.now+=3000;m.invoke(c['timer'],0,(0,0,567,m.now));assert len(m.sent)==before+1 and struct.unpack_from('<H',m.sent[-1],10)[0]==0
    m.invoke(c['down'],obj,(217,127));m.invoke(c['up'],obj,(290,50));assert len(m.sent)==before+1
    assert m.r(0x131F4E8+0x19C)==0,'outside release stranded capture'
    m.click(obj,217,127);assert len(m.sent)==before+1,'Active VIP applied membership again'
    m.ready(snapshot(flags=2|4,level=0))
    count=len(m.sent);m.click(obj,217,127);assert len(m.sent)==count and m.r(c['quest_state']+16)==3
    q=m.r(c['quest_state']);m.click(q,200,300);m.click(obj,447,10)
    assert struct.unpack_from('<HHIHHIII',m.sent[-1])==(0xBFA,24,0x55504956,4,6,77,0,0)
    assert m.r(s+16)==1 and m.r(obj+0x28)==0 and m.timer_calls[-1]=='stop'
    before=len(m.sent);m.invoke(c['timer'],0,(0,0,567,m.now));assert len(m.sent)==before
    m.receive(snapshot(flags=1|4|8));assert m.r(obj+0x28)==0,'late refresh reopened hidden UI'
    for field,value in [(8,1),(2,20),(16,11),(20,101)]:
        bad=snapshot();struct.pack_into('<H' if field<12 else '<I',bad,field,value);m.receive(bad);assert m.r(obj+0x28)==0
    foreign=snapshot();foreign[4:8]=b'NOPE';m.receive(foreign);assert len(m.stock)==1
    m.ready(snapshot(flags=2|4,level=0));m.preview(obj,args.output/'vip-inactive.png')
    before=len(m.sent);m.click(obj,196,259);m.click(obj,353,152);assert len(m.sent)==before,'inactive upgrade/buff request'
    # Drag release and close do not steal capture owned by another window.
    m.invoke(c['down'],obj,(50,8));assert m.r(s+12)==1
    m.invoke(c['drag'],obj,(70,8));m.invoke(c['up'],obj,(70,8));assert m.r(s+12)==0
    m.w(0x131F4E8+0x19C,0x20101010);m.invoke(c['destroy'],obj,(1,));assert m.r(0x131F4E8+0x19C)==0x20101010
    assert not m.r(s) and not m.r(s+24) and m.timer_calls[-1]=='stop'
    m.w(0x131F4E8+0x19C,0);obj=m.ready(snapshot(token=91,flags=1|2|4|8|16))
    m.click(obj,353,127);assert struct.unpack_from('<HI',m.sent[-1],10)==(2,91)
    obj=m.ready(snapshot(token=93));m.click(obj,447,10);assert struct.unpack_from('<H',m.sent[-1],10)[0]==6
    assert not m.r(obj+0x28)
    # Read back real emitted pixels: approved blue until full EXP, gold only when the
    # server allows upgrading. A refresh must remove gold after upgrading.
    def exp_bar(percent,flags=1|2|4|8,level=2,filename=None):
        p=snapshot(flags=flags,level=level);struct.pack_into('<I',p,20,percent)
        p[112:176]=f'{percent*5000:,} / 500,000 EXP'.encode().ljust(64,b'\0')
        obj=m.ready(p)
        if filename:m.preview(obj,args.output/filename)
        else:m.invoke(c['draw'],obj)
        pix,w,h=m.pixels(obj)
        return tuple(m.r(pix+((Y(653)+y)*w+X(180)+x)*4) for y in range(Y(681)-Y(653)) for x in range(X(1050)))
    track=exp_bar(0)
    green=exp_bar(99,filename='vip-exp-blue.png')
    gold=exp_bar(100,filename='vip-exp-gold.png')
    filled=X(1050)*99//100
    assert green[filled:X(1050)]==track[filled:X(1050)] and green[:filled]!=track[:filled]
    for ordinary,ready in zip(green[:filled],gold[:filled]):
        assert ordinary&255 >= (ordinary>>16)&255,'Below full EXP must remain blue'
        assert (ready>>16)&255 > (ready>>8)&255 > ready&255,'Full authorized EXP must be gold'
    assert gold!=exp_bar(100,flags=1|2|4),'No upgrade permission must not look ready'
    assert gold==exp_bar(100,flags=1|2|4|8|32),'Saved upgrade quest keeps the EXP ready state'
    assert gold!=exp_bar(100,flags=1|2|4,level=10),'Maximum level is not another upgrade'
    assert exp_bar(0,level=3)==track and exp_bar(99,level=3)==green,'Gold leaked into the next level'
    print('PASS: VIP native x86 ABI, real PNGs/private name text, separate current-tier effects, bounded scroll arrows, independent dispatcher/stock fallback, malformed envelopes, session tokens, disabled actions, safe capture/drag, late replies, timer lifecycle, close/destroy/reopen. Offline previews saved; live acceptance pending.')

if __name__=='__main__':main()
