"""Execute emitted ShopUI x86 and native packet routing at read-only boundaries.

Uses original PNGs to render evidence; never connects to a server or trades items.
"""
import argparse
from io import BytesIO
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX
from test_modern_chat_ui import Machine, pack, over
from test_gacha_ui import GachaMachine

FIELDS='api state receive hit draw down up move drag cursor destroy rightdown rightup wheel inventory name resource identified buyroute sellroute'.split()
ROOT=Path(__file__).resolve().parents[1]
GAME=Path(r'D:/AAARAGNAROK/Banquet of Heroes/Eitr Origin')
TEXTURES=GAME/'data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º'
NAMES={611:'Magnifier',1750:'Arrow',501:'Red Potion',502:'Orange Potion',503:'Yellow Potion',506:'Green Potion',645:'Concentration Potion',656:'Awakening Potion',601:'Fly Wing',602:'Butterfly Wing',607:'Yggdrasil Berry',604:'Dead Branch',12214:'Bloody Branch',507:'Red Herb',504:'White Potion',505:'Blue Potion',509:'White Herb',510:'Blue Herb',713:'Empty Bottle',909:'Jellopy',984:'Oridecon',985:'Elunium',756:'Rough Oridecon',757:'Rough Elunium'}

def contract(m):
    b=m.pe.get_memory_mapped_image();marker=b.find(b'ShopUI.v1\0');assert marker>=0
    record=b.find(pack(m.base+marker));assert record>=0
    return {name:m.r(m.base+record+4+i*4) for i,name in enumerate(FIELDS)}

def buylist(rows=None):
    rows=rows if rows is not None else [(611,40,40),(1750,1,1),(501,50,38),(502,200,200),(503,550,550),(504,1200,912),(506,40,40),(645,800,800),(656,1500,1500),(601,60,60),(602,300,300),(505,5000,5000)]
    body=b''.join(struct.pack('<IIIBHI',id,base,price,0,0,0) for id,base,price in rows)
    return struct.pack('<HH',0xb77,4+len(body))+body

def selllist(rows=None):
    rows=rows if rows is not None else [(2,100,124),(3,2,2),(4,15,18),(5,250,310),(6,600,744),(7,2500,3100),(8,9,11),(9,1,1),(10,30,37),(11,275,341),(12,60,74),(13,3,3)]
    body=b''.join(struct.pack('<HII',*r) for r in rows)
    return struct.pack('<HH',0xc7,4+len(body))+body

class ShopMachine(Machine):
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
        self.stub(0xA23470,lambda:self.ret(8));self.stub(0xA764A0,lambda:self.ret(4))
        self.closed=[];self.mode=self.alloc(0x300);self.mode_vtable=self.alloc(64);self.close_handler=self.alloc(16)
        self.w(0x121333C,self.mode);self.w(self.mode,self.mode_vtable);self.w(self.mode_vtable+6*4,self.close_handler)
        self.stub(self.close_handler,lambda:(self.closed.append(tuple(self.args(5))),self.w(self.mode+0x24c,0),self.ret(20)))
        self.stub(0xC9E1DD,lambda:self.ret(0))
        for addr in (0xCA10CA,0xCA10DB):self.stub(addr,lambda addr=addr:(self.stock.append(addr),self.ret(0)))
        api=self.c['api'];self.stub(self.r(api+8),lambda:self.ret(0,0x20200000));self.stub(self.r(api+12),self.send)
        self.stub(self.r(api+20),self.icon)
        self.stub(self.r(api+24),lambda:(self.described.append(self.args(1)[0]),self.ret(4)))
        self.stub(self.r(api+28),self.name)
        # Observe the PNG helper without replacing its emitted alpha compositor.
        self.u.hook_add(UC_HOOK_CODE,lambda u,a,s,d:self.png_calls.append(tuple(self.args(4))),begin=self.r(api+32),end=self.r(api+32))
        keys=self.alloc(16);self.stub(keys,lambda:self.ret(4,0x8000 if self.args(1)[0] in self.key_codes else 0));self.w(self.r(api+36),keys)
        clock=self.alloc(16);self.stub(clock,lambda:self.ret(0,self.now));self.w(0xFC17B0,clock)
        self.inventory([(2,12214,100),(3,604,11),(4,602,8),(5,607,12),(6,504,30),(7,505,18),(8,507,50),(9,1750,350),(10,601,24),(11,503,10),(12,509,15),(13,909,47)])
        self.load_icons()
    def inventory(self,items):
        self.slots={};head=self.alloc(12);previous=head
        for row in items:
            index,id,amount=row[:3];refine=row[3] if len(row)>3 else 0;identified=row[4] if len(row)>4 else 1
            node=self.alloc(0x110);self.w(previous,node);self.w(node+4,previous);self.w(node+12,index);self.w(node+8+0x10,amount);self.w(node+8+0x60,refine);self.u.mem_write(node+8+0x5c,bytes([identified]));self.slots[index]=node+8
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
                except (KeyError,TypeError):pass
        finally:grf.close()
    def name(self):
        value=NAMES.get(self.args(2)[0],'Example item '+str(self.args(2)[0])).encode()+b'\0';ptr=self.alloc(len(value));self.u.mem_write(ptr,value);self.ret(8,ptr)
    def load_texture(self,name):
        if name in self.missing:return 0
        old=self.assets;self.assets=old/('genericsui' if name.startswith(('buy_','cancel_','sell_')) else 'barter')
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
        self.w(self.mode+0x24c,1)
        self.u.mem_write(0x15E8198,bytes(p));op=struct.unpack_from('<H',p)[0]
        self.invoke(self.r(0xCAA2E0+(op-0x73)*4),0)
    def click(self,x,y):
        obj=self.r(self.c['state']);self.invoke(self.c['down'],obj,(x,y));self.invoke(self.c['up'],obj,(x,y))
    def preview(self,path=None):
        self.texts=[];self.text_colors=[];self.png_calls=[];obj=self.r(self.c['state']);self.invoke(self.c['draw'],obj);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB')
        if path:im.save(path)
        return im
    def move(self,x,y):self.invoke(self.c['move'],self.r(self.c['state']),(x,y))
    def state(self,offset):return self.r(self.c['state']+offset)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe',type=Path);ap.add_argument('--assets',type=Path,default=TEXTURES);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=ShopMachine(args.exe,args.assets);c=m.c;s=c['state'];cart=s+76+4096*32
    m.w(0x15FBA90,1250000)
    def wheel(x,y,delta):m.move(x,y);m.invoke(c['wheel'],m.r(s),(delta,))
    def drag(x,y,to):m.invoke(c['down'],m.r(s),(x,y));m.invoke(c['drag'],m.r(s),(x,to));m.invoke(c['up'],m.r(s),(x,to))
    m.receive(buylist());assert m.state(4)==1 and m.state(8)==0xb77 and m.state(12)==12 and not m.stock
    m.preview(args.output/'buy-empty.png');assert any(t[0]=='38' for t in m.texts),'server discount ignored'
    assert (464,351,m.textures['buy_off.png'],0) in m.png_calls
    m.click(250,180);assert m.state(28)==1
    m.click(585,105);assert m.r(cart+4)==2
    m.key_codes.add(16);m.click(585,105);m.key_codes.clear();assert m.r(cart+4)==12
    m.click(528,105);m.click(528,105);assert m.r(cart+4)==10
    m.click(70,110);m.click(250,50);assert m.state(28)==3
    m.w(cart+12,20);m.w(cart+20,100);m.w(s+24,0)
    m.preview(args.output/'buy-selected.png');assert any(t[0]=='9,980 z' for t in m.texts)
    wheel(480,150,-120);assert m.state(24)>0
    wheel(150,150,-120);assert m.state(16)>0
    drag(402,75,365);assert m.state(16)>40
    drag(609,90,305);assert m.state(24)>0
    m.preview(args.output/'buy-scrolled.png')
    m.w(s+16,0);m.w(s+24,0);m.move(475,359);m.preview(args.output/'buy-hover.png');assert (464,351,m.textures['buy_over.png'],0) in m.png_calls
    m.invoke(c['down'],m.r(s),(475,359));m.preview(args.output/'buy-pressed.png');assert (464,351,m.textures['buy_press.png'],0) in m.png_calls
    m.invoke(c['up'],m.r(s),(410,390));assert not m.sent
    m.click(475,359);assert not m.state(4) and m.sent[-1]==struct.pack('<HHHIHIHI',0xc8,22,10,504,20,501,100,1750)
    assert m.closed[-1]==(0x28,0,0,0,0) and m.r(m.mode+0x24c)==0
    count=len(m.sent);m.click(475,359);assert len(m.sent)==count,'double submission'
    m.receive(buylist([(505,5000,4000)]));m.click(70,50);m.w(0x15FBA90,3999);m.click(475,359);assert len(m.sent)==count
    m.preview(args.output/'buy-insufficient-zeny.png');assert any(t[0]=='Not enough Zeny.' for t in m.texts)
    m.w(0x15FBA90,1250000);m.click(535,359);assert m.sent[-1]==struct.pack('<H',0x9d4) and not m.state(4)
    assert m.closed[-1]==(0x28,0,0,0,0) and m.r(m.mode+0x24c)==0
    m.receive(selllist());assert m.state(8)==0xc7 and m.state(12)==12
    m.preview(args.output/'sell-empty.png');assert any(t[0]=='124' for t in m.texts),'server Overcharge ignored'
    m.click(70,110);m.click(250,110);m.click(70,50);assert m.state(28)==3
    m.w(cart+12,5);m.w(cart+20,5);m.w(s+24,0)
    m.preview(args.output/'sell-selected.png');assert any(t[0]=='2,188 z' for t in m.texts)
    m.click(48,394);m.preview();assert not any(t[0]=='x100' for t in m.texts)
    m.click(48,394);m.preview();assert any(t[0]=='x100' for t in m.texts)
    # Instance inspection passes the exact live inventory CItem to stock.
    desc=m.alloc(256);vtable=m.alloc(160);handler=m.alloc(16);m.w(desc,vtable);m.w(vtable+37*4,handler)
    m.stub(0xA39340,lambda:m.ret(4,desc));m.stub(handler,lambda:(m.described.append(tuple(m.args(6))),m.ret(24)))
    m.move(60,42);m.invoke(c['rightdown'],m.r(s),(60,42));m.invoke(c['rightup'],m.r(s),(60,42));assert m.described[-1]==(0,24,m.slots[2],0,0,0)
    m.click(475,359);assert m.sent[-1]==struct.pack('<HHHHHHHH',0xc9,16,4,1,5,5,2,5) and not m.state(4)
    assert m.closed[-1]==(0x28,0,0,0,0) and m.r(m.mode+0x24c)==0
    # Equal ItemIds must remain distinct inventory slots, with independent limits.
    m.inventory([(2,505,2),(3,505,30)]);m.receive(selllist([(2,2000,2480),(3,2000,2480)]));m.click(70,50);m.click(250,50);assert m.state(28)==2
    m.preview();described=len(m.described);m.invoke(c['rightdown'],m.r(s),(60,42));m.invoke(c['rightup'],m.r(s),(238,42));assert len(m.described)==described,'right-click crossed between identical ItemId stacks'
    m.key_codes.add(17);m.click(585,105);m.key_codes.clear();assert m.r(cart+4)==2
    m.click(585,203);assert m.r(cart+12)==2
    m.preview(args.output/'sell-two-identical-stacks.png');m.click(475,359);assert m.sent[-1]==struct.pack('<HHHHHH',0xc9,12,2,2,3,2)
    m.receive(selllist([(2,2000,2480)]));m.click(70,50);before=len(m.sent)
    m.w(m.slots[2]+0x1c,4001);m.click(475,359);assert len(m.sent)==before,'changed card fingerprint sold'
    m.preview(args.output/'sell-stale-inventory.png');assert any(t[0]=='Inventory changed' for t in m.texts)
    m.click(594,65);assert not m.state(28),'remove button failed'
    m.receive(selllist([(2,2000,2480)]));m.click(70,50);m.w(m.slots[2]+0x10,0);m.click(475,359);assert len(m.sent)==before,'removed inventory sold'
    m.receive(buylist([]));m.preview(args.output/'buy-no-items.png');assert not m.state(12)
    m.receive(buylist([(100000+i,1,1) for i in range(1001)]));assert m.state(12)==1001
    drag(402,70,372);m.preview(args.output/'large-catalog-bottom.png');assert m.state(16)>30000
    m.receive(buylist([(611,0,0)]));m.click(70,50);m.w(cart+4,30001);before=len(m.sent);m.click(475,359);assert len(m.sent)==before,'quantity overflow'
    m.w(cart+4,30000);m.click(475,359);assert m.sent[-1]==struct.pack('<HHHI',0xc8,10,30000,611)
    m.receive(buylist([(611,0x7fffffff,0x7fffffff)]));m.click(70,50);m.w(cart+4,2);m.w(0x15FBA90,0x7fffffff);before=len(m.sent);m.click(475,359);assert len(m.sent)==before,'price overflow'
    for packet in [struct.pack('<HH',0xb77,3),struct.pack('<HHB',0xb77,5,0),struct.pack('<HH',0xc7,40961),buylist([(505,1,1),(505,2,2)]),selllist([(2,1,1),(2,2,2)])]:
        old=len(m.stock);m.receive(packet);assert len(m.stock)==old+1
    m.missing.add('bg_sell.png');m.receive(selllist());assert m.stock[-1]==0xca10db and not m.state(4);m.missing.clear()
    m.missing.add('itembox_00.png');m.receive(buylist());assert m.stock[-1]==0xca10ca and not m.state(4);m.missing.clear()
    m.receive(buylist());before=len(m.sent);m.key_codes.add(27);m.invoke(c['cursor'],m.r(s),(40,20));m.key_codes.clear();assert len(m.sent)==before+1 and m.sent[-1]==struct.pack('<H',0x9d4)
    # Run the actual identified/unidentified lookup exports (normally stubbed at
    # the read-only item database boundary for drawing) against bounded strings.
    m.u.hook_del(m._machine_stubs.pop(c['name']));node=m.alloc(256);manager=m.alloc(32);m.w(0x159c088,manager)
    for off,value in [(4,b'Unknown'),(0x1c,b'unknown_stem'),(0x40,b'Blue Potion'),(0x58,b'blue_stem')]:
        m.u.mem_write(node+off,value+b'\0');m.w(node+off+16,len(value));m.w(node+off+20,15)
    m.stub(0xA7E780,lambda:m.ret(4,node))
    for identified,expected in [(0,'Unknown'),(1,'Blue Potion')]:
        m.invoke(c['name'],0,(505,identified));assert m.cstr(m.u.reg_read(UC_X86_REG_EAX))==expected
        m.w(c['identified'],identified);m.invoke(c['resource'],0,(505,));assert m.cstr(m.u.reg_read(UC_X86_REG_EAX))==('blue_stem' if identified else 'unknown_stem')
    print('PASS: emitted x86 Buy/Sell routing, server prices, exact inventory slots, duplicate stacks, instance descriptions, quantities, totals, clipping/scrolling, asset states/fallback, overflow/stale-inventory guards, native packets/close and callee-save/stack checks.')

if __name__=='__main__':main()
