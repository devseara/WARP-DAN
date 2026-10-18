"""Execute emitted BarterUI x86 and native packet routing at read-only boundaries.

Uses original PNGs to render evidence; never connects to a server or trades items.
"""
import argparse
from io import BytesIO
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS)
from test_modern_chat_ui import Machine, pack, over
from test_gacha_ui import GachaMachine

FIELDS='api state receive result hit draw down up move drag cursor destroy rightdown rightup wheel owned contact metadata normalroute expandedroute resultroute'.split()
ROOT=Path(__file__).resolve().parents[1]
GAME=Path(r'D:/AAARAGNAROK/Banquet of Heroes/Eitr Origin')
TEXTURES=GAME/'data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º'
NAMES={504:'White Potion',505:'Blue Potion',509:'White Herb',510:'Blue Herb',713:'Empty Bottle',909:'Jellopy',984:'Oridecon',985:'Elunium',756:'Rough Oridecon',757:'Rough Elunium'}

def contract(m):
    b=m.pe.get_memory_mapped_image();marker=b.find(b'BarterUI.v5\0');assert marker>=0
    record=b.find(pack(m.base+marker));assert record>=0
    return {name:m.r(m.base+record+4+i*4) for i,name in enumerate(FIELDS)}

def normal(items=None):
    items=items if items is not None else [(504,100,509,2,7),(505,0xffffffff,510,3,8),(984,0,756,5,9),(985,50,757,5,10),(909,3,713,1,11)]
    body=b''.join(struct.pack('<IBIIIIIHI',id,0,stock,currency,amount,10,index,0,0) for id,stock,currency,amount,index in items)
    return struct.pack('<HH',0xb78,4+len(body))+body

def expanded(count=6,materials=2,stock=100):
    rows=[]
    for i in range(count):
        req=[(509,0,2,0),(713,0,1,0),(909,0,4,0),(510,3,5,0),(756,0,5,0),(757,0,9,0)]
        body=b''.join(struct.pack('<IH I H',*req[j%len(req)]) for j in range(materials))
        rows.append(struct.pack('<I H I I I I H I I I',list(NAMES)[i] if i<len(NAMES) else 1000+i,0,stock,10,20+i,1200*(i+1),0,0,materials,i%3)+body)
    p=bytearray(struct.pack('<HHI',0xb79,8+sum(map(len,rows)),count)+b''.join(rows))
    return p

class BarterMachine(Machine):
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    def __init__(self,exe,assets):
        self.text_colors=[];super().__init__(exe,assets);self.c=contract(self)
        self.now=1000;self.sent=[];self.stock=[];self.described=[];self.key_codes=set();self.missing=set();self.png_calls=[];self.real_icons={}
        self.stub(0xA21C90,self.measure)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x86B950,lambda:self.ret(4));self.stub(0x86E240,lambda:self.ret(4))
        self.head=self.alloc(12);self.w(self.head,self.head);self.w(self.head+4,self.head)
        self.w(0x131F4E8+0x17c,self.head);self.w(0x131F4E8+0x180,0)
        self.stub(0xDBBC7F,lambda:self.ret(0));self.stub(0xA47B90,lambda:self.ret(4,0))
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19c,self.args(1)[0]),self.ret(4)))
        for addr,label in [(0x880AD0,'dragdown'),(0x880BB0,'dragup'),(0x880E00,'dragmove')]:self.stub(addr,lambda label=label:self.forward(label,2))
        self.stub(0xA23470,lambda:self.ret(8));self.stub(0xA764A0,lambda:self.ret(4));self.w(0x121333C,self.alloc(64))
        self.stub(0xC9E1DD,lambda:self.ret(0))
        for addr in (0xCA14EC,0xCA14FD,0xCA10EC):self.stub(addr,lambda addr=addr:(self.stock.append(addr),self.ret(0)))
        api=self.c['api'];self.stub(self.r(api+8),lambda:self.ret(0,0x20200000));self.stub(self.r(api+12),self.send)
        self.stub(self.r(api+20),self.icon)
        self.stub(self.r(api+24),lambda:(self.described.append(self.args(1)[0]),self.ret(4)))
        self.stub(self.r(api+28),self.name)
        # Observe the PNG helper without replacing its emitted alpha compositor.
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:self.png_calls.append(tuple(self.args(4))),begin=self.r(api+32),end=self.r(api+32))
        keys=self.alloc(16);self.stub(keys,lambda:self.ret(4,0x8000 if self.args(1)[0] in self.key_codes else 0));self.w(self.r(api+36),keys)
        clock=self.alloc(16);self.stub(clock,lambda:self.ret(0,self.now));self.w(0xFC17B0,clock)
        self.inventory([(509,40,0),(509,10,0),(510,10,3),(713,90,0),(909,200,0),(756,5,0),(757,4,0)])
        self.game=self.alloc(0x400);self.npc_names({})
        self.load_icons()
    def npc_names(self,names):
        head=self.alloc(0xB0);self.u.mem_write(head+0xD,b'\1');self.w(self.game+0x164,head)
        def tree(rows):
            if not rows:return head
            middle=len(rows)//2;id,name=rows[middle];node=self.alloc(0xB0)
            self.w(node,tree(rows[:middle]));self.w(node+8,tree(rows[middle+1:]));self.w(node+0x10,id)
            data=name.encode('cp1252');ptr=node+0x18
            if len(data)>=16:ptr=self.alloc(len(data)+1);self.w(node+0x18,ptr)
            self.u.mem_write(ptr,data+b'\0');self.w(node+0x28,len(data));self.w(node+0x2C,max(15,len(data)))
            self.u.mem_write(node+0xAC,b'\1');return node
        self.w(head+4,tree(sorted(names.items())))
    def native_context(self,address,registers,end=None):
        # Exercise actual installed bridges with dispatcher/click registers.
        saved={UC_X86_REG_EBX:0xBBBBBBBB,UC_X86_REG_ESI:0xEEEEEEEE,
               UC_X86_REG_EDI:self.game,UC_X86_REG_EBP:0xABABABAB,
               UC_X86_REG_ECX:0xCCCCCCCC,UC_X86_REG_EDX:0xDDDDDDDD}
        saved.update(registers);sp=0x3000F000;self.u.mem_write(sp,pack(self.stop))
        for reg,value in saved.items():self.u.reg_write(reg,value)
        self.u.reg_write(UC_X86_REG_ESP,sp);self.u.reg_write(UC_X86_REG_EFLAGS,0x246)
        self.u.emu_start(address,end or self.stop,count=60000000)
        assert self.u.reg_read(UC_X86_REG_EIP)==(end or self.stop)
        assert self.u.reg_read(UC_X86_REG_ESP)==sp+(0 if end else 4)
        for reg,value in saved.items():assert self.u.reg_read(reg)==value,(hex(address),reg,'register changed')
        assert self.u.reg_read(UC_X86_REG_EFLAGS)==0x246,'flags changed'
    def contact(self,id,action=False):
        pointer=self.alloc(12);self.w(pointer,id)
        site,reg=(0xC8BF2E,UC_X86_REG_EDX) if action else (0xC789B2,UC_X86_REG_EBX)
        self.native_context(site,{reg:pointer},site+5)
        assert self.u.reg_read(UC_X86_REG_EAX)==0x90,'original packet opcode was not replayed'
    def inventory(self,items):
        head=self.alloc(12);previous=head
        for id,amount,refine in items:
            node=self.alloc(0x110);self.w(previous,node);self.w(node+4,previous);self.w(node+8+0x10,amount);self.w(node+8+0x60,refine)
            value=str(id).encode();self.u.mem_write(node+8+0x2c,value+b'\0');self.w(node+8+0x3c,len(value));self.w(node+8+0x40,15);previous=node
        self.w(previous,head);self.w(head+4,previous)
        self.w(0x15FA3C0+0x16f0,head);self.w(0x15FA3C0+0x16f4,len(items))
    def load_icons(self):
        import re
        from dual_weapon_formats.grf_reader import GrfFile
        data=(GAME/'SystemEN/itemInfo_iro.lua').read_bytes()
        grf=GrfFile(GAME/'update.grf')
        try:
            for id in NAMES:
                m=re.search(rb'\['+str(id).encode()+rb'\]\s*=\s*\{(.*?)(?=\r?\n\s*\[\d+\])',data,re.S)
                if not m:continue
                resource=re.search(rb'(?<!un)identifiedResourceName\s*=\s*"([^"]*)"',m[1])
                if not resource:continue
                key='data/texture/유저인터페이스/item/'+resource[1].decode('cp949').lower()+'.bmp'
                try:self.real_icons[id]=Image.open(BytesIO(grf.read(key))).convert('RGBA')
                except KeyError:pass
        finally:grf.close()
    def name(self):
        value=NAMES.get(self.args(1)[0],'Example item '+str(self.args(1)[0])).encode()+b'\0';ptr=self.alloc(len(value));self.u.mem_write(ptr,value);self.ret(4,ptr)
    def load_texture(self,name):
        if name in self.missing:return 0
        old=self.assets;self.assets=old/('genericsui' if name.startswith(('buy_','cancel_')) else 'barter')
        try:return super().load_texture(name)
        finally:self.assets=old
    def measure(self):
        ptr,length,_,height,bold,_=self.args(6);font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',height)
        self.ret(24,int(font.getlength(self.cstr(ptr)[:length])))
    def icon(self):
        obj,id,x,y=self.args(4);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
        if id in self.real_icons:
            icon=self.real_icons[id].copy();px=icon.load()
            for yy in range(icon.height):
                for xx in range(icon.width):
                    if px[xx,yy][:3]==(255,0,255):px[xx,yy]=(0,0,0,0)
            im.alpha_composite(icon,(x+(32-icon.width)//2,y+(32-icon.height)//2))
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(16)
    def send(self):
        length,ptr=self.args(2);self.sent.append(bytes(self.u.mem_read(ptr,length)));self.ret(8)
    def receive(self,p):
        self.u.mem_write(0x15E8198,bytes(p));op=struct.unpack_from('<H',p)[0]
        self.native_context(self.r(0xCAA2E0+(op-0x73)*4),{})
    def click(self,x,y):
        obj=self.r(self.c['state']);self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def preview(self,path=None):
        self.texts=[];self.text_colors=[];self.png_calls=[];obj=self.r(self.c['state']);self.invoke(self.c['draw'],obj);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB')
        if path:im.save(path)
        return im
    def move(self,x,y):self.invoke(self.c['move'],self.r(self.c['state']),(x,y))
    def state(self,offset):return self.r(self.c['state']+offset)
    def native_owned(self,id,refine=0):
        self.invoke(self.c['owned'],0,(id,refine));return self.u.reg_read(UC_X86_REG_EAX)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe',type=Path);ap.add_argument('--assets',type=Path,default=TEXTURES);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=BarterMachine(args.exe,args.assets);c=m.c;s=c['state'];cart=s+5676
    m.npc_names({100:'Ashra#1',200:'Another Merchant#equipment',300:'A very long NPC name '*6})
    m.w(m.game+0x2DC,100) # Native mes / next / close2 retain this source NPC.
    m.receive(normal());m.preview(args.output/'npc-ashra.png');assert m.texts[0][0]=='Ashra'
    m.receive(expanded());m.preview();assert m.texts[0][0]=='Ashra'
    m.contact(200);m.receive(normal());m.preview();assert m.texts[0][0]=='Another Merchant'
    m.receive(expanded());m.preview();assert m.texts[0][0]=='Another Merchant','catalog refresh lost direct NPC'
    m.contact(300,action=True);m.receive(expanded());m.preview(args.output/'npc-long-name.png')
    assert m.texts[0][0].startswith('A very long NPC name') and len(m.texts[0][0])<120,'long name should fit before X'
    m.contact(200);m.w(m.game+0x2DC,300);m.receive(normal());m.preview()
    assert m.texts[0][0].startswith('A very long NPC name'),'new server dialogue must supersede contact'
    m.contact(999);m.receive(normal());m.preview();assert m.texts[0][0]=='Barter','missing name leaked previous title'
    m.click(530,360);m.w(m.game+0x2DC,0);m.receive(normal());m.preview();assert m.texts[0][0]=='Barter'
    m.npc_names({100:'Ashra'});m.w(m.game+0x2DC,100);m.receive(normal())
    m.npc_names({100:'Renamed NPC'});m.preview();assert m.texts[0][0]=='Ashra','draw should use copied title'
    m.click(530,360);m.receive(normal());m.preview();assert m.texts[0][0]=='Renamed NPC'
    # Distinct NPC IDs keep their identity while sharing the same visible title.
    cases=[('Ashra#1','Ashra'),('Ashra#2','Ashra'),('Ashra#3','Ashra'),
           ('Ashra#usables#extra','Ashra'),('Ashra#','Ashra'),('#internal','Barter'),('Ashra','Ashra')]
    m.npc_names({400+i:name for i,(name,_) in enumerate(cases)})
    for i,(name,expected) in enumerate(cases):
        m.contact(400+i,action=bool(i%2));m.receive(expanded() if i%2 else normal());m.preview()
        assert m.texts[0][0]==expected,(name,m.texts[0][0])
    m.click(530,360);m.npc_names({});m.w(m.game+0x2DC,0);m.sent.clear();m.stock.clear()
    print('PASS: NPC titles for both catalogs, close2 context, both native contact hooks, refresh, inline/heap names, # suffix removal, clipping, missing-name fallback and cached rendering',flush=True)
    m.w(0x15FBA90,1250000)
    def setscroll(left=0,right=0):m.w(s+16,left);m.w(s+24,right)
    def wheel(x,y,delta):m.move(x,y);m.invoke(c['wheel'],m.r(s),(delta,))
    def drag(x,y,to):m.invoke(c['down'],m.r(s),(x,y));m.invoke(c['drag'],m.r(s),(x,to));m.invoke(c['up'],m.r(s),(x,to))
    assert m.native_owned(509)==50 and m.native_owned(510,3)==10 and m.native_owned(510,4)==0 and not m.native_owned(123456)
    m.receive(normal());assert m.state(4)==1 and m.state(8)==0xb78 and m.state(12)==5 and not m.stock and not m.sent
    m.preview(args.output/'normal-empty.png');assert (464,351,m.textures['buy_off.png'],0) in m.png_calls
    assert (47,141,m.textures['itembox_00.png'],0) in m.png_calls
    assert any(t[:3]==('Not enough materials',228,323) for t in m.texts),'shortage text must remain above the bottom border'
    m.click(88,55);assert m.state(28)==1
    m.click(585,184);m.click(585,184);assert m.r(cart+4)==3
    m.move(480,360);m.preview(args.output/'normal-selected-hover.png');assert (464,351,m.textures['buy_over.png'],0) in m.png_calls
    m.invoke(c['down'],m.r(s),(480,360));m.preview(args.output/'normal-buy-pressed.png');assert (464,351,m.textures['buy_press.png'],0) in m.png_calls
    m.invoke(c['up'],m.r(s),(400,390));assert not m.sent,'release outside purchased'
    m.click(480,360);assert m.state(32)==1 and m.sent[-1]==struct.pack('<HHIIHI',0xb0f,18,504,3,0,7)
    n=len(m.sent);m.click(480,360);m.click(270,55);m.click(585,184);assert len(m.sent)==n and m.state(28)==1
    m.preview(args.output/'normal-pending.png');assert (464,351,m.textures['buy_off.png'],0) in m.png_calls
    m.receive(struct.pack('<HB',0xca,1));assert not m.state(32) and m.state(28)==1 and m.stock[-1]==0xca10ec
    m.click(480,360);m.receive(struct.pack('<HB',0xca,0));assert not m.state(28) and not m.state(32)
    m.preview(args.output/'normal-success.png');assert any(t[0]=='Stock: 97' for t in m.texts)
    wheel(200,200,-120);assert m.state(16)>0
    drag(402,100,362);assert m.state(16)>=120
    m.preview(args.output/'normal-scroll-bottom.png');assert any(t[0]=='Jellopy' for t in m.texts)
    m.move(530,360);m.preview(args.output/'cancel-hover.png');assert (516,351,m.textures['cancel_over.png'],0) in m.png_calls
    m.click(530,360);assert m.sent[-1]==struct.pack('<H',0xb12) and not m.state(4)
    print('PASS: normal purchase/close packets, stock updates, catalog wheel/drag scrolling, exact Buy/Cancel states and double-click guard',flush=True)

    # Ten requirements have two complete rows, every label below its icon.
    m.receive(expanded(materials=10));m.click(86,55);m.key_codes={16};m.click(585,228);m.key_codes.clear();assert m.r(cart+4)==11
    m.move(0,0);full=m.preview(args.output/'expanded-ten-required.png')
    assert (47,185,m.textures['itembox_00.png'],0) in m.png_calls
    assert (431,247,m.textures['itembox_00.png'],0) in m.png_calls
    assert any(t[:3]==('Not enough materials',49,205) for t in m.texts)
    for y in (155,199):assert len([t for t in m.texts if t[1]>=428 and t[2]==y])==5,(y,m.texts)
    m.move(430,128);m.preview(args.output/'expanded-tooltip.png');assert any(t[0]=='Required: 22' for t in m.texts) and any(t[0]=='In inventory: 50' for t in m.texts)
    m.invoke(c['rightdown'],m.r(s),(430,128));m.invoke(c['rightup'],m.r(s),(430,128));assert m.described[-1]==509
    m.click(272,55);assert m.state(28)==2 and m.state(24)>0
    setscroll();m.move(0,0);top=m.preview(args.output/'expanded-two-selected-top.png')
    assert len([t for t in m.texts if t[0].startswith('Receive x')])==2
    wheel(500,180,-120);assert m.state(24)==44
    m.preview(args.output/'expanded-partial-scroll.png')
    drag(610,110,300);assert m.state(24)>100
    bottom=m.preview(args.output/'expanded-two-selected-bottom.png')
    # The header, total, actions and footer must survive pane clipping/staging.
    assert top.crop((410,20,619,55)).tobytes()==bottom.crop((410,20,619,55)).tobytes()
    assert top.crop((410,320,619,380)).tobytes()==bottom.crop((410,320,619,380)).tobytes()
    setscroll();m.click(480,360);assert m.sent[-1]==struct.pack('<HH6I',0xb57,28,504,20,11,505,21,1)
    m.receive(struct.pack('<HB',0xca,0));m.click(530,360);assert m.sent[-1]==struct.pack('<H',0xb58)
    print('PASS: 2x5 required-item layout, all ten counts below icons, multi-entry wheel/drag scroll, clipped native draws, fixed footer and complete purchase',flush=True)

    # One row for five, two for six, with quantity hit boxes following the card.
    for count,height in [(1,173),(5,173),(6,217),(10,217),(13,261)]:
        m.receive(expanded(count=2,materials=count));m.click(80,50);setscroll();m.click(585,55+height-45);assert m.r(cart+4)==2
        if count in (5,6):m.move(0,0);m.preview(args.output/f'adaptive-{count}-requirements.png')
    m.receive(expanded(count=3,materials=2));m.click(80,50);m.click(260,50);m.click(80,200);assert m.state(28)==3
    setscroll();m.click(527,183);assert m.state(28)==2 and m.r(cart)==1
    m.preview();wheel(500,180,120);assert m.state(24)==0
    print('PASS: adaptive 1x5/2x5 sizing at five/six boundary, all 13 malformed-server requirements retained, per-entry quantity and removal',flush=True)

    m.receive(expanded(count=0,materials=0));assert not m.state(12) and not m.state(28)
    m.receive(expanded(count=1001,materials=0));assert m.state(12)==1001
    drag(402,100,362);m.preview(args.output/'large-catalog-last-row.png');assert any(t[0].endswith('Example item 2000') for t in m.texts)
    before=bytes(m.u.mem_read(s,47564));old=len(m.stock)
    for p in [b'\x79\x0b\x07\x00'+b'\0'*4,struct.pack('<HHI',0xb79,8,0xffffffff),normal()[:-1],expanded()[:-2]]:
        p=bytearray(p)
        if len(p)>8:struct.pack_into('<H',p,2,len(p))
        m.receive(p);assert bytes(m.u.mem_read(s,47564))==before,'malformed input partly replaced shop'
    assert len(m.stock)==old+4
    for missing in ('buy_press.png','item_sell_bg.png','itembox_00.png'):
        m.missing={missing};m.receive(normal());assert m.stock[-1]==0xca14ec and not m.state(4);m.missing.clear()
    m.receive(normal());assert m.state(4)
    print('PASS: 1,001-recipe scrolling, empty catalog, malformed packets and missing-art stock fallback',flush=True)

    p=expanded(count=2,materials=1,stock=3);struct.pack_into('<I',p,8+36+12,504)
    m.receive(p);m.click(80,55);m.click(265,55);assert m.state(28)==1
    m.key_codes={17};m.click(585,184);m.key_codes.clear();assert m.r(cart+4)==3
    p=expanded(count=1,materials=1);struct.pack_into('<I',p,8+18,0x7fffffff)
    m.receive(p);m.click(80,55);m.click(585,184);n=len(m.sent);m.click(480,360);assert len(m.sent)==n
    p=expanded(count=1,materials=1);struct.pack_into('<I',p,8+36+6,0x7fffffff)
    m.receive(p);m.click(80,55);m.click(585,184);m.click(480,360);assert len(m.sent)==n
    m.receive(normal());m.click(80,55);m.key_codes={27};m.invoke(c['cursor'],m.r(s),(60,60));m.key_codes.clear();assert not m.state(4) and m.sent[-1]==struct.pack('<H',0xb12)
    m.receive(expanded());m.click(80,55);m.invoke(c['down'],m.r(s),(480,360));m.receive(normal());n=len(m.sent);m.invoke(c['up'],m.r(s),(480,360));assert len(m.sent)==n
    m.invoke(c['destroy'],m.r(s),(1,));assert not m.r(s) and not m.state(4) and len(m.sent)==n
    m.receive(struct.pack('<HB',0xca,0));assert not m.r(s)
    print('PASS: overflow/duplicate/stock guards, Escape, stale clicks/results, destruction, x86 stack and callee-saved registers',flush=True)
    print('Live in-game acceptance remains required; no trades were sent to a server.',flush=True)

if __name__=='__main__':main()
